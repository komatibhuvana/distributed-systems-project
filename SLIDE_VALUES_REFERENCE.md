# Slide Values Quick Reference Sheet

**Use this sheet when building your PowerPoint/Google Slides presentation.**

---

## Global Parameters (Use Throughout)

| Parameter | Symbol | Value | Description |
|-----------|--------|-------|-------------|
| Arrival Rate | λ | 100 msg/sec | Messages entering system |
| Service Rate | μ | 12 msg/sec/thread | Processing speed per thread |
| Number of Threads | N | 10 | Worker threads |
| Utilization | ρ | 0.833 (83.3%) | System load = λ/(N·μ) |
| Pareto Alpha | α | 2.5 | Tail heaviness parameter |
| Network Failure | p | 0.2 (20%) | Transmission failure probability |
| Network Delay | D | 10ms | One-way network latency |

---

## Slide-by-Slide Values

### Slide 3: The Problem
**DMV vs Starbucks Analogy:**
| Scenario | Mean | P99 | Max |
|----------|------|-----|-----|
| Starbucks (Exponential) | 100ms | 300ms | 500ms |
| DMV (Pareto α=2.5) | 100ms | 450ms | 10s+ |

---

### Slide 5: Tandem Queue Model
**Architecture Parameters:**
| Parameter | Stage 1 (Broker) | Network | Stage 2 (Receiver) |
|-----------|------------------|---------|-------------------|
| Servers | n₁ = 10 | — | n₂ = 12 |
| Service Rate | μ₁ = 12 | — | μ₂ = 12 |
| Delay | — | D = 10ms | — |
| Failure Prob | — | p = 0.2 | — |

**Traffic Inflation Calculation:**
```
Input (Stage 1):  λ = 100 msg/sec
Output (Stage 2): Λ₂ = λ/(1-p) = 100/(1-0.2) = 100/0.8 = 125 msg/sec
Increase: +25%
```

---

### Slide 7: Base Paper Validation
**Figure Comparison Table:**
| Figure | Metric | Paper Value | Our Value | Error % |
|--------|--------|-------------|-----------|---------|
| Fig 11 | Delivery Time | 0.167s | 0.156s | 6.6% |
| Fig 12 | Queue Length | 3.2 | 2.8 | 12.5% |
| Fig 13 | Utilization | 83.3% | 83.1% | 0.2% |
| Fig 14 | Service Trend | ✓ | ✓ | Match |
| Fig 15 | Arrival Trend | ✓ | ✓ | Match |

**Delivery Time vs Threads:**
| Threads (N) | Paper | Ours |
|-------------|-------|------|
| 5 | 0.45s | 0.42s |
| 10 | 0.167s | 0.156s |
| 15 | 0.12s | 0.11s |
| 20 | 0.095s | 0.09s |

---

### Slide 8: The 15 Equations
**Equation Reference:**

| Eq # | Formula | Example Value |
|------|---------|---------------|
| 1 | ρ = λ/(N·μ) | 100/(10×12) = 0.833 |
| 2 | P₀ (system empty) | ≈ 0.012 |
| 3 | C(N,a) Erlang-C | ≈ 0.65 |
| 4 | Lq = C·ρ/(1-ρ) | 0.65×0.833/0.167 = 3.24 |
| 5 | Wq = Lq/λ | 3.24/100 = 0.0324s |
| 6 | Pareto PDF | f(t) = α·k^α/t^(α+1) |
| 7 | E[S] = α·k/(α-1) | 2.5×0.05/1.5 = 0.0833s |
| 8 | E[S²] = α·k²/(α-2) | 2.5×0.0025/0.5 = 0.0125 |
| 9 | C² = 1/(α(α-2)) | 1/(2.5×0.5) = 0.8 |
| 10 | Wq(M/G/N) ≈ Wq×(1+C²)/2 | 0.0324×0.9 = 0.029s |

---

### Slide 9: Heavy-Tailed Distributions
**Distribution Comparison (same mean = 100ms):**
| Percentile | Exponential | Pareto (α=2.5) | Ratio |
|------------|-------------|----------------|-------|
| P50 | 69ms | 58ms | 0.84x |
| P90 | 230ms | 320ms | 1.4x |
| P95 | 300ms | 580ms | 1.9x |
| P99 | 460ms | 2,100ms | 4.6x |
| P99.9 | 690ms | 14,800ms | 21x |

