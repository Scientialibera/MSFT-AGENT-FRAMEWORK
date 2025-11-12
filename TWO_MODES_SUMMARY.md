# Two-Mode System Implementation Summary

## What Was Added

### 1. System Prompt Files (New)
- **`config/orchestrator/system_prompt_full.txt`** - Full mode with both tools
- **`config/orchestrator/system_prompt_csv_only.txt`** - CSV-only mode with just sql_to_csv

### 2. Mode Selector (Updated)
- **`src/orchestrator/main.py`** (lines 63-68)
  - Reads `AGENT_MODE` environment variable
  - Defaults to `"full"`
  - Loads appropriate system prompt
  - Logs which mode and prompt file is being used

### 3. Environment Variable (Updated)
- **`.env.example`** - Added `AGENT_MODE` configuration option
  ```bash
  AGENT_MODE=full  # or "csv_only"
  ```

### 4. Documentation (New)
- **`AGENT_MODES.md`** - Complete guide to both modes with examples and FAQ

## How It Works

**At Application Startup:**
```python
# Read env var (default: "full")
AGENT_MODE = os.getenv("AGENT_MODE", "full").lower()

# Select prompt file based on mode
if AGENT_MODE == "csv_only":
    SYSTEM_PROMPT_FILE = "config/orchestrator/system_prompt_csv_only.txt"
else:
    SYSTEM_PROMPT_FILE = "config/orchestrator/system_prompt_full.txt"

# Load and use that prompt
system_prompt = _load_system_prompt()
```

## Mode Behavior

### Full Mode (Default: `AGENT_MODE=full`)
```
User Request
    ↓
Agent analyzes intent
    ↓
Agent chooses: fabric_data (small results) OR sql_to_csv (large results)
    ↓
Tool executes
    ↓
Agent returns: formatted table OR download URL
```

**Tools Available:** fabric_data + sql_to_csv

### CSV-Only Mode (`AGENT_MODE=csv_only`)
```
User Request
    ↓
Agent generates SQL query
    ↓
Agent sends to sql_to_csv tool
    ↓
Tool: Execute SQL → Generate CSV → Upload to blob → Return SAS URL
    ↓
Agent returns: download URL (always)
```

**Tools Available:** sql_to_csv only

## Usage Examples

### Start in Full Mode (Default)
```bash
# .env file
AGENT_MODE=full

# Application starts with both tools available
```

### Start in CSV-Only Mode
```bash
# .env file
AGENT_MODE=csv_only

# Application starts with only sql_to_csv tool
```

### Switch Modes
```bash
# Edit .env
AGENT_MODE=csv_only

# Restart application
python tests/mcp_server.py
```

## Files Modified
- ✅ `src/orchestrator/main.py` - Mode selector logic
- ✅ `.env.example` - Added AGENT_MODE variable
- ✅ `deployment/Dockerfile` - Added ODBC driver (separate update)
- ✅ `IMPLEMENTATION_SUMMARY.md` - Updated documentation

## Files Created
- ✅ `config/orchestrator/system_prompt_full.txt` - Full mode prompt
- ✅ `config/orchestrator/system_prompt_csv_only.txt` - CSV-only mode prompt
- ✅ `AGENT_MODES.md` - Complete mode documentation

## Testing the Modes

### Test Full Mode
```bash
# .env
AGENT_MODE=full

# User: "What are top 5 accounts?"
# Expected: Uses fabric_data → Returns table

# User: "Export all accounts"
# Expected: Uses sql_to_csv → Returns URL
```

### Test CSV-Only Mode
```bash
# .env
AGENT_MODE=csv_only

# User: "What are top 5 accounts?"
# Expected: Generates SQL → Uses sql_to_csv → Returns URL

# User: "Export all accounts"
# Expected: Generates SQL → Uses sql_to_csv → Returns URL
```

## Key Design Decisions

1. **Default is Full Mode** - Maximum flexibility and features
2. **CSV-Only is Opt-In** - Users explicitly choose it
3. **Mode Selection at Startup** - No runtime switching (cleaner architecture)
4. **Separate Prompt Files** - Each mode has optimized instructions
5. **Environment Variable Driven** - Easy to configure per deployment
6. **Backward Compatible** - Existing code still works with full mode

## Next Steps

1. Create `.env` file from `.env.example`
2. Set `AGENT_MODE=full` (default)
3. Fill in other required environment variables
4. Test both modes:
   ```bash
   AGENT_MODE=full python tests/test_agentic_queries.py
   AGENT_MODE=csv_only python tests/test_agentic_queries.py
   ```

## Prompt File Locations

```
config/orchestrator/
├── system_prompt_full.txt          (full mode - both tools)
├── system_prompt_csv_only.txt      (csv-only mode - export only)
└── middleware.py                   (interceptor logic)
```

---
**Implementation Complete!** ✅

Both modes are ready to use. Set `AGENT_MODE` in `.env` to switch between full functionality and CSV-only export workflows.
