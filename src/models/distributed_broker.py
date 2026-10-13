"""
Distributed Message Broker

Implements distributed storage with replication as described in
Li et al. (2015) for cloud message broker architecture.

Features:
- Multi-node distributed storage
- Configurable replication factor
- Consistent hashing for load distribution
- Fault tolerance
"""

import simpy
import random
import hashlib
import bisect
from typing import List, Optional, Dict
from .cloud_message import CloudMessage, MessageState
from .visibility_timeout import VisibilityTimeoutManager
from .message_ordering import MessageOrdering


class StorageNode:
    """
    Single storage node in distributed broker

    Each node has its own visibility timeout manager
    """

    def __init__(self, env: simpy.Environment, node_id: int,
                 ordering_mode: str = "out_of_order"):
        """
        Args:
            env: SimPy environment
            node_id: Unique node identifier
            ordering_mode: "in_order" or "out_of_order"
        """
        self.env = env
        self.node_id = node_id
        self.visibility_manager = VisibilityTimeoutManager(env)
        self.ordering = MessageOrdering(mode=ordering_mode)

        # Node-level metrics
        self.messages_stored = 0
        self.messages_received = 0

        # Node outage state (reads fail while the node is down)
        self.available = True

    def store_message(self, message: CloudMessage):
        """Store message in this node"""
        self.ordering.enqueue(message)
        self.visibility_manager.add_message(message)
        self.messages_stored += 1

    def receive_message(self) -> Optional[CloudMessage]:
        """Receive message from this node"""
        if not self.available:
            return None

        if self.ordering.mode == "in_order":
            # In-Order Delivery: HOL Blocking Logic
            # 1. Peek at the next EXPECTED message from ordering buffer
            next_msg = self.ordering.peek()

            if next_msg is None or not self.visibility_manager.is_visible(next_msg.id):
                # A message already released in sequence that timed out and is
                # visible again must still be redelivered (otherwise in-order
                # mode silently lost every failed message)
                for msg_id in self.visibility_manager.visible_messages:
                    if msg_id not in self.ordering.messages:
                        message = self.visibility_manager.receive_specific_message(msg_id)
                        self.messages_received += 1
                        return message

            if next_msg is None:
                # Buffer empty or next sequence not yet arrived
                return None

            # 2. Check if this specific message is available and visible
            if self.visibility_manager.is_visible(next_msg.id):
                # 3. Receive it
                message = self.visibility_manager.receive_specific_message(next_msg.id)
                if message:
                    # 4. Advance sequence in ordering buffer
                    self.ordering.dequeue()
                    self.messages_received += 1
                return message
            else:
                # HOL Blocking: Next expected message is not visible
                # (It might be processing, or not yet in visibility manager)
                # print(f"HOL Blocking: Waiting for {next_msg.id} (Queue Index: {self.ordering.queue_index})")
                return None
        else:
            # Out-of-Order: Just get any visible message
            message = self.visibility_manager.receive_message()
            if message:
                self.messages_received += 1
            return message

    def hide_replica(self, message_id: int) -> bool:
        """
        Hide this node's copy of a message that was received from another
        replica, so one logical message is delivered to one consumer at a time.
        """
        return self.visibility_manager.receive_specific_message(message_id) is not None

    def acknowledge_message(self, message_id: int) -> bool:
        """Acknowledge message on this node"""
        acked = self.visibility_manager.acknowledge_message(message_id)
        if acked:
            # The copy is gone for good; don't let it block in-order delivery
            self.ordering.remove(message_id)
        return acked

    def get_queue_depth(self) -> int:
        """Get number of visible messages"""
        return self.visibility_manager.get_queue_depth()


class ConsistentHashRing:
    """
    Consistent hashing for message distribution

    Based on distributed systems course material (Quiz 1)
    """

    def __init__(self, num_nodes: int, num_virtual_nodes: int = 150):
        """
        Args:
            num_nodes: Number of physical nodes
            num_virtual_nodes: Virtual nodes per physical node
        """
        self.num_nodes = num_nodes
        self.num_virtual_nodes = num_virtual_nodes

        # Build hash ring
        self.ring = {}
        self.sorted_keys = []
        self._build_ring()

    @staticmethod
    def _hash(key) -> int:
        """
        Stable 64-bit hash.

        Python's built-in hash() is unsuitable here: it is the identity for
        small ints (so every message ID mapped to the same ring position) and
        it is randomized per process for strings (so runs were not
        reproducible). MD5 gives a uniform, deterministic placement.
        """
        digest = hashlib.md5(str(key).encode()).digest()
        return int.from_bytes(digest[:8], "big")

    def _build_ring(self):
        """Build consistent hash ring with virtual nodes"""
        for node_id in range(self.num_nodes):
            for vnode in range(self.num_virtual_nodes):
                # Hash: node_id + virtual node number
                hash_key = self._hash(f"node_{node_id}_vnode_{vnode}")
                self.ring[hash_key] = node_id

        self.sorted_keys = sorted(self.ring.keys())

    def get_node(self, message_id: int) -> int:
        """
        Get primary node for message

        Args:
            message_id: Message identifier

        Returns:
            Node ID
        """
        if not self.sorted_keys:
            return 0

        # Hash message ID
        msg_hash = self._hash(f"msg_{message_id}")

        # Find first node clockwise on ring (wrap around to the first key)
        idx = bisect.bisect_left(self.sorted_keys, msg_hash)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]

    def get_replicas(self, primary_node: int, replication_factor: int) -> List[int]:
        """
        Get replica nodes for a message

        Args:
            primary_node: Primary node ID
            replication_factor: Number of replicas

        Returns:
            List of node IDs (including primary)
        """
        replicas = [primary_node]

        # Get next N-1 distinct nodes
        next_node = (primary_node + 1) % self.num_nodes
        while len(replicas) < min(replication_factor, self.num_nodes):
            if next_node not in replicas:
                replicas.append(next_node)
            next_node = (next_node + 1) % self.num_nodes

        return replicas


