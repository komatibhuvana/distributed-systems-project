"""Threading model implementations

Two threading architectures for message brokers:
1. Dedicated: Thread-per-connection (2 threads per connection)
2. Shared: Worker pool with thread sharing

Implements Equations 11-14 from the project plan.
"""

import simpy
import numpy as np
from typing import Optional
from .base import QueueModel
from ..core.config import QueueConfig
from ..core.distributions import ExponentialService, ServiceTimeDistribution
from ..core.metrics import SimulationMetrics


class DedicatedThreadingQueue(QueueModel):
    """
    Dedicated Threading Model (Thread-per-Connection)

    Architecture:
    - Each connection gets 2 dedicated threads (send + receive)
    - Maximum connections: Nmax = Nthreads / 2 (Equation 11)
    - Higher performance (no context switching overhead)
    - Limited scalability (fixed max connections)

    When connection limit reached, new arrivals are rejected.
    """

    def __init__(self, env: simpy.Environment, config: QueueConfig,
                 threads_per_connection: int = 2):
        """
        Args:
            env: SimPy environment
            config: Queue configuration
            threads_per_connection: Threads dedicated per connection (default: 2)
        """
        self.threads_per_connection = threads_per_connection

        # Calculate maximum connections (Equation 11) - must set before super().__init__()
        self.max_connections = config.num_threads // threads_per_connection

        # Track active connections
        self.active_connections = 0
        self.rejected_count = 0

        # Service time distribution (exponential for now)
        self.service_dist = ExponentialService(config.service_rate)

        # Now call parent init (which calls model_name())
        super().__init__(env, config)

    def model_name(self) -> str:
        return f"Dedicated-Threading(N={self.config.num_threads},Nmax={self.max_connections})"

    def get_service_time(self) -> float:
        """Sample from exponential distribution"""
        return self.service_dist.sample()

    def process_message(self, message_id: int):
        """
        Process a single message with dedicated threading

        Checks if connection slots available. If not, rejects the message.
        """
        arrival_time = self.env.now
        # Warmup messages are processed normally (so measurement starts from
        # steady state, as in QueueModel) but not recorded
        warmup = arrival_time < self.config.warmup_time

        # Check if we can accept this connection (Equation 11: Nmax = Nthreads/2)
        if self.active_connections >= self.max_connections:
            # Reject message - no available connection slots
            if not warmup:
                self.rejected_count += 1
            return

        # Accept connection
        self.active_connections += 1

        # Request threads (always available since we checked capacity)
        with self.threads.request() as req:
            queue_length = len(self.threads.queue)

            # Wait for threads
            yield req

            wait_time = self.env.now - arrival_time

            # Service time
            service_time = self.get_service_time()
            yield self.env.timeout(service_time)

            departure_time = self.env.now

            # Record metrics
            if not warmup:
                self.metrics.arrival_times.append(arrival_time)
                self.metrics.wait_times.append(wait_time)
                self.metrics.service_times.append(service_time)
                self.metrics.queue_lengths.append(queue_length)
                self.metrics.departure_times.append(departure_time)

        # Release connection
        self.active_connections -= 1

    def run(self) -> SimulationMetrics:
        """Run simulation and return metrics"""
        # Set random seed if provided
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Start message generator
        self.env.process(self.message_generator())

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        print(f"Simulation complete:")
        print(f"  Model: {self.model_name()}")
        print(f"  Total messages: {self.message_id}")
        print(f"  Rejected messages: {self.rejected_count}")
        print(f"  Acceptance rate: {(1 - self.rejected_count/self.message_id)*100:.1f}%" if self.message_id > 0 else "  Acceptance rate: N/A")

        return self.metrics


