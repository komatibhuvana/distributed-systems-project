"""Service time distribution implementations"""

from abc import ABC, abstractmethod
import numpy as np
from scipy import stats
from typing import Protocol


class ServiceTimeDistribution(Protocol):
    """Protocol for service time distributions"""

    def sample(self) -> float:
        """Generate one service time sample"""
        ...

    def mean(self) -> float:
        """Return E[S]"""
        ...

    def variance(self) -> float:
        """Return Var[S]"""
        ...

    def coefficient_of_variation(self) -> float:
        """Return C² = Var[S]/E[S]²"""
        ...


class ExponentialService:
    """Exponential service time (M/M/N)"""

    def __init__(self, rate: float):
        """
        Args:
            rate: μ (messages/sec per thread)
        """
        self.rate = rate  # μ
        self._dist = stats.expon(scale=1/rate)

    def sample(self) -> float:
        return self._dist.rvs()

    def mean(self) -> float:
        return 1.0 / self.rate

    def variance(self) -> float:
        return 1.0 / (self.rate ** 2)

    def coefficient_of_variation(self) -> float:
        return 1.0  # Always 1 for exponential


class ErlangService:
    """
    Erlang distribution service time (M/Ek/N)

    The Erlang distribution is a special case of Gamma distribution
    with integer shape parameter k, representing the sum of k
    independent exponential random variables.

    Use cases:
    - Multi-stage processing (k stages, each exponential)
    - Call centers with k service phases
    - Manufacturing with k sequential operations

    PDF: f(x) = (λ^k / (k-1)!) * x^(k-1) * e^(-λx)

    Properties:
    - E[S] = k/λ
    - Var[S] = k/λ²
    - CV² = 1/k (decreases with more phases)
    - As k→∞, approaches deterministic service time (M/D/N)

    Reference:
    Gross, D., & Harris, C. M. (1998). Fundamentals of queueing theory.
    Wiley-Interscience.
    """

    def __init__(self, shape: int, rate: float):
        """
        Args:
            shape: k (number of phases, must be positive integer)
            rate: λ (rate parameter for each phase)

        Example:
            >>> # 3-phase service, each phase with rate 12
            >>> erlang = ErlangService(shape=3, rate=12)
            >>> print(f"Mean: {erlang.mean():.3f}")  # 0.250
            >>> print(f"CV²: {erlang.coefficient_of_variation():.3f}")  # 0.333
        """
        if not isinstance(shape, int) or shape < 1:
            raise ValueError("Shape parameter k must be a positive integer")

        if rate <= 0:
            raise ValueError("Rate parameter must be positive")

        self.shape = shape  # k
        self.rate = rate    # λ
        self._dist = stats.erlang(a=shape, scale=1/rate)

    def sample(self) -> float:
        """Generate one sample from Erlang distribution"""
        return self._dist.rvs()

    def mean(self) -> float:
        """E[S] = k/λ"""
        return self.shape / self.rate

    def variance(self) -> float:
        """Var[S] = k/λ²"""
        return self.shape / (self.rate ** 2)

    def coefficient_of_variation(self) -> float:
        """
        CV² = 1/k (decreases with more phases)

        This shows:
        - k=1: CV²=1 (exponential, M/M/N)
        - k=2: CV²=0.5
        - k=4: CV²=0.25
        - k→∞: CV²→0 (deterministic, M/D/N)
        """
        return 1.0 / self.shape

    def percentile(self, p: float) -> float:
        """Exact percentile using scipy"""
        return self._dist.ppf(p)

    def pdf(self, x: float) -> float:
        """Probability density function"""
        return self._dist.pdf(x)

    def cdf(self, x: float) -> float:
        """Cumulative distribution function"""
        return self._dist.cdf(x)

    def __repr__(self) -> str:
        return f"ErlangService(shape={self.shape}, rate={self.rate:.3f})"


