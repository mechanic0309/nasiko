"""
Orchestrator Configuration
Contains all constants and configuration settings.
"""

import os

class Config:
    # Docker Configuration
    DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "nasiko-network")
    OTEL_ENDPOINT = "http://otel-collector:4318"
    NASIKO_API_URL = os.getenv("NASIKO_API_URL", "http://localhost:8000")
    KONG_GATEWAY_URL = os.getenv("KONG_GATEWAY_URL", "http://localhost:9100")
    LANGTRACE_ENABLED = os.getenv("LANGTRACE_ENABLED", "false").lower() in ("1", "true", "yes")
    LANGTRACE_API_KEY = os.getenv("LANGTRACE_API_KEY", "")
    LANGTRACE_API_HOST = os.getenv("LANGTRACE_API_HOST", "")

    # Agent Registry Configuration (for pre-built images)
    AGENT_REGISTRY_URL = os.getenv("AGENT_REGISTRY_URL", "docker.io")
    AGENT_IMAGE_TAG = os.getenv("AGENT_IMAGE_TAG", "latest")

    # Redis Configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Legacy constants for backward compatibility
DOCKER_NETWORK = Config.DOCKER_NETWORK
OTEL_ENDPOINT = Config.OTEL_ENDPOINT
NASIKO_API_URL = Config.NASIKO_API_URL
KONG_GATEWAY_URL = Config.KONG_GATEWAY_URL
LANGTRACE_ENABLED = Config.LANGTRACE_ENABLED
LANGTRACE_API_KEY = Config.LANGTRACE_API_KEY
LANGTRACE_API_HOST = Config.LANGTRACE_API_HOST
AGENT_REGISTRY_URL = Config.AGENT_REGISTRY_URL
AGENT_IMAGE_TAG = Config.AGENT_IMAGE_TAG

# Service Startup Configuration
LANGTRACE_STARTUP_DELAY = 20  # seconds
NASIKO_APP_STARTUP_CHECK_INTERVAL = 30  # seconds
NASIKO_WEB_STARTUP_DELAY = 5   # seconds
KONG_STARTUP_DELAY = 10  # seconds
OLLAMA_STARTUP_DELAY = 15  # seconds

# Agent Configuration
AGENTS_DIRECTORY = "agents"
CONTAINER_HEALTH_TIMEOUT = 60  # seconds

# Docker Compose Files
LANGTRACE_COMPOSE_FILE = "observability/langtrace/docker-compose.langtrace.yaml"
OTEL_COMPOSE_FILE = "observability/otel-collector/docker-compose.otel.yaml"
NASIKO_APP_COMPOSE_FILE = "app/docker-compose.app.yaml"
NASIKO_WEB_COMPOSE_FILE = "web/docker-compose.yml"
KONG_COMPOSE_FILE = "kong/docker-compose.yml"
OLLAMA_COMPOSE_FILE = "models/ollama/docker-compose.yml"
