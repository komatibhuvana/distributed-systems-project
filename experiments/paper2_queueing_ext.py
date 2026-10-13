"""
Paper 2, Section 6 (Queueing Extensions): persisted simulation measurements.

Runs (all seeded, deterministic):
  1. Finite capacity M/M/N/K   -> results/paper2/finite_capacity.csv
  2. Priority M/M/N (2 classes) -> results/paper2/priority.csv
  3. Erlang-k service M/E_k/N   -> results/paper2/erlang_k.csv
     (+ erlang_k_short_run_spread.csv: spread of the original 100 s single-run design)
Per-replication raw data is written to results/paper2/*_replications.csv.

Every reported number is computed by this script; nothing is hand-entered.

Usage:
    ./venv/bin/python experiments/paper2_queueing_ext.py [--workers 12] [--quick]
"""

import argparse
import os
import sys
import time
import warnings
from itertools import combinations_with_replacement
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy import stats, sparse
from scipy.sparse.linalg import spsolve

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import simpy  # noqa: E402

from src.core.config import FiniteCapacityConfig, PriorityQueueConfig  # noqa: E402
from src.models.finite_capacity_queue import FiniteCapacityQueue, ErlangBAnalytical  # noqa: E402
from src.models.priority_queue import PriorityQueueModel  # noqa: E402
from src.models.mekn_queue import MEkNQueue, MEkNConfig  # noqa: E402
from src.analysis.analytical import (  # noqa: E402
    MMNAnalytical, MEkNAnalytical, MMNKAnalytical, MMNPriorityAnalytical,
)

OUT = os.path.join(ROOT, "results", "paper2")

# ----------------------------------------------------------------------------
# Experiment parameters
# ----------------------------------------------------------------------------
FC = dict(N=10, mu=12.0, lambdas=[96.0, 120.0, 150.0],          # ρ = 0.8, 1.0, 1.25
          K_offsets=[0, 2, 5, 10, 20, 40, 190],                  # K = N + offset
          sim_duration=2000.0, warmup=200.0, reps=20, seed0=10_000)

PQ = dict(N=10, mu=12.0, base_lambda=100.0, base_frac=0.2,
          rhos=[0.5, 0.6, 0.7, 0.8, 0.9], fracs=[0.1, 0.2, 0.3, 0.5],
          sim_duration=2000.0, warmup=200.0, reps=20, seed0=20_000)

EK = dict(k_values=[1, 2, 4, 8, 16],
          configs={  # name: (λ, N, μ)
              "original_rho0.50": (30.0, 6, 10.0),   # demonstrate_erlang_improvement()
              "high_rho0.85": (51.0, 6, 10.0),
          },
          sim_duration=5000.0, warmup=500.0, reps=20, seed0=30_000,
          short_duration=100.0, short_warmup=10.0)   # original single-run design


def ci95(x):
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return float(np.mean(x)), float("nan"), float("nan")
    m = float(np.mean(x))
    s = float(np.std(x, ddof=1))
    h = float(stats.t.ppf(0.975, n - 1) * s / np.sqrt(n))
    return m, s, h


# ----------------------------------------------------------------------------
# Simulation workers (module-level so multiprocessing can pickle them)
# ----------------------------------------------------------------------------
def run_fc(args):
    lam, N, mu, K, dur, warm, seed = args
    np.random.seed(seed)
    cfg = FiniteCapacityConfig(arrival_rate=lam, num_threads=N, service_rate=mu,
                               max_capacity=K, blocking_strategy="reject",
                               sim_duration=dur, warmup_time=warm, random_seed=seed)
    env = simpy.Environment()
    model = FiniteCapacityQueue(env, cfg)
    model.run()
    m = model.metrics
    post = m.accepted_arrivals + m.blocked_arrivals
    w = np.asarray(m.wait_times)
    return dict(lambda_=lam, N=N, mu=mu, K=K, seed=seed,
                arrivals_post_warmup=post, blocked=m.blocked_arrivals,
                p_block=m.blocked_arrivals / post,
                p_block_legacy_key=m.blocked_arrivals / m.total_arrivals,
                lambda_eff=m.accepted_arrivals / (dur - warm),
                mean_wait=float(w.mean()), p99_wait=float(np.percentile(w, 99)),
                n_served=len(w))


