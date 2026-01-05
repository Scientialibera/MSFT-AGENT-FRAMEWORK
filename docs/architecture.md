# MSFT Agent Framework Architecture

This document provides detailed architectural diagrams for the Microsoft Agent Framework template.

## High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface"
        U[User Query]
    end
    
    subgraph "AIAssistant"
        O[Orchestrator<br/>main.py]
        C[Config Loader<br/>config.py]
        M[Middleware<br/>middleware.py]
        H[History Manager<br/>manager.py]
    end
    
    subgraph "Tool Sources"
        L[Local Tools<br/>loader.py]
        MCP[MCP Manager<br/>mcp_loader.py]
        W[Workflow Manager<br/>workflow_loader.py]
    end
    
    subgraph "Memory Layer"
        RC[Redis Cache<br/>cache.py]
        AP[ADLS Persistence<br/>persistence.py]
    end
    
    subgraph "Local Tools"
        T1[Tool 1<br/>JSON + Service]
        T2[Tool 2<br/>JSON + Service]
        TN[Tool N<br/>JSON + Service]
    end
    
    subgraph "MCP Servers"
        MS1[stdio<br/>Calculator, SQLite...]
        MS2[HTTP<br/>REST APIs]
        MS3[WebSocket<br/>Real-time]
    end
    
    subgraph "Workflows"
        WS[Sequential<br/>Agent Pipeline]
        WC[Custom<br/>Agent Graph]
    end
    
    subgraph "Azure OpenAI"
        AO[ChatAgent<br/>gpt-4o]
    end
    
    U --> O
    O --> C
    O --> M
    O --> H
    O --> L
    O --> MCP
    H --> RC
    H --> AP
    O --> W
    L --> T1
    L --> T2
    L --> TN
    MCP --> MS1
    MCP --> MS2
    MCP --> MS3
    W --> WS
    W --> WC
    O --> AO
    AO --> O
    O --> U
```

## Request Flow

```mermaid
sequenceDiagram
    participant User
    participant AIAssistant
    participant ConfigLoader
    participant ToolLoader
    participant MCPManager
    participant WorkflowManager
    participant AzureOpenAI
    participant Tools

    User->>AIAssistant: process_question("...")
    
    Note over AIAssistant: Initialization (first call)
    AIAssistant->>ConfigLoader: load_config()
    ConfigLoader-->>AIAssistant: AgentConfig
    
    AIAssistant->>ToolLoader: load_and_register_tools()
    ToolLoader-->>AIAssistant: Local tools
    
    AIAssistant->>MCPManager: load_mcp_servers()
    MCPManager-->>AIAssistant: MCP tools
    
    AIAssistant->>WorkflowManager: load_workflows()
    WorkflowManager-->>AIAssistant: Workflow agents
    
    Note over AIAssistant: Processing
    AIAssistant->>AzureOpenAI: agent.run(question)
    
    loop Agentic Loop
        AzureOpenAI->>AzureOpenAI: Reason about question
        AzureOpenAI->>Tools: Call tool if needed
        Tools-->>AzureOpenAI: Tool result
    end
    
    AzureOpenAI-->>AIAssistant: Final response
    AIAssistant-->>User: Result dict
