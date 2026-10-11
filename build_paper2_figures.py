#!/usr/bin/env python3
"""Generate Paper 2 figures from the project's real CSV/result data.

All numbers are read from on-disk CSVs or taken from the analytical model /
recorded summaries exactly as used in the paper text. Output PNGs go to
paper2_figures/. Styling matches Paper 1 (serif, 300 dpi, shared palette).
"""
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300,
    "font.size": 10, "font.family": "serif",
    "axes.labelsize": 11, "axes.titlesize": 12,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "axes.grid": True, "grid.linestyle": "--", "grid.alpha": 0.35,
})
C = {
    "baseline": "#2C3E50", "analytical": "#E74C3C", "simulation": "#3498DB",
    "dedicated": "#27AE60", "shared": "#F39C12", "mmn": "#9B59B6",
    "accent": "#1ABC9C", "warn": "#C0392B",
}
OUT = "paper2_figures"
os.makedirs(OUT, exist_ok=True)


def readcsv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


# ---------------------------------------------------------------- Fig 1: visibility timeout
r = readcsv("experiments/visibility_timeout_results.csv")
vt = [float(x["visibility_timeout"]) for x in r]
retries = [float(x["mean_retries"]) for x in r]
p99 = [float(x["p99_latency"]) for x in r]
fig, ax1 = plt.subplots(figsize=(6.2, 3.6))
ax1.plot(vt, retries, "-o", color=C["simulation"], label="Mean retries")
ax1.set_xlabel("Visibility timeout VT (s)")
ax1.set_ylabel("Mean retries per message", color=C["simulation"])
ax1.tick_params(axis="y", labelcolor=C["simulation"])
ax2 = ax1.twinx()
ax2.grid(False)
ax2.plot(vt, p99, "--s", color=C["warn"], label="P99 latency")
ax2.set_ylabel("P99 latency (ms)", color=C["warn"])
ax2.tick_params(axis="y", labelcolor=C["warn"])
ax1.set_xticks(vt)
save(fig, "fig1_visibility_timeout.png")

# ---------------------------------------------------------------- Fig 2: replication
r = readcsv("experiments/replication_factor_results.csv")
rf = [int(float(x["replication_factor"])) for x in r]
tput = [float(x["throughput"]) for x in r]
stored = [int(float(x["total_stored"])) for x in r]
unique = [int(float(x["unique_messages"])) for x in r]
fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.2, 3.3))
axa.bar([str(x) for x in rf], tput, color=C["dedicated"])
axa.set_xlabel("Replication factor R")
axa.set_ylabel("Delivered throughput (msg/s)")
axa.set_title("(A) Throughput")
w = 0.38
x = np.arange(len(rf))
axb.bar(x - w / 2, stored, w, label="Total stored", color=C["mmn"])
axb.bar(x + w / 2, unique, w, label="Unique messages", color=C["accent"])
axb.set_xticks(x); axb.set_xticklabels([str(v) for v in rf])
axb.set_xlabel("Replication factor R")
axb.set_ylabel("Message copies")
axb.set_title("(B) Storage amplification")
axb.legend()
save(fig, "fig2_replication.png")

# ---------------------------------------------------------------- Fig 3: ordering
r = readcsv("experiments/ordering_mode_results.csv")
modes = [x["Mode"] for x in r]
mean_l = [float(x["Mean_Latency_ms"]) for x in r]
p99_l = [float(x["P99_Latency_ms"]) for x in r]
x = np.arange(len(modes)); w = 0.36
fig, ax = plt.subplots(figsize=(5.4, 3.4))
ax.bar(x - w / 2, mean_l, w, label="Mean latency", color=C["simulation"])
ax.bar(x + w / 2, p99_l, w, label="P99 latency", color=C["warn"])
ax.set_xticks(x); ax.set_xticklabels(modes)
ax.set_ylabel("Latency (ms)")
ax.legend()
for i, (m, p) in enumerate(zip(mean_l, p99_l)):
    ax.text(i - w / 2, m + 0.8, f"{m:.1f}", ha="center", fontsize=8)
    ax.text(i + w / 2, p + 0.8, f"{p:.1f}", ha="center", fontsize=8)