def run_pq(args):
    lam, frac, N, mu, preemptive, dur, warm, seed = args
    np.random.seed(seed)
    rates = [lam * frac, lam * (1.0 - frac)]
    cfg = PriorityQueueConfig(arrival_rate=lam, num_threads=N, service_rate=mu,
                              num_priorities=2, priority_rates=rates,
                              preemptive=preemptive, sim_duration=dur,
                              warmup_time=warm, random_seed=seed)
    env = simpy.Environment()
    model = PriorityQueueModel(env, cfg)
    model.run()
    rows = []
    all_w = []
    for c in (1, 2):
        w = np.asarray(model.priority_metrics[c].wait_times)
        all_w.append(w)
        rows.append(dict(cls=str(c), mean_wait=float(w.mean()),
                         p95_wait=float(np.percentile(w, 95)),
                         p99_wait=float(np.percentile(w, 99)), n=len(w)))
    w = np.concatenate(all_w)
    rows.append(dict(cls="all", mean_wait=float(w.mean()),
                     p95_wait=float(np.percentile(w, 95)),
                     p99_wait=float(np.percentile(w, 99)), n=len(w)))
    for r in rows:
        r.update(lambda_=lam, frac_high=frac, N=N, mu=mu,
                 discipline="preemptive_resume" if preemptive else "nonpreemptive",
                 seed=seed)
    return rows


def run_ek(args):
    name, lam, N, mu, k, dur, warm, seed = args
    np.random.seed(seed)
    cfg = MEkNConfig(arrival_rate=lam, num_threads=N, service_rate=mu, erlang_k=k,
                     sim_duration=dur, warmup_time=warm, random_seed=seed)
    env = simpy.Environment()
    q = MEkNQueue(env, cfg)
    env.process(q.message_generator())
    env.run(until=dur)
    w = np.asarray(q.metrics.wait_times)
    s = np.asarray(q.metrics.service_times)
    return dict(config=name, lambda_=lam, N=N, mu=mu, k=k, sim_duration=dur,
                warmup=warm, seed=seed, mean_wait=float(w.mean()),
                p99_wait=float(np.percentile(w, 99)),
                mean_service=float(s.mean()),
                cv2_service=float(s.var() / s.mean() ** 2), n=len(w))


# ----------------------------------------------------------------------------
# Independent analytical checks
# ----------------------------------------------------------------------------
def mmnk_generator_solution(lam, N, mu, K):
    """Solve πQ = 0 for the M/M/N/K CTMC generator directly (linear algebra),
    independent of the closed-form product solution."""
    Q = np.zeros((K + 1, K + 1))
    for n in range(K + 1):
        if n < K:
            Q[n, n + 1] = lam
        if n > 0:
            Q[n, n - 1] = min(n, N) * mu
        Q[n, n] = -Q[n].sum()
    A = np.vstack([Q.T, np.ones(K + 1)])
    b = np.zeros(K + 2)
    b[-1] = 1.0
    pi, *_ = np.linalg.lstsq(A, b, rcond=None)
    Lq = float(np.sum(np.maximum(np.arange(K + 1) - N, 0) * pi))
    lam_eff = lam * (1 - pi[-1])
    return float(pi[-1]), lam_eff, Lq / lam_eff


