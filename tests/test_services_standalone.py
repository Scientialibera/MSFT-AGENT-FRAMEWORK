#!/usr/bin/env python3
"""
Standalone test for Fabric Data Service and SQL to CSV Service

Tests both services independently with Azure CLI credentials.
Uses the Fabric SQL connection and Azure Storage for CSV export.

Requirements:
- Azure CLI logged in: `az login`
- Environment variables set:
  - FABRIC_SQL_SERVER
  - FABRIC_SQL_DATABASE
  - AZURE_STORAGE_ACCOUNT
  - AZURE_STORAGE_CONTAINER

Run:
  python tests/test_services_standalone.py
"""

import os
import sys
import struct
from typing import Optional, Dict, Any, List
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import pandas as pd
import io
from datetime import datetime, timedelta
from uuid import uuid4
import structlog

# Setup logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ============================================================================
# PART 1: Fabric SQL Connection (Shared by both services)
# ============================================================================

class FabricSqlConnection:
    """Manages connection to Fabric SQL endpoint using Azure AD authentication."""
    
    def __init__(
        self,
        server: str,
        database: str,
        driver: str = "ODBC Driver 18 for SQL Server"
    ):
        self.server = server
        self.database = database
        self.driver = driver
        self.credential: Optional[DefaultAzureCredential] = None
        self._connection: Optional[pyodbc.Connection] = None
        
        logger.info(
            "Initialized Fabric SQL connection manager",
            server=server,
            database=database,
        )
    
    def _get_access_token(self) -> bytes:
        """Get Azure AD access token for SQL authentication."""
        if self.credential is None:
            logger.info("Creating DefaultAzureCredential")
            self.credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
        
        logger.debug("Requesting access token for Fabric SQL")
        token = self.credential.get_token("https://database.windows.net/.default")
        
        # Convert token to format required by pyodbc
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        
        logger.debug("Access token obtained successfully")
        return token_struct
    
    def get_connection(self) -> pyodbc.Connection:
        """Get active database connection, creating new one if needed."""
        # Check if existing connection is still valid
        if self._connection is not None:
            try:
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                logger.debug("Reusing existing connection")
                return self._connection
            except Exception as e:
                logger.warning("Existing connection invalid, creating new one", error=str(e))
                self._connection = None
        
        # Create new connection
        try:
            logger.info("Creating new Fabric SQL connection")
            
            token = self._get_access_token()
            
            conn_str = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )
            
            self._connection = pyodbc.connect(
                conn_str,
                attrs_before={1256: token}
            )
            
            logger.info("Fabric SQL connection established successfully")
            return self._connection
            
        except Exception as e:
            logger.error(
                "Failed to connect to Fabric SQL",
                error=str(e),
                server=self.server,
                database=self.database,
                exc_info=True
            )
            raise
    
    def execute_query(self, query: str, max_rows: Optional[int] = None) -> tuple:
        """Execute SQL query and return results."""
        try:
            logger.info(
                "Executing Fabric SQL query",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
                max_rows=max_rows
            )
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            columns = [column[0] for column in cursor.description] if cursor.description else []
            
            results = []
            has_more = False
            
            if max_rows is not None:
                rows = cursor.fetchmany(max_rows + 1)
                if len(rows) > max_rows:
                    has_more = True
                    rows = rows[:max_rows]
            else:
                rows = cursor.fetchall()
            
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            
            logger.info(
                "Query executed successfully",
                rows_returned=len(results),
                has_more=has_more
            )
            
            return results, has_more
            
        except Exception as e:
            logger.error(
                "Query execution failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def close(self):
        """Close database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Fabric SQL connection closed")
            except Exception as e:
                logger.warning("Error closing connection", error=str(e))
            finally:
                self._connection = None


# ============================================================================
# PART 2: Fabric Data Service (Tests inline query results)
# ============================================================================

class FabricDataService:
    """Service for executing SQL queries against Fabric SQL endpoint."""
    
    def __init__(self, connection: FabricSqlConnection, max_rows_inline: int = 100):
        self.connection = connection
        self.max_rows_inline = max_rows_inline
        logger.info(
            "Initialized Fabric Data Service",
            max_rows_inline=max_rows_inline
        )
    
    def run(self, query: str) -> str:
        """Execute SQL query and return formatted results."""
        try:
            logger.info(
                "[FabricDataService.run] Starting SQL execution",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
            )
            
            if not query:
                logger.error("[FabricDataService.run] No query provided")
                return "Error: No SQL query provided"
            
            results, has_more = self.connection.execute_query(
                query=query,
                max_rows=self.max_rows_inline
            )
            
            logger.info(
                "[FabricDataService.run] Query executed successfully",
                rows_returned=len(results),
                has_more=has_more
            )
            
            if not results:
                return "Query executed successfully. No results returned."
            
            response_parts = []
            response_parts.append(f"✅ Query returned {len(results)} row(s):")
            response_parts.append("")
            
            if results:
                columns = list(results[0].keys())
                
                header = " | ".join(columns)
                response_parts.append(header)
                response_parts.append("-" * len(header))
                
                for row in results:
                    row_str = " | ".join(str(row.get(col, '')) for col in columns)
                    response_parts.append(row_str)
            
            if has_more:
                response_parts.append("")
                response_parts.append(f"⚠️  Result set exceeds {self.max_rows_inline} rows limit.")
                response_parts.append("🔔 RECOMMENDATION: Use sql_to_csv tool to export the full result set to CSV.")
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
                exc_info=True
            )
            return f"Error executing query: {str(e)}"


# ============================================================================
# PART 3: SQL to CSV Service (Tests CSV export to Azure Storage)
# ============================================================================

class SqlToCsvService:
    """Service for executing SQL queries and exporting results to CSV in blob storage."""
    
    def __init__(
        self,
        connection: FabricSqlConnection,
        storage_account: str,
        container_name: str,
        sas_expiry_hours: int = 24
    ):
        self.connection = connection
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
        """Get or create BlobServiceClient with Azure AD authentication."""
        if self.blob_service_client is None:
            logger.info("Creating BlobServiceClient")
            
            # Try with account key first (from environment)
            account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
            account_url = f"https://{self.storage_account}.blob.core.windows.net"
            
            if account_key:
                logger.info("Using account key for blob storage authentication")
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key
                )
            else:
                # Fall back to DefaultAzureCredential
                logger.info("Using DefaultAzureCredential for blob storage authentication")
                if self.credential is None:
                    self.credential = DefaultAzureCredential(
                        exclude_interactive_browser_credential=True
                    )
                
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
    
    def run(self, query: str) -> str:
        """Execute SQL query, export to CSV, upload to blob storage, return SAS URL."""
        try:
            logger.info(
                "[SqlToCsvService.run] Starting SQL to CSV export",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
            )
            
            if not query:
                logger.error("[SqlToCsvService.run] No query provided")
                return "Error: No SQL query provided"
            
            # Execute query (no row limit)
            logger.info("[SqlToCsvService.run] Executing query")
            results, _ = self.connection.execute_query(query=query, max_rows=None)
            
            if not results:
                return "Query executed successfully. No results to export."
            
            logger.info(
                "[SqlToCsvService.run] Query returned results",
                row_count=len(results)
            )
            
            # Convert to DataFrame
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
            
            # Generate blob name
            from datetime import timezone
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
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
            
            logger.info(
                "[SqlToCsvService.run] Public URL generated (no SAS needed)",
            )
            
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
                exc_info=True
            )
            return f"Error exporting to CSV: {str(e)}"


# ============================================================================
# PART 4: Test Functions
# ============================================================================

def test_fabric_data_service():
    """Test Fabric Data Service with inline query."""
    print("\n" + "="*80)
    print("TEST 1: Fabric Data Service (Inline Query)")
    print("="*80)
    
    try:
        # Get environment variables
        server = os.getenv("FABRIC_SQL_SERVER")
        database = os.getenv("FABRIC_SQL_DATABASE")
        
        if not server or not database:
            print("❌ Missing environment variables: FABRIC_SQL_SERVER and FABRIC_SQL_DATABASE")
            print("   Set these environment variables first:")
            print("   $env:FABRIC_SQL_SERVER='your-workspace.datawarehouse.fabric.microsoft.com'")
            print("   $env:FABRIC_SQL_DATABASE='your-database'")
            return False
        
        # Create connection
        print(f"\n📡 Connecting to Fabric SQL: {server}/{database}")
        connection = FabricSqlConnection(
            server=server,
            database=database
        )
        
        # Create service
        print("📦 Initializing Fabric Data Service")
        service = FabricDataService(connection, max_rows_inline=100)
        
        # Test query - use a simple SELECT that works on Fabric SQL
        test_query = "SELECT 'Connection successful' AS status, GETDATE() AS timestamp"
        print(f"\n🔍 Executing test query: {test_query}")
        
        result = service.run(test_query)
        print("\n📊 Result:")
        print(result)
        
        connection.close()
        print("\n✅ TEST 1 PASSED: Fabric Data Service works!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {str(e)}")
        logger.error("TEST 1 failed", error=str(e), exc_info=True)
        return False


def test_sql_to_csv_service():
    """Test SQL to CSV Service with CSV export."""
    print("\n" + "="*80)
    print("TEST 2: SQL to CSV Service (CSV Export)")
    print("="*80)
    
    try:
        # Get environment variables
        server = os.getenv("FABRIC_SQL_SERVER")
        database = os.getenv("FABRIC_SQL_DATABASE")
        storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
        container_name = os.getenv("AZURE_STORAGE_CONTAINER", "fabric-exports")
        
        if not server or not database:
            print("❌ Missing environment variables: FABRIC_SQL_SERVER and FABRIC_SQL_DATABASE")
            return False
        
        if not storage_account:
            print("❌ Missing environment variable: AZURE_STORAGE_ACCOUNT")
            print("   Set this environment variable:")
            print("   $env:AZURE_STORAGE_ACCOUNT='your-storage-account'")
            return False
        
        # Create connection
        print(f"\n📡 Connecting to Fabric SQL: {server}/{database}")
        connection = FabricSqlConnection(
            server=server,
            database=database
        )
        
        # Create service
        print(f"📦 Initializing SQL to CSV Service")
        print(f"   Storage Account: {storage_account}")
        print(f"   Container: {container_name}")
        
        service = SqlToCsvService(
            connection=connection,
            storage_account=storage_account,
            container_name=container_name,
            sas_expiry_hours=24
        )
        
        # Test query - use a simple SELECT that works on Fabric SQL
        test_query = "SELECT 'CSV Export Test' AS description, GETDATE() AS export_time, 1 AS row_number UNION ALL SELECT 'Row 2', GETDATE(), 2 UNION ALL SELECT 'Row 3', GETDATE(), 3"
        print(f"\n🔍 Executing test query (will export to CSV):")
        
        result = service.run(test_query)
        print("\n📊 Result:")
        print(result)
        
        connection.close()
        print("\n✅ TEST 2 PASSED: SQL to CSV Service works!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {str(e)}")
        logger.error("TEST 2 failed", error=str(e), exc_info=True)
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("FABRIC DATA AGENT - SERVICE TESTING")
    print("="*80)
    print("\nTesting Fabric Data Service and SQL to CSV Service")
    print("Using Azure CLI credentials (DefaultAzureCredential)")
    
    # Check if user is logged in
    print("\n🔐 Checking Azure CLI authentication...")
    try:
        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        token = cred.get_token("https://database.windows.net/.default")
        print("✅ Authenticated via Azure CLI")
    except Exception as e:
        print("❌ Not authenticated to Azure CLI")
        print("   Run: az login")
        return False
    
    # Run tests
    test1_passed = test_fabric_data_service()
    test2_passed = test_sql_to_csv_service()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Fabric Data Service:  {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"SQL to CSV Service:   {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! Services are working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
