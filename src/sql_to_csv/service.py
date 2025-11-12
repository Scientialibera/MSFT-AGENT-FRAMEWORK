"""
SQL to CSV Service

Executes SQL queries against Fabric SQL endpoint, converts results to CSV,
uploads to Azure Blob Storage, and returns shareable SAS URL.
"""

import os
import io
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import uuid4

import pandas as pd
import structlog
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.identity import DefaultAzureCredential

from src.fabric_data.connection import get_fabric_sql_connection

logger = structlog.get_logger(__name__)


class SqlToCsvService:
    """
    Service for executing SQL queries and exporting results to CSV in blob storage.
    
    Provides full query results as downloadable CSV files with time-limited access.
    """

    def __init__(
        self,
        storage_account: str,
        container_name: str,
        sas_expiry_hours: int = 24
    ):
        """
        Initialize the SQL to CSV Service.
        
        Args:
            storage_account: Azure Storage account name
            container_name: Blob container name for CSV exports
            sas_expiry_hours: Hours until SAS URL expires (default: 24)
        """
        self.storage_account = storage_account
        self.container_name = container_name
        self.sas_expiry_hours = sas_expiry_hours
        self.credential: Optional[DefaultAzureCredential] = None
        self.blob_service_client: Optional[BlobServiceClient] = None
        
        logger.info(
            "Initialized SQL to CSV Service",
            storage_account=storage_account,
            container=container_name,
            sas_expiry_hours=sas_expiry_hours
        )
    
    def _get_blob_service_client(self) -> BlobServiceClient:
        """
        Get or create BlobServiceClient with Azure AD authentication.
        
        Returns:
            BlobServiceClient: Authenticated blob service client
        """
        if self.blob_service_client is None:
            logger.info("Creating BlobServiceClient")
            
            if self.credential is None:
                self.credential = DefaultAzureCredential(
                    exclude_interactive_browser_credential=True
                )
            
            account_url = f"https://{self.storage_account}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=self.credential
            )
            
            logger.info("BlobServiceClient created", account_url=account_url)
        
        return self.blob_service_client
    
    def _ensure_container_exists(self):
        """Ensure the blob container exists with public blob access, create if needed."""
        try:
            blob_service_client = self._get_blob_service_client()
            container_client = blob_service_client.get_container_client(self.container_name)
            
            if not container_client.exists():
                logger.info("Container does not exist, creating with public blob access", container=self.container_name)
                # Create container with public access level for blobs
                from azure.storage.blob import PublicAccess
                container_client.create_container(public_access=PublicAccess.Blob)
                logger.info("Container created with public blob access", container=self.container_name)
            else:
                logger.debug("Container exists", container=self.container_name)
                # Update existing container to have public blob access (if not already set)
                try:
                    from azure.storage.blob import PublicAccess
                    container_client.set_container_access_policy(
                        signed_identifiers={},
                        public_access=PublicAccess.Blob
                    )
                    logger.info("Container updated to public blob access", container=self.container_name)
                except Exception as e:
                    logger.warning("Could not update container access policy", error=str(e))
                
        except Exception as e:
            logger.error("Error ensuring container exists", error=str(e), exc_info=True)
            raise
    
    def run(self, tool_call: Dict[str, Any] = None) -> str:
        """
        Execute SQL query, export to CSV, upload to blob storage, return SAS URL.
        
        Args:
            tool_call: Tool call dictionary from agent framework
                      Contains: query (SQL string), reasoning
            
        Returns:
            String with download URL and metadata
        """
        try:
            # Extract parameters
            query = tool_call.get('query') if tool_call else None
            reasoning = tool_call.get('reasoning', '') if tool_call else ''
            
            logger.info(
                "[SqlToCsvService.run] Starting SQL to CSV export",
                query_preview=query[:100] + "..." if query and len(query) > 100 else query,
                reasoning=reasoning
            )
            
            if not query:
                logger.error("[SqlToCsvService.run] No query provided")
                return "Error: No SQL query provided in tool_call"
            
            # Execute query (no row limit - get all results)
            logger.info("[SqlToCsvService.run] Executing query")
            connection = get_fabric_sql_connection()
            results, _ = connection.execute_query(query=query, max_rows=None)
            
            if not results:
                return "Query executed successfully. No results to export."
            
            logger.info(
                "[SqlToCsvService.run] Query returned results",
                row_count=len(results)
            )
            
            # Convert to pandas DataFrame
            df = pd.DataFrame(results)
            
            # Convert to CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            
            logger.info(
                "[SqlToCsvService.run] CSV generated",
                size_bytes=len(csv_bytes),
                rows=len(df),
                columns=len(df.columns)
            )
            
            # Ensure container exists
            self._ensure_container_exists()
            
            # Generate blob name with timestamp and UUID
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob_name = f"fabric_export_{timestamp}_{uuid4().hex[:8]}.csv"
            
            # Upload to blob storage
            logger.info("[SqlToCsvService.run] Uploading to blob storage", blob_name=blob_name)
            blob_service_client = self._get_blob_service_client()
            blob_client = blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(csv_bytes, overwrite=True)
            logger.info("[SqlToCsvService.run] Upload complete")
            
            # Get the public URL (no SAS needed since container has public blob access)
            blob_url = blob_client.url
            
            logger.info("[SqlToCsvService.run] Public URL generated (no SAS needed)")
            
            # Build response
            response_parts = [
                "✅ CSV Export Complete",
                "",
                f"Rows exported: {len(df):,}",
                f"Columns: {len(df.columns)}",
                f"File size: {len(csv_bytes):,} bytes",
                f"Public Access: Enabled (no expiry)",
                "",
                "📥 Download URL (public):",
                blob_url,
                "",
                "Column names:",
                ", ".join(df.columns.tolist())
            ]
            
            final_response = "\n".join(response_parts)
            
            logger.info(
                "[SqlToCsvService.run] Export complete",
                blob_name=blob_name,
                rows=len(df)
            )
            
            return final_response
            
        except Exception as e:
            logger.error(
                "[SqlToCsvService.run] Export failed",
                error=str(e),
                query=query if 'query' in locals() else "unknown",
                exc_info=True
            )
            return f"Error exporting to CSV: {str(e)}"
    
    def close(self):
        """Clean up resources."""
        if self.blob_service_client:
            self.blob_service_client = None
        logger.info("SQL to CSV Service closed")


# Singleton instance
_service: Optional[SqlToCsvService] = None


def get_sql_to_csv_service() -> SqlToCsvService:
    """
    Get or create SQL to CSV service instance following naming convention.
    
    Environment Variables Required:
        AZURE_STORAGE_ACCOUNT: Storage account name
        AZURE_STORAGE_CONTAINER: Container name for CSV exports
        CSV_SAS_EXPIRY_HOURS: Hours until SAS URL expires (optional, default: 24)
    
    Returns:
        SqlToCsvService: Shared service instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    global _service
    
    if _service is None:
        storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER")
        sas_expiry_hours = int(os.getenv("CSV_SAS_EXPIRY_HOURS", "24"))
        
        if not storage_account or not container_name:
            raise ValueError(
                "AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_CONTAINER environment variables required"
            )
        
        _service = SqlToCsvService(
            storage_account=storage_account,
            container_name=container_name,
            sas_expiry_hours=sas_expiry_hours
        )
    
    return _service
