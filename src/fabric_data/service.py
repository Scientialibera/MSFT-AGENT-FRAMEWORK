"""
Fabric Data Service

Executes SQL queries directly against Fabric SQL endpoint.
Returns inline results for small datasets, suggests CSV export for large ones.
"""

import os
from typing import Dict, Any, Optional

import structlog

from .connection import get_fabric_sql_connection

logger = structlog.get_logger(__name__)


class FabricDataService:
    """
    Service for executing SQL queries against Fabric SQL endpoint.

    Provides direct SQL execution with automatic result limiting.
    """

    def __init__(self, max_rows_inline: int = 100):
        """
        Initialize the Fabric Data Service.
        
        Args:
            max_rows_inline: Maximum rows to return inline (default: 100)
        """
        self.max_rows_inline = max_rows_inline
        
        logger.info(
            "Initialized Fabric Data Service",
            max_rows_inline=max_rows_inline
        )
    
    def run(self, tool_call: Dict[str, Any] = None) -> str:
        """
        Execute SQL query against Fabric SQL endpoint.
        
        Args:
            tool_call: Tool call dictionary from agent framework with LLM-provided parameters
                      Contains: query (SQL string), reasoning
            
        Returns:
            String response with query results or suggestion to use sql_to_csv
        """
        try:
            # Extract parameters from tool_call (filled by LLM)
            query = tool_call.get('query') if tool_call else None
            reasoning = tool_call.get('reasoning', '') if tool_call else ''
            
            logger.info(
                "[FabricDataService.run] Starting SQL execution",
                query_preview=query[:100] + "..." if query and len(query) > 100 else query,
                reasoning=reasoning
            )
            
            if not query:
                logger.error("[FabricDataService.run] No query provided in tool_call")
                return "Error: No SQL query provided in tool_call"
            
            # Get shared connection
            connection = get_fabric_sql_connection()
            
            # Execute query with row limit
            results, has_more = connection.execute_query(
                query=query,
                max_rows=self.max_rows_inline
            )
            
            logger.info(
                "[FabricDataService.run] Query executed successfully",
                rows_returned=len(results),
                has_more=has_more
            )
            
            # Format results
            if not results:
                return "Query executed successfully. No results returned."
            
            # Build response
            response_parts = []
            response_parts.append(f"Query returned {len(results)} row(s):")
            response_parts.append("")
            
            # Format as table
            if results:
                # Get column names
                columns = list(results[0].keys())
                
                # Add header
                header = " | ".join(columns)
                response_parts.append(header)
                response_parts.append("-" * len(header))
                
                # Add rows
                for row in results:
                    row_str = " | ".join(str(row.get(col, '')) for col in columns)
                    response_parts.append(row_str)
            
            # Add suggestion if more rows exist
            if has_more:
                response_parts.append("")
                response_parts.append(f"⚠️  Result set exceeds {self.max_rows_inline} rows limit.")
                response_parts.append("🔔 RECOMMENDATION: Use the 'sql_to_csv' tool to export the full result set to CSV.")
                response_parts.append("   The agent should call sql_to_csv with the same query to get all data and a download URL.")
            
            final_response = "\n".join(response_parts)
            
            logger.info(
                "[FabricDataService.run] Response formatted",
                response_length=len(final_response)
            )
            
            return final_response
            
        except Exception as e:
            logger.error(
                "[FabricDataService.run] Query execution failed",
                error=str(e),
                query=query if 'query' in locals() else "unknown",
                exc_info=True
            )
            return f"Error executing query: {str(e)}"
    
    def close(self):
        """Clean up resources."""
        logger.info("Fabric Data Service closed")


# Singleton instance
_service: Optional[FabricDataService] = None


def get_fabric_data_service() -> FabricDataService:
    """Get or create Fabric Data service instance following naming convention."""
    global _service
    
    if _service is None:
        max_rows = int(os.getenv("MAX_ROWS_INLINE", "30"))
        
        _service = FabricDataService(
            max_rows_inline=max_rows
        )
    
    return _service
