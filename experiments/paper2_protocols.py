"""
Paper 2 — measured costs of consistency / consensus protocols.

Every number written by this script comes from a seeded simulation run (or an
exact numerical formula, clearly labelled `analytic_*`). Nothing is hand-typed.

Outputs (results/paper2/):
  twopc_overhead.csv        2PC overhead: sampled moments vs exact formulas
  twopc_queue_runs.csv      M/M/N with vs without 2PC, one row per replication
  twopc_queue.csv           ... aggregated (mean, 95% CI over replications)
  twopc_instability.csv     λ near/above the 2PC saturation point (backlog growth)
  twopc_protocol.csv        TwoPhaseCommitCluster commit rate / atomicity
  raft_elections_runs.csv   Raft election + leader-failover, one row per seed
  raft_elections.csv        ... aggregated
  raft_commit_runs.csv      Raft append->majority-commit latency, one row per seed
  raft_commit.csv           ... aggregated
  raft_queue_runs.csv       M/M/N with vs without synchronous Raft commit
  raft_queue.csv            ... aggregated
  protocol_capacity.csv     closed-loop (saturated) throughput, baseline/2PC/Raft
  vector_clocks_runs.csv    causal broadcast hold-back, one row per seed
  vector_clocks.csv         ... aggregated
  vector_clocks_correctness.csv  pass/fail correctness checks
  protocols_reproducibility.csv  same seed run twice -> identical outputs
  protocols_run_metadata.json    parameters, seeds, runtime

Usage:  ./venv/bin/python experiments/paper2_protocols.py [--quick]
"""

import argparse
import contextlib
import io
import json
import os
import random
import sys
import time
import warnings
from multiprocessing import Pool

warnings.filterwarnings('ignore', message='Field "model_type" has conflict')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import simpy
from scipy import stats

from src.core.config import MMNConfig
from src.core.distributions import ExponentialService, TwoPhaseCommitService
from src.models.base import QueueModel
from src.models.mmn_queue import MMNQueue
from src.models.mmn_2pc_queue import MMN2PCQueue
from src.models.raft_consensus import RaftCluster
from src.models.two_phase_commit import TwoPhaseCommitCluster
from src.models.vector_clocks import (CausalityTracker, CausalMessageQueue,
                                      CausalBroadcastMember,
                                      simulate_causal_broadcast)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 'paper2')

# ----------------------------------------------------------------------------
# Global experiment parameters
# ----------------------------------------------------------------------------
N_THREADS = 10
MU = 12.0
SIM_DURATION = 1000.0
WARMUP = 100.0
N_REPS = 10
BASE_SEED = 1000

RAFT_PARAM_SETS = {
    # name: (timeout_min, timeout_max, heartbeat, one-way delay, jitter)
    'default_model': (10.0, 20.0, 5.0, 0.0, 0.0),        # model defaults, instant network
    'realistic_lan': (0.150, 0.300, 0.050, 0.002, 0.003),  # one-way U[2,5] ms
    'realistic_wan': (0.150, 0.300, 0.050, 0.020, 0.010),  # one-way U[20,30] ms
}
RAFT_SIZES = [3, 5, 7]
RAFT_ELECTION_SEEDS = 30
RAFT_COMMIT_SEEDS = 20


def ci95(values):
    """(mean, half-width of 95% t-interval, n)."""
    a = np.asarray([v for v in values if v is not None and not np.isnan(v)], dtype=float)
    n = len(a)
    if n == 0:
        return np.nan, np.nan, 0
    if n == 1:
        return float(a[0]), np.nan, 1
    hw = stats.t.ppf(0.975, n - 1) * a.std(ddof=1) / np.sqrt(n)
    return float(a.mean()), float(hw), n


def aggregate(df, group_cols, metric_cols):
    rows = []
    for key, g in df.groupby(group_cols, dropna=False, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_cols, key))
        row['n_reps'] = len(g)
        for m in metric_cols:
            mean, hw, _ = ci95(g[m].values)
            row[f'{m}_mean'] = mean
            row[f'{m}_ci95'] = hw
        rows.append(row)
    return pd.DataFrame(rows)


def erlang_c(n, a):
    """Erlang-C probability of waiting, a = λ·E[S] (offered load), n servers."""
    import math
    rho = a / n
    if rho >= 1:
        return 1.0
    s = sum(a ** k / math.factorial(k) for k in range(n))
    last = a ** n / (math.factorial(n) * (1 - rho))
    return last / (s + last)


# ============================================================================
# 1. 2PC
# ============================================================================
TWOPC_OVERHEAD_CONFIGS = (
    # (label, replicas, availability, vote_timeout, rtt_mean, rtt_std)
    [('default', 3, 0.99, 1.0, 0.010, 0.002)]
    + [(f'avail_{a}', 3, a, 1.0, 0.010, 0.002) for a in (1.0, 0.999, 0.95)]
    + [(f'timeout_{t}', 3, 0.99, t, 0.010, 0.002) for t in (0.1, 0.5)]
    + [(f'replicas_{n}', n, 0.99, 1.0, 0.010, 0.002) for n in (1, 5, 7)]
)
TWOPC_OVERHEAD_SAMPLES = 200_000


