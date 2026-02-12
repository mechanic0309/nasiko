"""
Service Manager
Handles startup and management of core services (LangTrace, OTEL, Nasiko).
"""

import time
import logging
import requests
from docker_utils import run_cmd, wait_for_health
from config import (
    LANGTRACE_COMPOSE_FILE, OTEL_COMPOSE_FILE, NASIKO_APP_COMPOSE_FILE,
    NASIKO_WEB_COMPOSE_FILE, LANGTRACE_STARTUP_DELAY, NASIKO_APP_STARTUP_CHECK_INTERVAL,
    NASIKO_WEB_STARTUP_DELAY, NASIKO_API_URL,
    KONG_COMPOSE_FILE, KONG_STARTUP_DELAY, OLLAMA_COMPOSE_FILE, OLLAMA_STARTUP_DELAY
)

logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages core service lifecycle"""
    
    def __init__(self):
        self.services_started = []
    
    def start_langtrace(self):
        """Start LangTrace service"""
        try:
            logger.info("Starting LangTrace service...")
            run_cmd(["docker", "compose", "-f", LANGTRACE_COMPOSE_FILE, "up", "-d"])
            
            if wait_for_health("langtrace"):
                self.services_started.append("langtrace")
                logger.info("LangTrace started successfully")
                return True
            else:
                logger.error("LangTrace failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start LangTrace: {e}")
            return False
    
    def start_otel_collector(self):
        """Start OTEL Collector service"""
        try:
            logger.info("Starting OTEL Collector service...")
            run_cmd(["docker", "compose", "-f", OTEL_COMPOSE_FILE, "up", "-d"])
            
            if wait_for_health("otel-collector"):
                self.services_started.append("otel-collector")
                logger.info("OTEL Collector started successfully")
                return True
            else:
                logger.error("OTEL Collector failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start OTEL Collector: {e}")
            return False
    
    def start_nasiko_app(self):
        """Start Nasiko backend application and wait for API to be healthy"""
        try:
            logger.info("Starting Nasiko app...")
            run_cmd(["docker", "compose", "-f", NASIKO_APP_COMPOSE_FILE, "up", "-d"])
            
            if wait_for_health("nasiko-backend"):
                self.services_started.append("nasiko-backend")
                logger.info("Nasiko app started successfully")
                
                # Wait for API healthcheck to pass
                if self._wait_for_api_healthcheck(interval=NASIKO_APP_STARTUP_CHECK_INTERVAL):
                    logger.info("Nasiko API is healthy and ready")
                    return True
                else:
                    logger.error("Nasiko API healthcheck failed")
                    return False
            else:
                logger.error("Nasiko app failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Nasiko app: {e}")
            return False

    def _wait_for_api_healthcheck(self, max_attempts=10, interval=30):
        """
        Wait for Nasiko API healthcheck to pass
        
        Args:
            max_attempts: Maximum number of healthcheck attempts (default: 10)
            interval: Interval between checks in seconds (default: 30)
        
        Returns:
            bool: True if healthcheck passes, False otherwise
        """
        api_url = f"{NASIKO_API_URL}/api/v1/healthcheck"
        
        logger.info(f"Waiting for API healthcheck at {api_url}")
        logger.info(f"Will check every {interval} seconds for up to {max_attempts} attempts")
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Healthcheck attempt {attempt}/{max_attempts}")
                
                response = requests.get(api_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        logger.info(f"✅ API healthcheck passed on attempt {attempt}")
                        return True
                    else:
                        logger.warning(f"API responded but status is not 'ok': {data}")
                else:
                    logger.warning(f"API healthcheck failed with status {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection refused - API not ready yet (attempt {attempt}/{max_attempts})")
            except requests.exceptions.Timeout:
                logger.warning(f"API healthcheck timeout (attempt {attempt}/{max_attempts})")
            except Exception as e:
                logger.warning(f"API healthcheck error: {e} (attempt {attempt}/{max_attempts})")
            
            # Don't sleep after the last attempt
            if attempt < max_attempts:
                logger.info(f"Waiting {interval} seconds before next healthcheck...")
                time.sleep(interval)
        
        logger.error(f"❌ API healthcheck failed after {max_attempts} attempts")
        return False
    


    def start_nasiko_web(self):
        """Start Nasiko web frontend"""
        try:
            logger.info("Starting Nasiko web...")
            run_cmd(["docker", "compose", "-f", NASIKO_WEB_COMPOSE_FILE, "up", "-d"])
            
            if wait_for_health("nasiko-web"):
                self.services_started.append("nasiko-web")
                logger.info("Nasiko web started successfully")
                return True
            else:
                logger.error("Nasiko web failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Nasiko web: {e}")
            return False

    def start_kong_gateway(self):
        """Start Kong API Gateway with proper dependency handling"""
        try:
            logger.info("Starting Kong API Gateway...")

            # Start the entire Kong stack (database, migrations, kong)
            run_cmd(["docker", "compose", "-f", KONG_COMPOSE_FILE, "up", "-d"])

            # Wait for database to be ready first
            logger.info("Waiting for Kong database to be ready...")
            if not wait_for_health("kong-database"):
                logger.error("Kong database failed to start")
                return False

            # Wait for migrations to complete
            logger.info("Waiting for Kong migrations to complete...")

            # First, wait a bit for the container to start and check if it exists
            time.sleep(5)

            # Check if migrations completed (database already bootstrapped)
            try:
                # Check migration logs for "Database already bootstrapped" or successful completion
                result = run_cmd(["docker", "logs", "kong-migrations"])
                logs = result.stdout

                if "Database already bootstrapped" in logs or "Database is up-to-date" in logs:
                    logger.info("Kong database already bootstrapped - migrations completed")
                elif "migrations processed" in logs:
                    logger.info("Kong migrations completed successfully")
                else:
                    logger.warning("Kong migrations status unclear from logs")
                    logger.info(f"Migration logs: {logs}")
            except Exception as e:
                logger.warning(f"Could not check migration logs: {e}")
                # Continue anyway - Kong will handle migration state


            # Now wait for Kong itself to be healthy
            logger.info("Waiting for Kong gateway to be ready...")
            if wait_for_health("kong-gateway"):
                self.services_started.append("kong-gateway")
                logger.info("Kong API Gateway started successfully")
                return True
            else:
                logger.error("Kong API Gateway failed to start")
                return False

        except Exception as e:
            logger.error(f"Failed to start Kong API Gateway: {e}")
            return False

    def start_ollama(self):
        """Start Ollama service for LLM routing"""
        try:
            logger.info("Starting Ollama service...")
            run_cmd(["docker", "compose", "-f", OLLAMA_COMPOSE_FILE, "up", "-d"])
            
            if wait_for_health("ollama"):
                self.services_started.append("ollama")
                logger.info("Ollama started successfully")
                return True
            else:
                logger.error("Ollama failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            return False
    
    def start_all_services(self):
        """Start all services in proper order with delays"""
        success = True
        
        # Start LangTrace first and wait
        if self.start_langtrace():
            logger.info(f"Waiting {LANGTRACE_STARTUP_DELAY} seconds for LangTrace to be fully ready...")
            time.sleep(LANGTRACE_STARTUP_DELAY)
        else:
            success = False
        
        # Start Ollama for LLM routing (optional - will fallback to OpenAI if fails)
        # if self.start_ollama():
        #     logger.info(f"Waiting {OLLAMA_STARTUP_DELAY} seconds for Ollama to be fully ready...")
        #     time.sleep(OLLAMA_STARTUP_DELAY)
        # else:
        #     logger.warning("Ollama failed to start - router will fallback to OpenAI API")

        # Start Nasiko app
        if self.start_nasiko_app():
            logger.info(f"Nasiko backend is fully ready!")
        else:
            success = False

        # Start Kong API Gateway
        if self.start_kong_gateway():
            logger.info(f"Waiting {KONG_STARTUP_DELAY} seconds for Kong API Gateway to be fully ready...")
            time.sleep(KONG_STARTUP_DELAY)
        else:
            success = False

        # Start Nasiko web
        if self.start_nasiko_web():
            logger.info(f"Waiting {NASIKO_WEB_STARTUP_DELAY} seconds for Nasiko web to be fully ready...")
            time.sleep(NASIKO_WEB_STARTUP_DELAY)
        else:
            success = False

        
        if success:
            logger.info("All core services started successfully")
        else:
            logger.error("Some services failed to start")
            
        return success
    
    def get_started_services(self):
        """Get list of successfully started services"""
        return self.services_started.copy()