```

## Tool Loading Architecture

```mermaid
graph LR
    subgraph "Configuration"
        JSON[config/tools/*.json<br/>Tool definitions]
        TOML[config/agent.toml<br/>Tool settings]
    end
    
    subgraph "Discovery"
        SCAN[Scan config/tools/]
        MATCH[Match naming convention]
    end
    
    subgraph "Service Loading"
        IMPORT[Import src/&lt;name&gt;/service.py]
        CLASS[Find &lt;Name&gt;Service class]
        FACTORY[Or get_&lt;name&gt;_service factory]
    end
    
    subgraph "Registration"
        FUNC[Create tool function]
        BIND[Bind to AIAssistant]
    end
    
    JSON --> SCAN
    SCAN --> MATCH
    MATCH --> IMPORT
    TOML --> IMPORT
    IMPORT --> CLASS
    IMPORT --> FACTORY
    CLASS --> FUNC
    FACTORY --> FUNC
    FUNC --> BIND
```

## MCP Integration

```mermaid
graph TB
    subgraph "Configuration"
        TOML["[[agent.mcp]] in agent.toml"]
    end
    
    subgraph "MCPManager"
        PARSE[Parse MCP configs]
        CREATE[Create MCP tools]
    end
    
    subgraph "Transport Types"
        STDIO[MCPStdioTool<br/>Local subprocess]
        HTTP[MCPStreamableHTTPTool<br/>REST + SSE]
        WS[MCPWebsocketTool<br/>WebSocket]
    end
    
    subgraph "External Servers"
        CALC[mcp-server-calculator]
        FS[mcp-server-filesystem]
        CUSTOM[Custom MCP servers]
    end
    
    TOML --> PARSE
    PARSE --> CREATE
    CREATE --> STDIO
    CREATE --> HTTP
    CREATE --> WS
    STDIO --> CALC
    STDIO --> FS
    HTTP --> CUSTOM
    WS --> CUSTOM
```

## Workflow Architecture

```mermaid
graph TB
    subgraph "Configuration"
        WF_TOML["[[agent.workflows]] in agent.toml"]
    end
    
    subgraph "WorkflowManager"
        PARSE_WF[Parse workflow configs]
        BUILD[Build workflow graph]
    end
    
    subgraph "Workflow Types"
        SEQ[SequentialBuilder<br/>Linear pipeline]
        CUSTOM[WorkflowBuilder<br/>Custom graph]
    end
    
    subgraph "Agents"
        A1[Agent 1<br/>Researcher]
        A2[Agent 2<br/>Writer]
        A3[Agent 3<br/>Reviewer]
    end
    
    subgraph "Execution"
        THREAD[Create thread]
        RUN[Run workflow]
        STREAM[Stream updates]
    end
    
    WF_TOML --> PARSE_WF
    PARSE_WF --> BUILD
    BUILD --> SEQ
    BUILD --> CUSTOM
    SEQ --> A1
    A1 --> A2
    A2 --> A3
    CUSTOM --> A1
    A1 -.-> A2
    A1 -.-> A3
    
    SEQ --> THREAD
    CUSTOM --> THREAD
    THREAD --> RUN
    RUN --> STREAM
```

## Sequential Workflow Example

```mermaid
graph LR
    INPUT[User Input] --> R[Researcher<br/>Gather facts]
    R --> W[Writer<br/>Create content]
    W --> REV[Reviewer<br/>Polish output]
    REV --> OUTPUT[Final Response]
    
    style R fill:#e1f5fe
    style W fill:#fff3e0
    style REV fill:#e8f5e9
```

## Custom Workflow Example (Support Triage)

```mermaid
graph TB
    INPUT[Customer Issue] --> T[Triage Agent<br/>Analyze severity]
    T -->|Technical| TECH[Tech Support<br/>Solve issue]
    T -->|Billing| BILL[Billing Support<br/>Handle payment]
    TECH -->|Escalate| ESC[Escalation<br/>Senior review]
    BILL -->|Escalate| ESC
    ESC --> OUTPUT[Resolution]
    TECH --> OUTPUT
    BILL --> OUTPUT
    
    style T fill:#ffebee
    style TECH fill:#e3f2fd
    style BILL fill:#fff8e1
    style ESC fill:#fce4ec
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **AIAssistant** | `main.py` | Main orchestrator, question processing, lifecycle management |
| **AgentConfig** | `config.py` | TOML loading, validation, environment overrides |
| **ToolLoader** | `loader.py` | Dynamic tool discovery, service instantiation |
| **MCPManager** | `mcp_loader.py` | MCP server connections (stdio/http/ws) |
| **WorkflowManager** | `workflow_loader.py` | Multi-agent workflow creation and execution |
| **ChatHistoryManager** | `memory/manager.py` | Session management, cache + persistence orchestration |
| **RedisCache** | `memory/cache.py` | Azure Cache for Redis with AAD auth |
| **ADLSPersistence** | `memory/persistence.py` | ADLS Gen2 for long-term chat storage |
| **Middleware** | `middleware.py` | Request/response interception, logging |

## Chat History & Session Management

The framework supports multi-turn conversations with session persistence.

```mermaid
flowchart TB
    subgraph "Request"
        Q[Question + chat_id?]
    end
    
    subgraph "ChatHistoryManager"
        CHK{chat_id provided?}
        CACHE[Check Redis Cache]
        ADLS[Check ADLS]
        NEW[Create New Thread]
        RESTORE[Restore Thread]
    end
    
    subgraph "Storage"
        RC[(Redis Cache)]
        AP[(ADLS Gen2)]
    end
    
    Q --> CHK
    CHK -->|No| NEW
    CHK -->|Yes| CACHE
    CACHE -->|Hit| RESTORE
    CACHE -->|Miss| ADLS
    ADLS -->|Found| RESTORE
    ADLS -->|Not Found| NEW
    
    RESTORE --> RC
    NEW --> RC
    RC -.->|TTL expiring| AP
```

### Session Flow Edge Cases

| chat_id | Cache | ADLS | Action |
|---------|-------|------|--------|
| None | - | - | Generate new UUID, create thread |
| Provided | Hit | - | Restore from cache |
| Provided | Miss | Found | Load from ADLS → cache |
| Provided | Miss | Not Found | Create new with provided ID |

### Merge Logic

When persisting to ADLS, the manager:
1. Loads existing ADLS data (if any)
2. Merges with cache data (new messages win)
3. Preserves original `_created_at` timestamp
4. Increments `_merge_count` for auditing

## Data Flow Summary

1. **User Query** → AIAssistant receives question + optional `chat_id`
2. **Session Lookup** → ChatHistoryManager checks cache → ADLS → creates new
3. **Configuration** → Load TOML, environment vars
4. **Tool Loading** → Discover and instantiate all tools
5. **MCP Loading** → Connect to external MCP servers
6. **Workflow Loading** → Build multi-agent pipelines
7. **Agent Creation** → Initialize ChatAgent with tools
8. **Processing** → LLM reasons and calls tools as needed
9. **Session Save** → Update cache, persist to ADLS before TTL
10. **Response** → Final answer + `chat_id` returned to user