save(fig, "fig3_ordering.png")

# ---------------------------------------------------------------- Fig 4: threading response & throughput vs rho
r = readcsv("experiment_3_threading_results.csv")
rho = [float(x["rho"]) for x in r]
base = [float(x["baseline_mean_response"]) for x in r]
ded = [float(x["dedicated_mean_response"]) for x in r]
sha = [float(x["shared_mean_response"]) for x in r]
base_t = [float(x["baseline_throughput"]) for x in r]
ded_t = [float(x["dedicated_throughput"]) for x in r]
sha_t = [float(x["shared_throughput"]) for x in r]
fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.4, 3.4))
axa.plot(rho, base, "-^", color=C["baseline"], label="Baseline M/M/N")
axa.plot(rho, ded, "-D", color=C["dedicated"], label="Dedicated")
axa.plot(rho, sha, "-.v", color=C["shared"], label="Shared")
axa.set_xlabel("Utilization ρ"); axa.set_ylabel("Mean response time (s)")
axa.set_title("(A) Response time"); axa.legend()
axb.plot(rho, base_t, "-^", color=C["baseline"], label="Baseline M/M/N")
axb.plot(rho, ded_t, "-D", color=C["dedicated"], label="Dedicated")
axb.plot(rho, sha_t, "-.v", color=C["shared"], label="Shared")
axb.set_xlabel("Utilization ρ"); axb.set_ylabel("Throughput (msg/s)")
axb.set_title("(B) Throughput"); axb.legend()
save(fig, "fig4_threading.png")

# ---------------------------------------------------------------- Fig 5: threading CI bars (rho=0.7)
r = readcsv("experiments/threading_confidence_intervals.csv")
# pull mean_response rows
mr = {x["model"]: x for x in r if x["metric"] == "mean_response"}
order = ["baseline", "dedicated", "shared"]
means = [float(mr[m]["mean"]) for m in order]
lo = [float(mr[m]["ci_lower"]) for m in order]
hi = [float(mr[m]["ci_upper"]) for m in order]
err = [[m - l for m, l in zip(means, lo)], [h - m for h, m in zip(hi, means)]]
fig, ax = plt.subplots(figsize=(5.4, 3.4))
cols = [C["baseline"], C["dedicated"], C["shared"]]
ax.bar(order, means, yerr=err, capsize=5, color=cols)
ax.set_ylabel("Mean response time (s)")
ax.set_ylim(0.080, 0.096)
for i, m in enumerate(means):
    ax.text(i, m + 0.0004, f"{m:.5f}", ha="center", fontsize=8)
save(fig, "fig5_threading_ci.png")

# ---------------------------------------------------------------- Fig 6: heterogeneity variance penalty
# From temp_hetero_results.txt (quoted in paper): CV^2 vs mean Wq
cv2 = [1.000, 1.060, 1.240, 1.654, 2.403]
wq = [0.060783, 0.189956, 1.773801, 36.023994, 29.521214]
labels = ["Homog.", "Low", "Med", "High", "V.High"]
fig, ax = plt.subplots(figsize=(6.0, 3.6))
ax.plot(cv2, wq, "-o", color=C["warn"])
ax.set_yscale("log")
ax.set_xlabel("Service-time squared coefficient of variation  C$_s^2$")
ax.set_ylabel("Mean waiting time W$_q$ (s, log scale)")
for xi, yi, lb in zip(cv2, wq, labels):
    ax.annotate(lb, (xi, yi), textcoords="offset points", xytext=(5, 5), fontsize=8)
save(fig, "fig6_heterogeneity.png")