class ParetoService:
    """Pareto (heavy-tailed) service time

    Implements Equation 6 from the project plan:
    f(t) = α·k^α / t^(α+1) for t ≥ k
    """

    def __init__(self, alpha: float, scale: float):
        """
        Args:
            alpha: Shape parameter (α > 1)
            scale: Scale parameter (k > 0, minimum value)
        """
        if alpha <= 1:
            raise ValueError("alpha must be > 1")

        self.alpha = alpha
        self.scale = scale

    def sample(self) -> float:
        """Sample using inverse transform method

        Pareto CDF: F(t) = 1 - (k/t)^α
        Inverse CDF: F^(-1)(u) = k / (1-u)^(1/α)

        This ensures correct statistical properties.
        """
        u = np.random.uniform(0, 1)
        return self.scale / ((1 - u) ** (1.0 / self.alpha))

    def mean(self) -> float:
        """
        Equation 7: E[S] = α·k/(α-1)
        """
        return (self.alpha * self.scale) / (self.alpha - 1)

    def variance(self) -> float:
        """
        Equation 8: Var[S] = α·k²/((α-1)²·(α-2)) for α > 2
        """
        if self.alpha <= 2:
            return float('inf')
        numerator = self.alpha * (self.scale ** 2)
        denominator = ((self.alpha - 1) ** 2) * (self.alpha - 2)
        return numerator / denominator

    def coefficient_of_variation(self) -> float:
        """
        Equation 9 (CORRECTED): C² = 1/(α(α-2)) for α > 2

        Derived from: CV² = Var[S]/(E[S])²
        where Var[S] = α·k²/((α-1)²(α-2)) and E[S] = α·k/(α-1)

        Note: The original equation had an error. The correct formula
        includes the α term in the denominator.
        """
        if self.alpha <= 2:
            return float('inf')
        return 1.0 / (self.alpha * (self.alpha - 2))


class LognormalService:
    """Lognormal service time (alternative heavy-tail)"""

    def __init__(self, mu: float, sigma: float):
        """
        Args:
            mu: Location parameter
            sigma: Scale parameter
        """
        self.mu = mu
        self.sigma = sigma
        self._dist = stats.lognorm(s=sigma, scale=np.exp(mu))

    def sample(self) -> float:
        return self._dist.rvs()

    def mean(self) -> float:
        return np.exp(self.mu + self.sigma**2 / 2)

    def variance(self) -> float:
        exp_sigma2 = np.exp(self.sigma**2)
        return (exp_sigma2 - 1) * np.exp(2*self.mu + self.sigma**2)

    def coefficient_of_variation(self) -> float:
        return np.exp(self.sigma**2) - 1


class WeibullService:
    """Weibull service time distribution"""

    def __init__(self, shape: float, scale: float):
        """
        Args:
            shape: Shape parameter (k)
            scale: Scale parameter (λ)
        """
        self.shape = shape
        self.scale = scale
        self._dist = stats.weibull_min(c=shape, scale=scale)

    def sample(self) -> float:
        return self._dist.rvs()

    def mean(self) -> float:
        from scipy.special import gamma
        return self.scale * gamma(1 + 1/self.shape)

    def variance(self) -> float:
        from scipy.special import gamma
        mean = self.mean()
        second_moment = (self.scale ** 2) * gamma(1 + 2/self.shape)
        return second_moment - mean**2

    def coefficient_of_variation(self) -> float:
        return self.variance() / (self.mean() ** 2)


def create_distribution(config) -> ServiceTimeDistribution:
    """Factory function to create distribution from config

    Args:
        config: MGNConfig object with distribution parameters

    Returns:
        ServiceTimeDistribution instance
    """
    if config.distribution == "exponential":
        return ExponentialService(rate=config.service_rate)

    elif config.distribution == "erlang":
        # Erlang-k distribution
        shape = config.erlang_k if hasattr(config, 'erlang_k') else 2
        # Adjust rate to maintain mean service time: E[S] = k/λ = 1/μ
        # Therefore: λ = k * μ
        rate = shape * config.service_rate
        return ErlangService(shape=shape, rate=rate)

    elif config.distribution == "pareto":
        return ParetoService(alpha=config.alpha, scale=config.scale)

    elif config.distribution == "lognormal":
        # Derive mu, sigma to match desired mean service time
        target_mean = 1.0 / config.service_rate
        cv_squared = config.coefficient_of_variation if hasattr(config, 'coefficient_of_variation') else 1.0
        sigma = np.sqrt(np.log(1 + cv_squared))
        mu = np.log(target_mean) - sigma**2 / 2
        return LognormalService(mu=mu, sigma=sigma)

    elif config.distribution == "weibull":
        # Use shape parameter to control variability
        shape = 2.0  # Default shape
        scale = 1.0 / config.service_rate
        return WeibullService(shape=shape, scale=scale)

    else:
        raise ValueError(f"Unknown distribution: {config.distribution}")


