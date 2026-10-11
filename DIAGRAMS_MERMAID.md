# Mermaid Diagrams for Presentation

Copy these diagrams into your slides or use a Mermaid renderer (mermaid.live, VS Code extension, etc.)

---

## 1. System Architecture Diagram

```mermaid
flowchart TB
    subgraph Frontend["Frontend (Port 4000)"]
        UI[React + TypeScript]
        Charts[Recharts/ECharts]
        WS[WebSocket Client]
    end

    subgraph Backend["Backend (Port 6000)"]
        API[FastAPI Server]
        Routes["/api/simulations<br>/api/analytical<br>/api/distributed"]
        Service[Simulation Service]
    end

    subgraph SimEngine["Simulation Engine"]
        SimPy[SimPy DES]
        MMN[M/M/N Queue]
        MGN[M/G/N Queue]
        Tandem[Tandem Queue]
    end

    subgraph Protocols["Distributed Protocols"]
        Raft[Raft Consensus]
        VC[Vector Clocks]
        TPC[Two-Phase Commit]
    end

    subgraph Analysis["Analysis Layer"]
        Analytical[15 Equations]
        EVT[Extreme Value Theory]
        Stats[NumPy/SciPy/Pandas]
    end

    UI --> API
    WS -.->|Real-time| API
    API --> Routes
    Routes --> Service
    Service --> SimPy
    SimPy --> MMN
    SimPy --> MGN
    SimPy --> Tandem
    Service --> Protocols
    Service --> Analysis
    Analysis --> Stats
```

---

## 2. Tandem Queue Network Diagram

```mermaid
flowchart LR
    subgraph Publishers
        P1[Publisher 1]
        P2[Publisher 2]
        P3[Publisher N]
    end

    subgraph Stage1["Stage 1: Broker"]
        Q1[(Queue 1<br>Lq₁)]
        S1[["Servers<br>n₁=10, μ₁=12"]]
    end

    subgraph Network["Unreliable Network"]
        NET{{"D=10ms<br>p=20% fail"}}
    end

    subgraph Stage2["Stage 2: Receiver"]
        Q2[(Queue 2<br>Lq₂)]
        S2[["Servers<br>n₂=12, μ₂=12"]]
    end

    subgraph Consumers
        C1[Consumer 1]
        C2[Consumer 2]
        C3[Consumer N]
    end

    P1 & P2 & P3 -->|"λ=100 msg/s"| Q1
    Q1 --> S1
    S1 -->|Success| NET
    NET -->|"Λ₂=125 msg/s"| Q2
    NET -.->|"Retry (20%)"| Q1
    Q2 --> S2
    S2 --> C1 & C2 & C3

    style NET fill:#ffcccc,stroke:#cc0000
    style Q1 fill:#cce5ff,stroke:#0066cc
    style Q2 fill:#cce5ff,stroke:#0066cc
```

---

## 3. Traffic Inflation Flow

```mermaid
flowchart TD
    A["Original Messages<br>λ = 100 msg/sec"] --> B{Network<br>p=20% fail}
    B -->|"80% Success"| C["Delivered"]
    B -->|"20% Fail"| D["Retry Queue"]
    D --> B
    
    E["Stage 2 Total Traffic"] --> F["Λ₂ = λ/(1-p)<br>= 100/0.8<br>= 125 msg/sec"]
    
    style B fill:#ffcccc,stroke:#cc0000
    style F fill:#ccffcc,stroke:#00cc00
```

---

## 4. Two-Phase Commit Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Coordinator
    participant A as Participant A
    participant B as Participant B
    participant D as Participant C

    Note over C,D: Phase 1: Prepare
    C->>A: PREPARE
    C->>B: PREPARE
    C->>D: PREPARE
    
    A-->>C: YES (vote)
    B-->>C: YES (vote)
    D-->>C: YES (vote)
    
    Note over C: All voted YES
    
    Note over C,D: Phase 2: Commit
    C->>A: COMMIT
    C->>B: COMMIT
    C->>D: COMMIT
    
    A-->>C: ACK
    B-->>C: ACK
    D-->>C: ACK
    
    Note over C,D: ✓ Transaction Committed
```

---

## 5. Two-Phase Commit (Abort Scenario)

```mermaid
sequenceDiagram
    participant C as Coordinator
    participant A as Participant A
    participant B as Participant B

    Note over C,B: Phase 1: Prepare
    C->>A: PREPARE
    C->>B: PREPARE
    
    A-->>C: YES
    B-->>C: NO ❌
    
    Note over C: Received NO vote
    
    Note over C,B: Phase 2: Abort
    C->>A: ABORT
    C->>B: ABORT
    
    A-->>C: ACK (rolled back)
    B-->>C: ACK (rolled back)
    
    Note over C,B: ✗ Transaction Aborted