def mekn_exact_ctmc(lam, N, mu, k, qmax):
    """Exact M/E_k/N mean wait via the phase-type CTMC, truncated at qmax waiting.

    State: (phase-count vector of busy servers, number waiting q). q > 0 only if
    all N servers busy. Each phase has rate k·μ. Returns (Wq, tail_prob) where
    tail_prob is the stationary mass at the truncation level (should be ~0).
    """
    phase_rate = k * mu
    states = []
    for b in range(N + 1):
        for combo in combinations_with_replacement(range(k), b):
            c = tuple(np.bincount(combo, minlength=k)) if b else tuple([0] * k)
            qs = range(qmax + 1) if b == N else [0]
            for q in qs:
                states.append((c, q))
    idx = {s: i for i, s in enumerate(states)}
    rows, cols, vals = [], [], []

    def add(i, s2, rate):
        rows.append(i)
        cols.append(idx[s2])
        vals.append(rate)

    for i, (c, q) in enumerate(states):
        b = sum(c)
        # arrival
        if b < N:
            c2 = list(c)
            c2[0] += 1
            add(i, (tuple(c2), 0), lam)
        elif q < qmax:
            add(i, (c, q + 1), lam)
        # phase completions
        for ph in range(k):
            if c[ph] == 0:
                continue
            r = c[ph] * phase_rate
            c2 = list(c)
            c2[ph] -= 1
            if ph < k - 1:
                c2[ph + 1] += 1
                add(i, (tuple(c2), q), r)
            else:  # service completion
                if q > 0:
                    c2[0] += 1
                    add(i, (tuple(c2), q - 1), r)
                else:
                    add(i, (tuple(c2), 0), r)
    n = len(states)
    Q = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n))
    Q = Q - sparse.diags(np.asarray(Q.sum(axis=1)).ravel())
    A = Q.T.tolil()
    A[0, :] = np.ones(n)
    rhs = np.zeros(n)
    rhs[0] = 1.0
    pi = spsolve(A.tocsc(), rhs)
    qv = np.array([s[1] for s in states])
    Lq = float(np.sum(qv * pi))
    tail = float(pi[qv == qmax].sum())
    return Lq / lam, tail


def mmn_p99_wait(lam, N, mu):
    """Exact FCFS M/M/N P99 wait: P(W>t) = C·exp(-(Nμ-λ)t)."""
    C = MMNAnalytical(lam, N, mu).erlang_c()
    return 0.0 if C <= 0.01 else float(np.log(C / 0.01) / (N * mu - lam))


# ----------------------------------------------------------------------------
# Experiments
# ----------------------------------------------------------------------------
def experiment_finite_capacity(pool):
    p = FC
    tasks = []
    for lam in p["lambdas"]:
        for off in p["K_offsets"]:
            K = p["N"] + off
            for r in range(p["reps"]):
                tasks.append((lam, p["N"], p["mu"], K, p["sim_duration"],
                              p["warmup"], p["seed0"] + r))
    raw = pd.DataFrame(pool.map(run_fc, tasks, chunksize=1))
    raw.to_csv(os.path.join(OUT, "finite_capacity_replications.csv"), index=False)

    out = []
    for (lam, K), g in raw.groupby(["lambda_", "K"]):
        N, mu = p["N"], p["mu"]
        an = MMNKAnalytical(lam, N, mu, K)
        legacy = ErlangBAnalytical(lam, N, mu, K)
        gen_pk, gen_leff, gen_wq = mmnk_generator_solution(lam, N, mu, K)
        row = dict(lambda_=lam, N=N, mu=mu, K=K, rho=lam / (N * mu),
                   reps=len(g), sim_duration=p["sim_duration"], warmup=p["warmup"])
        for col, key in [("p_block", "P_K"), ("lambda_eff", "lambda_eff"),
                         ("mean_wait", "Wq"), ("p99_wait", "P99_Wq")]:
            m, s, h = ci95(g[col])
            row[f"sim_{key}_mean"] = m
            row[f"sim_{key}_ci95"] = h
        row["sim_P_K_legacy_summary_key_mean"] = float(g["p_block_legacy_key"].mean())
        row["ana_P_K"] = an.blocking_probability()
        row["ana_P_K_legacy_ErlangBAnalytical"] = legacy.blocking_probability_finite_k()
        row["ana_P_K_generator_solve"] = gen_pk
        row["ana_erlang_B_K_eq_N"] = legacy.erlang_b() if K == N else np.nan
        row["ana_lambda_eff"] = an.effective_arrival_rate()
        row["ana_Wq"] = an.mean_waiting_time()
        row["ana_Wq_generator_solve"] = gen_wq
        row["ana_P99_Wq"] = an.wait_percentile(0.99)
        row["P_K_within_ci"] = abs(row["sim_P_K_mean"] - row["ana_P_K"]) <= row["sim_P_K_ci95"]
        row["Wq_within_ci"] = abs(row["sim_Wq_mean"] - row["ana_Wq"]) <= row["sim_Wq_ci95"]
        out.append(row)
    df = pd.DataFrame(out).sort_values(["lambda_", "K"])
    df.to_csv(os.path.join(OUT, "finite_capacity.csv"), index=False)
    return df


