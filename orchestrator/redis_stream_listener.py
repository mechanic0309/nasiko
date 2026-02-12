"""
Redis Stream Listener for Orchestrator
Listens for orchestration commands from the backend app via Redis streams
"""

import redis
import json
import logging
import asyncio
import signal
import sys
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime, UTC
from pathlib import Path

from config import Config
from agent_builder import AgentBuilder


class RedisStreamListener:
    """Redis stream listener for orchestration commands"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.redis_client = None
        self.agent_builder = AgentBuilder(logger)
        self.running = False
        self.stream_name = "orchestration:commands"
        self.consumer_group = "orchestrator"
        self.consumer_name = "orchestrator-1"
        
    def connect_redis(self):
        """Connect to Redis server"""
        try:
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10
            )
            # Test connection
            self.redis_client.ping()
            self.logger.info(f"Connected to Redis at {Config.REDIS_HOST}:{Config.REDIS_PORT}")
            
            # Create consumer group if it doesn't exist
            try:
                self.redis_client.xgroup_create(
                    self.stream_name, 
                    self.consumer_group, 
                    id='0',
                    mkstream=True
                )
                self.logger.info(f"Created consumer group '{self.consumer_group}' for stream '{self.stream_name}'")
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    self.logger.info(f"Consumer group '{self.consumer_group}' already exists")
                else:
                    raise
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if Redis connection is active"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    async def start_listening(self):
        """Start listening for orchestration commands"""
        if not self.connect_redis():
            self.logger.error("Failed to connect to Redis, cannot start listener")
            return
        
        self.running = True
        self.logger.info("Starting Redis stream listener for orchestration commands")
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                try:
                    # Read messages from stream
                    messages = self.redis_client.xreadgroup(
                        self.consumer_group,
                        self.consumer_name,
                        {self.stream_name: '>'},
                        count=1,
                        block=1000  # Block for 1 second
                    )
                    
                    for stream, msgs in messages:
                        for msg_id, fields in msgs:
                            await self.process_message(msg_id, fields)
                            
                except redis.exceptions.ConnectionError as e:
                    self.logger.error(f"Redis connection error: {e}")
                    if not self.connect_redis():
                        self.logger.error("Failed to reconnect to Redis")
                        break
                    
                except Exception as e:
                    self.logger.error(f"Error reading from Redis stream: {e}")
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            self.running = False
            if self.redis_client:
                self.redis_client.close()
            self.logger.info("Redis stream listener stopped")
    
    async def process_message(self, msg_id: str, fields: Dict[str, str]):
        """Process a single orchestration command message"""
        try:
            self.logger.info(f"Processing message {msg_id}: {fields}")
            
            # Extract command details
            command = fields.get('command')
            agent_name = fields.get('agent_name')
            agent_path = fields.get('agent_path')
            base_url = fields.get('base_url', 'http://localhost:8000')
            
            # Extract additional data from orchestration message
            owner_id = fields.get('owner_id')
            upload_id = fields.get('upload_id')
            upload_type = fields.get('upload_type')
            
            if not all([command, agent_name, agent_path]):
                self.logger.error(f"Invalid message format: missing required fields")
                await self.acknowledge_message(msg_id)
                return
            
            # Log extracted ownership information
            if owner_id:
                self.logger.info(f"Processing agent '{agent_name}' for owner: {owner_id} (upload_id: {upload_id}, type: {upload_type})")
            
            # Set initial status in Redis and update database
            await self.set_agent_status(agent_name, 'processing', {
                'message': 'Orchestration command received',
                'stage': 'initializing',
                'owner_id': owner_id,
                'upload_id': upload_id,
                'upload_type': upload_type
            })
            await self.update_database_status(agent_name, base_url, 'orchestration_processing', 95, 
                                            'Orchestration processing started')
            
            # Process based on command type
            if command == 'deploy_agent':
                await self.handle_deploy_agent(agent_name, agent_path, base_url, owner_id, upload_id, upload_type)
            else:
                self.logger.warning(f"Unknown command: {command}")
                await self.set_agent_status(agent_name, 'error', {
                    'message': f'Unknown command: {command}',
                    'owner_id': owner_id,
                    'upload_id': upload_id
                })
            
            # Acknowledge message processing
            await self.acknowledge_message(msg_id)
            
        except Exception as e:
            self.logger.error(f"Error processing message {msg_id}: {e}")
            if 'agent_name' in locals():
                await self.set_agent_status(agent_name, 'error', {
                    'message': f'Failed to process orchestration command: {str(e)}',
                    'owner_id': locals().get('owner_id'),
                    'upload_id': locals().get('upload_id')
                })
            await self.acknowledge_message(msg_id)
    
    async def handle_deploy_agent(self, agent_name: str, agent_path: str, base_url: str, 
                                 owner_id: Optional[str] = None, upload_id: Optional[str] = None, 
                                 upload_type: Optional[str] = None):
        """Handle agent deployment command"""
        try:
            if owner_id:
                self.logger.info(f"Deploying agent '{agent_name}' from path '{agent_path}' for owner: {owner_id}")
            else:
                self.logger.info(f"Deploying agent '{agent_name}' from path '{agent_path}'")
            
            # Convert container path to host path
            # Container path: /app/agents/{agent_name}
            # Host path: agents/{agent_name}
            if agent_path.startswith('/app/agents/'):
                relative_path = agent_path.replace('/app/agents/', '')
                host_agent_path = str(Path('agents') / relative_path) # TODO - replace with config value
            else:
                host_agent_path = agent_path

            # Verify agent directory exists
            agent_dir = Path(host_agent_path)
            if not agent_dir.exists():
                raise ValueError(f"Agent directory does not exist: {host_agent_path}")
            
            # Set status to building (include ownership info)
            await self.set_agent_status(agent_name, 'building', {
                'message': 'Building Docker image',
                'stage': 'docker_build',
                'owner_id': owner_id,
                'upload_id': upload_id,
                'upload_type': upload_type
            })
            
            # Build and deploy agent using AgentBuilder
            result = await self.agent_builder.build_and_deploy_agent(
                agent_name=agent_name,
                agent_path=host_agent_path,
                base_url=base_url,
                owner_id=owner_id
            )
            
            if result.get('success', False):
                # Set status to running in Redis
                await self.set_agent_status(agent_name, 'running', {
                    'message': 'Agent deployed successfully',
                    'stage': 'deployed',
                    'url': result.get('url'),
                    'container_id': result.get('container_id'),
                    'service_name': result.get('service_name')
                })
                
                # Update database status to completed
                await self.update_database_status(agent_name, base_url, 'completed', 100, 
                                                'Agent deployed and running successfully', {
                                                    'url': result.get('url'),
                                                    'registry_updated': True
                                                })
                self.logger.info(f"Successfully deployed agent '{agent_name}'")
            else:
                # Set status to failed in Redis
                await self.set_agent_status(agent_name, 'failed', {
                    'message': result.get('error', 'Unknown deployment error'),
                    'stage': 'deployment_failed'
                })
                
                # Update database status to failed
                await self.update_database_status(agent_name, base_url, 'failed', 0, 
                                                f"Deployment failed: {result.get('error', 'Unknown error')}", {
                                                    'error_details': [result.get('error', 'Unknown deployment error')]
                                                })
                self.logger.error(f"Failed to deploy agent '{agent_name}': {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Error deploying agent '{agent_name}': {e}")
            await self.set_agent_status(agent_name, 'failed', {
                'message': f'Deployment failed: {str(e)}',
                'stage': 'deployment_error'
            })
    
    async def set_agent_status(self, agent_name: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Set agent deployment status in Redis"""
        if not self.is_connected():
            return
        
        try:
            status_key = f"agent:status:{agent_name}"
            status_data = {
                "agent_name": agent_name,
                "status": status,
                "last_updated": datetime.now(UTC).isoformat(),
                "updated_by": "orchestrator"
            }
            
            if details:
                # Filter out None values that Redis can't store
                filtered_details = {k: v for k, v in details.items() if v is not None}
                status_data.update(filtered_details)
            
            # Store as hash for easy field access
            self.redis_client.hset(status_key, mapping=status_data)
            
            # Set expiration (24 hours)
            self.redis_client.expire(status_key, 86400)
            
            self.logger.debug(f"Set agent status for {agent_name}: {status}")
            
        except Exception as e:
            self.logger.error(f"Failed to set agent status for {agent_name}: {e}")
    
    async def update_database_status(self, agent_name: str, base_url: str, status: str, 
                                   progress: int, message: str, additional_data: Optional[Dict[str, Any]] = None):
        """Update upload status in database via API call to the backend"""
        try:
            update_data = {
                "status": status,
                "progress_percentage": progress,
                "status_message": message,
                "orchestration_duration": None  # Could be calculated if needed
            }
            
            if additional_data:
                update_data.update(additional_data)
            
            # Make API call to update status
            url = f"{base_url}/api/v1/upload-status/agent/{agent_name}/latest"
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=update_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        self.logger.debug(f"Updated database status for {agent_name}: {status}")
                    else:
                        self.logger.warning(f"Failed to update database status for {agent_name}: {response.status}")
                        
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout updating database status for {agent_name}")
        except Exception as e:
            self.logger.error(f"Error updating database status for {agent_name}: {e}")

    async def acknowledge_message(self, msg_id: str):
        """Acknowledge message processing"""
        try:
            self.redis_client.xack(self.stream_name, self.consumer_group, msg_id)
            self.logger.debug(f"Acknowledged message {msg_id}")
        except Exception as e:
            self.logger.error(f"Failed to acknowledge message {msg_id}: {e}")
    
    def stop(self):
        """Stop the listener"""
        self.running = False


async def main():
    """Main function to run the Redis stream listener"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    listener = RedisStreamListener(logger)
    await listener.start_listening()


if __name__ == "__main__":
    asyncio.run(main())