def task_twopc_overhead(cfg):
    label, n, a, T, m, s = cfg
    seed = BASE_SEED + 7
    d = TwoPhaseCommitService(ExponentialService(MU), num_replicas=n,
                              network_rtt_mean=m, network_rtt_std=s,
                              replica_availability=a, vote_timeout=T)
    mom = d.overhead_moments()
    np.random.seed(seed)
    o = np.array([d.sample_overhead() for _ in range(TWOPC_OVERHEAD_SAMPLES)])
    np.random.seed(seed + 1)
    tot = np.array([d.sample() for _ in range(TWOPC_OVERHEAD_SAMPLES)])
    # Legacy (pre-fix) formulas, reproduced verbatim for comparison
    p_all = a ** n
    legacy_overhead_mean = m + (p_all * m + (1 - p_all) * T) + m
    legacy_overhead_var = 3 * s ** 2
    k = TWOPC_OVERHEAD_SAMPLES
    return {
        'config': label, 'num_replicas': n, 'replica_availability': a,
        'vote_timeout_s': T, 'rtt_mean_s': m, 'rtt_std_s': s,
        'n_samples': k, 'seed': seed,
        'sampled_timeout_fraction': d.timeout_count / k,  # counted by sample() only
        'analytic_p_any_timeout': mom['p_any_timeout'],
        'sampled_overhead_mean_s': float(o.mean()),
        'sampled_overhead_mean_se_s': float(o.std(ddof=1) / np.sqrt(k)),
        'analytic_overhead_mean_s': mom['E_O'],
        'legacy_formula_overhead_mean_s': legacy_overhead_mean,
        'sampled_overhead_var_s2': float(o.var(ddof=1)),
        'analytic_overhead_var_s2': mom['Var_O'],
        'legacy_formula_overhead_var_s2': legacy_overhead_var,
        'sampled_overhead_p99_s': float(np.percentile(o, 99)),
        'sampled_total_mean_s': float(tot.mean()),
        'analytic_total_mean_s': d.mean(),
        'sampled_total_var_s2': float(tot.var(ddof=1)),
        'analytic_total_var_s2': d.variance(),
        'base_mean_s': 1.0 / MU,
        'analytic_saturation_lambda_N10': N_THREADS / d.mean(),
        'baseline_saturation_lambda_N10': N_THREADS * MU,
        'analytic_capacity_reduction_pct': 100.0 * (1 - (N_THREADS / d.mean()) / (N_THREADS * MU)),
        'z_mean_diff': float((o.mean() - mom['E_O']) / (o.std(ddof=1) / np.sqrt(k))),
    }


def _queue_stats(metrics, model, sim_duration, warmup):
    w = np.asarray(metrics.wait_times)
    s = np.asarray(metrics.service_times)
    r = w + s
    return {
        'n_measured': len(w),
        'throughput': len(w) / (sim_duration - warmup),
        'mean_wait_s': float(w.mean()),
        'mean_response_s': float(r.mean()),
        'p50_response_s': float(np.percentile(r, 50)),
        'p95_response_s': float(np.percentile(r, 95)),
        'p99_response_s': float(np.percentile(r, 99)),
        'mean_holding_time_s': float(s.mean()),
        'backlog_at_end': model.message_id - model.messages_in_warmup - len(w),
        # measured offered utilisation: λ · (mean thread-holding time) / N
        'measured_rho_eff': model.config.arrival_rate * float(s.mean()) / model.config.num_threads,
    }


def task_twopc_queue(cfg):
    """cfg = (variant, lam, availability, vote_timeout, rep)."""
    variant, lam, a, T, rep = cfg
    seed = BASE_SEED + rep
    config = MMNConfig(arrival_rate=lam, num_threads=N_THREADS, service_rate=MU,
                       sim_duration=SIM_DURATION, warmup_time=WARMUP, random_seed=seed)
    env = simpy.Environment()
    if variant == 'no_2pc':
        model = MMNQueue(env, config)
        e_s = 1.0 / MU
        var_s = 1.0 / MU ** 2
        timeout_rate = np.nan
    else:
        model = MMN2PCQueue(env, config, num_replicas=3, network_rtt_mean=0.010,
                            replica_availability=a, network_rtt_std=0.002,
                            vote_timeout=T, verbose=False)
        e_s = model.service_dist.mean()
        var_s = model.service_dist.variance()
    with contextlib.redirect_stdout(io.StringIO()):
        metrics = model.run()
    if variant != 'no_2pc':
        tm = model.service_dist.get_2pc_metrics()
        timeout_rate = tm['timeout_rate']
    row = {'variant': variant, 'arrival_rate': lam,
           'replica_availability': a if variant != 'no_2pc' else np.nan,
           'vote_timeout_s': T if variant != 'no_2pc' else np.nan,
           'rep': rep, 'seed': seed,
           'analytic_E_S_s': e_s, 'analytic_rho_eff': lam * e_s / N_THREADS,
           'sampled_timeout_rate': timeout_rate}
    row.update(_queue_stats(metrics, model, SIM_DURATION, WARMUP))
    # Analytic reference values (labelled): Erlang-C M/M/N for the baseline;
    # Allen–Cunneen M/G/N approximation Wq ≈ Wq_MMN(E[S])·(1+C²)/2 for 2PC.
    a_load = lam * e_s
    c = erlang_c(N_THREADS, a_load)
    wq_mmn = c * e_s / (N_THREADS * (1 - a_load / N_THREADS))
    cs2 = var_s / e_s ** 2
    row['analytic_Wq_s'] = wq_mmn if variant == 'no_2pc' else wq_mmn * (1 + cs2) / 2
    row['analytic_Wq_method'] = 'erlang_c_exact' if variant == 'no_2pc' else 'allen_cunneen_approx'
    return row