def experiment_priority(pool):
    p = PQ
    N, mu = p["N"], p["mu"]
    combos = {(p["base_lambda"], p["base_frac"], "base")}
    for rho in p["rhos"]:
        combos.add((round(rho * N * mu, 6), p["base_frac"], "load_sweep"))
    for f in p["fracs"]:
        combos.add((p["base_lambda"], f, "frac_sweep"))
    # dedupe on (λ, f) keeping a sweep label list
    labels = {}
    for lam, f, lab in combos:
        labels.setdefault((lam, f), set()).add(lab)
    tasks = []
    for (lam, f) in sorted(labels):
        for pre in (False, True):
            for r in range(p["reps"]):
                tasks.append((lam, f, N, mu, pre, p["sim_duration"], p["warmup"],
                              p["seed0"] + r))
    raw = pd.DataFrame([row for rows in pool.map(run_pq, tasks, chunksize=1) for row in rows])
    raw.to_csv(os.path.join(OUT, "priority_replications.csv"), index=False)

    out = []
    for (lam, f, disc, cls), g in raw.groupby(["lambda_", "frac_high", "discipline", "cls"]):
        an = MMNPriorityAnalytical([lam * f, lam * (1 - f)], N, mu)
        pre = disc == "preemptive_resume"
        if cls == "all":
            ana = an.conservation_wait(preemptive=pre)
        else:
            k = int(cls)
            ana = an.preemptive_resume_wait(k) if pre else an.nonpreemptive_wait(k)
        row = dict(sweep="+".join(sorted(labels[(lam, f)])), discipline=disc,
                   lambda_=lam, rho=lam / (N * mu), frac_high=f, N=N, mu=mu, cls=cls,
                   reps=len(g), sim_duration=p["sim_duration"], warmup=p["warmup"])
        for col in ("mean_wait", "p95_wait", "p99_wait"):
            m, s, h = ci95(g[col])
            row[f"sim_{col}"] = m
            row[f"sim_{col}_ci95"] = h
        row["ana_mean_wait"] = ana
        row["ana_formula"] = ("conservation: sum(lam_k W_k)/lam" if cls == "all" else
                              "preemptive-resume exact (equal mu)" if pre else
                              "Cobham non-preemptive M/M/N")
        row["fcfs_mmn_Wq"] = an.fcfs_wait()
        row["fcfs_mmn_P99_Wq"] = mmn_p99_wait(lam, N, mu)
        row["within_ci"] = abs(row["sim_mean_wait"] - ana) <= row["sim_mean_wait_ci95"]
        out.append(row)
    df = pd.DataFrame(out).sort_values(["discipline", "lambda_", "frac_high", "cls"])
    df.to_csv(os.path.join(OUT, "priority.csv"), index=False)
    return df


