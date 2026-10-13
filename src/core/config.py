"""Type-safe configuration using Pydantic"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, List, Dict
from dataclasses import dataclass


class QueueConfig(BaseModel):
    """Base configuration for all queue models"""

    # Arrival process
    arrival_rate: float = Field(
        gt=0,
        description="λ (messages/sec)"
    )

    # Service process
    num_threads: int = Field(
        gt=0,
        le=1000,
        description="N (number of threads)"
    )
    service_rate: float = Field(
        gt=0,
        description="μ (messages/sec per thread)"
    )

    # Simulation parameters
    sim_duration: float = Field(
        default=1000.0,
        gt=0,
        description="Simulation time (seconds)"
    )
    warmup_time: float = Field(
        default=100.0,
        ge=0,
        description="Warmup period to discard"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility"
    )

    @field_validator('service_rate')
    @classmethod
    def check_stability(cls, v, info):
        """Ensure system is stable (ρ < 1)

        Note: This check is skipped for FiniteCapacityConfig since finite
        capacity queues are always stable (blocking prevents overflow).
        """
        # Skip stability check for finite capacity queues
        if cls.__name__ == 'FiniteCapacityConfig':
            return v

        data = info.data
        if 'arrival_rate' in data and 'num_threads' in data:
            rho = data['arrival_rate'] / (data['num_threads'] * v)
            if rho >= 1.0:
                raise ValueError(
                    f"System unstable: ρ = {rho:.3f} >= 1. "
                    f"Reduce arrival_rate or increase num_threads/service_rate"
                )
        return v

    @property
    def utilization(self) -> float:
        """Calculate ρ = λ/(N·μ)"""
        return self.arrival_rate / (self.num_threads * self.service_rate)

    @property
    def traffic_intensity(self) -> float:
        """Calculate λ/μ"""
        return self.arrival_rate / self.service_rate


class MMNConfig(QueueConfig):
    """M/M/N specific configuration"""
    model_type: Literal["M/M/N"] = "M/M/N"
    enable_qos: bool = Field(default=False, description="Enable Priority QoS")


class MGNConfig(QueueConfig):
    """M/G/N specific configuration

    Note: For Pareto distribution, the scale parameter is automatically
    calculated to match the mean service time (1/service_rate). This ensures
    that different α values are comparable.
    """
    model_type: Literal["M/G/N"] = "M/G/N"

    distribution: Literal["pareto", "lognormal", "weibull", "erlang", "exponential"] = Field(
        default="pareto",
        description="Service time distribution"
    )

    # Pareto parameters
    alpha: float = Field(
        default=2.5,
        gt=1.0,
        le=5.0,
        description="Pareto shape parameter"
    )
    
    # Erlang parameters
    erlang_k: int = Field(
        default=2,
        gt=0,
        le=20,
        description="Erlang shape parameter (k)"
    )
    enable_qos: bool = Field(default=False, description="Enable Priority QoS")

    @property
    def scale(self) -> float:
        """Calculate Pareto scale parameter to match mean service time

        From E[S] = α·k/(α-1) = 1/μ, we get:
        k = (1/μ) · (α-1)/α

        This ensures all α values have the same mean service time.
        """
        target_mean = 1.0 / self.service_rate  # Desired E[S]
        return target_mean * (self.alpha - 1) / self.alpha

    @property
    def mean_service_time(self) -> float:
        """E[S] = α·k/(α-1)"""
        return (self.alpha * self.scale) / (self.alpha - 1)

    @property
    def variance_service_time(self) -> float:
        """Var[S] for Pareto"""
        if self.alpha <= 2:
            return float('inf')
        return (self.alpha * self.scale**2) / ((self.alpha - 1)**2 * (self.alpha - 2))

    @property
    def coefficient_of_variation(self) -> float:
        """C² = 1/(α(α-2)) for α > 2 (CORRECTED formula)"""
        if self.alpha <= 2:
            return float('inf')
        return 1.0 / (self.alpha * (self.alpha - 2))


class PriorityQueueConfig(QueueConfig):
    """
    Priority Queue Configuration (M/M/N with priorities)

    Models a queue with multiple priority classes.
    Higher priority messages are served before lower priority messages.

    Example:
        config = PriorityQueueConfig(
            arrival_rate=100,
            num_threads=10,
            service_rate=12,
            num_priorities=3,
            priority_rates=[30, 50, 20],  # High, Medium, Low
            preemptive=False
        )
    """
    model_type: Literal["Priority"] = "Priority"

    num_priorities: int = Field(
        default=2,
        gt=0,
        le=10,
        description="Number of priority classes (1 = highest)"
    )

    priority_rates: List[float] = Field(
        default=[],
        description="Arrival rates for each priority class (must sum to arrival_rate)"
    )

    preemptive: bool = Field(
        default=False,
        description="Whether higher priority can preempt lower priority service"
    )

    @model_validator(mode='after')
    def validate_priority_rates(self):
        """Ensure priority rates sum to total arrival rate"""
        if not self.priority_rates:
            # Auto-distribute evenly if not specified
            rate_per_class = self.arrival_rate / self.num_priorities
            self.priority_rates = [rate_per_class] * self.num_priorities

        if len(self.priority_rates) != self.num_priorities:
            raise ValueError(
                f"priority_rates length ({len(self.priority_rates)}) "
                f"must match num_priorities ({self.num_priorities})"
            )

        total_rate = sum(self.priority_rates)
        if abs(total_rate - self.arrival_rate) > 0.01:
            raise ValueError(
                f"priority_rates sum ({total_rate:.2f}) must equal "
                f"arrival_rate ({self.arrival_rate:.2f})"
            )

        return self

    @property
    def priority_utilizations(self) -> List[float]:
        """Calculate utilization for each priority class"""
        return [rate / (self.num_threads * self.service_rate)
                for rate in self.priority_rates]


class FiniteCapacityConfig(QueueConfig):
    """
    Finite Capacity Queue Configuration (M/M/N/K)

    Models a queue with maximum capacity K.
    When queue is full, new arrivals are blocked/rejected.

    Example:
        config = FiniteCapacityConfig(
            arrival_rate=100,
            num_threads=10,
            service_rate=12,
            max_capacity=50,
            blocking_strategy='reject'
        )
    """
    model_type: Literal["FiniteCapacity"] = "FiniteCapacity"

    max_capacity: int = Field(
        gt=0,
        le=10000,
        description="Maximum queue capacity K (including those in service)"
    )

    blocking_strategy: Literal["reject", "wait"] = Field(
        default="reject",
        description="What to do when queue is full: reject or wait for space"
    )

    @property
    def max_queue_length(self) -> int:
        """Maximum number of messages waiting (excluding those in service)"""
        return max(0, self.max_capacity - self.num_threads)


class ThreadingConfig(BaseModel):
    """Threading model configuration"""

    model: Literal["dedicated", "shared"] = Field(
        default="shared",
        description="Threading model type"
    )

    # Shared thread pool parameters
    num_threads: int = Field(
        default=100,
        gt=0,
        description="Total threads in pool"
    )
    context_switch_overhead: float = Field(
        default=0.0001,
        ge=0,
        description="Context switch overhead (seconds)"
    )

    # Dedicated (thread-per-connection) parameters
    threads_per_connection: int = Field(
        default=2,
        gt=0,
        description="Threads per connection (dedicated model)"
    )

    @property
    def max_connections_dedicated(self) -> int:
        """Maximum concurrent connections (dedicated model)"""
        if self.model == "dedicated":
            return self.num_threads // self.threads_per_connection
        return 0


class MEkNConfig(QueueConfig):
    """M/Ek/N specific configuration (Erlang-k service)"""
    model_type: Literal["M/Ek/N"] = "M/Ek/N"

    erlang_k: int = Field(
        default=2,
        gt=0,
        le=20,
        description="Number of Erlang phases (k)"
    )


@dataclass
class ServerGroup:
    """
    Definition of a homogeneous server group

    Used in heterogeneous M/M/N queues where different servers have different speeds.

    Example:
        # 2 legacy t2.small instances @ 8 msg/sec
        ServerGroup(count=2, service_rate=8.0, name="t2.small")

        # 3 new t2.large instances @ 15 msg/sec
        ServerGroup(count=3, service_rate=15.0, name="t2.large")
    """
    count: int
    service_rate: float
    name: str = ""

    def __post_init__(self):
        if self.count <= 0:
            raise ValueError(f"count must be > 0, got {self.count}")
        if self.service_rate <= 0:
            raise ValueError(f"service_rate must be > 0, got {self.service_rate}")


class HeterogeneousMMNConfig(BaseModel):
    """
    Heterogeneous M/M/N Configuration

    Models M/M/N queues with multiple server groups having different service rates.
    This addresses the "Future Work" from Li et al. (2015) regarding heterogeneous
    server modeling.

    Example - Cloud Message Broker with Mixed Instance Types:
        config = HeterogeneousMMNConfig(
            arrival_rate=100,
            server_groups=[
                ServerGroup(count=2, service_rate=8.0, name="t2.small (legacy)"),
                ServerGroup(count=3, service_rate=15.0, name="t2.large (new)")
            ],
            sim_duration=1000,
            warmup_time=100,
            random_seed=42
        )

    Mathematical Properties:
    - Total servers: N = Σ n_i
    - Weighted avg service rate: μ_avg = (Σ n_i·μ_i) / N
    - Heterogeneity increases queueing delay compared to homogeneous system
      with same total capacity (due to increased service time variance)

    Reference:
    Whitt, W. (1985). "Deciding which queue to join: Some counterexamples."
    Operations Research, 34(1), 55-62.
    """
    model_type: Literal["HeterogeneousMMN"] = "HeterogeneousMMN"

    # Arrival process
    arrival_rate: float = Field(
        gt=0,
        description="λ (messages/sec)"
    )

    # Server groups (heterogeneous servers)
    server_groups: List[ServerGroup] = Field(
        description="List of server groups with different service rates"
    )

    # Server selection policy
    selection_policy: Literal["random", "random_capacity", "fastest_first", "round_robin", "shortest_queue", "work_stealing"] = Field(
        default="random",
        description="Policy for selecting which server group to use"
    )

    # Consistency Mode (for 2PC overhead)
    consistency_mode: Literal["eventual", "strong", "strong_2pc", "raft"] = Field(
        default="eventual",
        description="Consistency mode (affects service time)"
    )

    # Simulation parameters
    sim_duration: float = Field(
        default=1000.0,
        gt=0,
        description="Simulation time (seconds)"
    )
    warmup_time: float = Field(
        default=100.0,
        ge=0,
        description="Warmup period to discard"
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility"
    )

    @model_validator(mode='after')
    def validate_server_groups(self):
        """Ensure at least one server group exists"""
        if not self.server_groups:
            raise ValueError("Must specify at least one server group")

        if len(self.server_groups) == 1:
            # Only one group - this is effectively homogeneous M/M/N
            print(
                "WARNING: Only one server group specified. "
                "Consider using MMNConfig for homogeneous systems."
            )

        return self

    @model_validator(mode='after')
    def check_stability(self):
        """Ensure system is stable (ρ < 1) using weighted average service rate"""
        rho = self.utilization

        if rho >= 1.0:
            raise ValueError(
                f"System unstable: ρ = {rho:.3f} >= 1. "
                f"Total capacity: {self.total_capacity:.1f} msg/sec, "
                f"Arrival rate: {self.arrival_rate:.1f} msg/sec. "
                f"Reduce arrival_rate or add more servers/increase service rates."
            )

        overloaded = [u for u in self.static_pool_utilizations() if u >= 1.0]
        if overloaded:
            print(
                f"WARNING: '{self.selection_policy}' dispatch overloads a server pool "
                f"(per-pool ρ = {max(overloaded):.3f} >= 1) even though aggregate "
                f"ρ = {rho:.3f} < 1; that pool's queue grows without bound."
            )

        return self

    def static_pool_utilizations(self) -> List[float]:
        """
        Per-pool utilization ρ_i = λ_i / (n_i·μ_i) under a static split.

        For "random" and "round_robin" each
        server receives λ/N, so λ_i = λ·n_i/N; for "random_capacity" λ_i is
        proportional to n_i·μ_i. Dynamic policies (shortest_queue, work_stealing,
        fastest_first) have no static split and return the aggregate ρ.
        """
        n_total = sum(g.count for g in self.server_groups)
        capacity = sum(g.count * g.service_rate for g in self.server_groups)
        if self.selection_policy in ("random", "round_robin"):
            return [self.arrival_rate * g.count / n_total / (g.count * g.service_rate)
                    for g in self.server_groups]
        return [self.arrival_rate / capacity for _ in self.server_groups]

    @property
    def total_servers(self) -> int:
        """Total number of servers across all groups: N = Σ n_i"""
        return sum(group.count for group in self.server_groups)

    @property
    def weighted_service_rate(self) -> float:
        """
        Weighted average service rate: μ_avg = (Σ n_i·μ_i) / N

        This is the service rate of an equivalent homogeneous system.
        """
        total_capacity = sum(group.count * group.service_rate for group in self.server_groups)
        return total_capacity / self.total_servers

    @property
    def total_capacity(self) -> float:
        """
        Total system capacity: C = Σ n_i·μ_i (messages/sec)

        This is the maximum throughput if all servers are always busy.
        """
        return sum(group.count * group.service_rate for group in self.server_groups)

    @property
    def utilization(self) -> float:
        """
        System utilization: ρ = λ / C = λ / (Σ n_i·μ_i)

        For heterogeneous systems, utilization is calculated using total capacity.
        """
        return self.arrival_rate / self.total_capacity

    @property
    def heterogeneity_coefficient(self) -> float:
        """
        Coefficient of variation of service rates across server groups

        CV_μ = σ_μ / μ_avg

        Higher values indicate more heterogeneity (worse performance).
        CV_μ = 0 means homogeneous (all servers identical).
        """
        mu_avg = self.weighted_service_rate

        # Calculate variance of service rates (weighted by server count)
        variance = sum(
            group.count * (group.service_rate - mu_avg) ** 2
            for group in self.server_groups
        ) / self.total_servers

        std_dev = variance ** 0.5
        return std_dev / mu_avg if mu_avg > 0 else 0.0

    @property
    def traffic_intensity(self) -> float:
        """
        Traffic intensity using weighted average: a = λ / μ_avg

        Note: For heterogeneous systems, this is an approximation.
        """
        return self.arrival_rate / self.weighted_service_rate


class TandemQueueConfig(BaseModel):
    """
    Tandem (two-stage) queue configuration

    Models message broker → network → receiver architecture from Li et al. (2015)
    """

    # Arrival process
    arrival_rate: float = Field(
        gt=0,
        description="λ (messages/sec arriving at Stage 1)"
    )

    # Simulation parameters
    sim_duration: float = Field(
        default=1000.0,
        gt=0
    )
    warmup_time: float = Field(
        default=100.0,
        ge=0
    )
    random_seed: Optional[int] = Field(
        default=None
    )

    # Stage 1: Broker
    n1: int = Field(
        gt=0,
        le=100,
        description="Number of broker threads (Stage 1)"
    )
    mu1: float = Field(
        gt=0,
        description="Broker service rate (messages/sec/thread)"
    )

    # Stage 2: Receiver
    n2: int = Field(
        gt=0,
        le=100,
        description="Number of receiver threads (Stage 2)"
    )
    mu2: float = Field(
        gt=0,
        description="Receiver service rate (messages/sec/thread)"
    )

    # Network parameters
    network_delay: float = Field(
        gt=0,
        description="One-way network delay D_link (seconds)"
    )
    failure_prob: float = Field(
        ge=0,
        lt=1.0,
        description="Transmission failure probability p (0 ≤ p < 1)"
    )

    # Service Distribution Parameters
    distribution: Literal["exponential", "pareto", "erlang"] = Field(
        default="exponential",
        description="Service time distribution type"
    )
    
    alpha: float = Field(
        default=2.5,
        gt=1.0,
        description="Pareto shape parameter (if distribution='pareto')"
    )
    
    erlang_k: int = Field(
        default=2,
        gt=0,
        description="Erlang shape parameter (if distribution='erlang')"
    )

    @model_validator(mode='after')
    def check_stage2_stability(self):
        """
        Ensure Stage 2 is stable

        CRITICAL: Stage 2 arrival rate is Λ₂ = λ/(1-p), NOT λ!
        """
        # Effective arrival rate at Stage 2 (includes retries)
        Lambda2 = self.arrival_rate / (1 - self.failure_prob)

        # Stage 2 utilization
        rho2 = Lambda2 / (self.n2 * self.mu2)

        if rho2 >= 1.0:
            raise ValueError(
                f"Stage 2 unstable: ρ₂ = {rho2:.3f} >= 1. "
                f"Λ₂ = λ/(1-p) = {Lambda2:.1f} msg/sec. "
                f"Reduce arrival_rate or failure_prob, or increase n2/mu2."
            )

        return self

    @property
    def stage1_utilization(self) -> float:
        """ρ₁ = λ/(n₁·μ₁)"""
        return self.arrival_rate / (self.n1 * self.mu1)

    @property
    def stage2_effective_arrival(self) -> float:
        """
        Effective arrival rate at Stage 2 (includes retransmissions)

        Λ₂ = λ/(1-p)

        When p=0 (no failures): Λ₂ = λ
        When p=0.2 (20% failures): Λ₂ = 1.25λ (25% higher!)
        """
        return self.arrival_rate / (1 - self.failure_prob)

    @property
    def stage2_utilization(self) -> float:
        """
        ρ₂ = Λ₂/(n₂·μ₂) = λ/((1-p)·n₂·μ₂)

        Note: Stage 2 utilization is HIGHER than Stage 1 when p > 0!
        """
        return self.stage2_effective_arrival / (self.n2 * self.mu2)

    @property
    def expected_network_time(self) -> float:
        """
        Expected network time including retries

        E[Network Time] = (2 + p) · D_link

        Components:
        - 2·D_link: Initial send + ACK
        - p·D_link: Average retries (p failures × D_link per retry)
        """
        return (2 + self.failure_prob) * self.network_delay


class DistributedConfig(BaseModel):
    """
    Distributed Broker Configuration
    """
    model_type: Literal["Distributed"] = "Distributed"
    
    arrival_rate: float = Field(gt=0)
    service_rate: float = Field(gt=0)
    num_nodes: int = Field(default=3, gt=0)
    replication_factor: int = Field(default=3, gt=0)
    consistency_mode: Literal["eventual", "strong", "strong_2pc", "raft"] = "eventual"
    ordering_mode: Literal["unordered", "fifo", "strict_fifo", "causal"] = "unordered"
    enable_hedging: bool = False
    
    sim_duration: float = Field(default=1000.0, gt=0)
    warmup_time: float = Field(default=100.0, ge=0)
    random_seed: Optional[int] = None

