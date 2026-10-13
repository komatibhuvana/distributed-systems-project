"""
Heterogeneous M/M/N Queue Implementation

Implements M/M/N queues with multiple server groups having different service rates.
Addresses "Future Work" from Li et al. (2015) regarding heterogeneous server modeling.

Key Features:
- Multiple server groups with different speeds (e.g., 2 slow + 3 fast servers)
- Flexible server selection policies (random, fastest-first, round-robin, shortest-queue)
- Demonstrates that heterogeneity INCREASES waiting time vs homogeneous systems
  with same total capacity (due to increased service time variance)

Mathematical Challenge:
Unlike homogeneous M/M/N (exact Erlang-C formulas exist), heterogeneous M/M/N
has no closed-form solution. Must use approximations or simulation.

References:
- Whitt, W. (1985). "Deciding which queue to join: Some counterexamples."
  Operations Research, 34(1), 55-62.
- Li et al. (2015). "Modeling Message Queueing Services with Reliability Guarantee..."
  (Future Work section on heterogeneous servers)
"""

import numpy as np
import simpy
from typing import List, Optional
from ..core.config import HeterogeneousMMNConfig, ServerGroup
from ..core.metrics import SimulationMetrics
from ..core.distributions import TwoPhaseCommitService, ExponentialService


class ServerPool:
    """
    Represents a pool of homogeneous servers (one group)

    Each pool has:
    - n servers (SimPy Resource)
    - service_rate μ (messages/sec per server)
    - name for identification
    """

    def __init__(self, env: simpy.Environment, group: ServerGroup, pool_id: int, parent):
        self.env = env
        self.group = group
        self.pool_id = pool_id
        self.parent = parent # Reference to main queue for stealing
        self.count = group.count
        self.service_rate = group.service_rate
        self.name = group.name or f"Group(μ={group.service_rate})"
        
        # 2PC Service Wrapper (if enabled)
        self.twopc_service = None
        if parent.config.consistency_mode == "strong_2pc":
            base_dist = ExponentialService(rate=group.service_rate)
            self.twopc_service = TwoPhaseCommitService(
                base_distribution=base_dist,
                num_replicas=3, # Default
                network_rtt_mean=0.010 # 10ms
            )

        # Explicit Queue (Store)
        self.queue = simpy.Store(env)
        
        # Track busy servers
        self.busy_servers = 0
        
        # Start worker processes
        self.workers = []
        for i in range(self.count):
            self.workers.append(env.process(self.worker_loop(i)))

        # Metrics
        self.messages_processed = 0
        self.total_service_time = 0.0

    def get_service_time(self) -> float:
        """Sample service time for this pool"""
        if self.twopc_service:
            return self.twopc_service.sample()
        return np.random.exponential(1.0 / self.service_rate)

    def current_queue_length(self) -> int:
        """Current number of messages waiting in THIS pool's queue"""
        return len(self.queue.items)

    def current_utilization(self) -> float:
        """Current utilization of this pool"""
        return self.busy_servers / self.count if self.count > 0 else 0.0

    def worker_loop(self, worker_id: int):
        """
        Worker process that pulls jobs from queue OR steals them
        """
        while True:
            # 1. Try to get job from OWN queue
            if len(self.queue.items) > 0:
                job = yield self.queue.get()
                yield from self.process_job(job)
                continue

            # 2. WORK STEALING (If enabled)
            if self.parent.config.selection_policy == "work_stealing":
                # Look for victim
                victim = self.find_victim()
                if victim:
                    # Steal!
                    # print(f"Pool {self.name} stealing from {victim.name}")
                    job = yield victim.queue.get()
                    yield from self.process_job(job)
                    continue

            # 3. If nothing to do, wait for a job to arrive in OWN queue
            # We wait on the store.get() which blocks until an item is available
            job = yield self.queue.get()
            yield from self.process_job(job)

    def find_victim(self):
        """Find a pool to steal from (Longest Queue)"""
        best_victim = None
        max_q = 0
        
        for pool in self.parent.pools:
            if pool != self:
                q_len = len(pool.queue.items)
                if q_len > max_q:
                    max_q = q_len
                    best_victim = pool
        
        return best_victim

    def process_job(self, job):
        """Process a job (message)"""
        self.busy_servers += 1
        message_id, arrival_time = job
        
        # Service
        service_time = self.get_service_time()
        yield self.env.timeout(service_time)
        
        # Metrics
        self.busy_servers -= 1
        self.messages_processed += 1
        self.total_service_time += service_time
        
        # Global Metrics
        departure_time = self.env.now
        wait_time = self.env.now - service_time - arrival_time
        # Note: wait_time calculation here is tricky because we don't know exactly when service started relative to arrival
        # Actually: wait_time = (now - service_time) - arrival_time
        
        if not self.parent.is_warmup():
            self.parent.metrics.arrival_times.append(arrival_time)
            self.parent.metrics.wait_times.append(max(0, wait_time))
            self.parent.metrics.service_times.append(service_time)
            self.parent.metrics.departure_times.append(departure_time)
            # Queue length is hard to track perfectly per-job in this model, use current
            self.parent.metrics.queue_lengths.append(self.current_queue_length())
        else:
            self.parent.messages_in_warmup += 1