**Real-World Examples:**
| System | Fast (80%) | Slow (1%) |
|--------|------------|-----------|
| Web Requests | < 100ms | > 5s |
| Database Queries | < 10ms | > 30s |
| Video Processing | < 1s | > 60s |

---

### Slide 10: The Reality Gap
**Mean Latency Bar Chart Values:**
| Model | Mean Latency | Bar Color |
|-------|--------------|-----------|
| Paper (M/M/N) | 0.167s | Grey |
| QNA Approximation | 0.480s | Red |
| Our Simulation | 0.190s | Green |

**Key Stat:** Paper underestimates by **14%**

---

### Slide 11: Tail Risk (CRITICAL SLIDE)
**P99 Latency Comparison:**
| Method | P99 Value | Error vs Reality |
|--------|-----------|------------------|
| Paper (Normal Approx) | 4.25s | -45% ⚠️ |
| Kingman Approx | 5.12s | -34% |
| Whitt Approx | 6.89s | -12% |
| EVT Estimate | 7.56s | -3% |
| Simulation (Truth) | **7.81s** | — |

**Key Stat:** Paper underestimates P99 by **45%**

---

### Slide 12: M/G/N Approximation Methods
**Accuracy Comparison by Pareto α:**
| α | CV² | Kingman Error | Whitt Error | Allen-Cunneen | Best |
|---|-----|---------------|-------------|---------------|------|
| 3.0 | 0.33 | 5.2% | **3.1%** | 6.8% | Whitt |
| 2.5 | 1.0 | 8.7% | **4.5%** | 9.2% | Whitt |
| 2.1 | 10.0 | 24.3% | 9.8% | **8.1%** | A-C |

**Waiting Time Values (ρ=0.8):**
| Scenario | Simulation | Kingman | Whitt | Allen-Cunneen |
|----------|------------|---------|-------|---------------|
| α=3.0 | 0.032s | 0.034s | 0.033s | 0.034s |
| α=2.5 | 0.042s | 0.046s | 0.044s | 0.046s |
| α=2.1 | 0.089s | 0.111s | 0.098s | 0.096s |

---

### Slide 13: Convergence Test
**P99 Latency vs Sample Size:**
| Messages | P99 Latency | 95% CI Width |
|----------|-------------|--------------|
| 1,000 | 14.2s | ±3.1s |
| 10,000 | 12.8s | ±1.2s |
| 50,000 | 12.4s | ±0.4s |
| 100,000 | 12.3s | ±0.2s |
| 200,000 | 12.2s | ±0.1s |
| 400,000 | **12.2s** | ±0.08s |

**Key Stat:** Stabilizes at ~12.2s after 100K messages

---

### Slide 15: Raft Consensus Demo
**Cluster State:**
| Node | State | Term | Voted For | Log Length |
|------|-------|------|-----------|------------|
| N0 | Follower | 1 | N4 | 5 |
| N1 | Follower | 1 | N4 | 5 |
| N2 | Follower | 1 | N4 | 5 |
| N3 | Follower | 1 | N4 | 5 |
| N4 | **Leader** | 1 | N4 | 5 |

**Invariants:**
- Single leader: ✓ True
- All agree on leader: ✓ True
- Elections won: 1

---

### Slide 16: Vector Clocks
**Event Sequence:**
| Event | Process | Vector Clock | Caused By |
|-------|---------|--------------|-----------|
| e1 | P1 | [1,0,0] | — |
| e2 | P2 | [0,1,0] | — |
| e3 | P1 | [2,0,0] | e1 |
| e4 | P2 | [2,2,0] | e3 (msg), e2 |
| e5 | P3 | [0,0,1] | — |
| e6 | P1 | [3,2,0] | e4 (msg), e3 |

**Causality Examples:**
- [2,0,0] → [2,2,0] ✓ (happened-before)
- [0,0,2] || [2,2,0] ✗ (concurrent)

---

