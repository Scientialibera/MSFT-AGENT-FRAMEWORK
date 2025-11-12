# Agent Modes: Full vs CSV-Only

The agent supports two operational modes, selectable via the `AGENT_MODE` environment variable.

## Mode 1: Full Mode (DEFAULT)

**Configuration:**
```bash
AGENT_MODE=full
```

**System Prompt:** `config/orchestrator/system_prompt_full.txt`

**Available Tools:**
1. **fabric_data** - Inline query results
   - Returns up to 100 rows (configurable via `MAX_ROWS_INLINE`)
   - Formatted as ASCII table
   - Best for quick lookups and exploratory queries
   
2. **sql_to_csv** - CSV export
   - Executes SQL, exports to CSV, uploads to blob storage
   - Returns download URL (SAS token)
   - Best for large result sets

**Agent Behavior:**
- Analyzes user request
- Decides which tool to use based on expected result size
- Can chain multiple tool calls for complex queries
- Returns formatted results or download links
- Shows SQL queries executed (for transparency)

**Example Interactions:**

```
User: "What are the top 5 accounts by balance?"
Agent: Uses fabric_data → Returns formatted table

User: "Export all accounts to CSV"
Agent: Uses sql_to_csv → Returns download URL

User: "What categories exist? Then show top 5 items from the first category"
Agent: 
  1. Uses fabric_data → SELECT DISTINCT Category... (gets list)
  2. Uses fabric_data → SELECT TOP 5... (gets items)
  3. Returns synthesized response
```

**When to Use Full Mode:**
- ✅ Interactive data exploration
- ✅ Quick analyses with small result sets
- ✅ Multi-step queries requiring intermediate results
- ✅ Users want both inline viewing AND CSV export capability
- ✅ Maximum flexibility and control

---

## Mode 2: CSV-Only Mode

**Configuration:**
```bash
AGENT_MODE=csv_only
```

**System Prompt:** `config/orchestrator/system_prompt_csv_only.txt`

**Available Tools:**
1. **sql_to_csv** - CSV export ONLY
   - Every query generates CSV export
   - Every result becomes a download URL
   - No inline results

**Agent Behavior:**
- Analyzes user request
- Generates appropriate SQL query
- Sends to sql_to_csv tool
- Returns download URL
- All results are exported to CSV files

**Example Interactions:**

```
User: "What are the top 5 accounts by balance?"
Agent: Generates SQL → sql_to_csv → Returns CSV download URL

User: "Export all accounts"
Agent: Generates SQL → sql_to_csv → Returns CSV download URL

User: "How many duplicate account names exist?"
Agent: Generates SQL → sql_to_csv → Returns CSV download URL with analysis
```

**When to Use CSV-Only Mode:**
- ✅ All users expect CSV file downloads (default behavior)
- ✅ Consistent export format for every query
- ✅ Batch processing of data exports
- ✅ Simplified agent behavior (one tool only)
- ✅ Azure Data Lake / ETL workflows where everything is files
- ✅ Users explicitly want downloadable data for external processing

---

## Comparison Table

| Aspect | Full Mode | CSV-Only Mode |
|--------|-----------|---------------|
| Tools Available | 2 (fabric_data + sql_to_csv) | 1 (sql_to_csv only) |
| Inline Results | ✅ Yes (≤100 rows) | ❌ No |
| CSV Export | ✅ Yes | ✅ Yes (always) |
| Complexity | Higher (decision logic) | Lower (always export) |
| Use Cases | Exploration + Export | Export-first workflows |
| Prompt File | system_prompt_full.txt | system_prompt_csv_only.txt |
| Response Style | Varied (table/text/url) | Consistent (always url) |

---

## Configuration Examples

### Full Mode (Default)
```bash
# .env file
AGENT_MODE=full
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_CHAT_DEPLOYMENT=...
FABRIC_SQL_SERVER=...
FABRIC_SQL_DATABASE=...
AZURE_STORAGE_ACCOUNT=...
```

### CSV-Only Mode
```bash
# .env file
AGENT_MODE=csv_only
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_CHAT_DEPLOYMENT=...
FABRIC_SQL_SERVER=...
FABRIC_SQL_DATABASE=...
AZURE_STORAGE_ACCOUNT=...
```

---

## Switching Modes at Runtime

The mode is read once when the AIAssistant initializes:

```python
from src.orchestrator.main import AIAssistant

# Load .env with desired mode
import os
os.getenv("AGENT_MODE", "full")  # Default is "full"

# Create assistant (will use current AGENT_MODE)
assistant = AIAssistant()
```

To switch modes, change the `AGENT_MODE` environment variable and restart the application.

---

## System Prompt Differences

### Full Mode Prompt Focus
- Explains both tools and when to use each
- Decision logic for tool selection
- Multi-step reasoning examples
- Row limits and CSV export suggestions
- Interactive exploration patterns

### CSV-Only Mode Prompt Focus
- SQL query generation instructions
- Every request → SQL generation → CSV export workflow
- SQL best practices and guidelines
- Query generation examples
- Clear response format with download URLs

---

## FAQ

**Q: Which mode should I use by default?**
A: Use `full` mode (default). It provides maximum flexibility while CSV-only mode is a specialized variant.

**Q: Can I switch modes dynamically?**
A: You need to restart the application to switch modes. The mode is loaded once during AIAssistant initialization.

**Q: What if I only want CSV exports?**
A: Use `AGENT_MODE=csv_only`. This simplifies the agent behavior to always export.

**Q: Can I modify the prompts?**
A: Yes! Edit `config/orchestrator/system_prompt_full.txt` or `config/orchestrator/system_prompt_csv_only.txt` to customize agent behavior for each mode.

**Q: What happens if AGENT_MODE is not set?**
A: Defaults to `full` mode (see line 63 in `src/orchestrator/main.py`).

**Q: Can I add a third mode?**
A: Yes! Create a new prompt file (e.g., `system_prompt_custom.txt`) and add a condition in `main.py` to load it based on a new AGENT_MODE value.
