#!/usr/bin/env python3
"""Generate Paper 2 figures from the simulation CSVs.

Every plotted value is read from a CSV written by an experiment script:
  experiments/cloud_broker_simulation.py  -> experiments/visibility_timeout_results.csv,
                                             experiments/replication_factor_results.csv
  experiments/cost_of_consistency.py      -> experiments/ordering_mode_results.csv
  experiments/paper2_threading.py         -> results/paper2/threading.csv
  experiments/paper2_heterogeneous.py     -> results/paper2/hetero_*.csv
  experiments/paper2_protocols.py         -> results/paper2/twopc_*.csv, raft_*.csv, vector_clocks.csv
  experiments/paper2_queueing_ext.py      -> results/paper2/finite_capacity.csv, priority.csv, erlang_k.csv
Output PNGs go to paper2_figures/. Styling matches Paper 1 (serif, 300 dpi).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
R2 = "results/paper2"
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def panel_label(ax, text):
    ax.set_title(text, loc="left", fontsize=11, fontweight="bold")


# ---------------------------------------------------------------- visibility timeout
vt = pd.read_csv("experiments/visibility_timeout_results.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.6))
a.errorbar(vt.visibility_timeout, vt.mean_latency, yerr=vt.mean_latency_ci95, fmt="-o",
           color=C["simulation"], capsize=3, label="Mean latency")
a.errorbar(vt.visibility_timeout, vt.p99_latency, yerr=vt.p99_latency_ci95, fmt="--s",
           color=C["warn"], capsize=3, label="P99 latency")
a.set_xscale("log"); a.set_yscale("log")
a.set_xlabel("Visibility timeout VT (s)"); a.set_ylabel("End-to-end latency (s)")
a.legend(); panel_label(a, "(A)")
b.errorbar(vt.visibility_timeout, vt.duplicate_rate * 100, yerr=vt.duplicate_rate_ci95 * 100,
           fmt="-o", color=C["shared"], capsize=3, label="Duplicate deliveries")
b.errorbar(vt.visibility_timeout, vt.dlq_ratio * 100, yerr=vt.dlq_ratio_ci95 * 100,
           fmt="--^", color=C["mmn"], capsize=3, label="Dead-lettered")
b.set_xscale("log"); b.set_yscale("symlog", linthresh=0.1); b.set_ylim(bottom=0)
b.set_xlabel("Visibility timeout VT (s)"); b.set_ylabel("Percent of messages (%)")
b.legend(); panel_label(b, "(B)")
save(fig, "fig1_visibility_timeout.png")

# ---------------------------------------------------------------- replication
rep = pd.read_csv("experiments/replication_factor_results.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.6))
w = 0.38
for i, (state, color) in enumerate([("off", C["baseline"]), ("on", C["warn"])]):
    d = rep[rep.node_outages == state].sort_values("replication_factor")
    x = d.replication_factor.values + (i - 0.5) * w
    lbl = "No node outages" if state == "off" else "Node outages (MTBF 100 s, MTTR 20 s)"
    a.bar(x, d.mean_first_receive, w, yerr=d.mean_first_receive_ci95, capsize=3,
          color=color, alpha=0.85, label=lbl)
    b.bar(x, d.p99_first_receive, w, yerr=d.p99_first_receive_ci95, capsize=3,
          color=color, alpha=0.85, label=lbl)
for ax, ylabel, tag in [(a, "Mean time to first delivery (s)", "(A)"),
                        (b, "P99 time to first delivery (s)", "(B)")]:
    ax.set_yscale("log"); ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Replication factor R"); ax.set_ylabel(ylabel)
    panel_label(ax, tag)
a.legend(fontsize=8)
save(fig, "fig2_replication.png")

# ---------------------------------------------------------------- ordering
od = pd.read_csv("experiments/ordering_mode_results.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.6))
for mode, color, fmt in [("Out-of-Order", C["simulation"], "-o"), ("In-Order", C["warn"], "--s")]:
    d = od[od.Mode == mode]
    a.errorbar(d.arrival_rate, d.Mean_Latency_ms, yerr=d.Mean_Latency_ms_ci95, fmt=fmt,
               color=color, capsize=3, label=mode)
    b.errorbar(d.arrival_rate, d.P99_Latency_ms, yerr=d.P99_Latency_ms_ci95, fmt=fmt,
               color=color, capsize=3, label=mode)
for ax, ylabel, tag in [(a, "Mean latency (ms)", "(A)"), (b, "P99 latency (ms)", "(B)")]:
    ax.set_yscale("log"); ax.set_xlabel("Arrival rate λ (msg/s)"); ax.set_ylabel(ylabel)
    ax.legend(); panel_label(ax, tag)
save(fig, "fig3_ordering.png")

# ---------------------------------------------------------------- threading
th = pd.read_csv(f"{R2}/threading.csv")
fig, (a, b, c) = plt.subplots(1, 3, figsize=(11.5, 3.6))
for model, color, fmt in [("baseline", C["baseline"], "-o"), ("dedicated", C["dedicated"], "-s"),
                          ("shared", C["shared"], "-^")]:
    d = th[th.model == model]
    a.errorbar(d.rho, d.mean_response, yerr=d.mean_response_ci95, fmt=fmt, color=color,
               capsize=3, label=model.capitalize())
    b.errorbar(d.rho, d.throughput, yerr=d.throughput_ci95, fmt=fmt, color=color,
               capsize=3, label=model.capitalize())
base = th[th.model == "baseline"]
ded = th[th.model == "dedicated"]
a.plot(base.rho, base.analytical_mean_response, "x", color=C["analytical"], ms=9, mew=2, zorder=5, label="M/M/20 exact")
b.plot(ded.rho, ded.analytical_throughput, "x", color=C["analytical"], ms=9, mew=2, zorder=5, label="Erlang-B (M/M/10/10)")
c.errorbar(ded.rho, ded.rejection_rate * 100, yerr=ded.rejection_rate_ci95 * 100, fmt="-s",
           color=C["dedicated"], capsize=3, label="Dedicated (simulated)")
c.plot(ded.rho, ded.analytical_rejection_rate * 100, "x", color=C["analytical"], ms=9, mew=2, zorder=5,
       label="Erlang-B B(10, λ/μ)")
a.set_yscale("log"); a.set_ylabel("Mean response time (s)")
b.set_ylabel("Throughput (msg/s)"); c.set_ylabel("Rejected arrivals (%)")
for ax, tag in [(a, "(A)"), (b, "(B)"), (c, "(C)")]:
    ax.set_xlabel("Offered utilization ρ = λ/(Nμ)"); ax.legend(fontsize=8); panel_label(ax, tag)
save(fig, "fig4_threading.png")

# ---------------------------------------------------------------- heterogeneity
hs = pd.read_csv(f"{R2}/hetero_scenarios.csv")
scen = list(dict.fromkeys(hs.scenario))
fig, ax = plt.subplots(figsize=(7.4, 3.8))
w = 0.26
labels = {"random": "Random (per server)", "random_capacity": "Random (capacity-weighted)",
          "shortest_queue": "Shortest queue"}
colors = {"random": C["warn"], "random_capacity": C["simulation"], "shortest_queue": C["dedicated"]}
for i, pol in enumerate(["random", "random_capacity", "shortest_queue"]):
    d = hs[hs.policy == pol].set_index("scenario").loc[scen]
    x = np.arange(len(scen)) + (i - 1) * w
    ax.bar(x, d.sim_mean_wait, w, yerr=d.sim_mean_wait_ci95, capsize=2, color=colors[pol],
           alpha=0.85, label=labels[pol])
    exact = d.analytical_wq.astype(float)
    ok = np.isfinite(exact.values)
    if ok.any():
        ax.plot(x[ok], exact.values[ok], "k_", markersize=12, mew=2,
                label="Exact M/M/n_i" if i == 1 else None)
ax.set_yscale("log"); ax.set_xticks(np.arange(len(scen)))
groups = hs.drop_duplicates("scenario").set_index("scenario").loc[scen, "groups"]
ax.set_xticklabels([f"{s}\n{g}" for s, g in zip(scen, groups)], fontsize=7.5)
ax.set_ylabel("Mean waiting time (s)"); ax.legend(fontsize=8)
save(fig, "fig6_heterogeneity.png")

hp = pd.read_csv(f"{R2}/hetero_policies.csv")
fig, ax = plt.subplots(figsize=(6.2, 3.6))
names = {"random": "Random\n(per server)", "random_capacity": "Random\n(capacity)",
         "round_robin": "Round-\nrobin", "shortest_queue": "Shortest\nqueue",
         "fastest_first": "Fastest\nfirst", "work_stealing": "Work\nstealing"}
ax.bar([names[p] for p in hp.policy], hp.sim_mean_wait, yerr=hp.sim_mean_wait_ci95, capsize=3,
       color=[C["warn"] if p in ("random", "round_robin") else C["simulation"] for p in hp.policy])
ax.set_yscale("log"); ax.set_ylabel("Mean waiting time (s)")
save(fig, "fig7_dispatch_policy.png")

hi = pd.read_csv(f"{R2}/hetero_instability.csv")
fig, ax = plt.subplots(figsize=(5.6, 3.6))
for (name, d), m in zip(hi.groupby("scenario", sort=False), ["o", "s", "^"]):
    ax.errorbar(d.sim_duration, d.sim_mean_wait, yerr=d.sim_mean_wait_ci95, fmt="-" + m,
                capsize=3, label=name)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Simulated time T (s)"); ax.set_ylabel("Mean waiting time (s)")
ax.legend(fontsize=8)
save(fig, "fig11_hetero_instability.png")

# ---------------------------------------------------------------- 2PC
oh = pd.read_csv(f"{R2}/twopc_overhead.csv")
q = pd.read_csv(f"{R2}/twopc_queue.csv")
inst = pd.read_csv(f"{R2}/twopc_instability.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 3.7))
x = np.arange(len(oh))
a.bar(x - 0.2, oh.sampled_overhead_mean_s * 1000, 0.4, color=C["simulation"],
      yerr=1.96 * oh.sampled_overhead_mean_se_s * 1000, capsize=2, label="Sampled (2×10⁵ draws)")
a.bar(x + 0.2, oh.analytic_overhead_mean_s * 1000, 0.4, color=C["analytical"], label="Analytical E[T_2PC]")
a.set_xticks(x)
a.set_xticklabels([f"n={r.num_replicas}\na={r.replica_availability:g}\nT={r.vote_timeout_s:g}s"
                   for r in oh.itertuples()], fontsize=6.5)
a.set_ylabel("Mean 2PC overhead (ms)"); a.legend(fontsize=8); panel_label(a, "(A)")
base = q[q.variant == "no_2pc"]
b.errorbar(base.arrival_rate, base.mean_response_s_mean, yerr=base.mean_response_s_ci95, fmt="-o",
           color=C["baseline"], capsize=3, label="No 2PC")
for (av, to), d in q[q.variant == "2pc"].groupby(["replica_availability", "vote_timeout_s"]):
    b.errorbar(d.arrival_rate, d.mean_response_s_mean, yerr=d.mean_response_s_ci95, fmt="-s",
               capsize=3, label=f"2PC a={av:g}, T={to:g} s")
b.set_xlabel("Arrival rate λ (msg/s)"); b.set_ylabel("Mean response time (s)")
b.legend(fontsize=7); panel_label(b, "(B)")
save(fig, "fig9_2pc_overhead.png")

fig, ax = plt.subplots(figsize=(5.6, 3.5))
d = inst[inst.variant == "2pc"]
ax.errorbar(d.arrival_rate, d.measured_backlog_slope_msg_per_s_mean,
            yerr=d.measured_backlog_slope_msg_per_s_ci95, fmt="o", color=C["simulation"],
            capsize=3, label="Measured backlog growth")
ax.plot(d.arrival_rate, d.predicted_backlog_slope_if_unstable, "--", color=C["analytical"],
        label="max(0, λ − λ*)")
ax.axvline(d.analytic_saturation_lambda.iloc[0], color="gray", ls=":", label="λ* (2PC saturation)")
ax.set_xlabel("Arrival rate λ (msg/s)"); ax.set_ylabel("Backlog growth (msg/s)")
ax.legend(fontsize=8)
save(fig, "fig12_2pc_instability.png")

# ---------------------------------------------------------------- protocol capacity
pc = pd.read_csv(f"{R2}/protocol_capacity.csv")
lab = {"none": "No protocol"}
names = []
for r in pc.itertuples():
    if r.variant == "none":
        names.append("No protocol")
    elif r.variant == "2pc":
        av, to = eval(r.param)
        names.append(f"2PC\na={av:g}, T={to:g}s")
    else:
        ps, n = eval(r.param)
        names.append(f"Raft {ps.split('_')[1].upper()}\nn={n}")
fig, ax = plt.subplots(figsize=(7.6, 3.6))
ax.bar(names, pc.measured_capacity_msg_per_s_mean, yerr=pc.measured_capacity_msg_per_s_ci95,
       capsize=3, color=[C["baseline"] if v == "none" else C["shared"] if v == "2pc" else C["mmn"]
                         for v in pc.variant])
ok = pc.analytic_capacity_msg_per_s.notna()
ax.plot(np.arange(len(pc))[ok], pc.analytic_capacity_msg_per_s[ok], "k_", markersize=14, mew=2,
        label="Analytical N/E[S]")
ax.set_ylabel("Saturated throughput (msg/s)"); ax.tick_params(axis="x", labelsize=7)
ax.legend(fontsize=8)
save(fig, "fig13_protocol_capacity.png")

# ---------------------------------------------------------------- Raft
re = pd.read_csv(f"{R2}/raft_elections.csv")
rc = pd.read_csv(f"{R2}/raft_commit.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.4, 3.6))
w = 0.38
real = re[re.param_set != "default_model"]
for i, (ps, color) in enumerate([("realistic_lan", C["dedicated"]), ("realistic_wan", C["warn"])]):
    d = re[re.param_set == ps]
    xs = np.arange(len(d)) + (i - 0.5) * w
    a.bar(xs, d.reelection_time_s_mean * 1000, w, yerr=d.reelection_time_s_ci95 * 1000, capsize=3,
          color=color, label=ps.replace("realistic_", "").upper())
a.set_xticks(range(3)); a.set_xticklabels([f"n={n}" for n in [3, 5, 7]])
a.set_ylabel("Re-election time after leader crash (ms)"); a.legend(fontsize=8); panel_label(a, "(A)")
for ps, color in [("realistic_lan", C["dedicated"]), ("realistic_wan", C["warn"])]:
    d = rc[(rc.param_set == ps) & rc.replicate_log_entries]
    b.errorbar(d.cluster_size, d.commit_latency_mean_s_mean * 1000, yerr=d.commit_latency_mean_s_ci95 * 1000,
               fmt="-o", color=color, capsize=3, label=f"{ps.replace('realistic_', '').upper()} mean")
    b.plot(d.cluster_size, d.commit_latency_p99_s_mean * 1000, "--^", color=color,
           label=f"{ps.replace('realistic_', '').upper()} P99")
b.set_yscale("log"); b.set_xticks([3, 5, 7]); b.set_xlabel("Cluster size n")
b.set_ylabel("Append-to-commit latency (ms)"); b.legend(fontsize=8); panel_label(b, "(B)")
save(fig, "fig14_raft.png")

# ---------------------------------------------------------------- vector clocks
vc = pd.read_csv(f"{R2}/vector_clocks.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.4, 3.6))
for n, m in zip([3, 5, 10], ["o", "s", "^"]):
    d = vc[(vc.implementation == "bss") & (vc.num_processes == n) & (vc.broadcast_rate == 10)]
    a.errorbar(d.delay_cv, d.held_back_fraction_mean * 100, yerr=d.held_back_fraction_ci95 * 100,
               fmt="-" + m, capsize=3, label=f"P = {n}")
    d2 = vc[(vc.implementation == "none") & (vc.num_processes == n) & (vc.broadcast_rate == 10)]
    b.errorbar(d2.delay_cv, d2.violating_delivery_fraction_mean * 100,
               yerr=d2.violating_delivery_fraction_ci95 * 100, fmt="--" + m, capsize=3, label=f"P = {n}")
a.set_xlabel("Network delay CV"); a.set_ylabel("Messages held back (%)")
a.legend(fontsize=8); panel_label(a, "(A) causal delivery (vector clocks)")
b.set_xlabel("Network delay CV"); b.set_ylabel("Causally violating deliveries (%)")
b.legend(fontsize=8); panel_label(b, "(B) no ordering")
save(fig, "fig15_vector_clocks.png")

# ---------------------------------------------------------------- finite capacity
fc = pd.read_csv(f"{R2}/finite_capacity.csv")
fig, (a, b) = plt.subplots(1, 2, figsize=(9.4, 3.6))
for ((lam, rho), d), color in zip(fc.groupby(["lambda_", "rho"]), [C["simulation"], C["shared"], C["warn"]]):
    ds = d[d.sim_P_K_mean > 0]
    a.errorbar(ds.K, ds.sim_P_K_mean, yerr=ds.sim_P_K_ci95, fmt="o", color=color, capsize=3,
               label=f"ρ = {rho:g} sim")
    da = d[d.ana_P_K > 1e-7]
    a.plot(da.K, da.ana_P_K, "--", color=color, label=f"ρ = {rho:g} exact")
    dd = d[d.sim_Wq_mean > 0]
    b.errorbar(dd.K, dd.sim_Wq_mean, yerr=dd.sim_Wq_ci95, fmt="o", color=color, capsize=3,
               label=f"ρ = {rho:g} sim")
    b.plot(dd.K, dd.ana_Wq, "--", color=color, label=f"ρ = {rho:g} exact")
a.set_xscale("log"); a.set_yscale("log"); a.set_xlabel("System capacity K"); a.set_ylabel("Blocking probability P_K")
a.legend(fontsize=8); panel_label(a, "(A)")
b.set_xscale("log"); b.set_yscale("log"); b.set_xlabel("System capacity K"); b.set_ylabel("Mean wait of admitted messages (s)")
b.legend(fontsize=8); panel_label(b, "(B)")
save(fig, "fig16_finite_capacity.png")

# ---------------------------------------------------------------- priority
pr = pd.read_csv(f"{R2}/priority.csv")
fig, ax = plt.subplots(figsize=(6.2, 3.7))
d = pr[pr.sweep == "load_sweep"]
for (disc, cls), g in d[d.cls != "all"].groupby(["discipline", "cls"]):
    if disc.startswith("preemptive") and str(cls) == "1":
        continue  # waits ~0, not representable on a log axis
    name = ("High" if str(cls) == "1" else "Low") + (" (non-preemptive)" if disc.startswith("non") else " (preemptive-resume)")
    ax.errorbar(g.rho, g.sim_mean_wait, yerr=g.sim_mean_wait_ci95, fmt="o", capsize=3, label=name + " sim")
    ax.plot(g.rho, g.ana_mean_wait, "--", color=ax.lines[-1].get_color())
f = d.drop_duplicates("rho")
ax.plot(f.rho, f.fcfs_mmn_Wq, ":k", label="FCFS M/M/10 (exact)")
ax.set_yscale("log"); ax.set_xlabel("Utilization ρ"); ax.set_ylabel("Mean waiting time (s)")
ax.legend(fontsize=7)
save(fig, "fig17_priority.png")

# ---------------------------------------------------------------- Erlang-k
ek = pd.read_csv(f"{R2}/erlang_k.csv")
fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6))
for ax, (cfg, d), tag in zip(axes, ek.groupby("config", sort=False), ["(A)", "(B)"]):
    ax.errorbar(d.k, d.sim_mean_wait * 1000, yerr=d.sim_mean_wait_ci95 * 1000, fmt="-o",
                color=C["simulation"], capsize=3, label="Simulation")
    ax.plot(d.k, d.ana_allen_cunneen_Wq * 1000, "--s", color=C["analytical"], label="Allen–Cunneen")
    ex = d[d.exact_ctmc_Wq.notna()]
    ax.plot(ex.k, ex.exact_ctmc_Wq * 1000, "k_", markersize=14, mew=2, label="Exact CTMC")
    ax.set_xscale("log", base=2); ax.set_xticks(d.k); ax.set_xticklabels(d.k)
    ax.set_xlabel("Erlang phases k (C_s² = 1/k)"); ax.set_ylabel("Mean waiting time (ms)")
    ax.legend(fontsize=8); panel_label(ax, f"{tag} ρ = {d.rho.iloc[0]:g}")
save(fig, "fig8_erlangk.png")