```

---

## 6. Raft Leader Election Sequence

```mermaid
sequenceDiagram
    participant N0 as Node 0<br>(Follower)
    participant N1 as Node 1<br>(Follower)
    participant N4 as Node 4<br>(Candidate)
    participant N2 as Node 2<br>(Follower)
    participant N3 as Node 3<br>(Follower)

    Note over N0,N3: Election Timeout on Node 4
    
    N4->>N4: Increment term to 1<br>Vote for self
    
    N4->>N0: RequestVote(term=1)
    N4->>N1: RequestVote(term=1)
    N4->>N2: RequestVote(term=1)
    N4->>N3: RequestVote(term=1)
    
    N0-->>N4: VoteGranted ✓
    N1-->>N4: VoteGranted ✓
    N2-->>N4: VoteGranted ✓
    N3-->>N4: VoteGranted ✓
    
    Note over N4: Received majority (5/5)
    N4->>N4: Become LEADER
    
    Note over N0,N3: Heartbeat Phase
    loop Every 150ms
        N4->>N0: AppendEntries (heartbeat)
        N4->>N1: AppendEntries (heartbeat)
        N4->>N2: AppendEntries (heartbeat)
        N4->>N3: AppendEntries (heartbeat)
    end
```

---

## 7. Raft Cluster State Diagram

```mermaid
stateDiagram-v2
    [*] --> Follower: Start
    
    Follower --> Candidate: Election timeout<br>(no heartbeat)
    Candidate --> Leader: Receives majority votes
    Candidate --> Follower: Discovers higher term<br>or loses election
    Leader --> Follower: Discovers higher term
    
    Follower --> Follower: Receives heartbeat<br>(reset timeout)
    Leader --> Leader: Send heartbeats<br>Replicate logs
    Candidate --> Candidate: Election timeout<br>(split vote, retry)
```

---

## 8. Vector Clocks Timeline

```mermaid
sequenceDiagram
    participant P1 as Process 1
    participant P2 as Process 2
    participant P3 as Process 3

    Note over P1: [1,0,0]
    P1->>P1: Local event e1
    
    Note over P2: [0,1,0]
    P2->>P2: Local event e2
    
    Note over P1: [2,0,0]
    P1->>P1: Local event e3
    
    P1->>P2: Send message
    Note over P2: max([2,0,0],[0,1,0])+[0,1,0]<br>= [2,2,0]
    
    Note over P3: [0,0,1]
    P3->>P3: Local event e5
    
    P2->>P1: Send message
    Note over P1: max([2,0,0],[2,2,0])+[1,0,0]<br>= [3,2,0]
    
    P2->>P3: Send message
    Note over P3: max([0,0,1],[2,2,0])+[0,0,1]<br>= [2,2,2]
```

---

## 9. Message Queue Processing Flow

```mermaid
flowchart TD
    subgraph Arrival["Message Arrival (Poisson λ=100)"]
        MSG[New Message]
    end

    subgraph Queue["Queue (FIFO)"]
        Q[(Waiting Messages<br>Lq ≈ 3.24)]
    end

    subgraph Service["Service (N=10 threads)"]
        T1[Thread 1]
        T2[Thread 2]
        T3[Thread ...]
        T10[Thread 10]
    end

    subgraph Distribution["Service Time Distribution"]
        EXP["Exponential<br>μ=12 msg/s"]
        PAR["Pareto α=2.5<br>Heavy Tail"]
    end

    subgraph Output["Completed"]
        DONE[Message Processed]
    end

    MSG -->|"ρ=83.3%"| Q
    Q -->|"Wq=32ms"| T1 & T2 & T3 & T10
    T1 & T2 & T3 & T10 --> Distribution
    Distribution -->|"1/μ=83ms"| DONE

    style PAR fill:#ffcccc,stroke:#cc0000
    style EXP fill:#ccffcc,stroke:#00cc00