class TwoPhaseCommitService:
    """
    Service time distribution including Two-Phase Commit (2PC) protocol overhead

    Addresses professor's critique #3 about 2PC-reliability disconnect.

    This distribution models the COMPLETE service time when using 2PC for reliability:

    Total Service Time = Base Processing + 2PC Overhead

    2PC Overhead Components:
    1. PREPARE phase: Send prepare message to all replicas (network RTT)
    2. VOTE phase: Wait for all votes (blocking time, max of all responses)
    3. COMMIT phase: Send decision to all replicas (network RTT)

    Key Insight:
    ------------
    2PC BLOCKS the server during vote collection, preventing it from processing
    other messages. This increases effective service time and reduces throughput.

    Mathematical Model (what sample() actually draws):
    --------------------------------------------------
    Let R ~ max(0.001, Normal(RTT_mean, RTT_std)) be one clipped RTT sample,
    a = replica_availability, n = num_replicas, T = vote_timeout.

        Overhead O = R_prepare + V + R_commit
        V = max_i X_i,  X_i = T w.p. (1-a), else an independent R

    Since T > RTT in every sensible configuration, V = T whenever at least one
    replica times out, otherwise V = max of n RTTs (M_n). With
    q = P(any timeout) = 1 - a^n:

        E[O]   = 2·E[R] + a^n·E[M_n] + q·T
        Var[O] = 2·Var[R] + Var[V]
        Var[V] = a^n·E[M_n²] + q·T² − (E[V])²       (Bernoulli mixture)
        E[S_total] = E[S_base] + E[O],  Var[S_total] = Var[S_base] + Var[O]

    E[R], E[M_n], E[M_n²] are computed numerically (exact up to quadrature
    error) by `overhead_mean()` / `overhead_variance()`. Assumption: T is
    larger than any RTT sample (true for defaults; T=1 s vs RTT 10±2 ms).

    Worked numbers for the DEFAULTS (n=3, RTT 10 ms ± 2 ms, a=0.99, T=1.0 s):
    - q = 1 − 0.99³ ≈ 0.0297, so the timeout term alone contributes ≈ 29.7 ms
    - RTT terms contribute 2·10 ms + 0.9703·E[max of 3 RTTs](11.69 ms) ≈ 31.3 ms
    - E[O] ≈ 61.0 ms (NOT ≈30 ms as an earlier version of this docstring
      claimed; ≈30 ms is only roughly right for a=1.0, where E[O] ≈ 31.7 ms)
    - Var[O] ≈ 0.0282 s² is dominated by the Bernoulli(q)×T timeout term:
      SD[O] ≈ 168 ms (vs ≈3.5 ms if timeouts are ignored)
    - With μ=12 (E[S_base]=83.3 ms): E[S_total] ≈ 144.4 ms, so with N=10 the
      system saturates at λ ≈ N/E[S_total] ≈ 69.3 msg/s; λ=100 is UNSTABLE.
    Call overhead_mean()/mean() for exact values; numbers above are rounded.

    References:
    -----------
    - Gray, J., & Lamport, L. (1978). "The transaction concept."
    - Bernstein, P. A., & Goodman, N. (1981). "Concurrency control in distributed
      database systems." ACM Computing Surveys, 13(2), 185-221.
    - Li et al. (2015). "Modeling Message Queueing Services..." (used 2PC for reliability)

    Usage:
    ------
    >>> # Wrap existing distribution with 2PC overhead
    >>> base_dist = ExponentialService(rate=12)
    >>> twopc_dist = TwoPhaseCommitService(
    ...     base_distribution=base_dist,
    ...     num_replicas=3,
    ...     network_rtt_mean=0.010,  # 10ms
    ...     replica_availability=0.99
    ... )
    >>>
    >>> # Sample includes both base processing AND 2PC overhead
    >>> service_time = twopc_dist.sample()
    >>> print(f"Total service time: {service_time:.3f} sec")
    """

    def __init__(self,
                 base_distribution: ServiceTimeDistribution,
                 num_replicas: int = 3,
                 network_rtt_mean: float = 0.010,  # 10ms
                 network_rtt_std: float = 0.002,   # 2ms std dev
                 replica_availability: float = 0.99,
                 vote_timeout: float = 1.0):
        """
        Args:
            base_distribution: Underlying service time distribution (processing only)
            num_replicas: Number of replicas in 2PC protocol (default: 3)
            network_rtt_mean: Mean network round-trip time (seconds, default: 10ms)
            network_rtt_std: Std dev of network RTT (seconds, default: 2ms)
            replica_availability: Probability each replica responds (default: 0.99)
            vote_timeout: Timeout for vote collection (seconds, default: 1.0s)

        Example:
            >>> base = ExponentialService(rate=12)
            >>> twopc = TwoPhaseCommitService(
            ...     base_distribution=base,
            ...     num_replicas=3,
            ...     network_rtt_mean=0.010,
            ...     replica_availability=0.99
            ... )
        """
        self.base_dist = base_distribution
        self.num_replicas = num_replicas
        self.network_rtt_mean = network_rtt_mean
        self.network_rtt_std = network_rtt_std
        self.replica_availability = replica_availability
        self.vote_timeout = vote_timeout

        # Track 2PC-specific metrics
        self.total_samples = 0
        self.timeout_count = 0
        self.avg_2pc_overhead = 0.0

    def _sample_network_rtt(self) -> float:
        """
        Sample network round-trip time

        Uses truncated normal distribution (no negative RTTs)
        """
        rtt = np.random.normal(self.network_rtt_mean, self.network_rtt_std)
        return max(0.001, rtt)  # Minimum 1ms

    def sample(self) -> float:
        """
        Sample total service time = base processing + 2PC overhead

        2PC Protocol Flow:
        1. PREPARE phase: Coordinator sends prepare to all replicas
        2. VOTE phase: Replicas vote yes/no (blocking!)
        3. COMMIT phase: Coordinator sends decision

        Returns:
            Total service time (seconds)
        """
        self.total_samples += 1

        # 1. Base processing time (actual work)
        base_time = self.base_dist.sample()

        # 2-4. 2PC overhead (same RNG draw order as before the refactor)
        twopc_overhead = self._sample_overhead()

        # Update average overhead tracking
        alpha = 0.1  # Exponential moving average
        self.avg_2pc_overhead = (1 - alpha) * self.avg_2pc_overhead + alpha * twopc_overhead

        # Total service time
        total_time = base_time + twopc_overhead

        return total_time

    def sample_overhead(self) -> float:
        """Sample only the 2PC overhead O (no base processing, no metric tracking)."""
        return self._sample_overhead(track=False)

    def _sample_overhead(self, track: bool = True) -> float:
        """Draw one 2PC overhead sample: prepare RTT + vote collection + commit RTT."""
        # 2. PREPARE phase - send prepare message to all replicas
        prepare_rtt = self._sample_network_rtt()

        # 3. VOTE phase - wait for all votes (BLOCKING!)
        # Each replica responds with vote (or times out)
        vote_times = []
        any_timeout = False

        for _ in range(self.num_replicas):
            if np.random.random() < self.replica_availability:
                # Replica responds with vote
                vote_rtt = self._sample_network_rtt()
                vote_times.append(vote_rtt)
            else:
                # Replica timeout
                vote_times.append(self.vote_timeout)
                any_timeout = True

        # Coordinator must wait for ALL votes (or timeouts)
        # This is the BLOCKING component that reduces throughput!
        vote_collection_time = max(vote_times)

        if any_timeout and track:
            self.timeout_count += 1

        # 4. COMMIT phase - send decision (commit or abort) to all
        commit_rtt = self._sample_network_rtt()

        # Total 2PC overhead
        return prepare_rtt + vote_collection_time + commit_rtt

    # ------------------------------------------------------------------
    # Exact (numerical) moments of the overhead
    # ------------------------------------------------------------------
    _RTT_FLOOR = 0.001  # must match the clip in _sample_network_rtt()

    def _clipped_rtt_cdf(self, x):
        """CDF of R = max(0.001, Normal(m, s)); zero below the 1 ms floor."""
        x = np.asarray(x, dtype=float)
        if self.network_rtt_std == 0:
            cdf = (x >= max(self._RTT_FLOOR, self.network_rtt_mean)).astype(float)
        else:
            cdf = stats.norm.cdf(x, loc=self.network_rtt_mean, scale=self.network_rtt_std)
        return np.where(x < self._RTT_FLOOR, 0.0, cdf)

    def _clipped_rtt_max_moments(self, k: int):
        """
        (E[M_k], E[M_k²]) for M_k = max of k iid clipped RTTs (k>=1).

        Uses E[X] = ∫₀^∞ (1-F(x)) dx and E[X²] = ∫₀^∞ 2x(1-F(x)) dx with
        F = F_R^k, evaluated by adaptive quadrature over [0, m + 12·s].
        """
        from scipy import integrate
        if self.network_rtt_std == 0:
            v = max(self._RTT_FLOOR, self.network_rtt_mean)
            return v, v * v
        upper = self.network_rtt_mean + 12.0 * self.network_rtt_std
        upper = max(upper, self._RTT_FLOOR * 2)
        surv = lambda x: 1.0 - float(self._clipped_rtt_cdf(x)) ** k
        pts = [self._RTT_FLOOR, self.network_rtt_mean]
        pts = [p for p in pts if 0 < p < upper]
        m1, _ = integrate.quad(surv, 0.0, upper, points=pts, limit=200,
                               epsabs=1e-13, epsrel=1e-10)
        m2, _ = integrate.quad(lambda x: 2.0 * x * surv(x), 0.0, upper,
                               points=pts, limit=200, epsabs=1e-15, epsrel=1e-10)
        return m1, m2

    def overhead_moments(self) -> dict:
        """
        Exact moments of the 2PC overhead O as sampled by sample().

        Returns dict with E[R], Var[R], E[M_n], E[M_n²], q=P(any timeout),
        E[V], Var[V], E[O], Var[O]. Valid when vote_timeout >= every RTT
        sample (always true for the defaults).
        """
        n = self.num_replicas
        a = self.replica_availability
        T = self.vote_timeout
        key = (n, a, T, self.network_rtt_mean, self.network_rtt_std)
        cache = getattr(self, '_moments_cache', None)
        if cache is not None and cache[0] == key:
            return dict(cache[1])
        r1, r2 = self._clipped_rtt_max_moments(1)
        mn1, mn2 = self._clipped_rtt_max_moments(n)
        p_all = a ** n
        q = 1.0 - p_all
        ev = p_all * mn1 + q * T
        ev2 = p_all * mn2 + q * T * T
        var_r = r2 - r1 * r1
        var_v = ev2 - ev * ev
        result = {
            'E_R': r1, 'Var_R': var_r, 'E_Mn': mn1, 'E_Mn2': mn2,
            'p_any_timeout': q, 'E_V': ev, 'Var_V': var_v,
            'E_O': 2.0 * r1 + ev, 'Var_O': 2.0 * var_r + var_v,
        }
        self._moments_cache = (key, result)
        return dict(result)

    def overhead_mean(self) -> float:
        """E[O] = 2·E[R] + a^n·E[M_n] + (1-a^n)·T (exact up to quadrature)."""
        return self.overhead_moments()['E_O']

    def overhead_variance(self) -> float:
        """Var[O] = 2·Var[R] + Var[V], V a Bernoulli mixture of M_n and T."""
        return self.overhead_moments()['Var_O']

    def mean(self) -> float:
        """
        Expected total service time: E[S_total] = E[S_base] + E[O]

        E[O] = 2·E[R] + a^n·E[max of n RTTs] + (1 − a^n)·T
        (prepare + vote + commit). For the defaults the timeout term
        (1 − 0.99³)·1.0 s ≈ 29.7 ms is about half of E[O].

        Note: an earlier version used E[R] instead of E[max of n RTTs] for
        the no-timeout vote phase, which under-estimated E[O] slightly.
        """
        return self.base_dist.mean() + self.overhead_mean()

    def variance(self) -> float:
        """
        Variance of total service time

        Var[S_total] = Var[S_base] + Var[O], with
        Var[O] = 2·Var[R] + Var[V] and
        Var[V] = a^n·E[M_n²] + q·T² − (a^n·E[M_n] + q·T)².

        The Bernoulli(q)×T timeout term dominates Var[O] whenever q > 0.
        (An earlier version returned only Var[S_base] + 3·RTT_std², which
        ignored the timeout term and under-estimated the variance by orders
        of magnitude for replica_availability < 1.)
        Assumes base processing and 2PC overhead are independent (they are
        drawn independently in sample()).
        """
        return self.base_dist.variance() + self.overhead_variance()

    def coefficient_of_variation(self) -> float:
        """CV² = Var[S_total] / E[S_total]²"""
        mean_val = self.mean()
        var_val = self.variance()

        if mean_val == 0:
            return float('inf')

        return var_val / (mean_val ** 2)

    def get_2pc_metrics(self) -> dict:
        """
        Get 2PC-specific metrics

        Returns:
            Dictionary with 2PC statistics
        """
        timeout_rate = self.timeout_count / self.total_samples if self.total_samples > 0 else 0.0

        return {
            'total_samples': self.total_samples,
            'timeout_count': self.timeout_count,
            'timeout_rate': timeout_rate,
            'avg_2pc_overhead': self.avg_2pc_overhead,
            'expected_overhead': self.mean() - self.base_dist.mean(),
            'overhead_percentage': (self.mean() - self.base_dist.mean()) / self.mean() * 100
            if self.mean() > 0 else 0,
        }

    def __repr__(self) -> str:
        return (
            f"TwoPhaseCommitService("
            f"base={self.base_dist.__class__.__name__}, "
            f"replicas={self.num_replicas}, "
            f"network_rtt={self.network_rtt_mean*1000:.1f}ms)"
        )
