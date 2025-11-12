"""
Fabric Data Agent Service

Handles all interactions with the Fabric Data Agent, including:
- Client initialization
- Query execution
- Response formatting
- Error handling
"""

import os
from typing import Dict, Any, Optional

import structlog

from .client import FabricDataAgentClient

logger = structlog.get_logger(__name__)


class FabricDataService:
    """
    Service for interacting with Fabric Data Agent.

    Manages authentication and provides interface to published agents.
    """

    def __init__(self, tenant_id: str, data_agent_url: str):
        """
        Initialize the Fabric Data Service.
        
        Args:
            tenant_id: Azure tenant ID
            data_agent_url: Published Fabric Data Agent URL
        """
        self.tenant_id = tenant_id
        self.data_agent_url = data_agent_url
        self.client: Optional[FabricDataAgentClient] = None
        
        logger.info(
            "Initialized Fabric Data Service",
            tenant_id=tenant_id,
            data_agent_url=data_agent_url
        )
    
    def _ensure_client(self):
        """Ensure client is initialized."""
        if self.client is None:
            try:
                logger.info("Initializing Fabric Data Agent client")
                self.client = FabricDataAgentClient(
                    tenant_id=self.tenant_id,
                    data_agent_url=self.data_agent_url
                )
                logger.info("Fabric Data Agent client initialized")
            except Exception as e:
                logger.error("Failed to initialize client", error=str(e))
                raise
    
    def run(self, tool_call: Dict[str, Any] = None) -> str:
        """
        Run the Fabric Data Agent query.
        
        Args:
            tool_call: Tool call dictionary from agent framework with LLM-provided parameters
                      Contains: query, reasoning, any other parameters LLM provided
            
        Returns:
            String response from the Fabric Data Agent
        """
        try:
            # Extract parameters from tool_call (filled by LLM)
            question = tool_call.get('query') or tool_call.get('question') if tool_call else None
            
            logger.info(
                "[FabricDataService.run] Starting query",
                question=question,
                tool_call_keys=list(tool_call.keys()) if tool_call else None
            )
            
            if not question:
                logger.error("[FabricDataService.run] No question provided in tool_call")
                return "Error: No question provided in tool_call"
            
            self._ensure_client()
            
            logger.info(
                "[FabricDataService.run] Querying Fabric Data Agent",
                question=question
            )
            
            # Get the response
            response = self.client.ask(question)
            
            logger.info(
                "[FabricDataService.run] Query completed successfully",
                question=question,
                response_length=len(response) if response else 0
            )
            
            # Return as string (Agent Framework expects string return)
            return str(response)
            
        except Exception as e:
            logger.error(
                "[FabricDataService.run] Query failed",
                error=str(e),
                question=question if 'question' in locals() else "unknown",
                exc_info=True
            )
            return f"Error: {str(e)}"
    
    def close(self):
        """Clean up resources."""
        if self.client:
            self.client = None
        logger.info("Fabric Data Service closed")


# Singleton instance
_service: Optional[FabricDataService] = None


def get_fabric_data_service() -> FabricDataService:
    """Get or create Fabric Data service instance following naming convention."""
    global _service
    
    if _service is None:
        tenant_id = os.getenv("TENANT_ID")
        data_agent_url = os.getenv("DATA_AGENT_URL")
        
        if not tenant_id or not data_agent_url:
            raise ValueError(
                "TENANT_ID and DATA_AGENT_URL environment variables required"
            )
        
        _service = FabricDataService(
            tenant_id=tenant_id,
            data_agent_url=data_agent_url
        )
    
    return _service