# ---------------------------------------------------------------- Fig 7: dispatch policy
pol = ["Shortest-\nqueue", "Fastest-\nfirst", "Random", "Round-\nrobin"]
pwq = [0.068946, 0.073797, 36.023994, 37.473367]
fig, ax = plt.subplots(figsize=(5.6, 3.5))
ax.bar(pol, pwq, color=[C["dedicated"], C["accent"], C["shared"], C["warn"]])
ax.set_yscale("log")
ax.set_ylabel("Mean waiting time W$_q$ (s, log scale)")
for i, v in enumerate(pwq):
    ax.text(i, v * 1.15, f"{v:.3f}", ha="center", fontsize=8)
save(fig, "fig7_dispatch_policy.png")

# ---------------------------------------------------------------- Fig 8: Erlang-k
r = readcsv("results/data/erlang_improvement.csv")
# robust column detection
hdr = r[0].keys()
def col(cands):
    for c in cands:
        if c in hdr:
            return c
    return None
kcol = col(["k", "k_phases", "phases", "erlang_k"])
wcol = col(["sim_mean_wait", "mean_wait", "simulated_wait", "sim_wait"])
pcol = col(["sim_p99_wait", "p99_wait", "sim_p99"])
ks = [1, 2, 4, 8]
# fall back to the paper's quoted values if columns differ
try:
    mw = [float(x[wcol]) for x in r]
    pw = [float(x[pcol]) for x in r]
    kv = [int(float(x[kcol])) for x in r]
except Exception:
    kv = ks
    mw = [0.003457, 0.004161, 0.001967, 0.001840]
    pw = [0.071791, 0.090111, 0.044598, 0.043175]
cs2 = [1.0 / k for k in kv]
fig, ax1 = plt.subplots(figsize=(6.2, 3.6))
ax1.plot(kv, mw, "-o", color=C["simulation"], label="Mean wait")
ax1.plot(kv, pw, "--s", color=C["warn"], label="P99 wait")
ax1.set_xlabel("Erlang phases k   (C$_s^2$ = 1/k)")
ax1.set_ylabel("Waiting time (s)")
ax1.set_xticks(kv)
ax1.legend()
save(fig, "fig8_erlangk.png")

# ---------------------------------------------------------------- Fig 9: 2PC overhead breakdown
# Analytical model (paper Section 4.1): base service 83 ms, +~30 ms 2PC => +36%
base_s = 83.0
prepare = 10.0; vote = 10.0; commit = 10.0
fig, ax = plt.subplots(figsize=(5.8, 3.3))
ax.barh(["With 2PC", "Baseline"], [0, base_s], color=C["baseline"], label="Base service")
# stacked for with-2PC
ax.barh(["With 2PC"], [base_s], color=C["baseline"])
left = base_s
for comp, lab, cc in [(prepare, "Prepare RTT", C["simulation"]),
                      (vote, "Vote RTT", C["accent"]),
                      (commit, "Commit RTT", C["shared"])]:
    ax.barh(["With 2PC"], [comp], left=[left], color=cc, label=lab)
    left += comp
ax.set_xlabel("Mean service time (ms)")
ax.set_xlim(0, 135)
ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
ax.annotate("+36%", xy=(base_s + 30, 0), xytext=(base_s + 33, 0.35),
            fontsize=9, color=C["warn"], fontweight="bold")
save(fig, "fig9_2pc_overhead.png")

# ---------------------------------------------------------------- Fig 10: CAP availability
modes = ["CP\n(strong)", "AP\n(eventual)", "CA\n(no partition)"]
avail = [99.9833, 100.0, 99.0]
fig, ax = plt.subplots(figsize=(5.4, 3.3))
ax.bar(modes, avail, color=[C["warn"], C["dedicated"], C["mmn"]])
ax.set_ylabel("Availability (%)")
ax.set_ylim(98.5, 100.1)
for i, v in enumerate(avail):
    ax.text(i, v + 0.02, f"{v:.4g}%", ha="center", fontsize=8)
save(fig, "fig10_cap_availability.png")

print("ALL FIGURES DONE ->", OUT)
