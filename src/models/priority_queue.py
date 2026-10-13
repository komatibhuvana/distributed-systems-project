"""
Priority Queue Model (M/M/N with Priority Classes)

Implements multi-priority queueing system where higher priority
messages are served before lower priority messages.

Based on Kleinrock (1975) priority queueing theory.
"""

import simpy
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
from collections import defaultdict

from ..core.config import PriorityQueueConfig
from ..core.metrics import SimulationMetrics


@dataclass
class PriorityMessage:
    """Message with priority level"""
    id: int
    priority: int  # 1 = highest priority
    arrival_time: float
    start_service_time: float = 0.0
    completion_time: float = 0.0


@dataclass
class PriorityMetrics:
    """Per-priority class metrics"""
    priority: int
    wait_times: List[float] = field(default_factory=list)
    service_times: List[float] = field(default_factory=list)
    response_times: List[float] = field(default_factory=list)
    queue_lengths: List[int] = field(default_factory=list)
    arrivals: int = 0
    completions: int = 0

    def summary_statistics(self) -> Dict:
        """Calculate summary statistics for this priority class"""
        if not self.response_times:
            return {
                'priority': self.priority,
                'arrivals': self.arrivals,
                'completions': self.completions,
                'mean_wait': 0.0,
                'mean_service': 0.0,
                'mean_response': 0.0,
            }

        return {
            'priority': self.priority,
            'arrivals': self.arrivals,
            'completions': self.completions,
            'mean_wait': np.mean(self.wait_times),
            'std_wait': np.std(self.wait_times),
            'p95_wait': np.percentile(self.wait_times, 95),
            'p99_wait': np.percentile(self.wait_times, 99),
            'mean_service': np.mean(self.service_times),
            'mean_response': np.mean(self.response_times),
            'p50_response': np.percentile(self.response_times, 50),
            'p95_response': np.percentile(self.response_times, 95),
            'p99_response': np.percentile(self.response_times, 99),
            'mean_queue_length': np.mean(self.queue_lengths) if self.queue_lengths else 0,
        }


class PriorityQueueModel:
    """
    M/M/N queue with multiple priority classes

    Supports both preemptive and non-preemptive priority scheduling.

    Priority Discipline:
    - Non-preemptive: Higher priority messages jump queue but don't interrupt service
    - Preemptive: Higher priority can interrupt lower priority service (resume later)

    Based on:
    Kleinrock, L. (1975). Queueing Systems, Volume 2: Computer Applications.
    Wiley-Interscience.
    """

    def __init__(self, env: simpy.Environment, config: PriorityQueueConfig):
        self.env = env
        self.config = config

        # Thread pool (servers)
        if config.preemptive:
            # Preemptive requires PreemptiveResource
            self.servers = simpy.PreemptiveResource(env, capacity=config.num_threads)
        else:
            # Non-preemptive uses PriorityResource
            self.servers = simpy.PriorityResource(env, capacity=config.num_threads)

        # Per-priority metrics
        self.priority_metrics: Dict[int, PriorityMetrics] = {}
        for priority in range(1, config.num_priorities + 1):
            self.priority_metrics[priority] = PriorityMetrics(priority=priority)

        # Overall metrics
        self.total_arrivals = 0
        self.warmup_arrivals = 0

        # Queue monitoring
        self.queue_by_priority: Dict[int, List[PriorityMessage]] = defaultdict(list)

        # Random number generator
        if config.random_seed is not None:
            np.random.seed(config.random_seed)

    def message_generator(self, priority: int):
        """
        Generate messages for a specific priority class

        Args:
            priority: Priority class (1 = highest)
        """
        arrival_rate = self.config.priority_rates[priority - 1]
        interarrival_mean = 1.0 / arrival_rate

        message_id = 0
        while True:
            # Poisson arrival process
            interarrival_time = np.random.exponential(interarrival_mean)
            yield self.env.timeout(interarrival_time)

            message_id += 1
            msg = PriorityMessage(
                id=message_id,
                priority=priority,
                arrival_time=self.env.now
            )

            # Track arrival
            self.priority_metrics[priority].arrivals += 1
            self.total_arrivals += 1

            # Start processing
            self.env.process(self.process_message(msg))

    def process_message(self, msg: PriorityMessage):
        """
        Process a message through the queue

        Args:
            msg: Message to process
        """
        if self.config.preemptive:
            yield from self._process_preemptive_resume(msg)
            return

        arrival_time = self.env.now
        priority = msg.priority

        # Add to queue (for monitoring)
        self.queue_by_priority[priority].append(msg)

        # Request server with priority
        # Lower number = higher priority for SimPy
        if self.config.preemptive:
            # Preemptive: can interrupt lower priority
            request = self.servers.request(priority=priority, preempt=True)
        else:
            # Non-preemptive: priority queue only
            request = self.servers.request(priority=priority)

        # Wait for server
        try:
            yield request

            # Remove from queue
            if msg in self.queue_by_priority[priority]:
                self.queue_by_priority[priority].remove(msg)

            # Record queue length at arrival
            total_in_queue = sum(len(q) for q in self.queue_by_priority.values())
            self.priority_metrics[priority].queue_lengths.append(total_in_queue)

            # Start service
            msg.start_service_time = self.env.now
            wait_time = msg.start_service_time - arrival_time

            # Service time (exponential)
            service_time = np.random.exponential(1.0 / self.config.service_rate)

            # Serve message
            yield self.env.timeout(service_time)

            # Complete service
            msg.completion_time = self.env.now
            response_time = msg.completion_time - arrival_time

            # Record metrics (only after warmup)
            if self.env.now >= self.config.warmup_time:
                self.priority_metrics[priority].wait_times.append(wait_time)
                self.priority_metrics[priority].service_times.append(service_time)
                self.priority_metrics[priority].response_times.append(response_time)
                self.priority_metrics[priority].completions += 1

        except simpy.Interrupt as interrupt:
            # Preempted by higher priority
            # This message will be resumed later
            usage = self.env.now - msg.start_service_time
            # Remaining service time (simplified: start over)
            pass

        finally:
            # Release server
            self.servers.release(request)

    def _process_preemptive_resume(self, msg: PriorityMessage):
        """
        Preemptive-resume service.

        A higher-priority arrival interrupts the lowest-priority job in
        service; the interrupted job re-joins the queue (behind same-class
        jobs already waiting) and later resumes with its *remaining* work.
        Every job is eventually completed and recorded.

        Bug fixed here: the previous implementation caught simpy.Interrupt and
        silently discarded the preempted message, so low-priority statistics
        only contained jobs that were never preempted (survivor bias) and
        preempted work was lost.

        Recorded wait = all time spent not in service (initial queueing + time
        spent preempted), accumulated segment by segment.
        """
        arrival_time = self.env.now
        priority = msg.priority
        total_service = np.random.exponential(1.0 / self.config.service_rate)
        remaining = total_service
        first_start = None
        waited = 0.0
        queued_since = arrival_time

        self.queue_by_priority[priority].append(msg)

        while remaining > 0:
            request = self.servers.request(priority=priority, preempt=True)
            start = None
            try:
                yield request
                start = self.env.now
                waited += start - queued_since
                if first_start is None:
                    first_start = start
                    msg.start_service_time = start
                    if msg in self.queue_by_priority[priority]:
                        self.queue_by_priority[priority].remove(msg)
                    total_in_queue = sum(len(q) for q in self.queue_by_priority.values())
                    self.priority_metrics[priority].queue_lengths.append(total_in_queue)
                yield self.env.timeout(remaining)
                remaining = 0.0
            except simpy.Interrupt:
                if start is not None:
                    remaining = max(0.0, remaining - (self.env.now - start))
                    queued_since = self.env.now
            finally:
                if request.triggered:
                    self.servers.release(request)
                else:
                    request.cancel()

        msg.completion_time = self.env.now
        response_time = msg.completion_time - arrival_time
        wait_time = waited

        if self.env.now >= self.config.warmup_time:
            self.priority_metrics[priority].wait_times.append(wait_time)
            self.priority_metrics[priority].service_times.append(total_service)
            self.priority_metrics[priority].response_times.append(response_time)
            self.priority_metrics[priority].completions += 1

    def run(self) -> Dict[int, Dict]:
        """
        Run the priority queue simulation

        Returns:
            Dictionary mapping priority → metrics dict
        """
        # Start message generators for each priority class
        for priority in range(1, self.config.num_priorities + 1):
            self.env.process(self.message_generator(priority))

        # Run simulation
        self.env.run(until=self.config.sim_duration)

        # Collect results
        results = {}
        for priority, metrics in self.priority_metrics.items():
            results[priority] = metrics.summary_statistics()

        return results


