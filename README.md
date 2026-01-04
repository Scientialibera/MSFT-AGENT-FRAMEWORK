# MSFT Agent Framework

A general-purpose, extensible AI agent template using the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview) with dynamic tool loading.

Build intelligent AI assistants that can reason, chain tool calls, and solve complex multi-step problems.

## Features

- **Dynamic Tool Loading** — Drop JSON configs in `config/tools/` and matching services in `src/` for auto-discovery
- **TOML Configuration** — Professional configuration via `config/agent.toml` or `pyproject.toml`
- **Azure OpenAI Integration** — Built-in support for Azure OpenAI with DefaultAzureCredential
- **Agentic Reasoning** — Multi-step reasoning with automatic tool chaining
- **Middleware Support** — Extensible middleware for logging, security, and transformations
- **Clean Architecture** — Separation of concerns with modular services

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/your-org/MSFT-AGENT-FRAMEWORK.git
cd MSFT-AGENT-FRAMEWORK
pip install -e .
```

### 2. Configure Azure OpenAI

Edit `config/agent.toml`:

```toml
[agent.azure_openai]
endpoint = "https://your-resource.openai.azure.com/"
deployment = "gpt-4o"
```

Or set environment variables:

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
```

### 3. Run the Agent

```python
import asyncio
from src.orchestrator.main import AIAssistant

async def main():
    assistant = AIAssistant()
    result = await assistant.process_question("Hello! What can you help me with?")
    print(result["response"])

asyncio.run(main())
```

## Project Structure

```
MSFT-AGENT-FRAMEWORK/
├── config/
│   ├── agent.toml              # Main configuration file
│   ├── system_prompt.txt       # Agent's system prompt
│   └── tools/                  # Tool JSON definitions
│       └── example_tool.json
├── src/
│   ├── orchestrator/           # Core agent framework
│   │   ├── main.py            # AIAssistant class
│   │   ├── config.py          # TOML config loader
│   │   ├── loader.py          # Dynamic tool loader
│   │   └── middleware.py      # Request/response middleware
│   └── example_tool/           # Example tool implementation
│       ├── __init__.py
│       └── service.py
├── tests/
│   └── test_agent.py
├── deployment/
│   └── Dockerfile
└── pyproject.toml
```

## Adding New Tools

Adding a new tool requires just 2-3 simple steps:

### Step 1: Create Tool Config

Create `config/tools/<tool_name>.json`:

```json
{
  "type": "function",
  "function": {
    "name": "weather",
    "description": "Get current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City name or coordinates"
        }
      },
      "required": ["location"]
    }
  }
}
```

### Step 2: Create Service

Create `src/<tool_name>/service.py`:

```python
from typing import Any, Dict

class WeatherService:
    """Service for weather lookups."""
    
    def __init__(self):
        # Initialize API clients, connections, etc.
        pass
    
    def run(self, tool_call: Dict[str, Any]) -> str:
        """
        Execute the tool logic.
        
        Args:
            tool_call: Parameters from the LLM matching your JSON config
        
        Returns:
            str: Result to return to the LLM
        """
        location = tool_call.get("location", "")
        
        # Your logic here
        weather_data = self._fetch_weather(location)
        
        return f"Weather in {location}: {weather_data}"
    
    def _fetch_weather(self, location: str) -> str:
        # Call your weather API
        return "Sunny, 72°F"
```

### Step 3 (Optional): Add Tool Config

Add tool-specific settings in `config/agent.toml`:

```toml
[agent.tools.weather]
api_key = "your-api-key"
units = "fahrenheit"
```

Access in your service:

```python
from src.orchestrator.config import get_config

config = get_config()
tool_config = config.get_tool_config("weather")
api_key = tool_config.get("api_key")
```

## Naming Convention

The framework uses a strict naming convention for auto-discovery:

| Config File | Service File | Service Class |
|-------------|--------------|---------------|
| `config/tools/weather.json` | `src/weather/service.py` | `WeatherService` |
| `config/tools/database.json` | `src/database/service.py` | `DatabaseService` |
| `config/tools/my_api.json` | `src/my_api/service.py` | `MyApiService` |

## Configuration

### TOML Configuration (`config/agent.toml`)

```toml
[agent]
system_prompt = "config/system_prompt.txt"
log_level = "INFO"

[agent.azure_openai]
endpoint = "https://your-resource.openai.azure.com/"
deployment = "gpt-4o"
api_version = "2024-10-01-preview"

[agent.tools]
config_dir = "config/tools"

[agent.tools.my_tool]
api_key = "secret"
timeout = 30
```

### Environment Variable Overrides

Environment variables take precedence over TOML:

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | API version (optional) |

## System Prompt

Customize `config/system_prompt.txt` to define your agent's behavior:

```text
You are an intelligent AI assistant that helps users with...

YOUR CAPABILITIES:
- Use tools to gather information
- Chain multiple tool calls for complex questions
- Provide clear, structured responses

AVAILABLE TOOLS:
...
```

## Middleware

Add custom middleware in `src/orchestrator/middleware.py`:

```python
async def my_middleware(context, next):
    # Before tool execution
    print(f"Calling: {context.function.name}")
    
    await next(context)
    
    # After tool execution
    print(f"Result: {context.result}")
```

Register in `main.py`:

```python
self.agent = ChatAgent(
    chat_client=self.chat_client,
    instructions=self.system_prompt,
    tools=self.tools,
    middleware=[function_call_middleware, my_middleware],
)
```

## Docker Deployment

```bash
cd deployment
docker build -t msft-agent .
docker run -e AZURE_OPENAI_ENDPOINT=... -e AZURE_OPENAI_DEPLOYMENT=... msft-agent
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Requirements

- Python 3.10+
- Azure OpenAI resource with deployed model
- Azure identity configured (DefaultAzureCredential)

## License

MIT
