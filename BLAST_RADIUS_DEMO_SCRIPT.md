# Blast Radius Demo Script (2 Minutes)

**URL:** http://localhost:4000/tandem

---

## Page Layout & What You're Looking At

### Left Panel: Controls
- **Input Traffic (λ)**: Arrival rate of requests
- **Node 1 Capacity (μ1)**: How fast Node 1 processes
- **Node 2 Capacity (μ2)**: How fast Node 2 processes  
- **Failure Prob (p)**: Network failure rate causing retransmissions

**Speaker Notes for Controls:**
> "On the left we have our pipeline configuration. Lambda is incoming traffic rate. Mu-1 and Mu-2 are how fast each node processes requests. And failure probability - this is the network reliability, how often messages fail and need to retry."

### Top Right: Toggle Switch
- **Green "Smooth Workload"**: Poisson arrivals (what paper assumes)
- **Red "Bursty Workload"**: Pareto/heavy-tailed arrivals (reality)

**Speaker Notes for Toggle:**
> "This toggle is the key. Green means smooth Poisson traffic - what the textbook assumes. Red means bursty Pareto traffic - what real systems actually see."

### Middle: Two Live Graphs

**Left Graph: Node 1 (The Source)**
- Orange line showing real-time latency
- Y-axis: Latency in milliseconds (0-2000ms)
- First stage - the message broker

**Right Graph: Node 2 (The Victim)**  
- Red line showing real-time latency
- Same Y-axis scale for direct comparison
- Second stage - the receiver

**Speaker Notes for Graphs:**
> "These two graphs show real-time latency at each stage. Left is Node 1 - the source, like a message broker. Right is Node 2 - the downstream receiver. Same Y-axis scale so you can directly compare. Watch how they behave differently when we flip the switch."

### Bottom: Metrics (from Backend API)
- **Total Latency**: End-to-end time through both stages (in ms)
- **Load Amplification**: Shows as percentage, e.g., "11%" means Node 2 sees 11% more traffic than Node 1
  - Calculated as: `(λ₂/λ - 1) × 100` where `λ₂ = λ/(1-p)`
  - At p=10%: 11% amplification
  - At p=20%: 25% amplification
  - At p=30%: 43% amplification
- **Node 2 Utilization**: How busy Node 2 is (percentage)

**Note:** These metrics come from the backend API call. If the backend isn't running, you won't see these numbers, but the graphs still work.

**Speaker Notes for Metrics:**
> "At the bottom we have the analytical metrics from the backend. Total latency is end-to-end in milliseconds. Load amplification shows the percentage of extra traffic Node 2 sees - with 10% failure rate, that's 11% more traffic. And Node 2 utilization tells us how close to overload it is. Notice the utilization is higher than you'd expect from just the input rate - that's the amplification effect."

---

## Demo Flow with Speaker Notes

### 1. Start Smooth (20 sec)

**Action:** Make sure "Bursty Workload" toggle is OFF (green)

**Say:**
> "This is a two-stage pipeline - like a message broker feeding a receiver. Right now traffic is smooth, Poisson arrivals. Watch both graphs - Node 1 and Node 2 have similar, calm latency patterns."

---

### 2. Flip the Switch (40 sec)

**Action:** Toggle "Bursty Workload" ON (turns red)

**Say:**
> "Now let's make the input bursty - this is what real traffic looks like. Video uploads, batch jobs, ML inference."

*[Pause - watch the graphs for 3-4 seconds]*

> "Look at Node 1 - occasional spikes, that's the heavy tail. But Node 2 is WAY worse. The spikes are bigger, more frequent. This is the blast radius."

**Point to the graphs:**
> "Node 2 is 'the victim'. It receives clumped, bursty output from Node 1. Those bursts pile up and amplify."

---

### 3. Show the Amplification (30 sec)

**Action:** Point to the metrics at the bottom

**Say:**
> "Look at Load Amplification. With 10% failure rate, Node 2 sees 11% more traffic than Node 1."

> "But the VARIANCE amplification is even worse - you see it in the graphs. Small bursts at Node 1 become huge bursts at Node 2."

---

### 4. Make It Worse (30 sec)

**Action:** Increase "Failure Prob" slider to 20-30%

**Say:**
> "Increase the failure rate - more retransmissions, more amplification."

*[Watch metrics update]*

> "At 20% failure, Node 2 sees 25% more traffic. At 30%, it's 43% more. This is the paper's formula: Lambda-2 equals Lambda divided by one minus p."

---

## One-Liner Close

> "Bursts don't just propagate - they amplify. Size your downstream services for the blast radius, not just average load."

---

## Why Node 2 Gets Worse (Background Knowledge)

| Smooth Mode (Toggle OFF) | Bursty Mode (Toggle ON) |
|--------------------------|-------------------------|
| Both lines hover around same level | Node 2 spikes much higher |
| Small random noise | Node 1 has occasional spikes |
| Variance label shows "LOW" | Node 2 shows "EXTREME (Amplified)" |

**The Theory:**

1. **Burke's Theorem Violation**: Output of a queue is only Poisson if service is exponential. With Pareto service, output is clumped.

2. **Clumping Effect**: When Node 1 has a slow request, others queue up. When it finishes, they all release at once → burst to Node 2.

3. **Variance Amplification**: Node 2's input variance > Node 1's input variance.

4. **Retransmission Load**: Failed messages retry, adding λ/(1-p) load on top of variance amplification.

