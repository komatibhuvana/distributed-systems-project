"""
Queue models with Two-Phase Commit (2PC) protocol overhead integrated

Addresses professor's critique #3: "The 2PC-Reliability Disconnect"

These queue models include 2PC overhead in service time calculations,
demonstrating the REAL performance impact of distributed reliability protocols.

Key Insight:
-----------
Standard queue models assume service time = processing time only.
In reality, distributed reliability protocols (like 2PC) add significant overhead:
- Network round-trip times
- Blocking during vote collection
- Timeout handling

The size of the effect depends on RTT, replica count, replica availability and
vote timeout; see TwoPhaseCommitService for the exact E[O]/Var[O] and
experiments/paper2_protocols.py (results/paper2/twopc_*.csv) for measured
numbers. (An earlier docstring asserted "20-40% throughput reduction" without
a supporting measurement.)

Note: MMNConfig only validates the BASE utilization λ/(N·μ). With 2PC the
effective utilization is ρ_eff = λ·E[S_total]/N, which can exceed 1 even when
the config validates; check `effective_utilization()` before trusting results.
"""

import simpy
import numpy as np
from typing import Optional
from ..core.config import MMNConfig, MGNConfig
from ..core.metrics import SimulationMetrics
from ..core.distributions import ExponentialService, TwoPhaseCommitService, create_distribution
from .base import QueueModel


class MMN2PCQueue(QueueModel):
    """
    M/M/N Queue with Two-Phase Commit overhead

    Service time includes:
    - Base exponential processing time
    - 2PC protocol overhead (prepare + vote + commit)

    This models the REAL performance of a replicated message broker
    using 2PC for consistency.
    """

    def __init__(self, env: simpy.Environment, config: MMNConfig,
                 num_replicas: int = 3,
                 network_rtt_mean: float = 0.010,
                 replica_availability: float = 0.99,
                 network_rtt_std: float = 0.002,
                 vote_timeout: float = 1.0,
                 verbose: bool = True):
        """
        Args:
            env: SimPy environment
            config: M/M/N configuration
            num_replicas: Number of replicas for 2PC (default: 3)
            network_rtt_mean: Mean network RTT in seconds (default: 10ms)
            replica_availability: Probability replica responds (default: 0.99)
            network_rtt_std: Std dev of RTT in seconds (default: 2ms, same as
                TwoPhaseCommitService default)
            vote_timeout: Vote-collection timeout in seconds (default: 1.0)
            verbose: Print summary in run() (default: True, as before)
        """
        # Bug fix: QueueModel.__init__ calls self.model_name(), which needs
        # num_replicas, so it must be set BEFORE super().__init__ (previously
        # constructing MMN2PCQueue raised AttributeError).
        self.num_replicas = num_replicas
        self.network_rtt_mean = network_rtt_mean
        super().__init__(env, config)

        # Create base exponential distribution
        base_dist = ExponentialService(rate=config.service_rate)

        # Wrap with 2PC overhead
        self.service_dist = TwoPhaseCommitService(
            base_distribution=base_dist,
            num_replicas=num_replicas,
            network_rtt_mean=network_rtt_mean,
            network_rtt_std=network_rtt_std,
            replica_availability=replica_availability,
            vote_timeout=vote_timeout
        )

        self.num_replicas = num_replicas
        self.network_rtt_mean = network_rtt_mean
        self.verbose = verbose

    def effective_utilization(self) -> float:
        """ρ_eff = λ·E[S_total]/N (2PC overhead included). Unstable if >= 1."""
        return self.config.arrival_rate * self.service_dist.mean() / self.config.num_threads

    def model_name(self) -> str:
        return f"M/M/{self.config.num_threads} + 2PC({self.num_replicas} replicas)"

    def get_service_time(self) -> float:
        """
        Get service time INCLUDING 2PC overhead

        This is the key difference: service time = processing + 2PC protocol
        """
        return self.service_dist.sample()

    def run(self) -> SimulationMetrics:
        """Run simulation and report 2PC metrics"""
        # Set random seed
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Start message generator
        self.env.process(self.message_generator())

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        if not self.verbose:
            return self.metrics

        # Print results including 2PC metrics
        print(f"Simulation complete:")
        print(f"  Model: {self.model_name()}")
        print(f"  Total messages: {self.message_id}")
        print(f"  Measured messages: {len(self.metrics.wait_times)}")

        # Print 2PC-specific metrics
        twopc_metrics = self.service_dist.get_2pc_metrics()
        print(f"\n2PC Overhead Metrics:")
        print(f"  Avg 2PC overhead: {twopc_metrics['avg_2pc_overhead']*1000:.2f}ms")
        print(f"  Expected overhead: {twopc_metrics['expected_overhead']*1000:.2f}ms")
        print(f"  Overhead percentage: {twopc_metrics['overhead_percentage']:.1f}%")
        print(f"  Timeout rate: {twopc_metrics['timeout_rate']*100:.2f}%")

        return self.metrics


