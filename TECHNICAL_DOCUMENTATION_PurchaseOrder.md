# Order Status Agent - Technical Documentation

## Overview

This document describes the architecture and implementation of the **Order Status Agent**, a dual-mode agent hosted in **Azure AI Foundry** that provides real-time purchase order and sales order status tracking.

The agent runs in Azure AI Foundry and is configured with different tools based on operational mode:
1. **Fabric Agent Mode** - Foundry Agent assigned **Fabric Data Agent Tool** (natural language interface)
2. **MCP Direct SQL Mode** - Foundry Agent assigned **MCP tools** (fabric_data + sql_to_csv for direct SQL)

Both modes leverage the same underlying Fabric SQL data models but provide different query interfaces and tool capabilities.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Operational Modes](#operational-modes)
3. [Data Model Requirements](#data-model-requirements)
4. [Fabric Agent Mode (AI Foundry)](#fabric-agent-mode-ai-foundry)
5. [MCP Direct SQL Mode](#mcp-direct-sql-mode)
6. [Configuration & Deployment](#configuration--deployment)
7. [Implementation Guide](#implementation-guide)
8. [System Prompts](#system-prompts)

---

## Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                  Azure AI Foundry                               │
│              (Hosts Order Status Agent)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Agent: scm_order_status_agent                                 │
│  ├─ Model: GPT-4 (Azure OpenAI)                               │
│  └─ Tools (depend on AGENT_BACKEND mode):                     │
│                                                                 │
│     Mode 1: AGENT_BACKEND=fabric_agent                         │
│     ├─ Fabric Data Agent Tool (for queries)                   │
│     └─ sql_to_csv Tool (MCP, for exports)                     │
│                                                                 │
│     Mode 2: AGENT_BACKEND=mcp_direct_sql                       │
│     ├─ fabric_data Tool (MCP, for queries)                    │
│     └─ sql_to_csv Tool (MCP, for exports)                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
        │
        ├─ Mode 1: Query Tool = Fabric Data Agent
        │       ↓
        │   ┌────────────────────────┐
        │   │ Fabric Data Agent API  │
        │   │ (NL → SQL)             │
        │   └────────┬───────────────┘
        │            ↓
        │   ┌────────────────────────┐
        │   │ Fabric SQL Endpoint    │
        │   └────────────────────────┘
        │
        └─ Mode 2: Query Tool = fabric_data (MCP)
                ↓
        ┌────────────────────────┐
        │ MCP Orchestrator       │
        │ └─ fabric_data tool    │
        │    (Direct SQL)        │
        └────────┬───────────────┘
                 ↓
        ┌────────────────────────┐
        │ Fabric SQL Endpoint    │
        └────────────────────────┘

        Both Modes: Export Tool = sql_to_csv (MCP)
                ↓
        ┌────────────────────────┐
        │ MCP Orchestrator       │
        │ └─ sql_to_csv tool     │
        │    (CSV Export)        │
        └────────┬───────────────┘
                 ↓
        ┌────────────────────────┐
        │ Fabric SQL Endpoint    │
        └────────┬───────────────┘
                 ↓
        ┌────────────────────────┐
        │ Azure Blob Storage     │
        │ • CSV files            │
        │ • SAS URLs             │
        └────────────────────────┘
```

### Key Architecture Principles

- **Dual-Mode Flexibility** - Choose deployment model that fits infrastructure
- **Unified Data Model** - Both modes query the same Fabric SQL data sources
- **Prompt Parity** - Both modes use equivalent system prompts, tailored to their tool capabilities
- **Mode Selection at Startup** - Environment variable determines which mode runs
- **Single Instance Pattern** - Agents created once and reused across queries

---

## Operational Modes

### Mode 1: Fabric Agent Mode (Query: Fabric Data Agent + Export: sql_to_csv)

**Environment Variable:**
```bash
AGENT_BACKEND=fabric_agent
```

**Foundry Agent Tool Assignment:**
```
Azure AI Foundry Agent
├─ Fabric Data Agent Tool → For queries (NL → SQL)
└─ sql_to_csv Tool (MCP) → For large exports
```

**Architecture:**
```
Foundry Agent
    ├─ Query Path (uses Fabric Data Agent Tool):
    │       ↓
    │   Fabric Data Agent API (translates NL to SQL)
    │       ↓
    │   Fabric SQL Endpoint → Results (inline, formatted)
    │
    └─ Export Path (uses sql_to_csv Tool):
            ↓
        MCP Orchestrator (sql_to_csv tool)
            ↓
        Fabric SQL Endpoint → CSV
            ↓
        Azure Blob Storage (SAS URL returned)
```

**Characteristics:**
- Query tool: Fabric Data Agent (natural language)
- Export tool: sql_to_csv (MCP)
- Natural language query understanding (Fabric handles translation)
- Built-in CSV export capability

**Tools Assigned:**
- **Fabric Data Agent Tool** - Handles NL-to-SQL translation
- **sql_to_csv Tool (MCP)** - Exports results to CSV in Azure Blob Storage

---

### Mode 2: MCP Direct SQL Mode (Query: fabric_data + Export: sql_to_csv)

**Environment Variable:**
```bash
AGENT_BACKEND=mcp_direct_sql
```

**Foundry Agent Tool Assignment:**
```
Azure AI Foundry Agent
├─ fabric_data Tool (MCP) → For queries (direct SQL)
└─ sql_to_csv Tool (MCP) → For large exports
```

**Architecture:**
```
Foundry Agent
    ├─ Query Path (uses fabric_data Tool):
    │       ↓
    │   MCP Orchestrator (fabric_data tool)
    │       ↓
    │   FabricSqlConnection (Azure AD + pyodbc)
    │       ↓
    │   Fabric SQL Endpoint → Results (inline, ≤100 rows)
    │
    └─ Export Path (uses sql_to_csv Tool):
            ↓
        MCP Orchestrator (sql_to_csv tool)
            ↓
        FabricSqlConnection (unbounded)
            ↓
        Fabric SQL Endpoint → CSV
            ↓
        Azure Blob Storage (SAS URL returned)
```

**Characteristics:**
- Query tool: fabric_data (direct SQL, ≤100 rows)
- Export tool: sql_to_csv (MCP, any size)
- Full SQL control via direct execution
- Extensible middleware for logging/monitoring
- Containerizable MCP orchestrator

**When to Use:**
- When direct SQL control needed
- When avoiding Fabric Data Agent dependency

**Tools Assigned:**
- **fabric_data Tool (MCP)** - Direct SQL execution, inline results (≤100 rows default)
- **sql_to_csv Tool (MCP)** - CSV export to blob storage (any size)

---

## Data Model Requirements

### Overview

Both modes require the same underlying data model sourced from **Microsoft Dynamics 365 Finance & Operations (D365 F&O)**. The Order Status Agent queries **core tables** from D365 F&O via Dataverse or OData endpoints.

### Core Tables (From D365 F&O)

#### 1. PurchTable (Purchase Order Header)

**Table Name:** `PurchTable` (D365 F&O standard table)

**Required Columns:**
```
- PurchID (string, PK): Purchase order number (e.g., "PO-12345")
- OrderAccount (string, FK): Vendor/Supplier ID
- PurchName (string): Vendor Name
- DataAreaID (string): Legal Entity identifier (e.g., "USMF", "USP2", "FRRT")
- PurchStatus (int): Purchase order status (Backorder, Received, Invoiced, Cancelled, Open, etc.)
- DeliveryDate (datetime): Expected delivery date
- Payment (string): Term of payment (e.g., "Net30", "Net45")
- PaymMode (string): Method of payment (e.g., "CHECK", "BANKTRANSFER")
- DlvTerm (string, nullable): Delivery term code
- CreatedDate (datetime): Record creation timestamp
- ModifiedDate (datetime): Last update timestamp
```

**Index Recommendations:**
```sql
CREATE INDEX idx_purchtable_status ON PurchTable(PurchStatus)
CREATE INDEX idx_purchtable_entity ON PurchTable(DataAreaID)
CREATE INDEX idx_purchtable_vendor ON PurchTable(OrderAccount)
CREATE INDEX idx_purchtable_date ON PurchTable(DeliveryDate DESC)
```

**Sample Queries:**
```sql
-- Retrieve purchase order status
SELECT PurchID, OrderAccount, PurchName, DataAreaID, PurchStatus, DeliveryDate
FROM PurchTable
WHERE PurchID = 'PO-12345' AND DataAreaID = 'USMF'

-- Get all open POs for a vendor in specific entity
SELECT PurchID, PurchName, PurchStatus, DataAreaID
FROM PurchTable
WHERE OrderAccount = 'VENDOR001' AND PurchStatus = 1 AND DataAreaID = 'USP2'

-- Retrieve delivery dates for open POs
SELECT TOP 30 PurchID, PurchName, DeliveryDate, PurchStatus
FROM PurchTable
WHERE PurchStatus IN (1, 2) AND DataAreaID IN ('USMF', 'USP2', 'FRRT')
ORDER BY DeliveryDate ASC
```

**Status Value Mappings:**
```
0 = Backorder
1 = Open
2 = Received (Partial/Full)
3 = Invoiced
4 = Cancelled
(Values may vary by D365 F&O version)
```

---

#### 2. PurchLine (Purchase Order Line Items)

**Table Name:** `PurchLine` (D365 F&O standard table)

**Required Columns:**
```
- PurchID (string, FK): Reference to PurchTable
- LineNumber (int): Line sequence number (1, 2, 3, etc.)
- ItemID (string): Product/Item identifier (e.g., "M7001", "M0061")
- Name (string): Line description (product name)
- PurchQty (decimal): Quantity ordered
- PurchPrice (decimal): Unit price
- LineAmount (decimal): Total line value (Qty × Price)
- LineStatus (string, nullable): Line-specific status
- DeliveryDate (datetime, nullable): Line delivery date
- DataAreaID (string): Legal entity
```

**Sample Queries:**
```sql
-- Get line details for specific PO
SELECT LineNumber, ItemID, Name, PurchQty, PurchPrice, LineAmount
FROM PurchLine
WHERE PurchID = 'PO-12345' AND DataAreaID = 'USMF'
ORDER BY LineNumber

-- Get all line items for a vendor's POs
SELECT p.PurchID, l.LineNumber, l.ItemID, l.Name, l.PurchQty
FROM PurchLine l
JOIN PurchTable p ON l.PurchID = p.PurchID
WHERE p.OrderAccount = 'VENDOR001' AND p.DataAreaID = 'USP2'
ORDER BY p.PurchID, l.LineNumber
```

---

#### 3. VendTable (Vendor Master)

**Table Name:** `VendTable` (D365 F&O standard table)

**Required Columns:**
```
- AccountNum (string, PK): Vendor ID
- Name (string): Vendor name
- Email (string, nullable): Vendor email
- Phone (string, nullable): Vendor phone
- Status (int): Vendor status (Active, Hold, Blocked, etc.)
- DataAreaID (string): Legal entity
```

**Sample Queries:**
```sql
-- Get vendor details for purchase order lookup
SELECT v.AccountNum, v.Name, v.Email, v.Phone
FROM VendTable v
WHERE v.AccountNum = 'VENDOR001'

-- Match vendor ID to vendor name
SELECT DISTINCT p.OrderAccount, v.Name
FROM PurchTable p
LEFT JOIN VendTable v ON p.OrderAccount = v.AccountNum
WHERE p.DataAreaID = 'USMF'
```

---

### Data Entity Mappings (Dataverse/OData)

If using Dataverse or OData endpoints instead of direct SQL:

| D365 F&O Table | OData Entity | Data Endpoint |
|---|---|---|
| PurchTable | PurchaseOrderHeadersV2 | `/data/PurchaseOrderHeadersV2` |
| PurchLine | PurchaseOrderLinesV2 | `/data/PurchaseOrderLinesV2` |
| VendTable | Vendors | `/data/Vendors` |

---

### Data Model Configuration

#### For Fabric Agent Mode

**Where to Store Model Metadata:**
1. **In Fabric Data Agent Configuration** (UI or API):
   - Define available D365 F&O tables and columns
   - Map D365 F&O entity names to Fabric Data Agent
   - Set query scope and permissions
   - Configure natural language mappings for business terms

2. **In System Prompt** (`order_status_fabric_agent_prompt.txt`):
   - Document D365 F&O table names exactly (PurchTable, PurchLine, VendTable)
   - Document column names exactly (PurchID, OrderAccount, PurchStatus, DeliveryDate, etc.)
   - Explain column purposes and relationships
   - Provide example queries using correct D365 F&O table/column names
   - Document status value mappings (0=Backorder, 1=Open, 2=Received, 3=Invoiced, 4=Cancelled)

**Example System Prompt Section:**
```
AVAILABLE D365 F&O DATA SOURCES:

Tables:
1. PurchTable (Purchase Order Header)
   - PurchID: Purchase order number (e.g., "PO-12345")
   - OrderAccount: Vendor ID
   - PurchName: Vendor name
   - DataAreaID: Legal entity (USMF, USP2, FRRT, etc.)
   - PurchStatus: Status code (1=Open, 2=Received, 3=Invoiced, 4=Cancelled)
   - DeliveryDate: Expected delivery date
   - Payment: Payment terms (Net30, Net45, etc.)
   - PaymMode: Payment method (CHECK, BANKTRANSFER)
   - DlvTerm: Delivery term code

2. PurchLine (Purchase Order Line Items)
   - PurchID: Reference to PurchTable
   - LineNumber: Line sequence (1, 2, 3, etc.)
   - ItemID: Product code
   - Name: Product description
   - PurchQty: Quantity ordered
   - PurchPrice: Unit price
   - LineAmount: Total line value

3. VendTable (Vendor Master)
   - AccountNum: Vendor ID
   - Name: Vendor name
   - Email: Vendor email
   - Phone: Vendor phone

COMMON QUERIES YOU SHOULD HANDLE:
- "What is the status of purchase order PO12345?"
- "List all line items for PO45678"
- "Show me open purchase orders for vendor ABC in USP2"
- "Get delivery date for invoiced purchase orders"
- "Which vendors have invoiced POs?"
- "Show me all POs for vendor XYZ in USMF"

RESPONSE GUIDELINES:
- Always reference PO numbers exactly (e.g., "PO-12345")
- Show legal entity with each result
- Include delivery dates when relevant
- Show vendor names and status
- Highlight any concerning statuses (Backorder, Cancelled)
- Use the status mappings: 1=Open, 2=Received, 3=Invoiced, 4=Cancelled
```

---

#### For MCP Direct SQL Mode

**Where to Store Model Metadata:**
1. **In SQL Connection Configuration** (`src/fabric_data/connection.py`):
   - Database server connection to D365 F&O (SQL or Dataverse)
   - SQL driver configuration
   - Azure AD authentication setup
   - Query timeout and connection pooling

2. **In Tool Configurations** (`config/tools/`):
   - `fabric_data.json` - SQL query parameters for inline results
   - `sql_to_csv.json` - SQL query and CSV export parameters

3. **In System Prompts** (BOTH files):
   - `system_prompt_full.txt` (includes both fabric_data and sql_to_csv tools)
   - `system_prompt_csv_only.txt` (export-focused mode)

**Example System Prompt Section:**
```
D365 F&O DATA MODEL - SQL ACCESS:

Database: D365_Production (or your D365 F&O database)
Connection: Azure AD authenticated

Tables:
├─ PurchTable (Purchase Order Headers)
│  ├─ PurchID (nvarchar): PO number
│  ├─ OrderAccount (nvarchar): Vendor ID
│  ├─ PurchName (nvarchar): Vendor name
│  ├─ DataAreaID (nvarchar): Legal entity
│  ├─ PurchStatus (int): Status (1=Open, 2=Received, 3=Invoiced, 4=Cancelled)
│  ├─ DeliveryDate (datetime): Expected delivery
│  ├─ Payment (nvarchar): Payment terms
│  └─ PaymMode (nvarchar): Payment method
│
├─ PurchLine (Purchase Order Lines)
│  ├─ PurchID (nvarchar): FK to PurchTable
│  ├─ LineNumber (int): Line sequence
│  ├─ ItemID (nvarchar): Product code
│  ├─ Name (nvarchar): Product description
│  ├─ PurchQty (decimal): Quantity
│  ├─ PurchPrice (decimal): Unit price
│  └─ LineAmount (decimal): Total value
│
└─ VendTable (Vendor Master)
   ├─ AccountNum (nvarchar): Vendor ID
   ├─ Name (nvarchar): Vendor name
   ├─ Email (nvarchar): Vendor email
   └─ Phone (nvarchar): Vendor phone

QUERY EXAMPLES:

Get purchase order status:
SELECT PurchID, OrderAccount, PurchName, PurchStatus, DeliveryDate, DataAreaID
FROM PurchTable
WHERE PurchID = 'PO-12345' AND DataAreaID = 'USMF'

Get line details for PO:
SELECT l.LineNumber, l.ItemID, l.Name, l.PurchQty, l.PurchPrice, l.LineAmount
FROM PurchLine l
WHERE l.PurchID = 'PO-12345'
ORDER BY l.LineNumber

Get all open POs for vendor:
SELECT PurchID, PurchName, PurchStatus, DeliveryDate, DataAreaID
FROM PurchTable
WHERE OrderAccount = 'VENDOR001' AND PurchStatus = 1
ORDER BY DeliveryDate ASC

Get POs by legal entity:
SELECT TOP 30 PurchID, PurchName, PurchStatus, DeliveryDate, DataAreaID
FROM PurchTable
WHERE DataAreaID IN ('USMF', 'USP2', 'FRRT')
ORDER BY DeliveryDate DESC
```

---

## Fabric Agent Mode (Fabric Data Agent Tool + sql_to_csv Tool)

### Architecture

```
┌─────────────────────────────────────────────────────┐
│          Azure AI Foundry                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Agent: scm_order_status_agent                     │
│  Model: GPT-4 (Azure OpenAI)                       │
│                                                     │
│  Assigned Tools:                                    │
│  ├─ Fabric Data Agent Tool                         │
│  │  (for queries - NL to SQL translation)          │
│  └─ sql_to_csv Tool (MCP)                          │
│     (for large exports to CSV)                     │
│                                                     │
└─────────────────────────────────────────────────────┘
        │
        ├─ When query needed:
        │  ↓
        │  Fabric Data Agent Tool
        │  ↓
        │  Fabric Data Agent API (translates NL to SQL)
        │  ↓
        │  Fabric SQL Endpoint
        │  ↓
        │  Results (formatted table, returned inline)
        │
        └─ When export needed:
           ↓
           sql_to_csv Tool (MCP)
           ↓
           MCP Orchestrator executes query and generates CSV
           ↓
           Fabric SQL Endpoint
           ↓
           Azure Blob Storage (CSV uploaded)
           ↓
           SAS URL returned to user
```

### Agent Creation

**Class Definition:**

```python
class OrderStatusAgent(SmartSCMMCPAgent):
    """
    Order Status Agent for tracking purchase and sales orders.
    Uses MCP with Fabric Data Agent Tool for natural language interface.
    """
    
    AGENT_NAME = "scm_order_status_agent_fabric_mode"
    PROMPT_FILE = "config/prompts/order_status_fabric_agent_prompt.txt"
    
    def __init__(self):
        super().__init__()
        self.tools = [self._fabric_data_agent_tool()]
    
    def _fabric_data_agent_tool(self):
        """Return Fabric Data Agent MCP tool."""
        return {
            "name": "fabric_data_agent",
            "description": "Query Fabric SQL using Fabric Data Agent (NL to SQL)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"}
                }
            }
        }
```

### Environment Variables

**Mode Selection:**
```bash
AGENT_BACKEND=fabric_agent
```

**Azure OpenAI Configuration (MCP):**
```bash
AZURE_OPENAI_ENDPOINT=https://[resource].openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_KEY=sk-...
AZURE_OPENAI_API_VERSION=2024-10-01-preview
```

**Fabric Data Agent Configuration:**
```bash
FABRIC_DATA_AGENT_ENDPOINT=https://[fabric-endpoint].fabric.microsoft.com
FABRIC_DATA_AGENT_API_KEY=<key>
# OR use Azure AD with managed identity (no keys needed)
```

### System Prompt Configuration

**File:** `config/prompts/order_status_fabric_agent_prompt.txt`

**Purpose:** Guide the MCP agent when using Fabric Data Agent tool (natural language mode)

**Key Sections:**

```
You are an Order Status Agent specializing in purchase and sales order tracking.

YOUR ROLE:
- Track purchase order (PO) status and delivery schedules
- Monitor sales order (SO) status and fulfillment progress
- Identify delayed or at-risk orders
- Provide supplier and customer insights
- Alert on status changes and exceptions

AVAILABLE DATA (via Fabric Data Agent):
1. Purchase Orders (PO_ID, Status, Supplier, Delivery Dates)
2. Sales Orders (SO_ID, Status, Customer, Delivery Dates)
3. Order Line Items (SKU, Quantity, Status)
4. Order Status History (Status changes with timestamps)

COMMON QUERIES YOU SHOULD HANDLE:
- "What purchase orders are overdue?"
- "Show me the status of PO-2025-001"
- "Which suppliers have delayed deliveries?"
- "What's the delivery schedule for the next week?"
- "Export all active sales orders"

RESPONSE GUIDELINES:
- Always reference order IDs (PO-XXXX or SO-XXXX format)
- Include current status and expected/actual delivery dates
- Highlight any delays or issues
- Provide actionable recommendations
- Use Fabric data as source of truth
```

### Deployment

```bash
# Create agent (one-time)
agent = OrderStatusAgent()

# Use agent (reusable)
result = await agent.process_query("What POs are delayed?")
```

---

## MCP Direct SQL Mode (fabric_data Tool + sql_to_csv Tool)

### Architecture

```
┌─────────────────────────────────────────────────────┐
│          Azure AI Foundry                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Agent: scm_order_status_agent                     │
│  Model: GPT-4 (Azure OpenAI)                       │
│                                                     │
│  Assigned Tools (both MCP):                        │
│  ├─ fabric_data Tool                               │
│  │  (for queries - direct SQL, ≤100 rows)          │
│  └─ sql_to_csv Tool                                │
│     (for large exports to CSV)                     │
│                                                     │
└─────────────────────────────────────────────────────┘
        │
        ├─ When query needed (small):
        │  ↓
        │  fabric_data Tool (MCP)
        │  ↓
        │  MCP Orchestrator
        │  ↓
        │  FabricSqlConnection (Azure AD + pyodbc)
        │  ↓
        │  Fabric SQL Endpoint (execute query)
        │  ↓
        │  Results (inline table, ≤100 rows)
        │
        └─ When export needed (large):
           ↓
           sql_to_csv Tool (MCP)
           ↓
           MCP Orchestrator
           ↓
           FabricSqlConnection (unbounded rows)
           ↓
           Fabric SQL Endpoint (execute query)
           ↓
           Generate CSV file
           ↓
           Azure Blob Storage (CSV uploaded)
           ↓
           SAS URL returned to user
```

### Orchestrator Configuration

**Mode Selection in Code:**

```python
# In src/orchestrator/main.py
# Both modes run MCP Orchestrator - the difference is which tool is configured
AGENT_MODE = os.getenv("AGENT_BACKEND", "mcp_direct_sql").lower()

if AGENT_MODE == "fabric_agent":
    # Load Fabric Agent Tool configuration
    SYSTEM_PROMPT_FILE = "config/prompts/order_status_fabric_agent_prompt.txt"
    # Register: fabric_data_agent tool (MPC tool that calls Fabric Data Agent API)
    TOOLS = [fabric_data_agent_tool()]
elif AGENT_MODE == "mcp_direct_sql":
    # Load Direct SQL Tool configurations
    SYSTEM_PROMPT_FILE = "config/orchestrator/system_prompt_full.txt"
    # Register: fabric_data tool (direct SQL) + sql_to_csv tool (export)
    TOOLS = [fabric_data_tool(), sql_to_csv_tool()]
```

**Key Point:** Both modes instantiate an MCP Orchestrator. The difference is:
- **Fabric Agent Mode**: MCP orchestrator hosts `fabric_data_agent` tool which calls Fabric Data Agent API
- **MCP Direct SQL Mode**: MCP orchestrator hosts `fabric_data` and `sql_to_csv` tools which directly execute SQL

### Environment Variables

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://[resource].openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-10-01-preview

# Fabric SQL Connection
FABRIC_SQL_SERVER=your-workspace.datawarehouse.fabric.microsoft.com
FABRIC_SQL_DATABASE=your-database-name
FABRIC_SQL_DRIVER=ODBC Driver 18 for SQL Server

# Query Limits
MAX_ROWS_INLINE=100

# Azure Blob Storage (for sql_to_csv)
AZURE_STORAGE_ACCOUNT=your-storage-account-name
AZURE_STORAGE_CONTAINER=order-status-exports
CSV_SAS_EXPIRY_HOURS=24

# Mode Selection
AGENT_BACKEND=mcp_direct_sql
```

### System Prompt Configuration

**Two Variants Available:**

#### Option 1: Full Mode (`system_prompt_full.txt`)
- Both `fabric_data` and `sql_to_csv` tools available
- Agent chooses tool based on query scope
- Best for flexible query handling

```
You are an Order Status Agent with access to two tools:

1. fabric_data - Quick queries (≤100 rows)
   - Use for: Specific order lookups, small result sets
   - Returns: Formatted table results

2. sql_to_csv - Large exports (any size)
   - Use for: Bulk exports, all active orders, reports
   - Returns: CSV download link via Azure Blob Storage

QUERY ROUTING:
- "Show me PO-2025-001 status" → fabric_data (small result)
- "Export all overdue POs" → sql_to_csv (large result)
- "Get last 10 order updates" → fabric_data (small result)
- "Send all SOs to Finance" → sql_to_csv (export)
```

#### Option 2: CSV-Only Mode (`system_prompt_csv_only.txt`)
- Only `sql_to_csv` tool available
- All queries result in CSV export
- Best for batch processing and reporting

```
You are an Order Status Agent that exports all query results to CSV.

WORKFLOW:
1. User provides order query
2. You generate T-SQL query
3. Execute via sql_to_csv tool
4. Return CSV download link

Every response includes a downloadable CSV file.
```

---

## Configuration & Deployment

### Required Infrastructure

#### Fabric Agent Mode
```
✅ Azure AI Foundry Project
✅ Azure OpenAI (GPT-4)
✅ Fabric Workspace with SQL Endpoint
✅ Fabric Data Agent configured
✅ Managed Identity with Fabric permissions
```

#### MCP Direct SQL Mode
```
✅ Azure OpenAI (GPT-4)
✅ Fabric SQL Endpoint
✅ Azure Storage Account (for CSV exports)
✅ Managed Identity with SQL access
✅ Managed Identity with Blob Storage role
✅ Docker/Container runtime (if containerized)
✅ ODBC Driver 18 for SQL Server
```

### Environment Variable Reference

| Variable | Fabric Agent | MCP Mode | Required | Example |
|----------|-------------|----------|----------|---------|
| AGENT_BACKEND | N/A | ✅ | ✅ | `mcp_direct_sql` |
| AZURE_OPENAI_ENDPOINT | ✅ | ✅ | ✅ | `https://resource.openai.azure.com/` |
| AZURE_OPENAI_CHAT_DEPLOYMENT | ✅ | ✅ | ✅ | `gpt-4` |
| AZURE_OPENAI_API_KEY | ✅ | ✅ | ✅ | `sk-...` |
| AZURE_AI_FOUNDRY_URL | ✅ | | | `https://workspace.ai.azure.com` |
| FOUNDRY_FABRIC_ORDER_STATUS_RESOURCE_ID | ✅ | | | `<resource-id>` |
| FABRIC_SQL_SERVER | | ✅ | ✅ | `workspace.datawarehouse.fabric.microsoft.com` |
| FABRIC_SQL_DATABASE | | ✅ | ✅ | `YourDatabase` |
| FABRIC_SQL_DRIVER | | ✅ | | `ODBC Driver 18 for SQL Server` |
| AZURE_STORAGE_ACCOUNT | | ✅ | ✅ | `storageaccount` |
| AZURE_STORAGE_CONTAINER | | ✅ | | `order-status-exports` |
| MAX_ROWS_INLINE | | ✅ | | `100` |
| CSV_SAS_EXPIRY_HOURS | | ✅ | | `24` |

---

## Implementation Guide

### Step 1: Set Up Data Connection

**Connect to D365 F&O Data:**

1. **Ensure D365 F&O Tables are Accessible:**
   - Verify PurchTable, PurchLine, and VendTable exist in D365 F&O
   - Confirm tables have required columns (see Data Model section)
   - Ensure Dataverse or OData endpoints are available

2. **Verify Legal Entities:**
   - Confirm all required legal entities (USMF, USP2, FRRT, etc.) are set up
   - Verify user has access to query these entities

3. **Test Data Access:**
   - Test SQL connection or OData endpoint access
   - Verify sample queries return data from PurchTable and PurchLine
   - Validate status value mappings work correctly

4. **Document Column Names:**
   - Confirm column names match functional requirements (PurchID, OrderAccount, etc.)
   - Note any custom fields or column name variations

### Step 2: Choose Deployment Mode

**For Fabric Agent Mode:**
```bash
# Ensure Azure AI Foundry is configured and Foundry Agent is created

# Create agent in Foundry UI or API
# Set FOUNDRY_FABRIC_ORDER_STATUS_RESOURCE_ID
```

**For MCP Direct SQL Mode:**
```bash
# Set AGENT_BACKEND=mcp_direct_sql
# Configure Fabric SQL connection variables
# Configure Azure Storage for CSV exports
# Install ODBC Driver 18
```

### Step 3: Configure System Prompt

**For Fabric Agent Mode:**

Edit `config/prompts/order_status_fabric_agent_prompt.txt`:
- Document exact table and column names
- Provide example queries for common scenarios
- Include status value definitions
- Explain business logic for delayed/at-risk orders

**For MCP Direct SQL Mode:**

Edit `config/orchestrator/system_prompt_full.txt` (or `system_prompt_csv_only.txt`):
- Include complete data model schema
- Provide T-SQL query examples
- Explain when to use fabric_data vs sql_to_csv
- Include sample queries with exact table/column names

### Step 4: Set Environment Variables

**For Fabric Agent Mode:**
```bash
export AZURE_OPENAI_URL=https://resource.openai.azure.com/
export AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4
export AZURE_OPENAI_API_KEY=sk-...
export AZURE_AI_FOUNDRY_URL=https://workspace.ai.azure.com
export FOUNDRY_FABRIC_ORDER_STATUS_RESOURCE_ID=<resource-id>
```

**For MCP Direct SQL Mode:**
```bash
export AGENT_BACKEND=mcp_direct_sql
export AZURE_OPENAI_ENDPOINT=https://resource.openai.azure.com/
export AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4
export FABRIC_SQL_SERVER=workspace.datawarehouse.fabric.microsoft.com
export FABRIC_SQL_DATABASE=YourDatabase
export AZURE_STORAGE_ACCOUNT=storageaccount
export AZURE_STORAGE_CONTAINER=order-status-exports
```

### Step 5: Deploy & Test

**Fabric Agent Mode:**
```bash
# Create agent (one-time)
python -c "from order_status_agent import OrderStatusAgent; OrderStatusAgent()"

# Test queries
python -c "
import asyncio
from order_status_agent import OrderStatusAgent

async def test():
    agent = OrderStatusAgent()
    result = await agent.process_query('Show me PO-2025-001 status')
    print(result)

asyncio.run(test())
"
```

**MCP Direct SQL Mode:**
```bash
# Start MCP server
python foundry_mcp/app/mcp_server.py

# Or containerized
docker build -f deployment/Dockerfile -t order-status-agent .
docker run -e AGENT_BACKEND=mcp_direct_sql \
  -e AZURE_OPENAI_ENDPOINT=... \
  -e FABRIC_SQL_SERVER=... \
  order-status-agent
```

---

## System Prompts

### Fabric Agent Mode Prompt

**File:** `config/prompts/order_status_fabric_agent_prompt.txt`

**Purpose:** Guide the natural language agent in Fabric Data Agent

**Key Content:**
- Table names and meanings
- Column definitions
- Status value explanations
- Example queries in natural language
- Business rules and logic
- Response formatting guidelines

**Example Structure:**
```
You are an Order Status Agent specializing in supply chain order tracking.

YOUR RESPONSIBILITIES:
- Track purchase order delivery status
- Monitor sales order fulfillment progress
- Identify delayed or at-risk orders
- Provide insights into supplier/customer performance
- Alert on status exceptions

DATA SOURCES (Fabric SQL Endpoint):
1. PurchaseOrders - All purchase orders with delivery tracking
2. SalesOrders - All sales orders with delivery tracking
3. OrderLineItems - Line-by-line detail for orders
4. OrderStatus - Audit trail of status changes

BUSINESS RULES:
- Overdue PO: Status != "Delivered" AND Delivery_Date < TODAY
- At-Risk SO: Status = "Pending" AND Expected_Delivery < 3 days
- Delayed Update: Status_Date > 5 days ago

COMMON QUERIES:
- "What purchase orders are delayed?"
- "Show me status of all orders for Supplier X"
- "Which sales orders will be delivered this week?"
- "Export all active orders with line items"

RESPONSE FORMAT:
- Start with direct answer to question
- Include relevant order IDs and status values
- Show dates in MM/DD/YYYY format
- Highlight any issues or concerns
- Provide next recommended action
```

---

### MCP Direct SQL Mode Prompts

#### Full Mode (`system_prompt_full.txt`)

**Purpose:** Guide the SQL-capable agent with both inline and export tools

**Key Content:**
- Complete SQL schema documentation
- Tool usage guidelines (when to use fabric_data vs sql_to_csv)
- T-SQL query examples
- Row limit explanations
- CSV export descriptions

**Example Section:**
```
TOOLS AVAILABLE:

1. fabric_data - Quick inline results
   - Returns up to 100 rows (default)
   - Formatted as ASCII table
   - Response time: <1 second typical
   - Best for: Single order lookup, small summaries

2. sql_to_csv - CSV export to Azure Blob Storage
   - Returns any size result set as CSV
   - Response time: 5-30 seconds (depends on data)
   - Best for: Large exports, all active orders, reports

EXAMPLES:

Get single PO status:
SELECT TOP 1 PO_ID, Supplier_ID, Status, Expected_Delivery, Actual_Delivery
FROM dbo.PurchaseOrders
WHERE PO_ID = 'PO-2025-001'

Get all overdue orders:
SELECT PO_ID, Supplier_ID, Status, Expected_Delivery
FROM dbo.PurchaseOrders
WHERE Status != 'Delivered' AND Expected_Delivery < GETDATE()
ORDER BY Expected_Delivery ASC

Get order history:
SELECT Order_ID, Previous_Status, New_Status, Status_Date, Status_Reason
FROM dbo.OrderStatus
WHERE Order_ID = 'PO-2025-001'
ORDER BY Status_Date DESC
```

#### CSV-Only Mode (`system_prompt_csv_only.txt`)

**Purpose:** Guide the agent to always generate SQL and export

**Key Content:**
- SQL schema documentation
- SQL query generation guidelines
- All results go to CSV
- Download link patterns

**Example Section:**
```
WORKFLOW:
1. User requests order information
2. You generate appropriate T-SQL query
3. Send query to sql_to_csv tool
4. Tool returns CSV download link
5. Provide link to user

EVERY RESPONSE INCLUDES A DOWNLOADABLE CSV FILE.

QUERY TEMPLATES:

List all active POs:
SELECT * FROM dbo.PurchaseOrders 
WHERE Status IN ('Pending', 'In Transit')
ORDER BY PO_Date DESC

Export specific date range:
SELECT * FROM dbo.SalesOrders
WHERE SO_Date >= '2025-01-01' AND SO_Date < '2025-02-01'
ORDER BY SO_Date DESC

Supplier performance report:
SELECT s.Supplier_Name, COUNT(p.PO_ID) as PO_Count, 
  AVG(DATEDIFF(day, p.PO_Date, p.Actual_Delivery)) as AvgDays
FROM dbo.PurchaseOrders p
JOIN dbo.Suppliers s ON p.Supplier_ID = s.Supplier_ID
GROUP BY s.Supplier_Name
ORDER BY AvgDays DESC
```

---

## Monitoring & Operations

### Fabric Agent Mode

**Logging:**
- Agent Framework logs in Azure Monitor
- Query execution logs in Foundry
- Application Insights integration

---

### MCP Direct SQL Mode

**Monitoring Points:**
- SQL connection pool health
- Query execution time by complexity
- CSV export sizes and upload latency
- Tool selection patterns (fabric_data vs sql_to_csv)

**Logging:**
- Middleware logs in structlog
- SQL query execution logs
- Blob storage upload logs
- Performance timing data

---

## Troubleshooting

### Fabric Agent Mode

**Agent Creation Fails:**
- Verify Azure AI Foundry permissions
- Check Fabric resource ID is correct
- Ensure Fabric SQL Endpoint is accessible

**Queries Return No Results:**
- Verify table names match exactly in Fabric
- Check data exists in Fabric tables
- Validate Fabric Data Agent has table access permissions

**Slow Response Times:**
- Check Fabric SQL query performance
- Monitor Fabric Data Agent API latency
- Review agent model latency

---

### MCP Direct SQL Mode

**Connection Fails:**
- Verify ODBC Driver 18 is installed
- Check FABRIC_SQL_SERVER format is correct
- Verify managed identity has SQL access
- Test connection with sqlcmd

**Wrong Results:**
- Verify table/column names in query match schema exactly
- Check data exists in Fabric SQL
- Review system prompt for correct schema documentation

**CSV Export Fails:**
- Verify Azure Storage Account access permissions
- Check storage container exists
- Ensure managed identity has Blob Contributor role
- Verify SAS token generation settings

---

## Summary

The **Order Status Agent** runs in **Azure AI Foundry** with two operational modes that determine which query tool is assigned:

- **Fabric Agent Mode** - Uses Fabric Data Agent Tool for queries (natural language interface) + sql_to_csv for exports
- **MCP Direct SQL Mode** - Uses fabric_data Tool (direct SQL) + sql_to_csv for exports

Both modes:
- ✅ Run in Azure AI Foundry
- ✅ Use sql_to_csv (MCP) for large exports
- ✅ Share the same underlying Fabric SQL data model

**Key Implementation Requirements:**
1. Create and host Foundry Agent (scm_order_status_agent)
2. Assign tools based on AGENT_BACKEND mode:
   - fabric_agent: [Fabric Data Agent Tool, sql_to_csv Tool]
   - mcp_direct_sql: [fabric_data Tool, sql_to_csv Tool]
3. Configure D365 F&O data access (Dataverse or OData)
4. Verify PurchTable, PurchLine, and VendTable are accessible
5. Confirm all required columns exist and map correctly
6. Document D365 F&O schema in appropriate system prompts
7. Set environment variable AGENT_BACKEND for chosen mode
8. Deploy MCP Orchestrator instance (required for sql_to_csv and fabric_data tools)
9. Test with sample purchase orders before production use

**Documentation Maintenance:**
- Keep D365 F&O column mappings synchronized in system prompts
- Document any custom fields or column variations
- Update status value mappings if D365 F&O version changes
- Test all example queries quarterly