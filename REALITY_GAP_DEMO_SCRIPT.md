# Reality Gap Demo Script (2 Minutes)

**URL:** http://localhost:4000/compare

---

## Setup (before demo)
```bash
cd distributed-systems-project
./start.sh
```
Open http://localhost:4000/compare

---

## Demo Flow with Speaker Notes

### 1. Start Low (15 sec)

**Action:** Set Variance (Cv²) = 1.0

**Say:**
> "This is what the base paper assumes - exponential service times, variance equals one. See how all three lines track together? Blue is the textbook M/M/N formula, green is the M/G/N approximation, red is actual simulation. When variance is low, they all agree. The theory works."

---

### 2. Crank Up Variance (45 sec)

**Action:** Slowly drag Variance slider from 1.0 → 2.5

**Say:**
> "Now let's add realistic heavy-tailed traffic. Think video transcoding, ML inference, complex database queries - jobs where most are fast but some are huge."

*[Pause as lines diverge]*

> "Watch the red line. That's simulation - actual system behavior. See how it spikes above the others? It's jagged, unpredictable. The blue textbook line stays smooth and optimistic. That gap between blue and red? That's your SLA violation waiting to happen."

---

### 3. Show the Gap Numbers (30 sec)

**Action:** Point to the three metric cards at the bottom

**Say:**
> "Look at these numbers at 95% utilization. The textbook predicts around 140 milliseconds. Reality shows nearly 300 milliseconds. That's a 2x error margin. If you sized your system using the textbook formula, you're running at half the capacity you actually need."

---

### 4. Make It Worse (30 sec)

**Action:** Drag Variance slider to 5.0 or higher

**Say:**
> "And it gets worse. Crank up the variance - this is what you see with very bursty workloads like video processing or batch ML jobs."

*[Watch gap explode to 3-4x]*

> "Now we're at 3 to 4x error. The textbook is completely wrong. This is why Amazon, Google, Netflix all say 'don't trust the formulas' - they simulate everything."

---

## Close (5 sec)

**Say:**
> "Bottom line: the textbook lies when you have heavy tails. Simulate your actual workload, and budget 20 to 50 percent more capacity than the formulas suggest."