class DistributedBroker:
    """
    Distributed message broker with replication

    Models cloud message broker architecture from Li et al. (2015)
    with multiple storage nodes and configurable replication.
    """

    def __init__(self, env: simpy.Environment,
                 num_nodes: int = 3,
                 replication_factor: int = 3,
                 ordering_mode: str = "out_of_order",
                 node_mtbf: Optional[float] = None,
                 node_mttr: float = 10.0):
        """
        Args:
            env: SimPy environment
            num_nodes: Number of storage nodes
            replication_factor: Number of replicas per message
            ordering_mode: "in_order" or "out_of_order"
            node_mtbf: Mean time between node outages in seconds (exponential).
                None disables outages.
            node_mttr: Mean outage duration in seconds (exponential). While a
                node is down its copies cannot be received; acknowledgements
                are still applied (modelled as control-plane metadata).
        """
        self.env = env
        self.num_nodes = num_nodes
        self.replication_factor = min(replication_factor, num_nodes)
        self.ordering_mode = ordering_mode

        # Create storage nodes
        self.nodes: List[StorageNode] = []
        for i in range(num_nodes):
            node = StorageNode(env, node_id=i, ordering_mode=ordering_mode)
            self.nodes.append(node)

        # Consistent hashing for distribution
        self.hash_ring = ConsistentHashRing(num_nodes)

        # Broker-level metrics
        self.total_messages_published = 0
        self.total_messages_received = 0
        self.total_acks = 0
        self.total_outages = 0

        self.node_mttr = node_mttr
        if node_mtbf is not None:
            for node in self.nodes:
                env.process(self._outage_process(node, node_mtbf))

    def _outage_process(self, node: StorageNode, mtbf: float):
        """Alternate a node between up (Exp(mtbf)) and down (Exp(mttr))"""
        while True:
            yield self.env.timeout(random.expovariate(1.0 / mtbf))
            node.available = False
            self.total_outages += 1
            yield self.env.timeout(random.expovariate(1.0 / self.node_mttr))
            node.available = True

    def publish_message(self, message: CloudMessage):
        """
        Publish message to broker (replicate to N nodes)

        Args:
            message: Message to publish
        """
        # Get primary node using consistent hashing
        primary_node = self.hash_ring.get_node(message.id)

        # Get replica nodes
        replica_nodes = self.hash_ring.get_replicas(
            primary_node, self.replication_factor
        )

        # Store message on all replica nodes
        message.replication_nodes = replica_nodes
        for node_id in replica_nodes:
            # Create a copy for each replica
            message_copy = CloudMessage(
                id=message.id,
                content=message.content,
                arrival_time=message.arrival_time,
                visibility_timeout=message.visibility_timeout,
                max_receive_count=message.max_receive_count
            )
            message_copy.replication_nodes = replica_nodes
            # Preserve the producer's sequence number for in-order delivery
            message_copy.vector_clock = list(message.vector_clock)
            self.nodes[node_id].store_message(message_copy)

        self.total_messages_published += 1

    def receive_message(self, enable_hedging: bool = False) -> Optional[CloudMessage]:
        """
        Receive message from broker
        
        Args:
            enable_hedging: If True, query 2 nodes and take first response (Google Strategy)

        Returns:
            CloudMessage if available, None otherwise
        """
        if enable_hedging and self.num_nodes >= 2:
            # THE CURE: Request Hedging
            # "Send the same request to two different servers."
            
            # 1. Pick 2 random nodes
            nodes = random.sample(self.nodes, 2)
            
            # 2. Query both (Simulated)
            # In a real async system, we'd fire two futures.
            # Here, we check both and see which one "would" be faster or has data.
            # Simplified: Check both, if one has data, take it. 
            # If both have data, we assume the one with SHORTER queue is faster?
            # Or just take the first one that isn't empty.
            
            msg1 = nodes[0].receive_message()
            if msg1:
                return self._deliver(msg1, nodes[0])

            # If first failed/empty, try second immediately
            msg2 = nodes[1].receive_message()
            if msg2:
                return self._deliver(msg2, nodes[1])

            return None

        else:
            # Standard: Random node sampling (models SQS/Azure Queue behavior)
            sampled_node = random.choice(self.nodes)

            message = sampled_node.receive_message()
            if message:
                return self._deliver(message, sampled_node)

            return message

    def _deliver(self, message: CloudMessage, source: StorageNode) -> CloudMessage:
        """
        Hide the other replicas of a received message.

        Without this, each replica had its own visibility state and the same
        logical message could be handed to several consumers at once, so
        replication inflated measured throughput with duplicate processing.
        """
        for node_id in message.replication_nodes:
            if node_id != source.node_id:
                self.nodes[node_id].hide_replica(message.id)
        self.total_messages_received += 1
        return message

    def acknowledge_message(self, message: CloudMessage) -> bool:
        """
        Acknowledge message (delete from ALL replicas)

        Args:
            message: Message to acknowledge

        Returns:
            True if acknowledged successfully
        """
        # Acknowledge on all replica nodes
        success_count = 0
        for node_id in message.replication_nodes:
            if self.nodes[node_id].acknowledge_message(message.id):
                success_count += 1

        if success_count > 0:
            self.total_acks += 1

        # Success if acknowledged on majority of replicas
        return success_count > len(message.replication_nodes) // 2

    def get_total_queue_depth(self) -> int:
        """Get total messages across all nodes (with replication)"""
        return sum(node.get_queue_depth() for node in self.nodes)

    def get_unique_message_count(self) -> int:
        """
        Get count of unique messages (accounting for replication)

        Approximate: total / replication_factor
        """
        total = self.get_total_queue_depth()
        return total // self.replication_factor if self.replication_factor > 0 else total

    def get_node_metrics(self) -> List[Dict]:
        """Get metrics for each node"""
        metrics = []
        for node in self.nodes:
            node_metrics = {
                'node_id': node.node_id,
                'queue_depth': node.get_queue_depth(),
                'messages_stored': node.messages_stored,
                'messages_received': node.messages_received,
                **node.visibility_manager.get_metrics()
            }
            metrics.append(node_metrics)
        return metrics

    def get_broker_metrics(self) -> Dict:
        """Get broker-level metrics"""
        return {
            'num_nodes': self.num_nodes,
            'replication_factor': self.replication_factor,
            'total_messages_published': self.total_messages_published,
            'total_messages_received': self.total_messages_received,
            'total_acks': self.total_acks,
            'total_queue_depth': self.get_total_queue_depth(),
            'unique_message_count': self.get_unique_message_count(),
        }


