```mermaid
graph TD
    %% Global Styling
    classDef orchestrator fill:#f9d5e5,stroke:#333,stroke-width:2px;
    classDef agent fill:#e0f7fa,stroke:#00acc1,stroke-width:2px;
    classDef service fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef ai fill:#e1bee7,stroke:#8e24aa,stroke-width:2px;
    classDef ui fill:#c8e6c9,stroke:#43a047,stroke-width:2px,stroke-dasharray: 5 5;

    subgraph Frontend [Running in Main Thread]
        UI[AutoReturnApp (PySide6)]:::ui
        QQueue[QueueSummaryGenerator (QThread)]:::ui
    end

    subgraph Backend [Orchestrator Layer]
        Orchestrator[Orchestrator]:::orchestrator
        Worker[AgentWorker (QThread)]:::orchestrator
    end

    subgraph Agents [Intelligent Agent Layer]
        GmailAgent[GmailAgent (Async)]:::agent
        SlackAgent[SlackAgent (Async)]:::agent
        
        subgraph GmailLogic [Gmail Processing]
            GFetch[Fetch Raw Emails]
            GPriority[Lightweight Priority Analysis]
        end
        
        subgraph SlackLogic [Slack Processing]
            SFetch[Fetch Raw Messages]
            SPriority[Lightweight Priority Analysis]
        end
    end

    subgraph Services [Service Layer]
        GmailService[GmailIntegrationService]:::service
        SlackService[SlackBackendService]:::service
        OllamaService[OllamaService (API)]:::ai
        LocalLLM[Local LLM (kimi-k2.5)]:::ai
    end

    %% Flow: User Request
    UI -- "Sync Request" --> Orchestrator
    Orchestrator -- "Routes Request" --> Worker
    Worker -- "Executes Async Task" --> GmailAgent & SlackAgent

    %% Flow: Gmail Execution
    GmailAgent -- "Calls" --> GmailService
    GmailService -- "Fetching..." --> GoogleAPI((Google API))
    GmailAgent -- "Analyze Priority" --> GPriority
    GPriority -- "Returns with Score" --> Worker

    %% Flow: Slack Execution
    SlackAgent -- "Calls" --> SlackService
    SlackService -- "Fetching..." --> SlackAPI((Slack API))
    SlackAgent -- "Analyze Priority" --> SPriority
    SPriority -- "Returns with Score" --> Worker

    %% Flow: Immediate Return
    Worker -- "Returns Raw Messages (Fast)" --> UI
    
    %% Flow: Background Intelligence (Progressive Loading)
    UI -- "Queues New Messages" --> QQueue
    QQueue -- "Generates Summary" --> OllamaService
    OllamaService -- "HTTP Request" --> LocalLLM
    LocalLLM -- "Returns Summary + Task" --> OllamaService
    OllamaService -- "Updates UI Row" --> UI

    %% Detailed Notes
    note1[The Orchestrator manages Agent lifecycle<br/>and routing, decoupling UI from Logic]
    note2[Agents perform FAST initial processing<br/>(Priority & Task Extraction) to ensure<br/>instant UI feedback]
    note3[Heavy AI Summarization is handled<br/>background via QueueSummaryGenerator<br/>to prevent UI freezing]

    %% Connections for Notes
    Orchestrator -.- note1
    GmailAgent -.- note2
    QQueue -.- note3
```