def experiment_erlang(pool):
    p = EK
    tasks, short = [], []
    for name, (lam, N, mu) in p["configs"].items():
        for k in p["k_values"]:
            for r in range(p["reps"]):
                tasks.append((name, lam, N, mu, k, p["sim_duration"], p["warmup"],
                              p["seed0"] + r))
    lam, N, mu = p["configs"]["original_rho0.50"]
    for k in p["k_values"]:
        for r in range(p["reps"]):
            short.append(("original_short_100s", lam, N, mu, k, p["short_duration"],
                          p["short_warmup"], p["seed0"] + 1000 + r))
    res = pool.map(run_ek, tasks + short, chunksize=1)
    raw = pd.DataFrame(res)
    raw.to_csv(os.path.join(OUT, "erlang_k_replications.csv"), index=False)

    exact_cache = {}
    out = []
    for (name, k), g in raw[raw.config != "original_short_100s"].groupby(["config", "k"]):
        lam, N, mu = p["configs"][name]
        an = MEkNAnalytical(lam, N, mu, k)
        mmn = MMNAnalytical(lam, N, mu)
        row = dict(config=name, lambda_=lam, N=N, mu=mu, rho=lam / (N * mu), k=k,
                   cv2=1.0 / k, reps=len(g), sim_duration=p["sim_duration"],
                   warmup=p["warmup"])
        for col in ("mean_wait", "p99_wait", "cv2_service"):
            m, s, h = ci95(g[col])
            row[f"sim_{col}"] = m
            row[f"sim_{col}_ci95"] = h
        row["ana_allen_cunneen_Wq"] = an.mean_waiting_time()
        row["mmn_Wq"] = mmn.mean_waiting_time()
        row["mmn_P99_Wq_exact"] = mmn_p99_wait(lam, N, mu)
        # Exact CTMC only where the state space is tractable (k ≤ 4 for N = 6)
        if k <= 4:
            qmax = 150 if lam / (N * mu) > 0.7 else 60
            wq, tail = mekn_exact_ctmc(lam, N, mu, k, qmax)
            row["exact_ctmc_Wq"] = wq
            row["exact_ctmc_truncation_mass"] = tail
        else:
            row["exact_ctmc_Wq"] = np.nan
            row["exact_ctmc_truncation_mass"] = np.nan
        row["AC_within_ci"] = abs(row["sim_mean_wait"] - row["ana_allen_cunneen_Wq"]) <= row["sim_mean_wait_ci95"]
        out.append(row)
    df = pd.DataFrame(out).sort_values(["config", "k"])
    df.to_csv(os.path.join(OUT, "erlang_k.csv"), index=False)

    # Spread of the original single short-run design (100 s, 10 s warmup)
    sh = raw[raw.config == "original_short_100s"]
    old = pd.read_csv(os.path.join(ROOT, "results", "data", "erlang_improvement.csv"))
    rows = []
    for k, g in sh.groupby("k"):
        m, s, h = ci95(g["mean_wait"])
        old_val = old.loc[old.k_phases == k, "mean_wait"]
        old_val = float(old_val.iloc[0]) if len(old_val) else np.nan
        rows.append(dict(k=k, reps=len(g), sim_duration=p["short_duration"],
                         warmup=p["short_warmup"], mean_of_rep_means=m, sd_of_rep_means=s,
                         ci95=h, min_rep=float(g["mean_wait"].min()),
                         max_rep=float(g["mean_wait"].max()),
                         old_persisted_single_run=old_val,
                         old_value_percentile_among_reps=float(
                             (g["mean_wait"] <= old_val).mean() * 100) if old_val == old_val else np.nan))
    # how often a single short run of k=2 exceeds a single short run of k=1 (paired by rep index)
    w1 = sh[sh.k == 1].sort_values("seed")["mean_wait"].to_numpy()
    w2 = sh[sh.k == 2].sort_values("seed")["mean_wait"].to_numpy()
    sdf = pd.DataFrame(rows)
    sdf["frac_reps_k2_gt_k1"] = float(np.mean(w2 > w1))
    sdf.to_csv(os.path.join(OUT, "erlang_k_short_run_spread.csv"), index=False)
    return df, sdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--only", choices=["fc", "pq", "ek"], default=None)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    with Pool(args.workers) as pool:
        if args.only in (None, "fc"):
            t = time.time()
            df = experiment_finite_capacity(pool)
            print(f"\n[finite capacity] {time.time()-t:.0f}s")
            print(df[["lambda_", "K", "sim_P_K_mean", "sim_P_K_ci95", "ana_P_K",
                      "ana_P_K_generator_solve", "sim_Wq_mean", "sim_Wq_ci95", "ana_Wq",
                      "sim_P99_Wq_mean", "ana_P99_Wq"]].to_string(index=False))
        if args.only in (None, "pq"):
            t = time.time()
            df = experiment_priority(pool)
            print(f"\n[priority] {time.time()-t:.0f}s")
            print(df[["discipline", "lambda_", "frac_high", "cls", "sim_mean_wait",
                      "sim_mean_wait_ci95", "ana_mean_wait", "sim_p99_wait",
                      "fcfs_mmn_Wq"]].to_string(index=False))
        if args.only in (None, "ek"):
            t = time.time()
            df, sdf = experiment_erlang(pool)
            print(f"\n[erlang-k] {time.time()-t:.0f}s")
            print(df[["config", "k", "sim_mean_wait", "sim_mean_wait_ci95",
                      "ana_allen_cunneen_Wq", "exact_ctmc_Wq", "sim_p99_wait"]].to_string(index=False))
            print(sdf.to_string(index=False))


if __name__ == "__main__":
    main()