def run_distributed_simulation(config) -> Dict:
    """
    Run Distributed Broker Simulation
    """
    env = simpy.Environment()
    
    # Map config ordering mode to broker ordering mode
    broker_ordering = "in_order" if config.ordering_mode in ["fifo", "strict_fifo", "causal"] else "out_of_order"
    
    # Create Broker
    broker = DistributedBroker(
        env, 
        num_nodes=config.num_nodes,
        replication_factor=config.replication_factor,
        ordering_mode=broker_ordering
    )
    
    # Metrics
    latencies = []
    
    def message_generator(env, broker, arrival_rate):
        """Generate messages"""
        msg_id = 0
        while True:
            yield env.timeout(random.expovariate(arrival_rate))
            msg_id += 1
            msg = CloudMessage(
                id=msg_id,
                content=f"msg_{msg_id}",
                arrival_time=env.now
            )
            broker.publish_message(msg)
            
    def message_consumer(env, broker, service_rate, enable_hedging):
        """Consume messages"""
        while True:
            # Service time (processing overhead)
            yield env.timeout(random.expovariate(service_rate))
            
            # Receive
            msg = broker.receive_message(enable_hedging=enable_hedging)
            
            if msg:
                # Calculate latency
                latency = env.now - msg.arrival_time
                latencies.append(latency)
                
                # Acknowledge
                broker.acknowledge_message(msg)
            else:
                # Backoff if empty
                yield env.timeout(0.01)

    # Start processes
    env.process(message_generator(env, broker, config.arrival_rate))
    
    # Start consumers (assume 1 consumer per node for simplicity, or just 1 global consumer)
    # For distributed broker, usually we have multiple consumers.
    # Let's spawn 5 consumers.
    for _ in range(5):
        env.process(message_consumer(env, broker, config.service_rate, config.enable_hedging))
        
    # Run simulation
    env.run(until=config.sim_duration)
    
    # Calculate metrics
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    
    return {
        "mean_latency": mean_latency,
        "total_messages": len(latencies),
        "broker_metrics": broker.get_broker_metrics()
    }