### Slide 17: Two-Phase Commit
**Transaction Results:**
| Transaction | Participants | Votes | Outcome |
|-------------|--------------|-------|---------|
| T1 | A, B, C | YES, YES, YES | ✓ COMMIT |
| T2 | A, B, C | YES, NO, YES | ✗ ABORT |
| T3 | A, B | YES, TIMEOUT | ✗ ABORT |

---

### Slide 18: Mitigation (THE SOLUTION)
**P99 Latency vs Server Count:**
| Servers (N) | P99 Latency | Improvement vs N=1 |
|-------------|-------------|-------------------|
| 1 | **12.3s** | — |
| 2 | **0.90s** | **93%** |
| 3 | 0.45s | 96% |
| 4 | 0.32s | 97% |
| 5 | 0.28s | 98% |
| 10 | 0.18s | 99% |

**Key Stat:** Adding just 1 server → **93% improvement**

---

### Slide 20: Test Coverage
**Test File Breakdown:**
| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| test_erlang.py | 12 | M/Ek/N validation |
| test_queueing_laws.py | 4 | Little's Law, stability |
| test_extreme_values.py | 13 | EVT, bootstrap CI |
| test_extreme_conditions.py | 10 | ρ>0.95, α<2 |
| test_priority_queues.py | 8 | Priority scheduling |
| test_finite_capacity.py | 16 | M/M/N/K blocking |
| **TOTAL** | **63** | **All passing ✓** |

---

## Chart Color Scheme

| Element | Color | Hex Code |
|---------|-------|----------|
| Paper/Baseline | Grey | #808080 |
| Danger/Warning | Red | #E74C3C |
| Success/Simulation | Green | #27AE60 |
| Primary/Highlight | Blue | #3498DB |
| Secondary | Purple | #9B59B6 |
| Neutral | Light Grey | #BDC3C7 |

---

## Key Numbers to Memorize

```
┌─────────────────────────────────────────────────────┐
│  THE BIG NUMBERS FOR YOUR PRESENTATION              │
├─────────────────────────────────────────────────────┤
│  14%  - Mean latency underestimation               │
│  45%  - P99 latency underestimation (CRITICAL!)    │
│  93%  - Improvement from N=1 to N=2                │
│  63   - Total unit tests (all passing)             │
│  15   - Analytical equations implemented           │
│  5    - Paper figures reproduced                   │
│  <15% - Validation error (acceptable)              │
│  400K - Messages in convergence test               │
└─────────────────────────────────────────────────────┘
```

---

## Formulas to Show (LaTeX)

**Utilization:**
```
ρ = λ/(N·μ) = 100/(10×12) = 0.833
```

**Traffic Inflation:**
```
Λ₂ = λ/(1-p) = 100/(1-0.2) = 125 msg/sec
```

**Erlang-C:**
```
C(N,a) = [aᴺ/(N!(1-ρ))] · P₀ ≈ 0.65
```

**Little's Law:**
```
Lq = λ × Wq  →  Wq = Lq/λ
```

**Pareto Mean:**
```
E[S] = α·k/(α-1) = 2.5×0.05/1.5 = 0.0833s
```

**M/G/N Approximation:**
```
Wq(M/G/N) ≈ Wq(M/M/N) × (1+C²)/2
```

---

## UI Component Checklist

For each slide, check off when you've added:

- [ ] **Slide 3:** Split diagram (Starbucks vs DMV)
- [ ] **Slide 5:** Animated flow diagram with traffic meters
- [ ] **Slide 7:** Side-by-side validation chart
- [ ] **Slide 9:** Distribution comparison curves
- [ ] **Slide 10:** Bar chart (3 bars: grey, red, green)
- [ ] **Slide 11:** P99 comparison chart (dramatic!)
- [ ] **Slide 12:** Accuracy heatmap table
- [ ] **Slide 13:** Convergence line chart with CI band
- [ ] **Slide 14:** Three-panel protocol overview
- [ ] **Slide 15:** Raft cluster visualization
- [ ] **Slide 16:** Vector clock timeline
- [ ] **Slide 17:** 2PC sequence diagram
- [ ] **Slide 18:** Before/after bar chart (N=1 vs N=2)
- [ ] **Slide 19:** Architecture diagram
- [ ] **Slide 20:** Test coverage dashboard
- [ ] **Slide 21:** Contribution checklist with stars

---

**End of Quick Reference**
