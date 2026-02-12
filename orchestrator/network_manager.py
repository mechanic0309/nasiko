"""
Network Manager
Handles Docker network creation and management for agents.
"""

import yaml
import logging
from pathlib import Path
from docker_utils import create_network
from config import AGENTS_DIRECTORY

logger = logging.getLogger(__name__)

def get_external_networks_from_agents():
    """Scan all agent docker-compose files and collect external networks"""
    external_networks = set()
    agents_dir = Path(AGENTS_DIRECTORY)
    
    if not agents_dir.exists():
        logger.warning(f"Agents directory {AGENTS_DIRECTORY} not found")
        return external_networks
    
    for agent_folder in agents_dir.iterdir():
        if not agent_folder.is_dir():
            continue
            
        compose_path = agent_folder / "docker-compose.yml"
        if not compose_path.exists():
            continue
            
        try:
            with open(compose_path, "r") as f:
                compose_data = yaml.safe_load(f)
            
            # Check networks section for external networks
            networks = compose_data.get("networks", {})
            for network_name, network_config in networks.items():
                if isinstance(network_config, dict) and network_config.get("external", False):
                    external_networks.add(network_name)
                    
        except Exception as e:
            logger.error(f"Error reading docker-compose.yml for {agent_folder.name}: {e}")
            continue
    
    return external_networks

def create_external_networks():
    """Create all external networks required by agents"""
    external_networks = get_external_networks_from_agents()
    
    success_count = 0
    for network_name in external_networks:
        if create_network(network_name):
            success_count += 1
    
    logger.info(f"Created {success_count}/{len(external_networks)} external networks")
    return success_count == len(external_networks)

def ensure_core_networks():
    """Ensure core orchestrator networks exist"""
    core_networks = ["agents-net", "app-network"]
    
    success_count = 0
    for network_name in core_networks:
        if create_network(network_name):
            success_count += 1
    
    logger.info(f"Ensured {success_count}/{len(core_networks)} core networks")
    return success_count == len(core_networks)