def task_twopc_instability(cfg):
    """Default 2PC config at λ near/above saturation; monitor number in system."""
    lam, variant, rep = cfg
    seed = BASE_SEED + rep
    config = MMNConfig(arrival_rate=lam, num_threads=N_THREADS, service_rate=MU,
                       sim_duration=SIM_DURATION, warmup_time=WARMUP, random_seed=seed)
    env = simpy.Environment()
    if variant == 'no_2pc':
        model = MMNQueue(env, config)
        cap = N_THREADS * MU
    else:
        model = MMN2PCQueue(env, config, verbose=False)
        cap = N_THREADS / model.service_dist.mean()
    samples = []

    def monitor():
        while True:
            yield env.timeout(10.0)
            samples.append((env.now, len(model.threads.queue) + model.threads.count))

    env.process(monitor())
    with contextlib.redirect_stdout(io.StringIO()):
        metrics = model.run()
    t = np.array([x[0] for x in samples if x[0] >= WARMUP])
    q = np.array([x[1] for x in samples if x[0] >= WARMUP])
    slope = float(np.polyfit(t, q, 1)[0])
    return {
        'variant': variant, 'arrival_rate': lam, 'rep': rep, 'seed': seed,
        'analytic_saturation_lambda': cap,
        'analytic_rho_eff': lam / cap,
        'predicted_backlog_slope_if_unstable': max(0.0, lam - cap),
        'measured_number_in_system_at_t500': int(q[np.argmin(abs(t - 500))]),
        'measured_number_in_system_at_end': int(q[-1]),
        'measured_backlog_slope_msg_per_s': slope,
        'measured_throughput': len(metrics.wait_times) / (SIM_DURATION - WARMUP),
        'measured_mean_wait_s': float(np.mean(metrics.wait_times)),
    }


def task_twopc_protocol(cfg):
    n_part, f, rep = cfg
    seed = BASE_SEED + rep
    random.seed(seed)
    env = simpy.Environment()
    cluster = TwoPhaseCommitCluster(env=env, num_participants=n_part, failure_rate=f)
    n_tx = 200
    for i in range(n_tx):
        cluster.execute_transaction('delete_message', {'message_id': i}, timeout=5.0)
    env.run(until=100)
    m = cluster.get_metrics()
    commits = [p['commits_executed'] for p in m['participants']]
    aborts = [p['aborts_executed'] for p in m['participants']]
    lat = np.array(list(cluster.coordinator.decision_latencies.values()))
    return {
        'num_participants': n_part, 'vote_no_prob': f, 'rep': rep, 'seed': seed,
        'transactions': m['coordinator']['total_transactions'],
        'decided': len(lat),
        'commit_rate': m['coordinator']['commit_rate'],
        'analytic_commit_rate': (1 - f) ** n_part,
        'timeout_aborts': m['coordinator']['timeout_aborts'],
        'atomicity_ok': (len(set(commits)) == 1 and len(set(aborts)) == 1
                         and commits[0] == m['coordinator']['committed']
                         and aborts[0] == m['coordinator']['aborted']),
        'decision_latency_mean_s_POLLING_ARTIFACT': float(lat.mean()) if len(lat) else np.nan,
    }


# ============================================================================
# 2. Raft
# ============================================================================
def _make_cluster(env, n, pset, replicate=False):
    tmin, tmax, hb, d, j = RAFT_PARAM_SETS[pset]
    return RaftCluster(env, num_nodes=n, election_timeout_min=tmin,
                       election_timeout_max=tmax, heartbeat_interval=hb,
                       network_delay=d, network_jitter=j,
                       replicate_log_entries=replicate)


def task_raft_election(cfg):
    pset, n, seed = cfg
    tmin, tmax, hb, d, j = RAFT_PARAM_SETS[pset]
    random.seed(seed)
    env = simpy.Environment()
    cl = _make_cluster(env, n, pset)
    step = tmin / 20.0
    while not cl.leadership_events() and env.now < 100 * tmax:
        env.run(until=env.now + step)
    lead = cl.leadership_events()
    if not lead:
        return {'param_set': pset, 'cluster_size': n, 'seed': seed, 'leader_elected': False}
    t_first, term_first, leader_id = lead[0]
    cands_before = [c for c in cl.candidacy_events() if c[0] <= t_first]

    # Stable period of 10 heartbeats, then crash the leader
    t_crash = t_first + 10 * hb
    env.run(until=t_crash)
    spurious = len(cl.leadership_events()) - 1
    old = cl.nodes[leader_id]
    old_term = old.current_term
    old.crash()
    horizon = t_crash + 50 * tmax
    new = []
    while env.now < horizon:
        env.run(until=env.now + step)
        new = [e for e in cl.leadership_events() if e[0] > t_crash and e[1] > old_term]
        if new:
            break
    cands_failover = [c for c in cl.candidacy_events()
                      if c[0] > t_crash and (not new or c[0] <= new[0][0])]
    row = {
        'param_set': pset, 'cluster_size': n, 'seed': seed,
        'election_timeout_min_s': tmin, 'election_timeout_max_s': tmax,
        'heartbeat_s': hb, 'one_way_delay_s': d, 'jitter_s': j,
        'leader_elected': True,
        'first_leader_time_s': t_first,
        'first_leader_term': term_first,
        'failed_terms_before_first_leader': term_first - 1,
        'candidacies_before_first_leader': len(cands_before),
        'spurious_elections_in_stable_period': spurious,
        'failover_leader_elected': bool(new),
        'reelection_time_s': (new[0][0] - t_crash) if new else np.nan,
        'failover_candidacies': len(cands_failover),
        'failover_new_term': new[0][1] if new else np.nan,
        'election_safety_violations': cl.election_safety_violations(),
        'messages_sent_total': sum(x.messages_sent for x in cl.nodes),
    }
    return row


RAFT_APPEND_RATE = 100.0   # entries/s offered to the leader
RAFT_APPEND_DURATION = 5.0  # s (default_model: 50 s, scaled with timeouts)


