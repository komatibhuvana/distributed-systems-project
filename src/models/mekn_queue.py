"""
M/Ek/N Queue Model - Erlang Service Distribution

M/Ek/N Queue: Poisson arrivals, Erlang-k service, N servers

The Erlang distribution models multi-phase service processes where
each job must pass through k sequential exponential stages.

Properties:
- More regular than exponential (CV² = 1/k < 1)
- Models multi-phase service processes
- As k→∞, approaches deterministic service (M/D/N)
- As k=1, reduces to exponential service (M/M/N)

Reference:
Gross, D., & Harris, C. M. (1998). Fundamentals of queueing theory.
Wiley-Interscience.
"""

import simpy
import numpy as np
from typing import Optional
from pydantic import Field

from ..core.config import MMNConfig
from ..core.distributions import ErlangService
from ..core.metrics import SimulationMetrics


class MEkNConfig(MMNConfig):
    """
    Configuration for M/Ek/N queue

    Extends MMNConfig with Erlang-specific parameters
    """
    erlang_k: int = Field(
        default=2,
        gt=0,
        description="Number of Erlang phases (k)"
    )


class MEkNQueue:
    """
    M/Ek/N Queue simulation

    Architecture:
        Arrivals (Poisson λ) → Queue → N Servers (Erlang-k service) → Departures

    Key Difference from M/M/N:
        - Service time is Erlang-k (k exponential phases) instead of pure exponential
        - CV² = 1/k instead of CV² = 1
        - More predictable service times as k increases
    """

    def __init__(self, env: simpy.Environment, config: MEkNConfig):
        """
        Args:
            env: SimPy environment
            config: M/Ek/N configuration
        """
        self.env = env
        self.config = config

        # Seed the global NumPy RNG (used by np.random.exponential for arrivals
        # and by scipy.stats.erlang.rvs for service). Previously random_seed was
        # accepted but ignored, so runs were not reproducible.
        if config.random_seed is not None:
            np.random.seed(config.random_seed)

        # Create server pool
        self.servers = simpy.Resource(env, capacity=config.num_threads)

        # Create Erlang service distribution
        # Adjust rate to maintain mean service time: E[S] = k/λ = 1/μ
        # Therefore: λ = k * μ
        self.service_dist = ErlangService(
            shape=config.erlang_k,
            rate=config.erlang_k * config.service_rate
        )

        # Metrics
        self.metrics = SimulationMetrics()

        # Message counter
        self.message_id = 0
        self.messages_in_warmup = 0

    def is_warmup(self) -> bool:
        """Check if in warmup period"""
        return self.env.now < self.config.warmup_time

    def message_generator(self):
        """
        Generate Poisson arrivals

        Yields:
            SimPy timeout for inter-arrival time
        """
        while True:
            # Exponential inter-arrival time (Poisson process)
            interarrival = np.random.exponential(1.0 / self.config.arrival_rate)
            yield self.env.timeout(interarrival)

            # Create and process message
            self.message_id += 1

            if self.is_warmup():
                self.messages_in_warmup += 1

            self.env.process(self.process_message(self.message_id))

    def process_message(self, message_id: int):
        """
        Process a single message through the queue

        Args:
            message_id: Unique message identifier

        Flow:
            1. Arrive and record arrival time
            2. Wait in queue for available server
            3. Get served (Erlang-k service time)
            4. Depart and record metrics
        """
        arrival_time = self.env.now

        # Record queue length at arrival
        queue_length = len(self.servers.queue)

        # Request server
        with self.servers.request() as req:
            yield req

            # Record waiting time (time from arrival to service start)
            service_start = self.env.now
            wait_time = service_start - arrival_time

            # Erlang-k service time (k exponential phases)
            service_time = self.service_dist.sample()

            yield self.env.timeout(service_time)

            # Service complete
            departure_time = self.env.now

            # Record metrics (skip warmup period)
            if not self.is_warmup():
                self.metrics.arrival_times.append(arrival_time)
                self.metrics.wait_times.append(wait_time)
                self.metrics.service_times.append(service_time)
                self.metrics.queue_lengths.append(queue_length)
                self.metrics.departure_times.append(departure_time)


def run_mekn_simulation(config: MEkNConfig) -> SimulationMetrics:
    """
    Run M/Ek/N queue simulation

    Args:
        config: M/Ek/N configuration

    Returns:
        QueueMetrics with simulation results

    Example:
        >>> config = MEkNConfig(
        ...     arrival_rate=100,
        ...     num_threads=10,
        ...     service_rate=12,
        ...     erlang_k=3,  # 3-phase service
        ...     sim_duration=10000,
        ...     warmup_time=1000
        ... )
        >>> metrics = run_mekn_simulation(config)
        >>> stats = metrics.summary_statistics()
        >>> print(f"Mean wait: {stats['mean_wait']:.4f}")
        >>> print(f"CV²: {1/config.erlang_k:.3f}")
    """
    # Create environment
    env = simpy.Environment()

    # Create queue
    queue = MEkNQueue(env, config)

    # Start message generator
    env.process(queue.message_generator())

    # Run simulation
    env.run(until=config.sim_duration)

    # Print summary
    print(f"\nM/E{config.erlang_k}/{config.num_threads} Simulation Complete:")
    print(f"  Total messages: {queue.message_id}")
    print(f"  Warmup messages: {queue.messages_in_warmup}")
    print(f"  Measured messages: {len(queue.metrics.wait_times)}")
    print(f"  CV² = 1/{config.erlang_k} = {1/config.erlang_k:.3f}")

    return queue.metrics
