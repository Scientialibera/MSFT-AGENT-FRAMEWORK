"""
Fabric SQL Connection Service

Handles pyodbc connection to Microsoft Fabric SQL endpoints with Azure AD authentication.
Shared connection service used by multiple tools (fabric_data, sql_to_csv).
"""

import os
import struct
from typing import Optional
import pyodbc
from azure.identity import DefaultAzureCredential
import structlog

logger = structlog.get_logger(__name__)


class FabricSqlConnection:
    """
    Manages connection to Fabric SQL endpoint using Azure AD authentication.
    
    Provides connection pooling and automatic token refresh for long-running operations.
    """
    
    def __init__(
        self,
        server: str,
        database: str,
        driver: str = "ODBC Driver 18 for SQL Server"
    ):
        """
        Initialize Fabric SQL connection manager.
        
        Args:
            server: Fabric SQL endpoint (e.g., xxx.datawarehouse.fabric.microsoft.com)
            database: Database name
            driver: ODBC driver name (default: ODBC Driver 18 for SQL Server)
        """
        self.server = server
        self.database = database
        self.driver = driver
        self.credential: Optional[DefaultAzureCredential] = None
        self._connection: Optional[pyodbc.Connection] = None
        
        logger.info(
            "Initialized Fabric SQL connection manager",
            server=server,
            database=database,
            driver=driver
        )
    
    def _get_access_token(self) -> bytes:
        """
        Get Azure AD access token for SQL authentication.
        
        Returns:
            bytes: Access token in format required by pyodbc
        """
        if self.credential is None:
            logger.info("Creating DefaultAzureCredential")
            self.credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
        
        # Get token for Azure SQL Database
        # Scope: https://database.windows.net/.default
        logger.debug("Requesting access token for Fabric SQL")
        token = self.credential.get_token("https://database.windows.net/.default")
        
        # Convert token to format required by pyodbc
        # Token must be encoded as bytes with specific structure
        token_bytes = token.token.encode('utf-16-le')
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        
        logger.debug("Access token obtained successfully")
        return token_struct
    
    def get_connection(self) -> pyodbc.Connection:
        """
        Get active database connection, creating new one if needed.
        
        Returns:
            pyodbc.Connection: Active database connection
            
        Raises:
            Exception: If connection fails
        """
        # Check if existing connection is still valid
        if self._connection is not None:
            try:
                # Test connection with simple query
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
            
            # Get Azure AD access token
            token = self._get_access_token()
            
            # Build connection string
            conn_str = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                "Encrypt=yes;"
                "TrustServerCertificate=no;"
                "Connection Timeout=30;"
            )
            
            # Connect using Azure AD token
            # SQL_COPT_SS_ACCESS_TOKEN = 1256
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
    
    def execute_query(self, query: str, max_rows: Optional[int] = None) -> tuple[list[dict], bool]:
        """
        Execute SQL query and return results.
        
        Args:
            query: T-SQL query to execute
            max_rows: Maximum number of rows to return (None = unlimited)
            
        Returns:
            tuple: (results as list of dicts, has_more flag indicating if more rows exist)
            
        Raises:
            Exception: If query execution fails
        """
        try:
            logger.info(
                "Executing Fabric SQL query",
                query_preview=query[:100] + "..." if len(query) > 100 else query,
                max_rows=max_rows
            )
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Execute query
            cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description] if cursor.description else []
            
            # Fetch results
            results = []
            has_more = False
            
            if max_rows is not None:
                # Fetch one extra row to check if there are more
                rows = cursor.fetchmany(max_rows + 1)
                if len(rows) > max_rows:
                    has_more = True
                    rows = rows[:max_rows]
            else:
                rows = cursor.fetchall()
            
            # Convert to list of dicts
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
                query_preview=query[:100] + "..." if len(query) > 100 else query,
                exc_info=True
            )
            raise
    
    def close(self):
        """Close database connection and cleanup resources."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Fabric SQL connection closed")
            except Exception as e:
                logger.warning("Error closing connection", error=str(e))
            finally:
                self._connection = None


# Singleton instance
_connection: Optional[FabricSqlConnection] = None


def get_fabric_sql_connection() -> FabricSqlConnection:
    """
    Get or create singleton Fabric SQL connection instance.
    
    Environment Variables Required:
        FABRIC_SQL_SERVER: Fabric SQL endpoint
        FABRIC_SQL_DATABASE: Database name
        FABRIC_SQL_DRIVER: ODBC driver (optional, defaults to "ODBC Driver 18 for SQL Server")
    
    Returns:
        FabricSqlConnection: Shared connection instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    global _connection
    
    if _connection is None:
        server = os.getenv("FABRIC_SQL_SERVER")
        database = os.getenv("FABRIC_SQL_DATABASE")
        driver = os.getenv("FABRIC_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
        
        if not server or not database:
            raise ValueError(
                "FABRIC_SQL_SERVER and FABRIC_SQL_DATABASE environment variables required"
            )
        
        _connection = FabricSqlConnection(
            server=server,
            database=database,
            driver=driver
        )
    
    return _connection
