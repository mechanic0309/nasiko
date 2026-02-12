"""
Main Orchestrator
Simplified main orchestration flow using modular components.
"""

import logging
import sys
import time
import requests
from pathlib import Path
from service_manager import ServiceManager
from agent_builder import AgentBuilder
from network_manager import ensure_core_networks, create_external_networks
from superuser_manager import SuperuserManager

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class MainOrchestrator:
    """Main orchestrator that coordinates all components"""
    
    def __init__(self):
        self.service_manager = ServiceManager()
        self.agent_builder = AgentBuilder()
        self.superuser_manager = SuperuserManager()
        self.superuser_id = None
    
    def run_full_orchestration(self):
        """Run the complete orchestration process"""
        logger.info("Starting Nasiko orchestration...")
        
        try:
            # Step 1: Setup networks
            if not self._setup_networks():
                logger.error("Network setup failed")
                return False
            
            # Step 2: Start core services
            if not self._start_services():
                logger.error("Service startup failed")
                return False
            
            # Step 3: Setup superuser
            if not self._setup_superuser():
                logger.error("Superuser setup failed")
                return False
            
            # Step 4: Build and deploy agents
            if not self._build_agents():
                logger.error("Agent building failed")
                return False
            
            logger.info("All agents and logging stack are running successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Orchestration failed with error: {e}")
            return False
    
    def _setup_networks(self):
        """Setup required Docker networks"""
        logger.info("Setting up Docker networks...")
        
        # Ensure core networks exist
        if not ensure_core_networks():
            logger.error("Failed to create core networks")
            return False
        
        # Create external networks from agent configs
        if not create_external_networks():
            logger.error("Failed to create external networks")
            return False
        
        logger.info("Network setup completed successfully")
        return True
    
    def _start_services(self):
        """Start all core services"""
        logger.info("Starting core services...")
        
        if not self.service_manager.start_all_services():
            logger.error("Failed to start all services")
            started_services = self.service_manager.get_started_services()
            logger.info(f"Successfully started services: {started_services}")
            return False
        
        logger.info("All core services started successfully")
        return True
    
    def _setup_superuser(self):
        """Setup system superuser"""
        logger.info("Setting up system superuser...")
        
        self.superuser_id = self.superuser_manager.ensure_superuser()
        
        if self.superuser_id:
            logger.info(f"Superuser setup completed successfully - ID: {self.superuser_id}")
            return True
        else:
            logger.error("Failed to setup superuser")
            return False

    def _build_agents(self):
        """Build and deploy all agents"""
        logger.info("Building and deploying agents...")
        
        if not self.agent_builder.instrument_and_build_agents(owner_id=self.superuser_id):
            logger.error("Failed to build all agents")
            return False
        
        logger.info("All agents built and deployed successfully")
        return True
    
    def build_single_agent(self, agent_name):
        """Build a single agent (useful for testing or incremental builds)"""
        logger.info(f"Building single agent: {agent_name}")
        
        # Ensure networks are set up first
        if not self._setup_networks():
            logger.error("Network setup failed")
            return False
        
        # Build the specific agent
        success = self.agent_builder.build_single_agent(agent_name)
        
        if success:
            logger.info(f"Successfully built agent: {agent_name}")
        else:
            logger.error(f"Failed to build agent: {agent_name}")
        
        return success

def main():
    """Main entry point"""
    orchestrator = MainOrchestrator()
    
    # Check for single agent build mode
    if len(sys.argv) == 3 and sys.argv[1] == "--agent":
        agent_name = sys.argv[2]
        success = orchestrator.build_single_agent(agent_name)
    else:
        # Full orchestration
        success = orchestrator.run_full_orchestration()
    
    exit_code = 0 if success else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()