**Speaker Notes (if asked "why does this happen?"):**
> "There's a theorem called Burke's Theorem that says the output of a queue is Poisson only if the service time is exponential. But with heavy-tailed Pareto service, that breaks down. When Node 1 gets a slow request, everything behind it queues up. When it finally finishes, all those queued requests burst out at once - they arrive at Node 2 in a clump, not smoothly. So Node 2 sees higher variance than Node 1 received. Add retransmissions on top, and Node 2 is getting hit from both sides - more load AND more variance."

**Key Insight:**
> "Node 1 might look fine at 70% utilization. But Node 2 sees amplified load AND variance - it could be at 90%+ and about to collapse."

---

## What's Happening in the Backend

### Live Graphs (Client-Side Simulation)

The graphs update every 200ms (5Hz) with simulated latency values. The frontend code (`TandemQueue.tsx`) does this:

```javascript
// Node 1 latency calculation
let lat1 = (1 / mu1) * 1000;  // Base service time in ms
if (isBursty) {
  if (Math.random() > 0.9) lat1 *= (5 + Math.random() * 10);  // 10% chance of 5-15x spike
} else {
  lat1 += (Math.random() - 0.5) * 20;  // Small noise in smooth mode
}
lat1 = lat1 / (1 - Math.min(rho1, 0.99));  // Queueing delay factor

// Node 2 latency - THE AMPLIFICATION
let lat2 = (1 / mu2) * 1000;
let amplification = 1.0;

if (isBursty) {
  // Burst propagation! If Node 1 spiked, Node 2 gets flooded
  if (lat1 > 500) {
    amplification = 2.5;  // Massive amplification when Node 1 is slow
  }
  // Also Node 2 has its own spikes (15% chance, 8-23x multiplier)
  if (Math.random() > 0.85) lat2 *= (8 + Math.random() * 15);
} else {
  lat2 += (Math.random() - 0.5) * 20;  // Small noise in smooth mode
}

lat2 = (lat2 * amplification) / (1 - Math.min(rho2, 0.99));
```

**Key points:**
1. Node 1 has 10% spike chance in bursty mode (5-15x multiplier)
2. When Node 1 spikes above 500ms, Node 2 gets 2.5x amplification
3. Node 2 ALSO has its own 15% spike chance (8-23x multiplier) - more frequent than Node 1!
4. Both use queueing delay factor: `latency / (1 - ρ)` which explodes as utilization approaches 1

**Speaker Notes (if asked "how do the graphs work?"):**
> "The graphs are client-side simulation running at 5 updates per second. For each tick, we calculate latency using the queueing formula - base service time divided by one minus utilization. In bursty mode, Node 1 has a 10% chance of spiking 5 to 15x. But here's the key: Node 2 has TWO sources of spikes. First, when Node 1 spikes above 500ms, Node 2 gets a 2.5x amplification factor - that models the clumping effect. Second, Node 2 has its own 15% spike chance with an even bigger multiplier. So Node 2 spikes more often AND harder than Node 1. That's the blast radius."

### Metrics (Backend API Call)

When you change sliders, the frontend calls:
```
POST /api/analytical/tandem
```

**Request body:**
```json
{
  "arrival_rate": 20,
  "n1": 4, "mu1": 10,
  "n2": 4, "mu2": 10,
  "network_delay": 0.05,
  "failure_prob": 0.1
}
```

**Backend calculates** (in `src/analysis/analytical.py`):

```python
class TandemQueueAnalytical:
    def __init__(self, ...):
        # Stage 2 sees AMPLIFIED arrival rate
        self.Lambda2 = lambda_arrival / (1 - failure_prob)
        
        # Utilizations
        self.rho1 = lambda_arrival / (n1 * mu1)
        self.rho2 = self.Lambda2 / (n2 * mu2)  # Higher!
    
    def total_message_delivery_time(self):
        # T = W1 + S1 + (2+p)·D + W2 + S2
        return W1 + S1 + network_time + W2 + S2
```

**Speaker Notes (if asked "what's the backend doing?"):**
> "The metrics at the bottom come from the backend API. When you move a slider, we POST the parameters to the analytical endpoint. The backend uses the TandemQueueAnalytical class which implements the formulas from the Li et al. paper. The key calculation is Lambda-2 equals Lambda divided by one minus p - that's the traffic inflation formula. With 10% failure rate, Stage 2 sees 11% more traffic. The total latency formula adds up waiting time at Stage 1, service time, network delay with retry factor, then waiting and service at Stage 2."

**Key formulas used:**
- `Λ₂ = λ/(1-p)` — Traffic inflation (Eq. 3 from Li et al.)
- `T_network = (2+p)·D` — Expected network time with retries
- `W_q = C(N,a)·ρ/(1-ρ)·(1/μ)` — Erlang-C waiting time

### The Tandem Queue Model (from the paper)

```
Publishers → [Stage 1: Broker] → Network → [Stage 2: Receiver] → Consumers
     λ          n1 servers        D, p        n2 servers
                   μ1                            μ2
                   
                        ↑
                   Retries (p)
```

Stage 2 sees `λ/(1-p)` arrivals because failed messages retry. With p=20%, that's 25% more load on Stage 2 than Stage 1.

**Speaker Notes (if asked "what's the architecture?"):**
> "This is the tandem queue model from the Li et al. paper. Publishers send messages to Stage 1, the broker. The broker processes them and sends over the network to Stage 2, the receiver. The network has delay D and failure probability p. When a message fails, it retries - that's where the traffic inflation comes from. Stage 2 sees lambda divided by one minus p arrivals. So if p is 20%, Stage 2 sees 25% more traffic than Stage 1. That's before we even consider variance amplification."