class HeterogeneousMMNQueue:
    """
    M/M/N Queue with Heterogeneous Servers

    System:
    - Poisson arrivals (λ messages/sec)
    - Multiple server groups with different exponential service rates
    - Server selection policy determines which group handles each message

    Example Configuration:
        # Cloud broker with mixed EC2 instance types
        config = HeterogeneousMMNConfig(
            arrival_rate=100,
            server_groups=[
                ServerGroup(count=2, service_rate=8.0, name="t2.small (legacy)"),
                ServerGroup(count=3, service_rate=15.0, name="t2.large (new)")
            ],
            selection_policy="random"
        )

    Server Selection Policies:
    - "random": Randomly select server group (simple, baseline)
    - "fastest_first": Always try fastest servers first (minimize service time)
    - "round_robin": Cycle through groups evenly (load balancing)
    - "shortest_queue": Join group with shortest queue (minimize wait time)
    """

    def __init__(self, env: simpy.Environment, config: HeterogeneousMMNConfig):
        self.env = env
        self.config = config

        # Create server pools (one per server group)
        self.pools: List[ServerPool] = []
        for i, group in enumerate(config.server_groups):
            pool = ServerPool(env, group, i, self)
            self.pools.append(pool)

        # Metrics collection
        self.metrics = SimulationMetrics(
            model_name=self.model_name(),
            config={
                'arrival_rate': config.arrival_rate,
                'server_groups': [(g.count, g.service_rate, g.name) for g in config.server_groups],
                'selection_policy': config.selection_policy,
                'total_servers': config.total_servers,
                'total_capacity': config.total_capacity,
                'heterogeneity_coefficient': config.heterogeneity_coefficient,
            }
        )

        # Message counter
        self.message_id = 0
        self.messages_in_warmup = 0

        # Round-robin state
        self.round_robin_index = 0

    def model_name(self) -> str:
        """
        Generate descriptive model name

        Example: "Het-M/M/5 (2@8 + 3@15) [random]"
        """
        group_str = " + ".join(
            f"{g.count}@{g.service_rate:.0f}"
            for g in self.config.server_groups
        )
        return f"Het-M/M/{self.config.total_servers} ({group_str}) [{self.config.selection_policy}]"

    def select_server_pool(self) -> ServerPool:
        """
        Select which server pool to use based on selection_policy

        Returns:
            Selected ServerPool
        """
        policy = self.config.selection_policy

        if policy == "random":
            # Randomly select pool weighted by server count, i.e. every server
            # receives λ/N regardless of its speed. Slow pools are unstable
            # whenever λ/N >= μ_slow even if total capacity exceeds λ.
            weights = [pool.count for pool in self.pools]
            total_weight = sum(weights)
            probabilities = [w / total_weight for w in weights]
            return np.random.choice(self.pools, p=probabilities)

        elif policy == "random_capacity":
            # Randomly select pool weighted by capacity n_i·μ_i, so every pool
            # runs at the same utilization ρ = λ / Σ n_i·μ_i
            weights = [pool.count * pool.service_rate for pool in self.pools]
            total_weight = sum(weights)
            probabilities = [w / total_weight for w in weights]
            return np.random.choice(self.pools, p=probabilities)

        elif policy == "work_stealing":
            # Initial assignment is Random (or Round Robin)
            # The "Stealing" happens in the worker loop
            weights = [pool.count for pool in self.pools]
            total_weight = sum(weights)
            probabilities = [w / total_weight for w in weights]
            return np.random.choice(self.pools, p=probabilities)

        elif policy == "fastest_first":
            # Select fastest pool (highest service rate) if available, else next fastest
            sorted_pools = sorted(self.pools, key=lambda p: p.service_rate, reverse=True)
            for pool in sorted_pools:
                # Check if pool has capacity (not all servers busy)
                if pool.current_queue_length() == 0 and pool.busy_servers < pool.count:
                    return pool
            # All pools busy - return fastest anyway
            return sorted_pools[0]

        elif policy == "round_robin":
            # Cycle through pools evenly (proportional to server count)
            # Build list: [pool0, pool0, pool1, pool1, pool1] if counts are [2, 3]
            pool_list = []
            for pool in self.pools:
                pool_list.extend([pool] * pool.count)

            selected = pool_list[self.round_robin_index % len(pool_list)]
            self.round_robin_index += 1
            return selected

        elif policy == "shortest_queue":
            # Join pool with shortest queue (JSQ policy)
            # Normalize by server count (queue length per server)
            min_normalized_queue = float('inf')
            best_pool = self.pools[0]

            for pool in self.pools:
                normalized_queue = pool.current_queue_length() / pool.count
                if normalized_queue < min_normalized_queue:
                    min_normalized_queue = normalized_queue
                    best_pool = pool

            return best_pool

        else:
            raise ValueError(f"Unknown selection policy: {policy}")

    def is_warmup(self) -> bool:
        """Check if in warmup period"""
        return self.env.now < self.config.warmup_time

    def process_message(self, message_id: int):
        """
        Process a single message through heterogeneous queue
        """
        arrival_time = self.env.now

        # Select which server pool to use
        selected_pool = self.select_server_pool()

        # Put message in the pool's queue
        # The worker processes will pick it up
        yield selected_pool.queue.put((message_id, arrival_time))


    def message_generator(self):
        """
        Generate messages with Poisson arrivals

        Poisson process: inter-arrival times are exponential
        """
        while True:
            # Exponential inter-arrival time
            interarrival = np.random.exponential(1.0 / self.config.arrival_rate)
            yield self.env.timeout(interarrival)

            # Create new message
            self.message_id += 1
            self.env.process(self.process_message(self.message_id))

    def run(self) -> SimulationMetrics:
        """
        Run the simulation

        Returns:
            SimulationMetrics with collected data
        """
        # Set random seed if provided
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Start message generator
        self.env.process(self.message_generator())

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        # Print results
        print(f"\nSimulation complete:")
        print(f"  Model: {self.model_name()}")
        print(f"  Total messages: {self.message_id}")
        print(f"  Warmup messages: {self.messages_in_warmup}")
        print(f"  Measured messages: {len(self.metrics.wait_times)}")

        # Print per-pool statistics
        print(f"\nPer-Pool Statistics:")
        for i, pool in enumerate(self.pools):
            print(f"  Pool {i+1} ({pool.name}):")
            print(f"    Servers: {pool.count}")
            print(f"    Service rate: {pool.service_rate:.1f} msg/sec")
            print(f"    Messages processed: {pool.messages_processed}")
            pct = pool.messages_processed / self.message_id * 100 if self.message_id > 0 else 0
            print(f"    Load share: {pct:.1f}%")
            if pool.messages_processed > 0:
                avg_service = pool.total_service_time / pool.messages_processed
                print(f"    Avg service time: {avg_service:.6f} sec")

        return self.metrics

    def get_pool_metrics(self) -> dict:
        """Get detailed metrics for each server pool"""
        pool_metrics = []
        for i, pool in enumerate(self.pools):
            pool_metrics.append({
                'pool_id': i,
                'name': pool.name,
                'count': pool.count,
                'service_rate': pool.service_rate,
                'messages_processed': pool.messages_processed,
                'total_service_time': pool.total_service_time,
                'avg_service_time': pool.total_service_time / pool.messages_processed
                if pool.messages_processed > 0 else 0,
            })
        return {'pools': pool_metrics}


def run_heterogeneous_mmn_simulation(config: HeterogeneousMMNConfig) -> SimulationMetrics:
    """
    Convenience function to run heterogeneous M/M/N simulation

    Args:
        config: Heterogeneous M/M/N configuration

    Returns:
        SimulationMetrics with results

    Example:
        >>> from src.core.config import HeterogeneousMMNConfig, ServerGroup
        >>> config = HeterogeneousMMNConfig(
        ...     arrival_rate=100,
        ...     server_groups=[
        ...         ServerGroup(count=2, service_rate=8.0, name="slow"),
        ...         ServerGroup(count=3, service_rate=15.0, name="fast")
        ...     ],
        ...     selection_policy="random",
        ...     sim_duration=1000,
        ...     warmup_time=100,
        ...     random_seed=42
        ... )
        >>> metrics = run_heterogeneous_mmn_simulation(config)
        >>> stats = metrics.summary_statistics()
        >>> print(f"Mean wait: {stats['mean_wait']:.6f} sec")
    """
    env = simpy.Environment()
    model = HeterogeneousMMNQueue(env, config)
    return model.run()
