"""
Paper 2, Section 6.1: heterogeneous servers and dispatch policy.

Each server group has its own FCFS queue (src/models/heterogeneous_mmn.py).
Under a static probabilistic split (random, random_capacity) group i receives
a Poisson stream of rate λ_i, so it is an exact M/M/n_i queue. That gives an
exact analytical mean wait, Wq = Σ (λ_i/λ)·Wq_i, to validate the simulation
against, and makes the stability condition explicit: ρ_i = λ_i/(n_i·μ_i) < 1
for every group, not just λ < Σ n_i·μ_i.

Outputs (results/paper2/):
  hetero_scenarios.csv   - variance scenarios × {random, random_capacity, shortest_queue}
  hetero_policies.csv    - all dispatch policies on the 2@8 + 3@15 configuration
  hetero_instability.csv - mean wait vs. simulation length for unstable configs
  hetero_runs.csv        - every individual replication
"""

import contextlib
import io
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from scipy import stats

from src.core.config import HeterogeneousMMNConfig, ServerGroup
from src.models.heterogeneous_mmn import run_heterogeneous_mmn_simulation

OUT = "results/paper2"
ARRIVAL_RATE = 50.0
SEEDS = list(range(1, 11))
SIM_DURATION = 2000.0
WARMUP = 200.0

SCENARIOS = [
    ("Homogeneous", [(5, 12.0)]),
    ("Low variance", [(3, 11.0), (2, 13.5)]),
    ("Medium variance", [(3, 10.0), (2, 15.0)]),
    ("High variance", [(2, 8.0), (3, 15.0)]),
    ("Very high variance", [(1, 6.0), (4, 16.0)]),
]
POLICIES = ["random", "random_capacity", "round_robin", "shortest_queue",
            "fastest_first", "work_stealing"]


def erlang_c_wq(lam, n, mu):
    """Exact M/M/n mean wait; inf if unstable"""
    a = lam / mu
    if a >= n:
        return math.inf
    top = a ** n / math.factorial(n) * n / (n - a)
    c = top / (sum(a ** k / math.factorial(k) for k in range(n)) + top)
    return c / (n * mu - lam)


def split(groups, policy):
    """Per-group arrival rates for static policies, else None"""
    n_total = sum(n for n, _ in groups)
    cap = sum(n * mu for n, mu in groups)
    if policy == "random":
        return [ARRIVAL_RATE * n / n_total for n, _ in groups]
    if policy == "random_capacity":
        return [ARRIVAL_RATE * n * mu / cap for n, mu in groups]
    return None


def analytical(groups, policy):
    rates = split(groups, policy)
    if rates is None:
        return None, None
    rhos = [lam / (n * mu) for lam, (n, mu) in zip(rates, groups)]
    wq = sum(lam / ARRIVAL_RATE * erlang_c_wq(lam, n, mu)
             for lam, (n, mu) in zip(rates, groups))
    return wq, max(rhos)


def ci95(values):
    values = np.asarray(values, dtype=float)
    half = stats.t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values))
    return float(values.mean()), float(half)


def simulate(groups, policy, seed, duration=SIM_DURATION, warmup=WARMUP):
    config = HeterogeneousMMNConfig(
        arrival_rate=ARRIVAL_RATE,
        server_groups=[ServerGroup(count=n, service_rate=mu) for n, mu in groups],
        selection_policy=policy,
        sim_duration=duration,
        warmup_time=warmup,
        random_seed=seed,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        metrics = run_heterogeneous_mmn_simulation(config)
    return metrics.summary_statistics()


def run_config(scenario, groups, policy, runs):
    waits, p99s, p99r = [], [], []
    for seed in SEEDS:
        s = simulate(groups, policy, seed)
        waits.append(s["mean_wait"])
        p99s.append(s["p99_wait"])
        p99r.append(s["p99_response"])
        runs.append({"scenario": scenario, "policy": policy, "seed": seed,
                     "mean_wait": s["mean_wait"], "p99_wait": s["p99_wait"],
                     "p99_response": s["p99_response"]})
    cap = sum(n * mu for n, mu in groups)
    mus = np.repeat([mu for _, mu in groups], [n for n, _ in groups])
    wq_exact, max_rho = analytical(groups, policy)
    mean, half = ci95(waits)
    row = {
        "scenario": scenario,
        "groups": " + ".join(f"{n}@{mu:g}" for n, mu in groups),
        "policy": policy,
        "capacity": cap,
        "aggregate_rho": ARRIVAL_RATE / cap,
        "cv_mu": float(mus.std() / mus.mean()),
        "max_pool_rho": max_rho,
        "stable": None if max_rho is None else bool(max_rho < 1),
        "analytical_wq": wq_exact,
        "sim_mean_wait": mean,
        "sim_mean_wait_ci95": half,
        "sim_p99_wait": float(np.mean(p99s)),
        "sim_p99_response": float(np.mean(p99r)),
        "replications": len(SEEDS),
    }
    print(f"{scenario:<19} {policy:<16} Wq={mean:10.4f} ± {half:.4f}  "
          f"exact={wq_exact}  max ρ_i={max_rho}")
    return row


def main():
    os.makedirs(OUT, exist_ok=True)
    runs = []

    scenario_rows = []
    for name, groups in SCENARIOS:
        for policy in ["random", "random_capacity", "shortest_queue"]:
            scenario_rows.append(run_config(name, groups, policy, runs))
    pd.DataFrame(scenario_rows).to_csv(f"{OUT}/hetero_scenarios.csv", index=False)

    high = dict(SCENARIOS)["High variance"]
    policy_rows = [r for r in scenario_rows if r["scenario"] == "High variance"]
    done = {r["policy"] for r in policy_rows}
    for policy in POLICIES:
        if policy not in done:
            policy_rows.append(run_config("High variance", high, policy, runs))
    order = {p: i for i, p in enumerate(POLICIES)}
    policy_rows.sort(key=lambda r: order[r["policy"]])
    pd.DataFrame(policy_rows).to_csv(f"{OUT}/hetero_policies.csv", index=False)

    # Unstable pools: mean wait keeps growing with the observation window
    inst_rows = []
    for name in ["Medium variance", "High variance", "Very high variance"]:
        groups = dict(SCENARIOS)[name]
        for duration in [500.0, 1000.0, 2000.0, 4000.0]:
            waits = [simulate(groups, "random", seed, duration=duration, warmup=0.1 * duration)["mean_wait"]
                     for seed in SEEDS]
            mean, half = ci95(waits)
            inst_rows.append({"scenario": name, "policy": "random", "sim_duration": duration,
                              "sim_mean_wait": mean, "sim_mean_wait_ci95": half,
                              "replications": len(SEEDS)})
            print(f"instability {name:<19} T={duration:6.0f} Wq={mean:.3f} ± {half:.3f}")
    pd.DataFrame(inst_rows).to_csv(f"{OUT}/hetero_instability.csv", index=False)

    pd.DataFrame(runs).to_csv(f"{OUT}/hetero_runs.csv", index=False)
    print(f"Saved {OUT}/hetero_*.csv")


if __name__ == "__main__":
    main()