def task_raft_commit(cfg):
    pset, n, seed, replicate = cfg
    tmin, tmax, hb, d, j = RAFT_PARAM_SETS[pset]
    random.seed(seed)
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    cl = _make_cluster(env, n, pset, replicate=replicate)
    step = tmin / 20.0
    while cl.get_current_leader() is None and env.now < 100 * tmax:
        env.run(until=env.now + step)
    leader = cl.get_current_leader()
    t0 = env.now + 2 * hb
    env.run(until=t0)
    duration = RAFT_APPEND_DURATION if pset != 'default_model' else 10 * RAFT_APPEND_DURATION
    appended = []

    def client():
        while env.now < t0 + duration:
            yield env.timeout(rng.exponential(1.0 / RAFT_APPEND_RATE))
            L = cl.get_current_leader()
            if L is not None and L.append_log_entry('publish', {'t': env.now}):
                appended.append((L.node_id, len(L.log)))

    env.process(client())
    env.run(until=t0 + duration + 20 * hb + 10 * (d + j))
    lat = []
    for node_id, idx in appended:
        L = cl.nodes[node_id]
        if idx in L.entry_commit_time:
            lat.append(L.entry_commit_time[idx] - L.entry_append_time[idx])
    lat = np.array(lat)
    # Log Matching check on committed prefixes
    lm_ok = True
    ref = max(cl.nodes, key=lambda x: x.commit_index)
    for x in cl.nodes:
        k = min(x.commit_index, len(x.log))
        if [(e.term, e.index) for e in x.log[:k]] != [(e.term, e.index) for e in ref.log[:k]]:
            lm_ok = False
    leaders_changed = len(cl.leadership_events()) - 1
    return {
        'param_set': pset, 'cluster_size': n, 'seed': seed,
        'replicate_log_entries': replicate,
        'one_way_delay_s': d, 'jitter_s': j, 'heartbeat_s': hb,
        'append_rate': RAFT_APPEND_RATE, 'append_duration_s': duration,
        'entries_appended': len(appended),
        'entries_committed': int(len(lat)),
        'committed_fraction': len(lat) / len(appended) if appended else np.nan,
        'commit_latency_mean_s': float(lat.mean()) if len(lat) else np.nan,
        'commit_latency_p50_s': float(np.percentile(lat, 50)) if len(lat) else np.nan,
        'commit_latency_p95_s': float(np.percentile(lat, 95)) if len(lat) else np.nan,
        'commit_latency_p99_s': float(np.percentile(lat, 99)) if len(lat) else np.nan,
        'commit_latency_max_s': float(lat.max()) if len(lat) else np.nan,
        'follower_commit_index_min': min(x.commit_index for x in cl.nodes if x is not leader) if leader else np.nan,
        'log_matching_ok': lm_ok,
        'leader_changes_during_run': leaders_changed,
        'election_safety_violations': cl.election_safety_violations(),
    }


class MMNRaftQueue(QueueModel):
    """
    M/M/N broker where each message, after base processing, is appended to a
    Raft log and its worker thread BLOCKS until the leader marks the entry
    committed (synchronous replication before ack). Same blocking assumption
    as MMN2PCQueue. No batching, no disk fsync, no client retries modelled.
    Holding time recorded as service_time = base processing + commit wait.
    """

    COMMIT_GIVEUP_S = 1.0

    def __init__(self, env, config, cluster):
        self.cluster = cluster
        self.commit_latencies = []
        self.commit_giveups = 0
        super().__init__(env, config)

    def model_name(self):
        return f"M/M/{self.config.num_threads} + Raft"

    def get_service_time(self):
        return np.random.exponential(1.0 / self.config.service_rate)

    def process_message(self, message_id):
        arrival_time = self.env.now
        queue_length = len(self.threads.queue)
        with self.threads.request() as request:
            yield request
            wait_time = self.env.now - arrival_time
            start = self.env.now
            yield self.env.timeout(self.get_service_time())
            t_app = self.env.now
            while True:
                L = self.cluster.get_current_leader()
                ev = L.append_and_wait('publish', {'id': message_id}) if L else None
                if ev is not None:
                    break
                yield self.env.timeout(0.01)  # no leader yet (only during warmup)
            res = yield ev | self.env.timeout(self.COMMIT_GIVEUP_S)
            if ev in res:
                self.commit_latencies.append(self.env.now - t_app)
            else:
                self.commit_giveups += 1
            service_time = self.env.now - start
            if not self.is_warmup():
                self.metrics.arrival_times.append(arrival_time)
                self.metrics.wait_times.append(wait_time)
                self.metrics.service_times.append(service_time)
                self.metrics.queue_lengths.append(queue_length)
                self.metrics.departure_times.append(self.env.now)
            else:
                self.messages_in_warmup += 1


RAFT_QUEUE_LAMBDAS = [60.0, 100.0]  # 100 = paper default (ρ = 0.833 without consensus)


def task_raft_queue(cfg):
    variant, n, lam, rep = cfg  # variant: 'no_consensus' or a RAFT_PARAM_SETS key
    seed = BASE_SEED + rep
    random.seed(seed)
    config = MMNConfig(arrival_rate=lam, num_threads=N_THREADS, service_rate=MU,
                       sim_duration=SIM_DURATION, warmup_time=WARMUP, random_seed=seed)
    env = simpy.Environment()
    if variant == 'no_consensus':
        model = MMNQueue(env, config)
        with contextlib.redirect_stdout(io.StringIO()):
            metrics = model.run()
        extra = {'commit_latency_mean_s': np.nan, 'commit_giveups': 0,
                 'leader_changes': 0}
    else:
        cl = _make_cluster(env, n, variant, replicate=True)
        model = MMNRaftQueue(env, config, cl)
        with contextlib.redirect_stdout(io.StringIO()):
            metrics = model.run()
        extra = {'commit_latency_mean_s': float(np.mean(model.commit_latencies)),
                 'commit_giveups': model.commit_giveups,
                 'leader_changes': len(cl.leadership_events()) - 1}
    row = {'variant': variant, 'cluster_size': n if variant != 'no_consensus' else 0,
           'arrival_rate': lam, 'rep': rep, 'seed': seed}
    row.update(_queue_stats(metrics, model, SIM_DURATION, WARMUP))
    row.update(extra)
    return row


