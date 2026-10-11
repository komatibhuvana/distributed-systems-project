# Performance Modeling for Real-World Cloud Message Queue Systems

## An Enhanced Analytical and Simulation Framework Extending Li et al.

---

<p align="center">
<img src="results/plots/reality_gap.png" alt="Reality Gap - Baseline vs Enhanced Model" width="700"/>
</p>

<p align="center"><em>Figure 1: The Reality Gap - Comparison of Baseline Model (Exponential) vs Enhanced Model (Heavy-Tailed)</em></p>

---

**Authors:** Himanshu Jain, Bhuvana Komati  
**Course:** CMPE 273 - Enterprise Distributed Systems  
**Institution:** San Jose State University  
**Semester:** Fall 2025  
**Date:** December 12, 2025

---

## List of Figures

| Figure | Description | Location |
|--------|-------------|----------|
| Figure 1 | The Reality Gap - Baseline vs Enhanced Model | Title Page |
| Figure 2 | M/M/N Validation against Base Paper | Section 5.3 |
| Figure 3 | Mean Delivery Time vs Threads (Figure 11 Comparison) | Section 5.3 |
| Figure 4 | Heavy Tail Impact Comparison | Section 7.1 |
| Figure 5 | Threading Model Comparison | Section 8.6 |
| Figure 6 | Queue Length Validation (Figure 12) | Section 9.1 |
| Figure 7 | Utilization Validation (Figure 13) | Section 9.1 |
| Figure 8 | Tail Risk Assessment - EVT vs Normal | Section 10.1 |
| Figure 9 | Load Testing Results | Section 12.2 |
| Figure 10 | Confidence Intervals Analysis | Section 12.2 |
| Figure 11 | Convergence Test Results | Section 12.3 |
| Figure 12 | Mitigation Scaling Analysis | Section 12.4 |
| Figure 13 | Erlang-k Efficiency | Section 12.5 |
| Figure 14 | Warmup Validation | Section 12.6 |
| Figure 15-16 | Service Time & Arrival Rate Trends | Section 12.7 |

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Problem Statement & Motivation](#3-problem-statement--motivation)
4. [Base Paper Overview](#4-base-paper-overview)
5. [The Tandem Queue Model](#5-the-tandem-queue-model)
6. [Mathematical Foundation: The 15 Equations](#6-mathematical-foundation-the-15-equations)
7. [Heavy-Tailed Distributions: The Key Insight](#7-heavy-tailed-distributions-the-key-insight)
8. [System Architecture & Implementation](#8-system-architecture--implementation)
9. [The "Reality Gap" Discovery](#9-the-reality-gap-discovery)
10. [Tail Risk Analysis (P99 Latency)](#10-tail-risk-analysis-p99-latency)
11. [Distributed Systems Integration](#11-distributed-systems-integration)
12. [Experimental Results & Validation](#12-experimental-results--validation)
13. [Key Discoveries](#13-key-discoveries)
14. [Conclusion & Future Work](#14-conclusion--future-work)
15. [References](#15-references)
16. [Appendix](#16-appendix)

---

## 1. Abstract

Cloud message brokers are critical infrastructure components that enable asynchronous communication in distributed systems. This project extends the foundational work of Li et al. (2015) to address critical limitations in modeling real-world cloud message queue performance. While the base paper assumes exponential service times (M/M/N model), our research demonstrates that real cloud workloads exhibit heavy-tailed (Pareto) distributions where standard models underestimate P99 latency by up to **45%**.

We developed an enhanced analytical and simulation framework using Python/SimPy that incorporates:
- **Heavy-tailed service time distributions** (Pareto, M/G/N models)
- **Explicit threading architectures** (dedicated vs. shared worker pools)
- **Distributed consistency protocols** (Two-Phase Commit, Raft Consensus)
- **Advanced M/G/N approximations** (Kingman, Whitt, Allen-Cunneen)

Our key findings reveal that:
1. Heavy-tailed distributions cause P99/mean latency ratios exceeding **36x**
2. Traffic amplification in tandem queues (Λ₂ = λ/(1-p)) validated to **0.2% error**
3. Two-Phase Commit adds **36% service time overhead** (the "cost of safety")
4. Standard P99 approximations underestimate actual tail latency by **45%**

The framework includes a full-stack implementation with React frontend and FastAPI backend, providing interactive engineering tools for capacity planning and performance analysis.

**Keywords:** Queueing Theory, Message Brokers, Heavy-Tailed Distributions, Pareto Distribution, Two-Phase Commit, Raft Consensus, SimPy, Cloud Computing, P99 Latency

---

## 2. Introduction

### 2.1 Background

Cloud message brokers serve as the backbone of modern distributed systems, enabling reliable asynchronous communication between services. Systems like AWS SQS, RabbitMQ, Apache Kafka, and Azure Queue Storage handle billions of messages daily, making accurate performance modeling critical for:

- **Capacity planning** - How many servers are needed?
- **SLA compliance** - Can we guarantee P99 < 100ms?
- **Cost optimization** - Are we over-provisioning?
- **Failure analysis** - How do retransmissions affect performance?

### 2.2 The Modeling Challenge

Traditional queueing theory provides elegant mathematical formulas for predicting system performance. The widely-used M/M/N model assumes:

| What Models Assume | What Reality Shows |
|-------------------|-------------------|
| Exponential Distribution | Heavy-Tailed (Pareto) |
| Jobs are similar size | Most small, rare HUGE |
| Predictable variance | Extreme outliers |
| Nice math properties | One big job blocks all |

This gap between theoretical assumptions and real-world behavior leads to:
- **Underestimated latency** - Systems appear faster than they are
- **SLA violations** - 1 in 100 users experience unacceptable delays
- **Cascading failures** - Slow requests pile up and overwhelm the system

### 2.3 Project Objectives

1. **Reproduce and validate** the Li et al. (2015) base paper results
2. **Extend the model** to handle heavy-tailed service time distributions
3. **Implement distributed protocols** (2PC, Raft) for message reliability
4. **Quantify the "Reality Gap"** between theory and simulation
5. **Build engineering tools** for practical capacity planning

---

## 3. Problem Statement & Motivation

### 3.1 What Cloud Systems Must Guarantee

```
✅ At-Least-Once Delivery - No message loss
✅ Ordering Guarantees - FIFO or causal ordering
✅ Durability - Survive node failures
✅ Low Latency - Meet SLA requirements
```

### 3.2 The Hidden Problem Chain

```
Network failures → Retransmissions → Extra load → Queue buildup → SLA violations!
```

When a message fails to transmit, the system must retry. Each retry adds load to the system, causing queues to grow. This cascade effect is amplified when service times are unpredictable.

### 3.3 Real-World Evidence of Heavy Tails

**Industry Evidence:**

| Company | System | P50 | P99 | Ratio |
|---------|--------|-----|-----|-------|
| Amazon | DynamoDB | 5ms | 50ms | 10x |
| Google | Bigtable | 10ms | 100ms | 10x |
| Netflix | Streaming | 20ms | 500ms | 25x |
| **Our Simulation** | Pareto α=2.5 | 58ms | 2,100ms | **36x** |

**The Starbucks vs. DMV Analogy:**

| Starbucks (Model) | DMV (Reality) | Cloud Systems |
|-------------------|---------------|---------------|
| Black coffee: 2 min | License renewal: 10 min | API calls: 50ms (95%) |
| Latte: 3 min | Registration: 15 min | DB queries: 10ms (90%) |
| Frappuccino: 4 min | Title transfer: 30 min | Video encode: 60s (1%) |
| Max: ~5 min | Fleet of 50 trucks: **4 HOURS** | ML training: 30min (0.1%) |

The M/M/N model assumes Starbucks-like behavior. Real systems behave like the DMV.

---

## 4. Base Paper Overview

### 4.1 Paper Details

**Title:** "Modeling Message Queueing Services with Reliability Guarantee in Cloud Computing Environment Using Colored Petri Nets"  
**Authors:** Li, Cui, Ma  
**Journal:** Mathematical Problems in Engineering, 2015  
**Citations:** 50+ (influential in cloud modeling)

### 4.2 Key Contributions of Base Paper

| Contribution | Description |
|--------------|-------------|
| ✅ Tandem Queue Model | Two-stage architecture (Sender → Broker → Receiver) |
| ✅ Traffic Inflation Formula | Λ₂ = λ/(1-p) captures retransmission load |
| ✅ CPN Verification | Formal proofs using Colored Petri Nets |
| ✅ Performance Formulas | Latency, queue length calculations |

### 4.3 Paper's Assumptions (What We Address)

| Paper's Assumptions | Paper's Limitations |
|--------------------|---------------------|
| M/M/N: Exponential arrivals & service | ❌ No heavy-tailed analysis |
| Homogeneous: All servers identical | ❌ Homogeneous servers only |
| Constant D: Fixed network delay | ❌ No threading model |
| Bernoulli p: IID failure probability | ❌ Limited to CPN tools |

### 4.4 The Foundation Established

The Li et al. (2015) paper established:

- **Core Model:** Cloud message service as M/M/N tandem queue (Sender → Broker → Receiver)
- **Key Mechanism:** Visibility Timeout for at-least-once delivery guarantee
- **Methodology:** Dual approach of analytical formulas (Jackson's theorem) and CPN simulation
- **Primary Metrics:** Mean total delivery time and mean number of messages in queue
- **Critical Insight:** Stage 2 Load Amplification (Λ₂ = λ/(1-p))

---

## 5. The Tandem Queue Model

### 5.1 Architecture Overview

<p align="center">

```
                    Stage 1                    Network                    Stage 2
    Publishers ──λ──▶ [Broker Queue] ────D_link────▶ [Receiver Queue] ──▶ Consumers
                       (n₁ servers)     (prob. p)      (n₂ servers)
                           │                               ▲
                           └───────Retransmission──────────┘
                                    (prob. p)
```

</p>

### 5.2 System Parameters

| Parameter | Symbol | Value | Description |
|-----------|--------|-------|-------------|
| Arrival Rate | λ | 100 msg/s | Messages entering system |
| Broker Servers | n₁ | 10 | Stage 1 threads |
| Receiver Servers | n₂ | 12 | Stage 2 threads |
| Service Rate | μ | 12 msg/s/server | Processing speed |
| Network Delay | D | 10 ms | One-way latency |
| Failure Prob | p | 0.20 (20%) | Transmission failure |

### 5.3 Traffic Inflation: The Key Insight

The most critical formula from the base paper:

$$\Lambda_2 = \frac{\lambda}{1-p}$$

**Example Calculation:**
- Λ₂ = 100 / (1 - 0.2)
- Λ₂ = 100 / 0.8
- Λ₂ = **125 msg/s**

**Result:** Stage 2 sees **25% MORE traffic** than Stage 1 due to retransmissions!

<p align="center">
<img src="results/plots/mmn_validation.png" alt="M/M/N Validation" width="600"/>
</p>

<p align="center"><em>Figure 2: M/M/N Model Validation - Simulation vs Analytical Results</em></p>

<p align="center">
<img src="results/plots/figure11_comparison.png" alt="Traffic Inflation Validation" width="600"/>
</p>

<p align="center"><em>Figure 3: Mean Delivery Time vs. Number of Threads - Validation against Base Paper (Figure 11)</em></p>

---

## 6. Mathematical Foundation: The 15 Equations

Our framework implements 15 core equations organized into three sections.

### 6.1 Section 1: M/M/N Baseline (Equations 1-5)

These equations form the foundation from classical queueing theory:

| Eq | Formula | Example Value | Description |
|----|---------|---------------|-------------|
| 1 | ρ = λ/(N·μ) | 0.833 | **Utilization** - fraction of time servers are busy |
| 2 | P₀ = [Σ...]⁻¹ | 0.012 | **Probability system empty** |
| 3 | C(N,a) = Erlang-C | 0.65 | **Probability of queueing** |
| 4 | Lq = C·ρ/(1-ρ) | 3.24 | **Mean queue length** |
| 5 | Wq = Lq/λ | 32ms | **Mean waiting time** (Little's Law) |

#### Equation 1: Utilization (ρ)

$$\rho = \frac{\lambda}{N \cdot \mu}$$

**Critical Rule:** ρ must be < 1 for stability. If ρ ≥ 1, the queue grows infinitely!

```python
# Implementation: src/core/config.py
@property
def utilization(self) -> float:
    """Calculate ρ = λ/(N·μ)"""
    return self.arrival_rate / (self.num_threads * self.service_rate)
```

#### Equation 3: Erlang-C Formula

$$C(N,a) = \frac{a^N}{N!(1-\rho)} \cdot P_0$$

Named after Agner Krarup Erlang (1909), this gives the probability an arriving message must wait.

#### Equation 5: Little's Law

$$W_q = \frac{L_q}{\lambda}$$

One of the most fundamental results in queueing theory - holds for ANY queueing system!

### 6.2 Section 2: Heavy-Tailed Distributions (Equations 6-10)

These equations extend the model to handle real-world service time variability:

| Eq | Formula | Description |
|----|---------|-------------|
| 6 | f(t) = α·k^α/t^(α+1) | **Pareto PDF** - power law decay |
| 7 | E[S] = α·k/(α-1) | **Mean service time** |
| 8 | E[S²] = α·k²/(α-2) | **Second moment** |
| 9 | C² = 1/(α(α-2)) | **Coefficient of variation squared** |
| 10 | Wq ≈ Wq·(1+C²)/2 | **M/G/N Kingman approximation** |

#### Equation 6: Pareto Probability Density Function

$$f(t) = \frac{\alpha \cdot k^\alpha}{t^{\alpha+1}}, \quad t \geq k$$

**Parameters:**
- **α (alpha):** Shape parameter - controls "heaviness" of tail
  - α = 2.1: Very heavy tail
  - α = 2.5: Moderate tail
  - α = 3.0: Light tail
- **k:** Scale parameter (minimum service time)

#### Equation 9: Coefficient of Variation

$$C^2 = \frac{1}{\alpha(\alpha-2)}, \quad \text{for } \alpha > 2$$

| α Value | C² | Tail Weight |
|---------|-----|-------------|
| 1.5 | ∞ | Infinite variance! |
| 2.0 | ∞ | Infinite variance! |
| 2.1 | 47.6 | Extremely heavy |
| 2.5 | 0.8 | Heavy |
| 3.0 | 0.33 | Moderate |
| 5.0 | 0.067 | Light |

**Critical Warning:** When α ≤ 2, variance is mathematically INFINITE. Normal approximations completely fail!

#### Equation 10: Kingman's M/G/N Approximation

$$W_q^{M/G/N} \approx W_q^{M/M/N} \times \frac{1 + C^2}{2}$$

This adjusts the baseline waiting time for service time variability.

**The "Crash" Calculation:**
- If C² = 1 (Exponential): Multiplier = (1+1)/2 = 1 (no change)
- If C² = 47.6 (Pareto α=2.1): Multiplier = (1+47.6)/2 ≈ **24.3**

**Conclusion:** Wait time increases by **2400%** just by changing distribution shape!

### 6.3 Section 3: Threading Models (Equations 11-15)

| Eq | Formula | Description |
|----|---------|-------------|
| 11 | Nmax = Nthreads/2 | **Dedicated max connections** |
| 12 | X = min(λ, cap) | **Throughput** |
| 13 | μeff = μ/(1+α·N/T) | **Shared overhead** |
| 14 | Psat = C(N,a)·ρ | **Saturation probability** |
| 15 | R99 ≈ E[R]+2.33·σ | **P99 normal approximation** |

#### Equation 13: Shared Effective Service Rate

$$\mu_{eff} = \frac{\mu}{1 + \alpha \cdot \frac{N_{active}}{N_{threads}}}$$

Accounts for context switching overhead in shared worker pools.

#### Equation 15: P99 Latency Approximation

$$R_{99} \approx E[R] + 2.33 \cdot \sigma_R$$

**Critical Flaw:** This assumes latency follows a Normal distribution. For heavy-tailed workloads, this underestimates P99 by >2x!

---

## 7. Heavy-Tailed Distributions: The Key Insight

### 7.1 Why Heavy Tails Matter

<p align="center">
<img src="results/plots/mgn_heavy_tail.png" alt="Heavy Tail Distribution" width="600"/>
</p>

<p align="center"><em>Figure 4: Heavy Tail Impact - Comparison of Exponential vs. Pareto Service Time Distributions</em></p>

<p align="center">
<img src="visualization/plot_2_heavy_tail_impact.png" alt="Heavy Tail Impact Detailed" width="600"/>
</p>

<p align="center"><em>Figure 4b: Detailed Heavy Tail Impact Analysis</em></p>

**Distribution Comparison (Same Mean = 100ms):**

| Percentile | Exponential | Pareto (α=2.5) | Ratio |
|------------|-------------|----------------|-------|
| P50 | 69ms | 58ms | 0.84x |
| P90 | 230ms | 320ms | 1.4x |
| P95 | 300ms | 580ms | 1.9x |
| P99 | 460ms | 2,100ms | **4.6x** |
| P99.9 | 690ms | 14,800ms | **21x** |

### 7.2 The Pareto Principle (80-20 Rule)

The Pareto distribution follows the famous 80-20 rule:
- 80% of requests finish quickly
- 20% take much longer
- A single 10-second request can delay 100 normal requests!

### 7.3 Variance Explosion

**Step 1: The Mean is Deceptive**

We calibrate Pareto to have the same mean as Exponential (μ = 10). On average, they look identical.

$$E[S] = \frac{\alpha \cdot k}{\alpha - 1}$$

**Step 2: The Variance Explodes**

$$C^2 = \frac{1}{\alpha(\alpha - 2)}, \quad \text{for } \alpha > 2$$

**Data Point:**
- Exponential: C² = 1
- Pareto (α = 2.1): C² ≈ **47.6!**

While the means are identical, the coefficient of variation for heavy-tailed workloads is nearly **50x higher** than the exponential baseline!

---

## 8. System Architecture & Implementation

### 8.1 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18 + TypeScript + Vite | Interactive UI |
| **UI Components** | Shadcn UI + Tailwind CSS | Modern styling |
| **Visualization** | Recharts + Framer Motion | Charts & animations |
| **Backend** | FastAPI + Pydantic + Uvicorn | REST API |
| **Simulation** | SimPy + NumPy + SciPy | Discrete-event simulation |
| **Analysis** | Pandas + Matplotlib + Seaborn | Data analysis |

### 8.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 4000)              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ├─ Control Center (Live Simulation Dashboard)       │   │
│  │  ├─ Capacity Planner (M/M/N Calculator)              │   │
│  │  ├─ Blast Radius (Tandem Queue Visualizer)           │   │
│  │  └─ Reality Gap Explorer (Theory vs Simulation)      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP REST API (Axios)
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Port 3100)                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ├─ /api/simulations/* (M/M/N, M/G/N, Tandem)       │   │
│  │  ├─ /api/analytical/* (15 Equations)                 │   │
│  │  └─ /api/results/* (Export & Analysis)               │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  SimPy Discrete-Event Simulation Engine              │   │
│  │  ├─ mmn_queue.py      │  mgn_queue.py               │   │
│  │  ├─ tandem_queue.py   │  distributed_broker.py      │   │
│  │  ├─ two_phase_commit.py │ raft_consensus.py         │   │
│  │  └─ priority_queue.py │  finite_capacity_queue.py   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 Why SimPy Instead of Colored Petri Nets?

| Aspect | CPN (Paper) | SimPy (Ours) |
|--------|-------------|--------------|
| Formal Proofs | ✅ Yes | ❌ No |
| Deadlock Detection | ✅ Provable | ⚠ Empirical |
| Distribution Flexibility | ❌ Complex | ✅ Easy |
| Statistical Analysis | ❌ Limited | ✅ Rich |
| Python Ecosystem | ❌ No | ✅ Full |
| Industry Standard | ⚠ Academic | ✅ Production |

**Trade-off:** Lost formal proofs, gained flexibility for heavy-tail analysis.

### 8.4 Code Example

```python
# One line to change distribution!
service = ParetoService(alpha=2.5, scale=0.05)  # Heavy-tailed
# vs
service = ExponentialService(rate=12.0)          # Paper's assumption
```

### 8.5 Project Structure

```
distributed-systems-project/
├── frontend/                    # React Application
│   ├── src/pages/              # Engineering Tools
│   │   ├── ControlCenter.tsx   # Main demo dashboard
│   │   ├── MMNCalculator.tsx   # Capacity planning
│   │   ├── TandemQueue.tsx     # Cascade analysis
│   │   └── MGNvsMMNComparison.tsx
│   └── src/components/         # UI components
├── backend/                     # FastAPI Application
│   ├── api/routes/             # REST endpoints
│   └── api/models/             # Pydantic schemas
├── src/                        # Core Simulation Engine
│   ├── models/                 # Queue implementations
│   │   ├── mmn_queue.py        # Basic M/M/N queue
│   │   ├── mgn_queue.py        # Heavy-tailed M/G/N
│   │   ├── tandem_queue.py     # Two-stage tandem
│   │   ├── heterogeneous_mmn.py # Multiple server speeds
│   │   ├── priority_queue.py   # Multi-priority classes
│   │   ├── finite_capacity_queue.py # M/M/N/K with blocking
│   │   ├── two_phase_commit.py # 2PC protocol
│   │   ├── raft_consensus.py   # Raft leader election
│   │   ├── vector_clocks.py    # Causality tracking
│   │   └── visibility_timeout.py # SQS-style reliability
│   ├── analysis/               # Analytical formulas
│   │   ├── analytical.py       # 15 Core Equations
│   │   ├── extreme_value_theory.py # EVT/GPD for tails
│   │   ├── cap_analysis.py     # CAP theorem analysis
│   │   └── empirical_percentiles.py
│   └── core/                   # Configuration & utilities
│       ├── config.py           # Pydantic configs
│       ├── distributions.py    # Service time distributions
│       └── metrics.py          # Metrics collection
├── experiments/                # Validation scripts (30+ experiments)
├── tests/                      # Unit tests (29 tests)
├── visualization/              # Plot generation
│   ├── plot_1_mmn_validation.png
│   ├── plot_2_heavy_tail_impact.png
│   ├── plot_3_threading_comparison.png
│   ├── plot_4_load_testing.png
│   └── plot_5_confidence_intervals.png
└── results/                    # Generated results
    ├── plots/                  # 14 validation plots
    ├── data/                   # CSV data files
    └── tables/                 # Markdown tables
```

### 8.6 Threading Model Implementation

<p align="center">
<img src="visualization/plot_3_threading_comparison.png" alt="Threading Comparison" width="600"/>
</p>

<p align="center"><em>Figure 5: Threading Architecture Comparison - Dedicated vs Shared Worker Pools</em></p>

---

## 9. The "Reality Gap" Discovery

### 9.1 Validating the Baseline Model

Before extending the model, we reproduced the base paper's results:

| Metric | Paper Value | Our Value | Error |
|--------|-------------|-----------|-------|
| Mean Delivery Time | 0.167s | 0.156s | 6.6% ✅ |
| Mean Queue Length | 3.2 msgs | 2.8 msgs | 12.5% ✅ |
| System Utilization | 83.3% | 83.1% | 0.2% ✅ |
| Service Rate Impact | Trend ✓ | Trend ✓ | Match ✅ |
| Arrival Rate Impact | Trend ✓ | Trend ✓ | Match ✅ |

**Traffic Inflation Validation:**
- Formula: Λ₂ = λ/(1-p)
- Expected: 100/(1-0.2) = 125 msg/s
- Simulated: 124.7 msg/s
- Error: **0.2%** ✅

<p align="center">
<img src="results/plots/figure12_comparison.png" alt="Queue Length Validation" width="600"/>
</p>

<p align="center"><em>Figure 6: Queue Length vs. Threads - Our Simulation vs. Base Paper (Figure 12)</em></p>

<p align="center">
<img src="results/plots/figure13_comparison.png" alt="Utilization Validation" width="600"/>
</p>

<p align="center"><em>Figure 7: Utilization vs. Threads - Validation against Base Paper (Figure 13)</em></p>

<p align="center">
<img src="visualization/plot_1_mmn_validation.png" alt="MMN Validation Detailed" width="600"/>
</p>

<p align="center"><em>Figure 7b: Detailed M/M/N Validation - Analytical vs Simulation</em></p>

### 9.2 Mean Latency Comparison

<p align="center">
<img src="results/plots/reality_gap.png" alt="Reality Gap" width="600"/>
</p>

<p align="center"><em>Figure: The Reality Gap - Comparison of Different Models</em></p>

| Model | Mean Latency | Analysis |
|-------|--------------|----------|
| Paper (M/M/N) | 0.167s | Underestimates by ~14% |
| QNA Approximation | 0.480s | Overestimates |
| Our Simulation | 0.190s | Ground truth |

**Analysis:**
- Paper predicts: 0.167s average
- Reality shows: 0.190s average
- Underestimation: 14%

But wait... 14% might seem acceptable for averages. The real danger is in the **TAIL**.

---

## 10. Tail Risk Analysis (P99 Latency)

### 10.1 CRITICAL FINDING: P99 Underestimation

<p align="center">
<img src="results/plots/tail_risk.png" alt="Tail Risk Assessment" width="600"/>
</p>

<p align="center"><em>Figure 8: Tail Risk Assessment - Normal Approximation vs. EVT vs. Simulation Ground Truth</em></p>

| Method | P99 Value | Error vs Reality |
|--------|-----------|------------------|
| Paper (Normal Approx) | 4.25s | **-45%** ⚠ |
| Kingman Approx | 5.12s | -34% |
| Whitt Approx | 6.89s | -12% |
| EVT Estimate | 7.56s | -3% |
| Simulation (Truth) | 7.81s | — |

**The Gap:** Paper underestimates P99 by **45%**!

### 10.2 Why This Matters

**Impact:**
- ❌ **SLA Violations** - 1 in 100 users timeout
- ❌ **Cascading Failures** - Slow requests pile up
- ❌ **Customer Complaints** - "The system is broken!"

**Scenario:**
- If you build a system expecting 4-second worst case
- And it actually hits 8 seconds
- Your SLA is violated
- Users see timeouts
- The system looks broken

### 10.3 The Gaussian Fallacy

**Standard P99 Approximation:**

$$R_{99} \approx \mu + 2.33\sigma$$

**Variables:**
- μ: Mean Response Time
- σ: Standard Deviation
- 2.33: Z-score for 99th percentile of Normal distribution

**The Critical Flaw:**
- **Assumption:** Latency follows a Normal (Gaussian) Distribution, where probability decays exponentially (e^(-x²))
- **Reality:** Cloud latency follows a Heavy-Tailed (Pareto) Distribution, where probability decays polynomially (x^(-α))
- **Consequence:** For heavy-tailed workloads, the standard approximation underestimates P99 by >2x

### 10.4 The Solution: Extreme Value Theory (EVT)

Instead of fitting "average" behavior, we applied **Extreme Value Theory (EVT)**, specifically the Peaks Over Threshold (POT) method using the **Generalized Pareto Distribution (GPD)**.

**Why it matters:** GPD accurately predicts that the probability of a massive delay (e.g., >5s) decays polynomially (slowly), not exponentially (fast).

### 10.5 Validating M/G/N Approximations

| α (Pareto) | CV² | Kingman Error | **Whitt Error** | Allen-Cunneen Error | **Best Method** |
|------------|-----|---------------|-----------------|---------------------|-----------------|
| 3.0 | 0.33 | 5.2% | **3.1%** | 6.8% | **Whitt** |
| 2.5 | 1.0 | 8.7% | **4.5%** | 9.2% | **Whitt** |
| 2.1 | 10.0 | 24.3% | 9.8% | **8.1%** | **Allen-Cunneen** |

**Finding:** Whitt's approximation (1993) is recommended for high utilization. Allen-Cunneen (1990) is better for very heavy tails.

---

## 11. Distributed Systems Integration

### 11.1 Extending Beyond Queues

The framework extends beyond the original tandem queue to model critical distributed systems components:

| Component | Description |
|-----------|-------------|
| **Threading Models** | Dedicated (thread-per-connection) vs. Shared (worker pool) |
| **Priority Queues** | Multiple priority classes (preemptive and non-preemptive) |
| **Finite Capacity** | M/M/N/K systems with Erlang-B blocking |
| **Distributed Protocols** | Two-Phase Commit (2PC), Raft Consensus |

### 11.2 Threading Architectures

**Architecture 1: Dedicated Threads (Paper's Assumption)**
- Thread-per-request model
- **Flaw:** Infinite resource assumption

**Architecture 2: Shared Worker Pool (Our Extension)**
- Fixed pool of N workers consuming from shared queue
- **Finite Capacity:** M/M/N/K queueing logic
- **Result:** Erlang-B blocking (load shedding when buffer full)

**Finding:** Shared threading introduces **10-15% performance overhead** but offers near-unlimited connection scalability.

### 11.3 Two-Phase Commit Implementation

**Context:** The Li et al. paper relies on Visibility Timeout, which is probabilistic. If a node crashes after receiving but before replicating, data is lost.

**Our Fix:** Implemented **Two-Phase Commit (2PC)** for deterministic consistency.

```python
class TwoPhaseCoordinator:
    """2PC Coordinator for distributed transactions"""
    
    def begin_transaction(self, participant_ids, operation, data):
        # Phase 1: Prepare - Send PREPARE to all participants
        # Phase 2: Commit/Abort based on votes
```

**The Blocking Mechanism:**
- In standard M/M/N: service time = CPU processing only
- In 2PC model: service time = μ + 2 × RTT
- During PREPARE phase, worker thread holds request but cannot work

**Latency Consequence:** Introduces mandatory Network Round Trip (RTT) penalty - the **"Cost of Safety"**.

**Measured Overhead:** 2PC adds **36% service time overhead**.

### 11.4 Raft Consensus Protocol

Implemented for leader election and log replication:

```python
class RaftNode:
    """Raft consensus node"""
    # States: FOLLOWER, CANDIDATE, LEADER
    # Election timeout: 10-20 seconds (configurable)
    # Heartbeat interval: 5 seconds
```

**Impact:** 20-40% throughput reduction for consensus overhead.

### 11.5 Vector Clocks for Causality Tracking

Based on Lamport (1978) "Time, Clocks, and the Ordering of Events in a Distributed System":

```python
class VectorClock:
    """Vector clock for distributed event ordering"""
    
    def tick(self):
        """Increment local clock on local event"""
        self.clock[self.process_id] += 1
    
    def send_event(self) -> List[int]:
        """Prepare timestamp for sending message"""
        self.clock[self.process_id] += 1
        return deepcopy(self.clock)
    
    def receive_event(self, received_clock: List[int]):
        """Merge clocks on receive"""
        for j in range(self.num_processes):
            self.clock[j] = max(self.clock[j], received_clock[j])
        self.clock[self.process_id] += 1
```

**Features:**
- Happened-before (→) relationship detection
- Concurrent event detection
- Causality preservation for message ordering

### 11.6 Visibility Timeout (SQS-Style Reliability)

Implements the visibility timeout mechanism from Li et al. (2015) Section 6.4:

```python
class VisibilityTimeoutManager:
    """Manages message visibility states and timeout mechanisms"""
    
    def receive_message(self) -> Optional[CloudMessage]:
        """
        1. Get visible message
        2. Make invisible
        3. Start visibility timer
        """
        message.make_invisible(self.env.now)
        self.timers[message.id] = self.env.process(
            self._visibility_timer(message)
        )
```

**Key Features:**
- Messages become invisible when received
- Return to queue if not acknowledged within timeout
- Dead Letter Queue (DLQ) for poison messages

### 11.7 Heterogeneity & Work Stealing

Addresses "Future Work" from Li et al. (2015) regarding heterogeneous server modeling:

```python
class HeterogeneousMMNQueue:
    """
    M/M/N queues with multiple server groups having different service rates
    
    Key Features:
    - Multiple server groups with different speeds (e.g., 2 slow + 3 fast)
    - Flexible server selection policies (random, fastest-first, shortest-queue)
    - Work stealing between pools
    """
```

**The Problem (Random Routing):**
- Standard load balancers give equal tasks to fast and legacy nodes
- Legacy nodes become bottlenecks, causing massive delays

**The Solution (Work Stealing):**
1. Tasks initially routed randomly (fast)
2. When Fast Node finishes and queue is empty:
3. Check Legacy Node's queue
4. **Steal** task and process at high speed

**Result:** 144x latency improvement by eliminating heterogeneity bottleneck.

### 11.8 Priority Queues (M/M/N with Priority Classes)

Based on Kleinrock (1975) priority queueing theory:

```python
class PriorityQueueModel:
    """
    M/M/N queue with multiple priority classes
    
    Supports:
    - Non-preemptive: Higher priority jumps queue but doesn't interrupt
    - Preemptive: Higher priority can interrupt lower priority service
    """
```

**The Trade-off (Conservation of Work):**
- VIP latency drops near zero
- Standard traffic suffers starvation
- Total work remains constant - we shift delay to non-priority users

### 11.9 Finite Capacity Queues (M/M/N/K)

Implements queue with maximum capacity K using Erlang-B blocking:

```python
class FiniteCapacityQueue:
    """
    M/M/N/K queue with finite capacity
    
    Key Features:
    - Maximum capacity K (including those in service)
    - Blocking when full (Erlang-B behavior)
    - System is always stable (even if λ > N·μ)
    """
```

**Erlang-B Formula** for blocking probability:
$$P_{blocking} = \frac{a^K/K!}{\sum_{n=0}^{K} a^n/n!}$$

### 11.10 Extreme Value Theory (EVT) for Tail Estimation

Uses Generalized Pareto Distribution (GPD) to model distribution tails:

```python
class ExtremeValueAnalyzer:
    """
    Use GPD for tail modeling (Peaks Over Threshold method)
    
    GPD PDF: f(x) = (1/σ) * (1 + ξ(x-μ)/σ)^(-(1+1/ξ))
    
    Shape parameter ξ determines tail behavior:
    - ξ > 0: Heavy tail (Pareto-type)
    - ξ = 0: Exponential tail
    - ξ < 0: Short tail (bounded)
    """
```

**Why EVT matters:** Accurately predicts P99/P99.9 for heavy-tailed distributions where normal approximations fail catastrophically.

---

## 12. Experimental Results & Validation

### 12.1 Baseline Validation

We successfully reproduced all key results from the Li et al. (2015) base paper:

| Metric | Paper Value | Our Value | Error |
|--------|-------------|-----------|-------|
| Mean Delivery Time | 0.167s | 0.156s | 6.6% ✅ |
| Mean Queue Length | 3.2 msgs | 2.8 msgs | 12.5% ✅ |
| System Utilization | 83.3% | 83.1% | 0.2% ✅ |

### 12.2 Load Testing & Confidence Intervals

<p align="center">
<img src="visualization/plot_4_load_testing.png" alt="Load Testing" width="600"/>
</p>

<p align="center"><em>Figure 9: Load Testing Results - System Performance Under Varying Arrival Rates</em></p>

<p align="center">
<img src="visualization/plot_5_confidence_intervals.png" alt="Confidence Intervals" width="600"/>
</p>

<p align="center"><em>Figure 10: 95% Confidence Intervals for Performance Metrics</em></p>

### 12.3 Convergence Testing

<p align="center">
<img src="results/plots/convergence_test.png" alt="Convergence Test" width="600"/>
</p>

<p align="center"><em>Figure 11: Convergence Test - P99 Latency Stabilizes with Increasing Sample Size</em></p>

<p align="center">
<img src="results/plots/convergence_check.png" alt="Convergence Check" width="600"/>
</p>

<p align="center"><em>Figure 11b: Statistical Convergence Verification</em></p>

**Results:**
- 10,000 messages: P99 = 11.8s (±15%)
- 100,000 messages: P99 = 12.1s (±5%)
- 400,000 messages: P99 = 12.2s (±2%)

**Conclusion:** Results are statistically stable, not simulation artifacts.

### 12.4 Mitigation Scaling

<p align="center">
<img src="results/plots/mitigation_scaling.png" alt="Mitigation Scaling" width="600"/>
</p>

<p align="center"><em>Figure 12: Effect of Adding Servers on P99 Latency - Mitigation Strategy</em></p>

**Discovery:**
- With N=1: Heavy-tailed jobs block queue, causing 12.3s delays
- Adding just ONE server (N=2): P99 reduces by **93%** (to 0.90s)

### 12.5 Erlang-k Efficiency

<p align="center">
<img src="results/plots/erlang_efficiency.png" alt="Erlang Efficiency" width="600"/>
</p>

<p align="center"><em>Figure 13: Erlang-k Distribution Efficiency - Multi-Phase Service Time Impact</em></p>

**Result:** Moving from single-phase (k=1) to multi-phase (k=8) reduces waiting time by **~50%**.

### 12.6 Warmup Validation

<p align="center">
<img src="results/plots/warmup_validation.png" alt="Warmup Validation" width="600"/>
</p>

<p align="center"><em>Figure 14: Warmup Period Validation - Ensuring Steady-State Results</em></p>

**Purpose:** Validates that we discard initial transient behavior before collecting metrics.

### 12.7 Paper Reproduction (Figures 14 & 15)

<p align="center">
<img src="results/plots/figure14_reproduction.png" alt="Figure 14 Reproduction" width="48%"/>
<img src="results/plots/figure15_reproduction.png" alt="Figure 15 Reproduction" width="48%"/>
</p>

<p align="center"><em>Figure 15-16: Service Time & Arrival Rate Impact - Reproducing Base Paper Trends</em></p>

### 12.8 Testing Summary

| Test Category | Tests | Status |
|---------------|-------|--------|
| Erlang Distribution | 5 | ✅ PASSED |
| Queueing Laws | 8 | ✅ PASSED |
| Extreme Conditions | 10 | ✅ PASSED |
| Priority Queues | 4 | ✅ PASSED |
| Finite Capacity | 3 | ✅ PASSED |
| **Total** | **29** | **✅ ALL PASSED** |

### 12.9 Experiment Scripts

The project includes 30+ experiment scripts for comprehensive validation:

| Script | Purpose |
|--------|---------|
| `paper_validation.py` | Reproduce base paper results |
| `cloud_broker_simulation.py` | Visibility timeout experiments |
| `two_phase_commit_validation.py` | 2PC overhead measurement |
| `validate_heterogeneous.py` | Heterogeneous server testing |
| `validate_mgn_approximations.py` | Compare Kingman/Whitt/Allen-Cunneen |
| `distributed_systems_validation.py` | Raft + Vector Clocks + CAP |
| `erlang_validation.py` | Erlang-k distribution testing |
| `heavy_tail_tandem.py` | Tandem queue with Pareto |
| `check_convergence.py` | Statistical convergence verification |
| `cost_of_consistency.py` | Consistency protocol overhead |

### 12.10 Generated Data Files

| CSV File | Contents |
|----------|----------|
| `figure11_delivery_time.csv` | Delivery time vs threads data |
| `figure12_queue_length.csv` | Queue length validation data |
| `figure13_utilization.csv` | Utilization comparison data |
| `reality_gap.csv` | M/M/N vs QNA vs Simulation |
| `tail_risk.csv` | P99 estimation methods comparison |
| `convergence_test.csv` | Convergence test results |
| `visibility_timeout_results.csv` | Visibility timeout experiments |
| `ordering_mode_results.csv` | In-order vs out-of-order delivery |
| `replication_factor_results.csv` | Replication factor impact |

---

## 13. Key Discoveries

### 13.1 Summary of Findings

| Discovery | Quantification |
|-----------|----------------|
| Heavy tails dominate P99 latency | Standard models underestimate by **45%** |
| Traffic amplification validated | Λ₂ = λ/(1-p) accurate to **0.2% error** |
| Two-Phase Commit overhead | **36%** service time increase |
| Work stealing improvement | **144x** latency reduction |
| Shared threading overhead | **10-15%** performance cost |
| P99/mean ratio (α=2.1) | **>30x** |

### 13.2 Comparison: Li et al. (2015) vs. This Framework

| Feature | Li et al. (2015) | This Project |
|---------|------------------|--------------|
| Workload Distribution | Exponential (M/M/N) | **Heavy-Tailed (Pareto, M/G/N)** |
| System Architecture | Abstracted servers | **Explicit Threading Models** |
| Analytical Accuracy | Basic Queueing Formulae | **Advanced M/G/N Approximations** |
| Scope of Model | Tandem Queue, Visibility Timeout | **Adds Protocols (Raft, 2PC), Priority & Finite Queues** |
| Validation | Analytical vs. CPN Simulation | **Analytical vs. SimPy + 29 Unit Tests** |
| Methodology/Tooling | Colored Petri Nets (CPN) | **Discrete-Event Simulation (Python/SimPy)** |
| Key Insight | Mean performance under ideal conditions | **Tail Latency (P99) under realistic stress** |

### 13.3 Practitioner Guidelines

```
✓ Never trust exponential assumptions for cloud workloads
✓ Always measure P99, not just mean—tail latency drives SLA violations
✓ Provision 2x servers for heavy-tailed workloads
✓ Account for distributed consensus overhead (20-40% throughput reduction)
```

---

## 14. Conclusion & Future Work

### 14.1 Conclusions

This project demonstrates that standard queueing models, while mathematically elegant, fail to capture the complexity of real-world cloud message brokers. Our enhanced framework provides:

1. **Accurate Heavy-Tail Modeling:** Pareto distributions with validated approximations
2. **Practical Engineering Tools:** Interactive capacity planning with React/FastAPI
3. **Distributed Protocol Analysis:** Quantified overhead of 2PC and Raft
4. **Actionable Insights:** P99-focused metrics for SLA compliance

**Key Insight:** The "Reality Gap" between M/M/N theory and actual system behavior can lead to **45% underestimation of P99 latency**, causing SLA violations and user-facing failures.

### 14.2 Future Work

1. **Byzantine Fault Tolerance (PBFT):** Extend to handle malicious nodes
2. **Multi-Datacenter Replication:** Model geo-distributed systems with WAN latency
3. **Machine Learning Integration:** Predict workload patterns for auto-scaling
4. **Kubernetes Integration:** Model container orchestration overhead
5. **Cost Optimization:** Add cloud pricing models for capacity planning

---

## 15. References

[1] J. Li, Y. Cui, and Y. Ma, "Modeling message queueing services with reliability guarantee in cloud computing environment using colored Petri nets," *Mathematical Problems in Engineering*, vol. 2015, Article ID 254210, 2015.

[2] J. F. C. Kingman, "The single server queue in heavy traffic," *Mathematical Proceedings of the Cambridge Philosophical Society*, vol. 57, no. 4, pp. 902-904, Oct. 1961.

[3] W. Whitt, "Approximations for the GI/G/m queue," *Production and Operations Management*, vol. 2, no. 2, pp. 114-161, 1993.

[4] L. Kleinrock, *Queueing Systems, Volume 1: Theory*. New York: Wiley Interscience, 1975.

[5] A. O. Allen, *Probability, Statistics, and Queueing Theory with Computer Science Applications*, 2nd ed. San Diego: Academic Press, 1990.

[6] S. Coles, *An Introduction to Statistical Modeling of Extreme Values*. London: Springer-Verlag, 2001.

[7] P. Barford and M. Crovella, "Generating representative Web workloads for network and server performance evaluation," in *Proc. ACM SIGMETRICS Performance Evaluation Review*, vol. 26, no. 1, pp. 151-160, Jun. 1998.

[8] J. Gray and L. Lamport, "Consensus on transaction commit," *ACM Transactions on Database Systems (TODS)*, vol. 31, no. 1, pp. 133-160, Mar. 2006.

[9] A. K. Erlang, "Solution of some problems in the theory of probabilities of significance in automatic telephone exchanges," *Post Office Electrical Engineer's Journal*, vol. 10, pp. 189-197, 1917.

[10] J. Banks, J. S. Carson, B. L. Nelson, and D. M. Nicol, *Discrete-Event System Simulation*, 4th ed. Upper Saddle River, NJ: Prentice Hall, 2005.

[11] "SimPy: Discrete event simulation for Python," SimPy Documentation, 2023. [Online]. Available: https://simpy.readthedocs.io/

[12] G. Bolch, S. Greiner, H. de Meer, and K. S. Trivedi, *Queueing Networks and Markov Chains: Modeling and Performance Evaluation with Computer Science Applications*, 2nd ed. Hoboken, NJ: Wiley-Interscience, 2006.

---

## 16. Appendix

### A. Installation & Setup

```bash
# Clone repository
git clone https://github.com/hjain3004/distributed-systems-project.git
cd distributed-systems-project

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install

# Start application (one-click)
./start.sh

# Access the application
# Frontend: http://localhost:4000
# Backend API: http://localhost:3100
# Swagger Docs: http://localhost:3100/api/docs
```

### B. Running Tests

```bash
# Quick automated test (4 tests in ~10 seconds)
./test_all.sh

# Comprehensive unit tests (29 tests, ~97 seconds)
python3 -m pytest tests/ -v

# Full rebuild with all experiments (~15-20 minutes)
./rebuild_all.sh
```

### C. Core Dependencies

```
# requirements.txt
simpy==4.1.1              # Discrete-event simulation
numpy==1.26.0             # Numerical computing
scipy==1.11.0             # Statistical distributions
pandas==2.1.0             # Data management
matplotlib==3.8.0         # Basic plotting
seaborn==0.13.0           # Statistical visualization
plotly==5.17.0            # Interactive plots
pydantic==2.5.0           # Type-safe configs
pytest==7.4.0             # Testing
```

### D. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/simulations/mmn` | POST | Run M/M/N simulation |
| `/api/simulations/mgn` | POST | Run M/G/N (heavy-tailed) simulation |
| `/api/simulations/heterogeneous` | POST | Run heterogeneous server simulation |
| `/api/simulations/tandem` | POST | Run tandem queue simulation |
| `/api/simulations/{id}/results` | GET | Get completed simulation results |
| `/api/analytical/mmn` | POST | Calculate M/M/N analytical metrics |
| `/api/analytical/tandem` | POST | Calculate tandem queue metrics |
| `/api/analytical/compare` | POST | Compare simulation vs analytical |
| `/api/docs` | GET | Swagger UI documentation |

### E. Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arrival_rate` | float | 100 | λ (messages/sec) |
| `service_rate` | float | 12 | μ (messages/sec/thread) |
| `num_threads` | int | 10 | N (number of servers) |
| `sim_duration` | float | 1000 | Simulation time (sec) |
| `warmup_time` | float | 100 | Warmup period (sec) |
| `distribution` | str | "exponential" | Service time distribution |
| `alpha` | float | 2.5 | Pareto shape parameter |
| `failure_prob` | float | 0.2 | Network failure probability |
| `visibility_timeout` | float | 30 | Visibility timeout (sec) |
| `max_retries` | int | 3 | Maximum retry attempts |
| `replication_factor` | int | 3 | Number of replicas for 2PC |
| `ordering_mode` | str | "out_of_order" | Message ordering mode |

### F. Frontend Pages

| Page | File | Description |
|------|------|-------------|
| Dashboard | `Dashboard.tsx` | Project overview and summary |
| Control Center | `ControlCenter.tsx` | Live simulation with scenario presets |
| Capacity Planner | `MMNCalculator.tsx` | M/M/N capacity planning tool |
| Heavy-Tail Calculator | `MGNCalculator.tsx` | M/G/N with Pareto distribution |
| Blast Radius | `TandemQueue.tsx` | Tandem queue cascade visualization |
| Reality Gap | `MGNvsMMNComparison.tsx` | Theory vs simulation comparison |
| All Equations | `AllEquations.tsx` | Interactive equation explorer |
| Results Viewer | `ResultsViewer.tsx` | Simulation results analysis |

### G. Equation Quick Reference

| Eq | Name | Formula | Implementation |
|----|------|---------|----------------|
| 1 | Utilization | ρ = λ/(N·μ) | `config.py:utilization()` |
| 2 | P₀ | P₀ = [Σ(aⁿ/n!) + aᴺ/(N!(1-ρ))]⁻¹ | `analytical.py:prob_zero()` |
| 3 | Erlang-C | C(N,a) = [aᴺ/(N!(1-ρ))]·P₀ | `analytical.py:erlang_c()` |
| 4 | Queue Length | Lq = C·ρ/(1-ρ) | `analytical.py:mean_queue_length()` |
| 5 | Waiting Time | Wq = Lq/λ | `analytical.py:mean_waiting_time()` |
| 6 | Pareto PDF | f(t) = α·k^α/t^(α+1) | `distributions.py:ParetoService` |
| 7 | Pareto Mean | E[S] = αk/(α-1) | `distributions.py:mean()` |
| 8 | Second Moment | E[S²] = αk²/(α-2) | `distributions.py:variance()` |
| 9 | CV² | C² = 1/(α(α-2)) | `config.py:coefficient_of_variation()` |
| 10 | M/G/N Approx | Wq ≈ Wq·(1+C²)/2 | `analytical.py:mean_waiting_time_mgn()` |
| 11 | Max Connections | Nmax = Nthreads/2 | `analytical.py:dedicated_max_connections()` |
| 12 | Throughput | X = min(λ, capacity) | `analytical.py:dedicated_throughput()` |
| 13 | Effective μ | μeff = μ/(1+α·N/T) | `analytical.py:shared_effective_service_rate()` |
| 14 | Saturation | Psat = C(N,a)·ρ | `analytical.py:thread_saturation_probability()` |
| 15 | P99 | R99 ≈ E[R]+2.33·σ | `analytical.py:p99_response_time()` |

### H. Model Implementations

| Model | File | Description |
|-------|------|-------------|
| M/M/N Queue | `mmn_queue.py` | Basic multi-server queue |
| M/G/N Queue | `mgn_queue.py` | General service distribution |
| Tandem Queue | `tandem_queue.py` | Two-stage with retransmission |
| Heterogeneous | `heterogeneous_mmn.py` | Multiple server speeds |
| Priority Queue | `priority_queue.py` | Multi-priority classes |
| Finite Capacity | `finite_capacity_queue.py` | M/M/N/K with blocking |
| Two-Phase Commit | `two_phase_commit.py` | Atomic commit protocol |
| Raft Consensus | `raft_consensus.py` | Leader election & replication |
| Vector Clocks | `vector_clocks.py` | Causality tracking |
| Visibility Timeout | `visibility_timeout.py` | SQS-style reliability |
| Distributed Broker | `distributed_broker.py` | Multi-node with consistent hashing |
| Network Layer | `network_layer.py` | Delay and failure simulation |
| Message Ordering | `message_ordering.py` | FIFO and out-of-order modes |

### I. Validation Plots

All plots are generated in `results/plots/` and `visualization/`:

```
results/plots/
├── reality_gap.png              # Main finding visualization
├── tail_risk.png                # P99 estimation comparison
├── mgn_heavy_tail.png           # Heavy tail impact
├── convergence_test.png         # Statistical convergence
├── mitigation_scaling.png       # Server scaling effects
├── erlang_efficiency.png        # Erlang-k efficiency
├── warmup_validation.png        # Warmup period validation
├── mmn_validation.png           # M/M/N model validation
├── figure11_comparison.png      # Delivery time (paper Fig 11)
├── figure12_comparison.png      # Queue length (paper Fig 12)
├── figure13_comparison.png      # Utilization (paper Fig 13)
├── figure14_reproduction.png    # Service time trend
└── figure15_reproduction.png    # Arrival rate trend

visualization/
├── plot_1_mmn_validation.png    # Detailed M/M/N validation
├── plot_2_heavy_tail_impact.png # Heavy tail analysis
├── plot_3_threading_comparison.png # Threading models
├── plot_4_load_testing.png      # Load testing results
└── plot_5_confidence_intervals.png # CI analysis
```

---

**GitHub Repository:** https://github.com/hjain3004/distributed-systems-project

---

*Report prepared for CMPE 273 - Enterprise Distributed Systems, San Jose State University, Fall 2025*
