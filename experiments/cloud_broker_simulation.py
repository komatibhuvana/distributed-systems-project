"""
Cloud Message Broker Simulation

Implements the cloud message broker model from Li et al. (2015)
with visibility timeout, distributed storage, and reliability guarantees.

This is the CORRECT implementation of the paper's model.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import simpy
import numpy as np
import pandas as pd
from typing import List

from src.models.cloud_message import CloudMessage
from src.models.distributed_broker import DistributedBroker


class CloudBrokerSimulation:
    """
    Complete cloud message broker simulation

    Features:
    - Distributed storage with replication
    - Visibility timeout mechanism
    - Message ordering (in-order or out-of-order)
    - Reliability guarantees (Dead Letter Queue)
    - Fault tolerance
    """

    def __init__(self,
                 arrival_rate: float = 100,
                 processing_time_mean: float = 0.05,
                 processing_failure_rate: float = 0.1,
                 visibility_timeout: float = 30.0,
                 num_storage_nodes: int = 3,
                 replication_factor: int = 3,
                 ordering_mode: str = "out_of_order",
                 sim_duration: float = 1000,
                 warmup_time: float = 100,
                 random_seed: int = 42,
                 node_mtbf: float = None,
                 node_mttr: float = 10.0):
        """
        Args:
            arrival_rate: Message arrival rate (messages/sec)
            processing_time_mean: Mean processing time (sec)
            processing_failure_rate: Probability of processing failure
            visibility_timeout: Visibility timeout duration (sec)
            num_storage_nodes: Number of distributed storage nodes
            replication_factor: Number of replicas per message
            ordering_mode: "in_order" or "out_of_order"
            sim_duration: Total simulation time (sec)
            warmup_time: Warmup period to discard (sec)
            random_seed: Random seed for reproducibility
        """
        self.arrival_rate = arrival_rate
        self.processing_time_mean = processing_time_mean
        self.processing_failure_rate = processing_failure_rate
        self.visibility_timeout = visibility_timeout
        self.num_storage_nodes = num_storage_nodes
        self.replication_factor = replication_factor
        self.ordering_mode = ordering_mode
        self.sim_duration = sim_duration
        self.warmup_time = warmup_time
        self.random_seed = random_seed

        # Initialize (the broker samples nodes/messages with the stdlib
        # `random` module, so both generators must be seeded)
        np.random.seed(random_seed)
        random.seed(random_seed)
        self.env = simpy.Environment()

        # Create distributed broker
        self.broker = DistributedBroker(
            env=self.env,
            num_nodes=num_storage_nodes,
            replication_factor=replication_factor,
            ordering_mode=ordering_mode,
            node_mtbf=node_mtbf,
            node_mttr=node_mttr
        )
        self.node_mtbf = node_mtbf
        self.node_mttr = node_mttr

        # Metrics
        self.message_id_counter = 0
        self.published_messages = []
        self.processed_messages = []
        self.failed_messages = []

        # Processing metrics
        self.latencies = []
        self.retries = []
        self.duplicate_deliveries = 0
        self.first_receive_delays = []  # publish -> first delivery attempt

    def run(self, num_consumers: int = 10):
        """
        Run the simulation

        Args:
            num_consumers: Number of concurrent consumers (default 10)
                          Should be sized to handle arrival_rate
        """
        # Start processes
        self.env.process(self.message_producer())

        # FIXED: Start multiple consumers to handle the load
        # With arrival_rate=100 and processing_time=0.05,
        # need ~5 consumers minimum (100 * 0.05 = 5)
        # Using 10 for safety margin
        for i in range(num_consumers):
            self.env.process(self.message_consumer())

        # Run simulation
        self.env.run(until=self.sim_duration)

        # Return results
        return self.get_results()

    def message_producer(self):
        """
        Produce messages with Poisson arrivals

        Publishes messages to distributed broker
        """
        while True:
            # Exponential inter-arrival time
            interarrival_time = np.random.exponential(1.0 / self.arrival_rate)
            yield self.env.timeout(interarrival_time)

            # Create cloud message
            self.message_id_counter += 1
            message = CloudMessage(
                id=self.message_id_counter,
                content=f"Message_{self.message_id_counter}",
                arrival_time=self.env.now,
                visibility_timeout=self.visibility_timeout,
                max_receive_count=3
            )

            # Publish to broker (replicated)
            self.broker.publish_message(message)

            if self.env.now >= self.warmup_time:
                self.published_messages.append(message)

    def message_consumer(self):
        """
        Consume and process messages

        Implements:
        1. Receive message (makes invisible)
        2. Process message (may fail)
        3. Acknowledge if successful (deletes message)
        4. If failed, visibility timeout returns message to queue
        """
        while True:
            # Try to receive message
            message = self.broker.receive_message()

            if message is not None:
                # Process message
                yield self.env.process(self.process_message(message))
            else:
                # No messages available - wait briefly
                yield self.env.timeout(0.1)

    def process_message(self, message: CloudMessage):
        """
        Process a received message

        May succeed or fail based on failure rate
        """
        # Receipt handle: an ack is only valid for the receive that issued it
        # (as in SQS). If the visibility timeout expired mid-processing and the
        # message was redelivered, this consumer's ack is stale.
        receipt = message.receive_count

        # Processing time
        processing_time = np.random.exponential(self.processing_time_mean)
        yield self.env.timeout(processing_time)

        # Check if processing succeeds
        if np.random.random() > self.processing_failure_rate:
            if message.receive_count != receipt or not self.broker.acknowledge_message(message):
                # Work was done but the message was already redelivered
                if self.env.now >= self.warmup_time:
                    self.duplicate_deliveries += 1
                return

            if self.env.now >= self.warmup_time:
                latency = self.env.now - message.arrival_time
                self.latencies.append(latency)
                self.first_receive_delays.append(message.first_receive_time - message.arrival_time)
                self.retries.append(message.receive_count - 1)  # -1 because we count retries
                self.processed_messages.append(message)
        else:
            # Failure - message will timeout and become visible again
            if self.env.now >= self.warmup_time:
                self.failed_messages.append(message)

    def get_results(self) -> dict:
        """Calculate and return simulation results"""
        # Basic metrics
        total_published = len(self.published_messages)
        total_processed = len(self.processed_messages)
        total_failed = len(self.failed_messages)

        # Latency metrics
        latencies_array = np.array(self.latencies) if self.latencies else np.array([0])
        retries_array = np.array(self.retries) if self.retries else np.array([0])

        # Broker metrics
        broker_metrics = self.broker.get_broker_metrics()
        node_metrics = self.broker.get_node_metrics()

        # Logical (per message ID) outcomes for messages published after warmup
        # and early enough to have had max_receive_count (3) delivery attempts
        cutoff = self.sim_duration - 3 * self.visibility_timeout - 10
        published_ids = {m.id for m in self.published_messages if m.arrival_time <= cutoff}
        delivered_ids = {m.id for m in self.processed_messages}
        dlq_ids = set()
        for node in self.broker.nodes:
            dlq_ids.update(node.visibility_manager.dlq_messages.keys())
        delivered = len(published_ids & delivered_ids)
        dead_lettered = len(published_ids & dlq_ids)

        results = {
            # Message counts
            'total_published': total_published,
            'total_processed': total_processed,
            'total_failed': total_failed,
            'processing_success_rate': total_processed / total_published if total_published > 0 else 0,
            'delivery_ratio': delivered / len(published_ids) if published_ids else 0,
            'dlq_ratio': dead_lettered / len(published_ids) if published_ids else 0,
            'duplicate_deliveries': self.duplicate_deliveries,
            'copies_written': sum(node.messages_stored for node in self.broker.nodes),
            'node_outages': self.broker.total_outages,

            # Latency metrics
            'mean_latency': np.mean(latencies_array),
            'median_latency': np.median(latencies_array),
            'p95_latency': np.percentile(latencies_array, 95),
            'p99_latency': np.percentile(latencies_array, 99),
            'mean_first_receive': float(np.mean(self.first_receive_delays)) if self.first_receive_delays else 0.0,
            'p99_first_receive': float(np.percentile(self.first_receive_delays, 99)) if self.first_receive_delays else 0.0,

            # Retry metrics
            'mean_retries': np.mean(retries_array),
            'max_retries': np.max(retries_array),

            # Throughput
            'throughput': total_processed / (self.sim_duration - self.warmup_time),

            # Broker metrics
            'broker_metrics': broker_metrics,
            'node_metrics': node_metrics,

            # Configuration
            'config': {
                'arrival_rate': self.arrival_rate,
                'processing_time_mean': self.processing_time_mean,
                'processing_failure_rate': self.processing_failure_rate,
                'visibility_timeout': self.visibility_timeout,
                'num_storage_nodes': self.num_storage_nodes,
                'replication_factor': self.replication_factor,
                'ordering_mode': self.ordering_mode,
            }
        }

        return results


SEEDS = list(range(1, 11))  # 10 independent replications per configuration


def _ci95(values):
    """Mean and 95% t-confidence half-width"""
    from scipy import stats
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return float(values.mean()), 0.0
    half = stats.t.ppf(0.975, n - 1) * values.std(ddof=1) / np.sqrt(n)
    return float(values.mean()), float(half)


METRICS = ['mean_latency', 'p99_latency', 'mean_first_receive', 'p99_first_receive',
           'mean_retries', 'throughput',
           'delivery_ratio', 'dlq_ratio', 'duplicate_rate', 'copies_per_message']


def _replicate(label, num_consumers=10, seeds=SEEDS, **kwargs):
    """Run one configuration over SEEDS; return (per-run rows, summary row)"""
    runs = []
    for seed in seeds:
        sim = CloudBrokerSimulation(random_seed=seed, **kwargs)
        r = sim.run(num_consumers=num_consumers)
        published = max(r['total_published'], 1)
        runs.append({
            **label, 'seed': seed,
            'mean_latency': r['mean_latency'],
            'p99_latency': r['p99_latency'],
            'mean_first_receive': r['mean_first_receive'],
            'p99_first_receive': r['p99_first_receive'],
            'mean_retries': r['mean_retries'],
            'throughput': r['throughput'],
            'delivery_ratio': r['delivery_ratio'],
            'dlq_ratio': r['dlq_ratio'],
            'duplicate_rate': r['duplicate_deliveries'] / published,
            'copies_per_message': r['copies_written'] / max(r['broker_metrics']['total_messages_published'], 1),
            'node_outages': r['node_outages'],
        })
    summary = dict(label)
    for m in METRICS:
        mean, half = _ci95([run[m] for run in runs])
        summary[m] = mean
        summary[m + '_ci95'] = half
    summary['replications'] = len(runs)
    return runs, summary


def experiment_visibility_timeout():
    """
    Experiment 1: Visibility Timeout Impact

    Mean processing time is 0.5 s (exponential), so small VT values expire
    while healthy consumers are still working (premature redelivery), and
    large VT values delay the retry of genuinely failed messages.
    """
    print("="*70)
    print("EXPERIMENT: Visibility Timeout Impact")
    print("="*70)

    runs, summaries = [], []
    for timeout in [0.5, 1, 2, 5, 10, 30, 60, 120]:
        print(f"  VT = {timeout} s")
        r, s = _replicate(
            {'visibility_timeout': timeout},
            arrival_rate=10,
            processing_time_mean=0.5,
            processing_failure_rate=0.1,
            visibility_timeout=timeout,
            num_storage_nodes=3,
            replication_factor=2,
            sim_duration=2000,
            warmup_time=200,
        )
        runs += r
        summaries.append(s)

    df = pd.DataFrame(summaries)
    print(df[['visibility_timeout', 'mean_latency', 'p99_latency', 'mean_retries',
              'duplicate_rate', 'delivery_ratio']].to_string(index=False))
    return df, pd.DataFrame(runs)


def experiment_replication_factor():
    """
    Experiment 2: Replication Factor Impact

    Without node failures replication can only cost storage, so each
    replication factor is run with and without node outages
    (MTBF 100 s, MTTR 20 s per node). 20 consumers are used so that polls
    wasted on a down node (0.1 s back-off each) do not saturate the consumer
    pool, which would otherwise dominate latency regardless of R.
    """
    print("\n" + "="*70)
    print("EXPERIMENT: Replication Factor Impact")
    print("="*70)

    runs, summaries = [], []
    for mtbf in [None, 100.0]:
        for rep_factor in [1, 2, 3]:
            print(f"  R = {rep_factor}, outages = {'on' if mtbf else 'off'}")
            r, s = _replicate(
                {'replication_factor': rep_factor, 'node_outages': 'on' if mtbf else 'off'},
                num_consumers=20,
                seeds=list(range(1, 31)),
                arrival_rate=100,
                processing_time_mean=0.05,
                processing_failure_rate=0.1,
                visibility_timeout=30,
                num_storage_nodes=3,
                replication_factor=rep_factor,
                sim_duration=500,
                warmup_time=50,
                node_mtbf=mtbf,
                node_mttr=20.0,
            )
            runs += r
            summaries.append(s)

    df = pd.DataFrame(summaries)
    print(df[['node_outages', 'replication_factor', 'mean_latency', 'p99_latency',
              'throughput', 'delivery_ratio', 'copies_per_message']].to_string(index=False))
    return df, pd.DataFrame(runs)


def main():
    """Run cloud broker experiments (ordering lives in cost_of_consistency.py)"""
    print("\n" + "="*70)
    print(" CLOUD MESSAGE BROKER SIMULATION")
    print("="*70)

    vt_df, vt_runs = experiment_visibility_timeout()
    rep_df, rep_runs = experiment_replication_factor()

    vt_df.to_csv('experiments/visibility_timeout_results.csv', index=False)
    vt_runs.to_csv('experiments/visibility_timeout_runs.csv', index=False)
    rep_df.to_csv('experiments/replication_factor_results.csv', index=False)
    rep_runs.to_csv('experiments/replication_factor_runs.csv', index=False)
    print("\nSaved experiments/visibility_timeout_results.csv and replication_factor_results.csv")


if __name__ == "__main__":
    main()