def run_priority_queue_simulation(config: PriorityQueueConfig) -> Dict[int, Dict]:
    """
    Run a priority queue simulation

    Args:
        config: Priority queue configuration

    Returns:
        Dictionary mapping priority class → metrics

    Example:
        >>> config = PriorityQueueConfig(
        ...     arrival_rate=100,
        ...     num_threads=10,
        ...     service_rate=12,
        ...     num_priorities=3,
        ...     priority_rates=[30, 50, 20],
        ...     preemptive=False
        ... )
        >>> results = run_priority_queue_simulation(config)
        >>> print(f"Priority 1 mean wait: {results[1]['mean_wait']:.6f}")
    """
    env = simpy.Environment()
    model = PriorityQueueModel(env, config)
    results = model.run()

    # Print summary
    print("\nPriority Queue Simulation Complete:")
    print(f"  Model: M/M/{config.num_threads} with {config.num_priorities} priorities")
    print(f"  Scheduling: {'Preemptive' if config.preemptive else 'Non-preemptive'}")
    print(f"  Total messages processed:")
    for priority in range(1, config.num_priorities + 1):
        print(f"    Priority {priority}: {results[priority]['completions']} messages")

    return results


def compare_priority_classes(results: Dict[int, Dict]) -> None:
    """
    Compare performance across priority classes

    Args:
        results: Dictionary mapping priority → metrics
    """
    print("\n" + "="*70)
    print("Priority Class Comparison")
    print("="*70)

    print(f"\n{'Priority':>10} {'Arrivals':>10} {'Mean Wait':>12} {'Mean Response':>15} {'P99':>12}")
    print("-"*70)

    for priority in sorted(results.keys()):
        metrics = results[priority]
        print(f"{priority:>10} {metrics['arrivals']:>10} "
              f"{metrics['mean_wait']:>12.6f} {metrics['mean_response']:>15.6f} "
              f"{metrics.get('p99_response', 0):>12.6f}")

    print("="*70)
    print("\nObservations:")
    print("  - Lower priority number = higher priority")
    print("  - Higher priority should have lower wait times")
    print("  - Lower priority may experience 'starvation' under high load")