```

---

## 10. Heavy Tail Impact Comparison

```mermaid
flowchart LR
    subgraph Exponential["M/M/N (Paper's Assumption)"]
        E1["Most jobs: 50-150ms"]
        E2["P99: 460ms"]
        E3["Max: ~500ms"]
    end

    subgraph Pareto["M/G/N (Reality)"]
        P1["Most jobs: 20-80ms"]
        P2["P99: 2,100ms"]
        P3["Max: 10,000ms+"]
    end

    subgraph Impact["Impact on System"]
        I1["❌ SLA Violations"]
        I2["❌ Timeouts"]
        I3["❌ Queue Buildup"]
    end

    Exponential -->|"Looks OK"| Safe["✓ Safe"]
    Pareto -->|"Hidden Risk"| Impact

    style Pareto fill:#ffcccc,stroke:#cc0000
    style Impact fill:#ffcccc,stroke:#cc0000
    style Safe fill:#ccffcc,stroke:#00cc00
```

---

## 11. Simulation vs Analytical Pipeline

```mermaid
flowchart TB
    subgraph Input["Configuration"]
        CFG["λ=100, μ=12, N=10<br>α=2.5 (Pareto)"]
    end

    subgraph Analytical["Analytical Path"]
        A1["M/M/N Formulas<br>(Eq 1-5)"]
        A2["M/G/N Approximation<br>(Kingman/Whitt)"]
        A3["P99 Normal Approx<br>(Eq 15)"]
        AR["Result: 4.25s P99"]
    end

    subgraph Simulation["Simulation Path"]
        S1["SimPy DES Engine"]
        S2["400K Messages<br>20 Replications"]
        S3["EVT Tail Analysis"]
        SR["Result: 7.81s P99"]
    end

    subgraph Compare["Comparison"]
        CMP["45% Underestimation!<br>Paper is WRONG"]
    end

    CFG --> A1 --> A2 --> A3 --> AR
    CFG --> S1 --> S2 --> S3 --> SR
    AR --> CMP
    SR --> CMP

    style AR fill:#ffcccc,stroke:#cc0000
    style SR fill:#ccffcc,stroke:#00cc00
    style CMP fill:#fff3cd,stroke:#ffc107
```

---

## 12. Mitigation Strategy Flow

```mermaid
flowchart TD
    subgraph Problem["Problem: Heavy Tail"]
        HT["Pareto α=2.5<br>P99 = 12.3s with N=1"]
    end

    subgraph Solution["Solution: Add Capacity"]
        N1["N=1: 12.3s ❌"]
        N2["N=2: 0.90s ✓"]
        N3["N=3: 0.45s ✓"]
        N5["N=5: 0.28s ✓"]
    end

    subgraph Result["Result"]
        IMP["93% Improvement<br>Just add 1 server!"]
    end

    HT --> N1
    N1 -->|"+1 server"| N2
    N2 -->|"+1 server"| N3
    N3 -->|"+2 servers"| N5
    N2 --> IMP

    style N1 fill:#ffcccc,stroke:#cc0000
    style N2 fill:#ccffcc,stroke:#00cc00
    style IMP fill:#ccffcc,stroke:#00cc00
```

---

## 13. Full System Data Flow

```mermaid
flowchart LR
    subgraph User["User Interface"]
        Browser[Web Browser]
    end

    subgraph FE["Frontend :4000"]
        React[React App]
        Form[Config Form]
        Chart[Result Charts]
    end

    subgraph BE["Backend :6000"]
        FastAPI[FastAPI]
        Pydantic[Validation]
    end

    subgraph Core["Simulation Core"]
        Config[MMNConfig<br>MGNConfig]
        SimPy[SimPy Engine]
        Metrics[Metrics Collector]
    end

    subgraph Analysis["Analysis"]
        Analytical[15 Equations]
        EVT[EVT P99]
    end

    subgraph Output["Results"]
        JSON[JSON Response]
        Plots[Matplotlib Plots]
    end

    Browser --> React
    React --> Form
    Form -->|POST /api/sim| FastAPI
    FastAPI --> Pydantic
    Pydantic --> Config
    Config --> SimPy
    SimPy --> Metrics
    Metrics --> Analytical
    Metrics --> EVT
    Analytical --> JSON
    EVT --> JSON
    JSON --> Chart
    Chart --> Browser
    Metrics --> Plots
```

---

## Usage Instructions

### Option 1: Mermaid Live Editor
1. Go to https://mermaid.live
2. Paste the diagram code
3. Export as PNG/SVG

### Option 2: VS Code
1. Install "Mermaid Preview" extension
2. Create `.md` file with diagram
3. Preview and screenshot

### Option 3: PowerPoint/Google Slides
1. Render diagram to image
2. Insert image into slide
3. Add annotations as needed

### Option 4: GitHub/GitLab
- Mermaid renders automatically in markdown files

---

**End of Diagrams**