class SharedThreadingQueue(QueueModel):
    """
    Shared Threading Model (Worker Pool)

    Architecture:
    - All threads in a shared pool
    - Unlimited connections (no fixed limit)
    - Context switching overhead reduces effective service rate
    - Better scalability

    Effective service rate degrades with load (Equation 13):
    μeff = μ / (1 + α·Nactive/Nthreads)

    where α is the overhead coefficient (default: 0.1 = 10% overhead)
    """

    def __init__(self, env: simpy.Environment, config: QueueConfig,
                 overhead_coefficient: float = 0.1):
        """
        Args:
            env: SimPy environment
            config: Queue configuration
            overhead_coefficient: Context switching overhead (α, default: 0.1)
        """
        self.overhead_coefficient = overhead_coefficient

        # Track active connections
        self.active_connections = 0
        self.max_observed_connections = 0

        # Base service distribution
        self.base_service_dist = ExponentialService(config.service_rate)

        # Now call parent init (which calls model_name())
        super().__init__(env, config)

    def model_name(self) -> str:
        return f"Shared-Threading(N={self.config.num_threads},α={self.overhead_coefficient})"

    def get_service_time(self) -> float:
        """
        Sample service time with overhead adjustment (Equation 13)

        μeff = μ / (1 + α·Nactive/Nthreads)

        Higher Nactive → more context switching → longer service time
        """
        # Base service time
        base_time = self.base_service_dist.sample()

        # Calculate overhead factor
        overhead_factor = 1.0 + (self.overhead_coefficient *
                                 self.active_connections / self.config.num_threads)

        # Adjusted service time (slower when more connections active)
        effective_time = base_time * overhead_factor

        return effective_time

    def process_message(self, message_id: int):
        """
        Process a single message with shared threading

        No rejection - all messages are accepted but may experience
        increased service time due to context switching overhead.
        """
        arrival_time = self.env.now
        # Warmup messages are processed normally but not recorded
        warmup = arrival_time < self.config.warmup_time

        # Request threads from shared pool
        with self.threads.request() as req:
            queue_length = len(self.threads.queue)

            # Wait for threads
            yield req

            # NOW increment active connections (only when actively being served)
            self.active_connections += 1
            self.max_observed_connections = max(self.max_observed_connections,
                                                self.active_connections)

            wait_time = self.env.now - arrival_time

            # Service time with overhead
            service_time = self.get_service_time()
            yield self.env.timeout(service_time)

            departure_time = self.env.now

            # Record metrics
            if not warmup:
                self.metrics.arrival_times.append(arrival_time)
                self.metrics.wait_times.append(wait_time)
                self.metrics.service_times.append(service_time)
                self.metrics.queue_lengths.append(queue_length)
                self.metrics.departure_times.append(departure_time)

            # Release connection BEFORE exiting with block
            self.active_connections -= 1

    def run(self) -> SimulationMetrics:
        """Run simulation and return metrics"""
        # Set random seed if provided
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Start message generator
        self.env.process(self.message_generator())

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        print(f"Simulation complete:")
        print(f"  Model: {self.model_name()}")
        print(f"  Total messages: {self.message_id}")
        print(f"  Max concurrent connections: {self.max_observed_connections}")
        print(f"  Avg overhead factor: {1 + self.overhead_coefficient * self.max_observed_connections / self.config.num_threads:.2f}x")

        return self.metrics


def run_dedicated_simulation(config: QueueConfig,
                             threads_per_connection: int = 2) -> SimulationMetrics:
    """
    Convenience function to run dedicated threading simulation

    Args:
        config: Queue configuration
        threads_per_connection: Threads per connection (default: 2)

    Returns:
        SimulationMetrics with results
    """
    env = simpy.Environment()
    model = DedicatedThreadingQueue(env, config, threads_per_connection)
    return model.run()


def run_shared_simulation(config: QueueConfig,
                          overhead_coefficient: float = 0.1) -> SimulationMetrics:
    """
    Convenience function to run shared threading simulation

    Args:
        config: Queue configuration
        overhead_coefficient: Context switching overhead (default: 0.1)

    Returns:
        SimulationMetrics with results
    """
    env = simpy.Environment()
    model = SharedThreadingQueue(env, config, overhead_coefficient)
    return model.run()