class MGN2PCQueue(QueueModel):
    """
    M/G/N Queue with Two-Phase Commit overhead

    Service time includes:
    - Base general distribution (e.g., Pareto, lognormal)
    - 2PC protocol overhead

    This shows the combined impact of:
    1. Heavy-tailed service times (M/G/N)
    2. Distributed reliability overhead (2PC)
    """

    def __init__(self, env: simpy.Environment, config: MGNConfig,
                 num_replicas: int = 3,
                 network_rtt_mean: float = 0.010,
                 replica_availability: float = 0.99):
        """
        Args:
            env: SimPy environment
            config: M/G/N configuration
            num_replicas: Number of replicas for 2PC (default: 3)
            network_rtt_mean: Mean network RTT in seconds (default: 10ms)
            replica_availability: Probability replica responds (default: 0.99)
        """
        # Bug fix: attributes used by model_name() must exist before
        # QueueModel.__init__ calls it.
        self.num_replicas = num_replicas
        self.network_rtt_mean = network_rtt_mean
        self.base_distribution = config.distribution
        super().__init__(env, config)

        # Create base distribution (Pareto, lognormal, etc.)
        base_dist = create_distribution(config)

        # Wrap with 2PC overhead
        self.service_dist = TwoPhaseCommitService(
            base_distribution=base_dist,
            num_replicas=num_replicas,
            network_rtt_mean=network_rtt_mean,
            replica_availability=replica_availability
        )

        self.num_replicas = num_replicas
        self.network_rtt_mean = network_rtt_mean
        self.base_distribution = config.distribution

    def model_name(self) -> str:
        return f"M/{self.base_distribution}/{self.config.num_threads} + 2PC({self.num_replicas} replicas)"

    def get_service_time(self) -> float:
        """
        Get service time INCLUDING 2PC overhead

        Combines:
        - Heavy-tailed base service time
        - 2PC protocol overhead
        """
        return self.service_dist.sample()

    def run(self) -> SimulationMetrics:
        """Run simulation and report 2PC metrics"""
        # Set random seed
        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

        # Start message generator
        self.env.process(self.message_generator())

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        # Print results including 2PC metrics
        print(f"Simulation complete:")
        print(f"  Model: {self.model_name()}")
        print(f"  Total messages: {self.message_id}")
        print(f"  Measured messages: {len(self.metrics.wait_times)}")

        # Print 2PC-specific metrics
        twopc_metrics = self.service_dist.get_2pc_metrics()
        print(f"\n2PC Overhead Metrics:")
        print(f"  Avg 2PC overhead: {twopc_metrics['avg_2pc_overhead']*1000:.2f}ms")
        print(f"  Expected overhead: {twopc_metrics['expected_overhead']*1000:.2f}ms")
        print(f"  Overhead percentage: {twopc_metrics['overhead_percentage']:.1f}%")
        print(f"  Timeout rate: {twopc_metrics['timeout_rate']*100:.2f}%")

        return self.metrics


def run_mmn_2pc_simulation(config: MMNConfig,
                            num_replicas: int = 3,
                            network_rtt_mean: float = 0.010,
                            replica_availability: float = 0.99) -> SimulationMetrics:
    """
    Run M/M/N simulation with 2PC overhead

    Args:
        config: M/M/N configuration
        num_replicas: Number of replicas (default: 3)
        network_rtt_mean: Network RTT in seconds (default: 10ms)
        replica_availability: Replica availability (default: 0.99)

    Returns:
        SimulationMetrics

    Example:
        >>> from src.core.config import MMNConfig
        >>> config = MMNConfig(
        ...     arrival_rate=100,
        ...     num_threads=10,
        ...     service_rate=12,
        ...     sim_duration=1000,
        ...     warmup_time=100
        ... )
        >>> metrics = run_mmn_2pc_simulation(config, num_replicas=3)
    """
    env = simpy.Environment()
    model = MMN2PCQueue(env, config, num_replicas, network_rtt_mean, replica_availability)
    return model.run()


def run_mgn_2pc_simulation(config: MGNConfig,
                            num_replicas: int = 3,
                            network_rtt_mean: float = 0.010,
                            replica_availability: float = 0.99) -> SimulationMetrics:
    """
    Run M/G/N simulation with 2PC overhead

    Args:
        config: M/G/N configuration
        num_replicas: Number of replicas (default: 3)
        network_rtt_mean: Network RTT in seconds (default: 10ms)
        replica_availability: Replica availability (default: 0.99)

    Returns:
        SimulationMetrics

    Example:
        >>> from src.core.config import MGNConfig
        >>> config = MGNConfig(
        ...     arrival_rate=100,
        ...     num_threads=10,
        ...     service_rate=12,
        ...     distribution='pareto',
        ...     alpha=2.5,
        ...     sim_duration=1000,
        ...     warmup_time=100
        ... )
        >>> metrics = run_mgn_2pc_simulation(config, num_replicas=3)
    """
    env = simpy.Environment()
    model = MGN2PCQueue(env, config, num_replicas, network_rtt_mean, replica_availability)
    return model.run()
