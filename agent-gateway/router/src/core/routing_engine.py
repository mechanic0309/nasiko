"""
Routing engine service for AI-powered agent selection.
"""

import json
import logging
import os
from typing import Any, Dict, List, Tuple

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS

from router.src.config import settings
from router.src.entities import RouterOutput

logger = logging.getLogger(__name__)


class RoutingEngineError(Exception):
    """Custom exception for routing engine errors."""
    pass


class RoutingEngine:
    """Service for AI-powered agent routing and selection."""
    
    def __init__(self):
        self.llm = self._create_llm()
    
    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance for routing decisions."""
        return ChatOpenAI(
            model="google/gemini-2.5-flash",
            temperature=0,
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        ).with_structured_output(RouterOutput)
    
    def route_query(
        self, 
        message: str, 
        agent_cards: List[Dict[str, Any]], 
        vectorstore: FAISS
    ) -> Tuple[List[str], RouterOutput]:
        """
        Route a user query to the most appropriate agent.
        
        Args:
            message: User's query message
            agent_cards: List of available agent card dictionaries
            vectorstore: FAISS vector store for similarity search
            
        Returns:
            Tuple of (shortlisted_agents, router_output)
            
        Raises:
            RoutingEngineError: If routing fails
        """
        try:
            # First, perform semantic search to shortlist agents
            shortlisted_agents, shortlisted_agent_cards = self._semantic_search(
                message, agent_cards, vectorstore
            )
            
            # Then use LLM to make final selection
            router_output = self._llm_route(message, shortlisted_agent_cards)
            
            return shortlisted_agents, router_output
            
        except Exception as e:
            error_msg = f"Routing failed: {str(e)}"
            logger.error(error_msg)
            raise RoutingEngineError(error_msg) from e
    
    def _semantic_search(
        self, 
        message: str, 
        agent_cards: List[Dict[str, Any]], 
        vectorstore: FAISS
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Perform semantic search to shortlist relevant agents.
        
        Args:
            message: User's query message
            agent_cards: List of available agent cards
            vectorstore: FAISS vector store
            
        Returns:
            Tuple of (agent_names, agent_cards) for shortlisted agents
        """
        try:
            # Search for top 2 most similar agents
            search_results = vectorstore.similarity_search(message, k=2)
            
            shortlisted_agents = [result.metadata["name"] for result in search_results]
            logger.info(f"Shortlisted agents: {shortlisted_agents}")
            
            # Filter agent cards to only include shortlisted ones
            shortlisted_agent_cards = []
            for agent_card in agent_cards:
                if agent_card.get("name") in shortlisted_agents:
                    shortlisted_agent_cards.append(agent_card)
            
            return shortlisted_agents, shortlisted_agent_cards
            
        except Exception as e:
            error_msg = f"Semantic search failed: {str(e)}"
            logger.error(error_msg)
            raise RoutingEngineError(error_msg) from e
    
    def _llm_route(self, message: str, agent_cards: List[Dict[str, Any]]) -> RouterOutput:
        """
        Use LLM to make final agent selection from shortlisted agents.
        
        Args:
            message: User's query message
            agent_cards: Shortlisted agent cards
            
        Returns:
            RouterOutput with selected agent information
            
        Raises:
            RoutingEngineError: If LLM routing fails
        """
        try:
            system_prompt = """You are an agent router. Your job is to route a user's request to the appropriate agent.

            INSTRUCTIONS:
            1. You will be given a user's request.
            2. You will also be given a list of agent ids along with their capabilities.
            3. You must use this list to determine which agent is appropriate to serve the user's request.
            4. You must return agent_id.
            5. agent_id is the id of the agent which should be used to serve the request.
            """
            
            user_prompt = """List of agents:
            {agent_cards_str}.
            User's request: {message}."""
            
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessage(content=system_prompt),
                ("human", user_prompt)
            ])
            
            # Prepare agent cards as JSON string
            agent_cards_str = json.dumps(agent_cards, indent=2) + "\n"
            
            # Create and invoke prompt
            prompt = prompt_template.invoke({
                "message": message,
                "agent_cards_str": agent_cards_str
            })
            
            response = self.llm.invoke(prompt)
            
            if not isinstance(response, RouterOutput):
                raise RoutingEngineError("LLM response is not of type RouterOutput")
            
            logger.info(f"LLM selected agent: {response.agent_name}")
            return response
            
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            logger.error(f"Prompt sent: {prompt}")
            raise RoutingEngineError(f"LLM routing failed: {str(e)}") from e


# Convenience function for backward compatibility
def router(
    message: str, 
    agent_cards: List[Dict[str, Any]], 
    vectorstore: FAISS
) -> Tuple[List[str], RouterOutput]:
    """
    Route a user query to the most appropriate agent.
    
    This is a convenience function that maintains backward compatibility
    with the existing router interface.
    
    Args:
        message: User's query message
        agent_cards: List of available agent card dictionaries
        vectorstore: FAISS vector store for similarity search
        
    Returns:
        Tuple of (shortlisted_agents, router_output)
    """
    routing_engine = RoutingEngine()
    return routing_engine.route_query(message, agent_cards, vectorstore)