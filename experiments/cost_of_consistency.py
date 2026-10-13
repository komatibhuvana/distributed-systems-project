import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import simpy
import random
import numpy as np
import pandas as pd
from src.core.config import MMNConfig
from src.core.distributions import ParetoService
from src.models.cloud_message import CloudMessage
from src.models.distributed_broker import DistributedBroker

def run_ordering_experiment(ordering_mode: str, arrival_rate=80, service_rate=100, duration=500,
                            seed=42, warmup=50):
    # The broker and this script both use the stdlib `random` module
    random.seed(seed)
    np.random.seed(seed)
    env = simpy.Environment()
    
    # Setup Broker
    broker = DistributedBroker(env, num_nodes=1, replication_factor=1, ordering_mode=ordering_mode)
    
    # Metrics
    latencies = []
    
    # Service Process (Consumer)
    def consumer(env, broker):
        while True:
            msg = broker.receive_message()
            if msg:
                # Simulate processing time (Pareto - Heavy Tail)
                # Using Pareto to exacerbate HOL blocking effects
                # Alpha 1.5 = Infinite Variance = Massive Stragglers
                service_time = random.paretovariate(1.5) * (1.0/service_rate) 
                yield env.timeout(service_time)
                
                broker.acknowledge_message(msg)
                
                # Record latency (after warmup)
                if msg.arrival_time >= warmup:
                    latencies.append(env.now - msg.arrival_time)
            else:
                # Wait if no message available (or blocked)
                yield env.timeout(0.001) # Poll interval

    # Arrival Process (Producer) with Network Jitter
    def producer(env, broker):
        msg_id = 0
        while True:
            interarrival = random.expovariate(arrival_rate)
            yield env.timeout(interarrival)
            
            # Create message
            msg = CloudMessage(
                id=msg_id,
                content=f"msg-{msg_id}",
                arrival_time=env.now
            )
            # Set sequence number for In-Order delivery
            msg.vector_clock = [msg_id]
            
            # Simulate Network Jitter (The "Slow Path" vs "Fast Path")
            # Some messages get delayed, causing out-of-order arrival
            delay = random.uniform(0.01, 0.1) # 10ms to 100ms jitter
            env.process(delayed_publish(env, broker, msg, delay))
            
            msg_id += 1

    def delayed_publish(env, broker, msg, delay):
        yield env.timeout(delay)
        broker.publish_message(msg)

    # Start processes
    env.process(producer(env, broker))
    # Multiple consumers to create out-of-order processing opportunities
    for _ in range(5): 
        env.process(consumer(env, broker))
        
    # Run simulation
    env.run(until=duration)
    
    return latencies

def _ci95(values):
    from scipy import stats
    values = np.asarray(values, dtype=float)
    half = stats.t.ppf(0.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values))
    return float(values.mean()), float(half)


if __name__ == "__main__":
    print("Running 'Cost of Consistency' Experiment...")
    print("-" * 50)

    # 5 consumers, Pareto(1.5) service with mean 1.5/(0.5*100) = 0.03 s
    # -> capacity ~166.7 msg/s; sweep offered load up to rho ~0.9
    seeds = list(range(1, 11))
    rows, runs = [], []
    for arrival_rate in [40, 80, 120, 150]:
        for mode, label in [("out_of_order", "Out-of-Order"), ("in_order", "In-Order")]:
            means, p99s = [], []
            for seed in seeds:
                lat = run_ordering_experiment(mode, arrival_rate=arrival_rate, seed=seed)
                means.append(np.mean(lat) * 1000)
                p99s.append(np.percentile(lat, 99) * 1000)
                runs.append({'arrival_rate': arrival_rate, 'Mode': label, 'seed': seed,
                             'Mean_Latency_ms': means[-1], 'P99_Latency_ms': p99s[-1]})
            m, mh = _ci95(means)
            p, ph = _ci95(p99s)
            rows.append({'arrival_rate': arrival_rate, 'Mode': label,
                         'Mean_Latency_ms': m, 'Mean_Latency_ms_ci95': mh,
                         'P99_Latency_ms': p, 'P99_Latency_ms_ci95': ph,
                         'replications': len(seeds)})
            print(f"lambda={arrival_rate:>4} {label:<13} mean {m:8.2f} +/- {mh:.2f} ms  "
                  f"P99 {p:8.2f} +/- {ph:.2f} ms")

    results = pd.DataFrame(rows)
    results.to_csv('experiments/ordering_mode_results.csv', index=False)
    pd.DataFrame(runs).to_csv('experiments/ordering_mode_runs.csv', index=False)
    print("Results saved to experiments/ordering_mode_results.csv")
