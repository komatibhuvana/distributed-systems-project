"""
Paper 2, Section 5: dedicated vs. shared thread pools, with replications.

Models (src/models/threading.py), N = 20 threads, μ = 12 msg/s/thread:
  baseline  - M/M/20 (src/models/mmn_queue.py)
  dedicated - at most N/2 = 10 concurrent connections, extra arrivals rejected.
              Each accepted message is served at rate μ, so this is an
              M/M/10/10 loss system: blocking = Erlang-B B(10, λ/μ).
  shared    - M/M/20 whose service time is stretched by (1 + α·busy/N), α = 0.1

Outputs (results/paper2/):
  threading.csv      - per (ρ, model) means with 95% CIs and analytical checks
  threading_runs.csv - every replication
"""

import contextlib
import io
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import simpy
from scipy import stats

from src.core.config import MMNConfig
from src.models.mmn_queue import run_mmn_simulation
from src.models.threading import DedicatedThreadingQueue, SharedThreadingQueue

OUT = "results/paper2"
N_THREADS = 20
MU = 12.0
RHOS = [0.5, 0.6, 0.7, 0.8, 0.9]
SEEDS = list(range(1, 11))
SIM_DURATION = 2000.0
WARMUP = 200.0


def erlang_b(n, a):
    b = 1.0
    for k in range(1, n + 1):
        b = a * b / (k + a * b)
    return b


def erlang_c_wq(lam, n, mu):
    a = lam / mu
    top = a ** n / math.factorial(n) * n / (n - a)
    c = top / (sum(a ** k / math.factorial(k) for k in range(n)) + top)
    return c / (n * mu - lam)


def run_one(args):
    rho, model, seed = args
    lam = rho * N_THREADS * MU
    config = MMNConfig(arrival_rate=lam, num_threads=N_THREADS, service_rate=MU,
                       sim_duration=SIM_DURATION, warmup_time=WARMUP, random_seed=seed)
    rejected = 0
    with contextlib.redirect_stdout(io.StringIO()):
        if model == "baseline":
            metrics = run_mmn_simulation(config)
        else:
            env = simpy.Environment()
            if model == "dedicated":
                q = DedicatedThreadingQueue(env, config, threads_per_connection=2)
            else:
                q = SharedThreadingQueue(env, config, overhead_coefficient=0.1)
            metrics = q.run()
            rejected = getattr(q, "rejected_count", 0)
    s = metrics.summary_statistics()
    accepted = len(metrics.wait_times)
    return {
        "rho": rho, "arrival_rate": lam, "model": model, "seed": seed,
        "mean_response": s["mean_response"], "p95_response": s["p95_response"],
        "p99_response": s["p99_response"], "mean_wait": s["mean_wait"],
        "throughput": accepted / (SIM_DURATION - WARMUP),
        "rejection_rate": rejected / (accepted + rejected) if accepted + rejected else 0.0,
    }


def ci95(values):
    values = np.asarray(values, dtype=float)
    half = stats.t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values))
    return float(values.mean()), float(half)


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [(rho, model, seed) for rho in RHOS for model in ["baseline", "dedicated", "shared"]
            for seed in SEEDS]
    with ProcessPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(run_one, jobs))
    runs_df = pd.DataFrame(runs)
    runs_df.to_csv(f"{OUT}/threading_runs.csv", index=False)

    rows = []
    for (rho, model), g in runs_df.groupby(["rho", "model"], sort=False):
        lam = rho * N_THREADS * MU
        row = {"rho": rho, "arrival_rate": lam, "model": model, "replications": len(g)}
        for m in ["mean_response", "p95_response", "p99_response", "mean_wait",
                  "throughput", "rejection_rate"]:
            row[m], row[m + "_ci95"] = ci95(g[m])
        if model == "baseline":
            row["analytical_mean_response"] = erlang_c_wq(lam, N_THREADS, MU) + 1 / MU
            row["analytical_throughput"] = lam
        elif model == "dedicated":
            b = erlang_b(N_THREADS // 2, lam / MU)
            row["analytical_mean_response"] = 1 / MU
            row["analytical_throughput"] = lam * (1 - b)
            row["analytical_rejection_rate"] = b
        rows.append(row)
        print(f"ρ={rho} {model:<9} R={row['mean_response']:.4f}±{row['mean_response_ci95']:.4f} "
              f"X={row['throughput']:.1f} rej={row['rejection_rate']:.3f} "
              f"analytic R={row.get('analytical_mean_response')} X={row.get('analytical_throughput')}")
    pd.DataFrame(rows).to_csv(f"{OUT}/threading.csv", index=False)
    print(f"Saved {OUT}/threading.csv")


if __name__ == "__main__":
    main()