# ---------------------------------------------------------------------------
# Closed-loop saturated capacity (N always-busy workers)
# ---------------------------------------------------------------------------
CAP_DURATION = 300.0
CAP_WARMUP = 30.0


def task_capacity(cfg):
    variant, param, rep = cfg
    seed = BASE_SEED + rep
    np.random.seed(seed)
    random.seed(seed)
    env = simpy.Environment()
    done = [0]
    cluster = None
    dist = None
    if variant == '2pc':
        a, T = param
        dist = TwoPhaseCommitService(ExponentialService(MU), replica_availability=a, vote_timeout=T)
    elif variant == 'raft':
        pset, n = param
        cluster = _make_cluster(env, n, pset, replicate=True)

    def worker():
        while True:
            if variant == '2pc':
                yield env.timeout(dist.sample())
            else:
                yield env.timeout(np.random.exponential(1.0 / MU))
                if variant == 'raft':
                    while True:
                        L = cluster.get_current_leader()
                        ev = L.append_and_wait('publish', {}) if L else None
                        if ev is not None:
                            break
                        yield env.timeout(0.01)
                    yield ev | env.timeout(1.0)
            if env.now > CAP_WARMUP:
                done[0] += 1

    for _ in range(N_THREADS):
        env.process(worker())
    env.run(until=CAP_DURATION)
    return {'variant': variant, 'param': str(param), 'rep': rep, 'seed': seed,
            'num_threads': N_THREADS, 'mu': MU,
            'measured_capacity_msg_per_s': done[0] / (CAP_DURATION - CAP_WARMUP),
            'analytic_capacity_msg_per_s': (N_THREADS * MU if variant == 'none'
                                            else N_THREADS / dist.mean() if variant == '2pc'
                                            else np.nan)}


# ============================================================================
# 3. Vector clocks
# ============================================================================
def task_vc(cfg):
    impl, n, rate, cv, seed = cfg
    return simulate_causal_broadcast(num_processes=n, broadcast_rate=rate,
                                     delay_mean=0.010, delay_cv=cv, duration=30.0,
                                     seed=seed, implementation=impl)


def vector_clock_correctness(vc_runs):
    rows = []

    def add(check, passed, detail=''):
        rows.append({'check': check, 'passed': bool(passed), 'detail': detail})

    # Scripted scenario from experiments/distributed_systems_validation.py (Exp. 3)
    t = CausalityTracker(num_processes=3)
    t.local_event(0); e1 = t.send_event(0); t.receive_event(1, e1); t.local_event(1)
    t.local_event(2); e5 = t.send_event(1); t.receive_event(2, e5)
    for (i, j, want, name) in [(0, 1, 'happened_before', 'E0->E1 same process'),
                               (1, 2, 'happened_before', 'E1->E2 send-receive'),
                               (0, 2, 'happened_before', 'E0->E2 transitivity'),
                               (2, 4, 'concurrent', 'E2||E4 concurrent'),
                               (1, 4, 'concurrent', 'E1||E4 concurrent'),
                               (2, 6, 'happened_before', 'E2->E6 transitivity')]:
        got = t.check_causality(i, j)
        add(f'CausalityTracker {name}', got == want, f'got={got}')

    # Out-of-order scenario (Exp. 4) with the legacy queue and with BSS
    q = [CausalMessageQueue(i, 3) for i in range(3)]
    m1 = q[0].send_message('m1'); q[1].receive_message(*m1)
    m2 = q[1].send_message('m2')
    held = q[2].receive_message(*m2) is None
    q[2].receive_message(*m1)
    add('Legacy CausalMessageQueue: m2 held back before m1', held)
    add('Legacy CausalMessageQueue: m2 eventually delivered', len(q[2].pending_messages) == 0,
        f'pending={len(q[2].pending_messages)} (known bug: clock counts receives)')

    b = [CausalBroadcastMember(i, 3) for i in range(3)]
    ts1 = b[0].broadcast(); b[1].receive(0, ts1, 'm1')
    ts2 = b[1].broadcast()
    d_first = b[2].receive(1, ts2, 'm2')
    d_second = b[2].receive(0, ts1, 'm1')
    add('BSS: m2 held back before m1', d_first == [])
    add('BSS: m1 then m2 delivered in causal order', d_second == ['m1', 'm2'], f'{d_second}')

    df = pd.DataFrame(vc_runs)
    bss = df[df.implementation == 'bss']
    none = df[df.implementation == 'none']
    add('BSS simulation: zero causal-order violations (all runs)',
        int(bss.causal_violations.sum()) == 0, f'runs={len(bss)}, violations={int(bss.causal_violations.sum())}')
    add('BSS simulation: every reception eventually delivered (all runs)',
        int(bss.undelivered.sum()) == 0, f'undelivered={int(bss.undelivered.sum())}')
    const = bss[bss.delay_cv == 0]
    add('BSS simulation: constant delay -> zero hold-backs (FIFO+uniform delay)',
        int(const.held_back.sum()) == 0, f'held_back={int(const.held_back.sum())}')
    var = none[none.delay_cv > 0]
    add('Checker negative control: no-ordering delivery shows violations when delay varies',
        int(var.causal_violations.sum()) > 0, f'violations={int(var.causal_violations.sum())}')
    return pd.DataFrame(rows)


# ============================================================================
# Driver
# ============================================================================
def _init_globals(values):
    """Pool initializer: workers are spawned fresh, so copy run-time globals."""
    globals().update(values)


def run_pool(pool, fn, cfgs, name):
    t = time.time()
    out = pool.map(fn, cfgs, chunksize=1)
    print(f'  {name}: {len(cfgs)} runs in {time.time() - t:.1f}s', flush=True)
    return out


def main():
    global N_REPS, SIM_DURATION, WARMUP, RAFT_ELECTION_SEEDS, RAFT_COMMIT_SEEDS, TWOPC_OVERHEAD_SAMPLES
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='tiny smoke run (results NOT for the paper)')
    ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = ap.parse_args()
    out_dir = OUT_DIR
    if args.quick:
        N_REPS, SIM_DURATION, WARMUP = 2, 200.0, 20.0
        RAFT_ELECTION_SEEDS, RAFT_COMMIT_SEEDS, TWOPC_OVERHEAD_SAMPLES = 3, 2, 5000
        out_dir = os.path.join(OUT_DIR, 'quick')
    os.makedirs(out_dir, exist_ok=True)
    t_start = time.time()

    def save(df, name):
        df.to_csv(os.path.join(out_dir, name), index=False)
        print(f'  wrote {name} ({len(df)} rows)', flush=True)

    shared = {k: globals()[k] for k in ('N_REPS', 'SIM_DURATION', 'WARMUP', 'RAFT_ELECTION_SEEDS',
                                        'RAFT_COMMIT_SEEDS', 'TWOPC_OVERHEAD_SAMPLES')}
    with Pool(args.procs, initializer=_init_globals, initargs=(shared,)) as pool:
        # ---------------- 2PC ----------------
        print('2PC overhead moments...', flush=True)
        save(pd.DataFrame(run_pool(pool, task_twopc_overhead, TWOPC_OVERHEAD_CONFIGS, 'overhead')),
             'twopc_overhead.csv')

        print('2PC queue sweep...', flush=True)
        q_cfgs = []
        lambdas = [20.0, 40.0, 60.0, 75.0]
        for lam in lambdas:
            for rep in range(N_REPS):
                q_cfgs.append(('no_2pc', lam, np.nan, np.nan, rep))
        variants = [(a, 1.0) for a in (1.0, 0.999, 0.99)] + [(0.99, 0.1), (0.99, 0.5)]
        for a, T in variants:
            e_s = TwoPhaseCommitService(ExponentialService(MU), replica_availability=a,
                                        vote_timeout=T).mean()
            for lam in lambdas:
                if lam * e_s / N_THREADS < 0.9:  # keep ρ_eff < 0.9 (stable, finite variance)
                    for rep in range(N_REPS):
                        q_cfgs.append(('2pc', lam, a, T, rep))
        runs = pd.DataFrame(run_pool(pool, task_twopc_queue, q_cfgs, 'twopc queue'))
        save(runs, 'twopc_queue_runs.csv')
        metrics = ['throughput', 'mean_wait_s', 'mean_response_s', 'p95_response_s',
                   'p99_response_s', 'mean_holding_time_s', 'sampled_timeout_rate',
                   'measured_rho_eff', 'backlog_at_end']
        agg = aggregate(runs, ['variant', 'replica_availability', 'vote_timeout_s', 'arrival_rate'],
                        metrics)
        first = runs.groupby(['variant', 'replica_availability', 'vote_timeout_s', 'arrival_rate'],
                             dropna=False, sort=True)[['analytic_E_S_s', 'analytic_rho_eff',
                                                       'analytic_Wq_s', 'analytic_Wq_method']].first().reset_index()
        agg = agg.merge(first, on=['variant', 'replica_availability', 'vote_timeout_s', 'arrival_rate'])
        base = agg[agg.variant == 'no_2pc'].set_index('arrival_rate')
        for col in ['mean_response_s_mean', 'p99_response_s_mean', 'mean_wait_s_mean']:
            agg[col.replace('_mean', '') + '_ratio_vs_no2pc'] = [
                r[col] / base.loc[r.arrival_rate, col] for _, r in agg.iterrows()]
        save(agg, 'twopc_queue.csv')

        print('2PC instability...', flush=True)
        lam_star = N_THREADS / TwoPhaseCommitService(ExponentialService(MU)).mean()
        inst_lams = [round(f * lam_star, 3) for f in (0.9, 0.95, 1.05, 1.1)] + [100.0]
        i_cfgs =[(lam, '2pc', rep) for lam in inst_lams for rep in range(N_REPS)] + \
                 [(100.0, 'no_2pc', rep) for rep in range(N_REPS)]
        inst = pd.DataFrame(run_pool(pool, task_twopc_instability, i_cfgs, 'instability'))
        inst_agg = aggregate(inst, ['variant', 'arrival_rate'],
                             ['measured_backlog_slope_msg_per_s', 'measured_number_in_system_at_end',
                              'measured_throughput', 'measured_mean_wait_s'])
        f2 = inst.groupby(['variant', 'arrival_rate'])[['analytic_saturation_lambda', 'analytic_rho_eff',
                                                        'predicted_backlog_slope_if_unstable']].first().reset_index()
        save(inst_agg.merge(f2, on=['variant', 'arrival_rate']), 'twopc_instability.csv')
        save(inst, 'twopc_instability_runs.csv')

        print('2PC protocol cluster...', flush=True)
        p_cfgs = [(n, f, rep) for n in (3, 5) for f in (0.0, 0.05, 0.1, 0.3) for rep in range(N_REPS)]
        prot = pd.DataFrame(run_pool(pool, task_twopc_protocol, p_cfgs, 'protocol'))
        pagg = aggregate(prot, ['num_participants', 'vote_no_prob'],
                         ['commit_rate', 'decision_latency_mean_s_POLLING_ARTIFACT'])
        pagg = pagg.merge(prot.groupby(['num_participants', 'vote_no_prob']).agg(
            analytic_commit_rate=('analytic_commit_rate', 'first'),
            atomicity_ok_all_reps=('atomicity_ok', 'all'),
            timeout_aborts_total=('timeout_aborts', 'sum')).reset_index(),
            on=['num_participants', 'vote_no_prob'])
        save(pagg, 'twopc_protocol.csv')

        # ---------------- Raft ----------------
        print('Raft elections...', flush=True)
        e_cfgs = [(p, n, s) for p in RAFT_PARAM_SETS for n in RAFT_SIZES
                  for s in range(RAFT_ELECTION_SEEDS)]
        el = pd.DataFrame(run_pool(pool, task_raft_election, e_cfgs, 'elections'))
        save(el, 'raft_elections_runs.csv')
        el_agg = aggregate(el, ['param_set', 'cluster_size'],
                           ['first_leader_time_s', 'failed_terms_before_first_leader',
                            'candidacies_before_first_leader', 'reelection_time_s',
                            'failover_candidacies', 'spurious_elections_in_stable_period'])
        extra = el.groupby(['param_set', 'cluster_size']).agg(
            leader_elected_all=('leader_elected', 'all'),
            failover_success_all=('failover_leader_elected', 'all'),
            split_vote_runs=('failed_terms_before_first_leader', lambda x: int((x > 0).sum())),
            first_leader_time_p95_s=('first_leader_time_s', lambda x: float(np.percentile(x, 95))),
            reelection_time_p95_s=('reelection_time_s', lambda x: float(np.nanpercentile(x, 95))),
            reelection_time_max_s=('reelection_time_s', 'max'),
            election_safety_violations_total=('election_safety_violations', 'sum')).reset_index()
        save(el_agg.merge(extra, on=['param_set', 'cluster_size']), 'raft_elections.csv')

        print('Raft commit latency...', flush=True)
        c_cfgs = [(p, n, s, True) for p in RAFT_PARAM_SETS for n in RAFT_SIZES
                  for s in range(RAFT_COMMIT_SEEDS)]
        # Original model (replicate_log_entries=False) to document that nothing commits
        c_cfgs += [('default_model', n, s, False) for n in RAFT_SIZES for s in range(RAFT_COMMIT_SEEDS)]
        cm = pd.DataFrame(run_pool(pool, task_raft_commit, c_cfgs, 'commit'))
        save(cm, 'raft_commit_runs.csv')
        cm_agg = aggregate(cm, ['param_set', 'replicate_log_entries', 'cluster_size'],
                           ['committed_fraction', 'commit_latency_mean_s', 'commit_latency_p50_s',
                            'commit_latency_p95_s', 'commit_latency_p99_s', 'entries_appended'])
        cm_agg = cm_agg.merge(cm.groupby(['param_set', 'replicate_log_entries', 'cluster_size']).agg(
            commit_latency_max_s=('commit_latency_max_s', 'max'),
            log_matching_ok_all=('log_matching_ok', 'all'),
            leader_changes_total=('leader_changes_during_run', 'sum'),
            election_safety_violations_total=('election_safety_violations', 'sum')).reset_index(),
            on=['param_set', 'replicate_log_entries', 'cluster_size'])
        save(cm_agg, 'raft_commit.csv')

        print('Raft-in-queue (N=10, μ=12)...', flush=True)
        rq_cfgs = [('no_consensus', 0, lam, rep) for lam in RAFT_QUEUE_LAMBDAS for rep in range(N_REPS)]
        rq_cfgs += [(p, n, lam, rep) for p in ('realistic_lan', 'realistic_wan') for n in (3, 5)
                    for lam in RAFT_QUEUE_LAMBDAS for rep in range(N_REPS)]
        rq = pd.DataFrame(run_pool(pool, task_raft_queue, rq_cfgs, 'raft queue'))
        save(rq, 'raft_queue_runs.csv')
        gk = ['variant', 'cluster_size', 'arrival_rate']
        rq_agg = aggregate(rq, gk,
                           ['throughput', 'mean_wait_s', 'mean_response_s', 'p95_response_s',
                            'p99_response_s', 'mean_holding_time_s', 'commit_latency_mean_s',
                            'measured_rho_eff', 'backlog_at_end'])
        rq_agg = rq_agg.merge(rq.groupby(gk).agg(
            commit_giveups_total=('commit_giveups', 'sum'),
            leader_changes_total=('leader_changes', 'sum'),
            backlog_at_end_max=('backlog_at_end', 'max')).reset_index(), on=gk)
        b = rq_agg[rq_agg.variant == 'no_consensus'].set_index('arrival_rate')
        for col in ['mean_response_s_mean', 'p99_response_s_mean', 'mean_wait_s_mean', 'throughput_mean']:
            rq_agg[col.replace('_mean', '') + '_ratio_vs_no_consensus'] = [
                r[col] / b.loc[r.arrival_rate, col] for _, r in rq_agg.iterrows()]
        save(rq_agg, 'raft_queue.csv')

        print('Closed-loop capacity...', flush=True)
        cap_cfgs = [('none', None, rep) for rep in range(N_REPS)]
        cap_cfgs += [('2pc', (a, T), rep) for (a, T) in [(1.0, 1.0), (0.999, 1.0), (0.99, 1.0), (0.99, 0.1)]
                     for rep in range(N_REPS)]
        cap_cfgs += [('raft', (p, n), rep) for p in ('realistic_lan', 'realistic_wan') for n in (3, 5)
                     for rep in range(N_REPS)]
        cap = pd.DataFrame(run_pool(pool, task_capacity, cap_cfgs, 'capacity'))
        save(cap, 'protocol_capacity_runs.csv')
        cap_agg = aggregate(cap, ['variant', 'param'], ['measured_capacity_msg_per_s'])
        cap_agg = cap_agg.merge(cap.groupby(['variant', 'param'])['analytic_capacity_msg_per_s']
                                .first().reset_index(), on=['variant', 'param'])
        b0 = cap_agg[cap_agg.variant == 'none']['measured_capacity_msg_per_s_mean'].iloc[0]
        cap_agg['measured_capacity_reduction_pct_vs_none'] = 100 * (1 - cap_agg['measured_capacity_msg_per_s_mean'] / b0)
        save(cap_agg, 'protocol_capacity.csv')

        # ---------------- Vector clocks ----------------
        print('Vector clocks...', flush=True)
        seeds = range(N_REPS)
        v_cfgs = [(impl, n, 10.0, cv, s) for impl in ('bss', 'none') for n in (3, 5, 10)
                  for cv in (0.0, 0.25, 0.5, 1.0, 2.0) for s in seeds]
        v_cfgs += [(impl, 5, rate, 1.0, s) for impl in ('bss', 'none') for rate in (2.0, 50.0) for s in seeds]
        v_cfgs += [('legacy', n, 10.0, cv, s) for n in (3, 5, 10) for cv in (0.0, 1.0) for s in seeds]
        vc = run_pool(pool, task_vc, v_cfgs, 'vector clocks')
    vdf = pd.DataFrame(vc)
    save(vdf, 'vector_clocks_runs.csv')
    vm = ['held_back_fraction', 'mean_holdback_all', 'mean_holdback_heldonly', 'p95_holdback_all',
          'p99_holdback_all', 'max_holdback', 'violating_delivery_fraction', 'undelivered_fraction']
    vagg = aggregate(vdf, ['implementation', 'num_processes', 'broadcast_rate', 'delay_cv'],
                     [m for m in vm if m in vdf.columns])
    vagg = vagg.merge(vdf.groupby(['implementation', 'num_processes', 'broadcast_rate', 'delay_cv']).agg(
        delay_mean_s=('delay_mean', 'first'), receptions_total=('receptions', 'sum'),
        undelivered_total=('undelivered', 'sum'),
        causal_violations_total=('causal_violations', 'sum')).reset_index(),
        on=['implementation', 'num_processes', 'broadcast_rate', 'delay_cv'])
    # drop all-NaN metric columns that do not apply to an implementation
    save(vagg, 'vector_clocks.csv')
    save(vector_clock_correctness(vc), 'vector_clocks_correctness.csv')

    # Reproducibility: same seed twice -> identical results (run in-process)
    rep_rows = []
    for name, fn, cfg in [('MMN2PCQueue', task_twopc_queue, ('2pc', 40.0, 0.99, 1.0, 0)),
                          ('MMNQueue', task_twopc_queue, ('no_2pc', 40.0, np.nan, np.nan, 0)),
                          ('RaftCluster_election', task_raft_election, ('realistic_lan', 5, 0)),
                          ('RaftCluster_commit', task_raft_commit, ('realistic_lan', 5, 0, True)),
                          ('causal_broadcast', task_vc, ('bss', 5, 10.0, 1.0, 0))]:
        r1, r2 = fn(cfg), fn(cfg)
        keys = sorted(k for k in r1 if isinstance(r1[k], (int, float, np.floating, np.integer)))
        same = all((r1[k] == r2[k]) or (np.isnan(r1[k]) and np.isnan(r2[k])) for k in keys)
        rep_rows.append({'model': name, 'config': str(cfg), 'identical_on_rerun': same,
                         'numeric_fields_compared': len(keys)})
    save(pd.DataFrame(rep_rows), 'protocols_reproducibility.csv')

    meta = {
        'script': 'experiments/paper2_protocols.py', 'quick': args.quick,
        'runtime_s': round(time.time() - t_start, 1), 'procs': args.procs,
        'N_THREADS': N_THREADS, 'MU': MU, 'SIM_DURATION': SIM_DURATION, 'WARMUP': WARMUP,
        'N_REPS': N_REPS, 'BASE_SEED': BASE_SEED, 'seeds': 'BASE_SEED + rep (queues); seed index (Raft, VC)',
        'TWOPC_OVERHEAD_SAMPLES': TWOPC_OVERHEAD_SAMPLES,
        'RAFT_PARAM_SETS(tmin,tmax,heartbeat,one_way_delay,jitter)': RAFT_PARAM_SETS,
        'RAFT_ELECTION_SEEDS': RAFT_ELECTION_SEEDS, 'RAFT_COMMIT_SEEDS': RAFT_COMMIT_SEEDS,
        'RAFT_APPEND_RATE': RAFT_APPEND_RATE, 'RAFT_QUEUE_LAMBDAS': RAFT_QUEUE_LAMBDAS,
        'CAP_DURATION': CAP_DURATION, 'CAP_WARMUP': CAP_WARMUP,
        'vector_clock_delay_mean_s': 0.010, 'vector_clock_duration_s': 30.0,
    }
    with open(os.path.join(out_dir, 'protocols_run_metadata.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    print(f'Done in {time.time() - t_start:.1f}s -> {out_dir}')


if __name__ == '__main__':
    main()
