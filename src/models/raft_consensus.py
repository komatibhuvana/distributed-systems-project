"""
Raft Consensus Protocol Implementation

Based on Ongaro & Ousterhout (2014) "In Search of an Understandable Consensus Algorithm"
and distributed systems course material (Midterm content).

Implements:
- Leader election with randomized timeouts
- Log replication for message operations
- Commit protocol requiring majority agreement
- Safety guarantees (election safety, leader append-only, etc.)
"""

import simpy
import random
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


class RaftState(Enum):
    """Raft node states"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class LogEntry:
    """
    Replicated log entry

    Each entry contains:
    - term: Election term when entry was created
    - operation: Message operation (publish, ack, delete)
    - data: Operation data (message ID, content, etc.)
    """
    term: int
    operation: str
    data: Dict[str, Any]
    index: int = 0


@dataclass
class RaftMessage:
    """Messages exchanged between Raft nodes"""
    msg_type: str  # "vote_request", "vote_response", "append_entries", "append_response"
    term: int
    sender_id: int
    data: Dict[str, Any] = field(default_factory=dict)


class RaftNode:
    """
    Single Raft consensus node

    Implements Raft consensus algorithm with:
    - Leader election
    - Log replication
    - Commit protocol
    """

    def __init__(self,
                 env: simpy.Environment,
                 node_id: int,
                 cluster_size: int,
                 election_timeout_min: float = 10.0,
                 election_timeout_max: float = 20.0,
                 heartbeat_interval: float = 5.0,
                 network_delay: float = 0.0,
                 network_jitter: float = 0.0,
                 replicate_log_entries: bool = False):
        """
        Args:
            env: SimPy environment
            node_id: Unique node ID
            cluster_size: Total number of nodes in cluster
            election_timeout_min: Minimum election timeout (sec)
            election_timeout_max: Maximum election timeout (sec)
            heartbeat_interval: Leader heartbeat interval (sec)
            network_delay: Fixed one-way message delay (sec). Default 0 =
                instantaneous delivery (original behaviour).
            network_jitter: Extra one-way delay ~ U[0, jitter] (sec), drawn
                independently per message with the `random` module. Default 0.
            replicate_log_entries: If True, AppendEntries actually carries log
                entries (sent immediately on append and on every heartbeat),
                followers apply Raft's conflict rule, and match_index follows
                the Raft paper. Default False keeps the original behaviour, in
                which AppendEntries never carries entries, so appended entries
                are NEVER replicated or committed (a known limitation of the
                original model).
        """
        self.env = env
        self.node_id = node_id
        self.cluster_size = cluster_size
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval
        self.network_delay = network_delay
        self.network_jitter = network_jitter
        self.replicate_log_entries = replicate_log_entries

        # Failure injection (see crash()/recover())
        self.crashed = False

        # Instrumentation (pure bookkeeping; does not affect protocol)
        self.candidacy_history: List[tuple] = []   # (time, term) per election started
        self.leadership_history: List[tuple] = []  # (time, term) per election won
        self.entry_append_time: Dict[int, float] = {}  # log index -> append time (as leader)
        self.entry_commit_time: Dict[int, float] = {}  # log index -> time leader committed it
        self._commit_waiters: Dict[int, simpy.Event] = {}
        self.messages_sent = 0

        # Raft persistent state (all servers)
        self.current_term = 0
        self.voted_for: Optional[int] = None
        self.log: List[LogEntry] = []

        # Raft volatile state (all servers)
        self.commit_index = 0
        self.last_applied = 0

        # Raft volatile state (leaders only)
        self.next_index: Dict[int, int] = {}  # For each server, index of next log entry to send
        self.match_index: Dict[int, int] = {}  # For each server, highest log entry known to be replicated

        # Node state
        self.state = RaftState.FOLLOWER
        self.leader_id: Optional[int] = None

        # Election state
        self.votes_received: Dict[int, bool] = {}  # Track votes for current term

        # Communication
        self.inbox = simpy.Store(env)
        self.outboxes: Dict[int, simpy.Store] = {}  # Set by cluster

        # Timers
        self.election_timer = None
        self.heartbeat_timer = None

        # Metrics
        self.elections_started = 0
        self.elections_won = 0
        self.heartbeats_sent = 0
        self.log_entries_replicated = 0

    def start(self):
        """Start Raft node processes"""
        self.env.process(self._run())
        self._reset_election_timer()

    def _run(self):
        """Main Raft node event loop"""
        while True:
            # Process incoming messages
            msg = yield self.inbox.get()

            if self.crashed:
                # Crashed nodes silently drop everything they receive
                continue

            if msg.msg_type == "vote_request":
                self._handle_vote_request(msg)
            elif msg.msg_type == "vote_response":
                self._handle_vote_response(msg)
            elif msg.msg_type == "append_entries":
                self._handle_append_entries(msg)
            elif msg.msg_type == "append_response":
                self._handle_append_response(msg)

    def _send(self, dest: int, msg: RaftMessage):
        """Send a message to node `dest` (instant if no delay configured)."""
        if self.crashed or dest not in self.outboxes:
            return
        self.messages_sent += 1
        if self.network_delay == 0.0 and self.network_jitter == 0.0:
            # Original behaviour: direct, instantaneous delivery
            self.outboxes[dest].put(msg)
            return
        delay = self.network_delay
        if self.network_jitter > 0.0:
            delay += random.uniform(0.0, self.network_jitter)
        self.env.process(self._deliver_later(self.outboxes[dest], msg, delay))

    def _deliver_later(self, store: simpy.Store, msg: RaftMessage, delay: float):
        yield self.env.timeout(delay)
        store.put(msg)

    def _reset_election_timer(self, interrupt_current=True):
        """Reset election timeout with randomized duration"""
        if self.election_timer is not None and interrupt_current:
            try:
                self.election_timer.interrupt()
            except RuntimeError:
                # Already interrupted or process can't interrupt itself
                pass

        timeout = random.uniform(self.election_timeout_min, self.election_timeout_max)
        self.election_timer = self.env.process(self._election_timeout(timeout))

    def _election_timeout(self, timeout: float):
        """Election timeout - triggers leader election"""
        try:
            yield self.env.timeout(timeout)

            # Timeout occurred - start election
            if self.state != RaftState.LEADER:
                self._start_election(from_timeout=True)

        except simpy.Interrupt:
            # Timer was reset
            pass

    def _start_election(self, from_timeout=False):
        """Start leader election process"""
        # Become candidate
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.elections_started += 1
        self.candidacy_history.append((self.env.now, self.current_term))

        # Reset and track votes (vote for self)
        self.votes_received = {self.node_id: True}

        # Single-node cluster: own vote is already a majority
        if self.cluster_size == 1:
            self._become_leader()
            return

        # Request votes from all other nodes
        for node_id in range(self.cluster_size):
            if node_id != self.node_id and node_id in self.outboxes:
                vote_request = RaftMessage(
                    msg_type="vote_request",
                    term=self.current_term,
                    sender_id=self.node_id,
                    data={
                        'last_log_index': len(self.log),
                        'last_log_term': self.log[-1].term if self.log else 0
                    }
                )
                self._send(node_id, vote_request)

        # Reset election timer (don't interrupt if called from timeout)
        self._reset_election_timer(interrupt_current=not from_timeout)

    def _handle_vote_request(self, msg: RaftMessage):
        """Handle RequestVote RPC"""
        # Update term if behind
        if msg.term > self.current_term:
            self._step_down(msg.term)

        grant_vote = False

        if msg.term == self.current_term:
            # Grant vote if haven't voted or already voted for this candidate
            if self.voted_for is None or self.voted_for == msg.sender_id:
                # Check log is up-to-date
                last_log_index = len(self.log)
                last_log_term = self.log[-1].term if self.log else 0

                candidate_log_ok = (
                    msg.data['last_log_term'] > last_log_term or
                    (msg.data['last_log_term'] == last_log_term and
                     msg.data['last_log_index'] >= last_log_index)
                )

                if candidate_log_ok:
                    self.voted_for = msg.sender_id
                    grant_vote = True
                    self._reset_election_timer()

        # Send vote response
        if msg.sender_id in self.outboxes:
            response = RaftMessage(
                msg_type="vote_response",
                term=self.current_term,
                sender_id=self.node_id,
                data={'vote_granted': grant_vote}
            )
            self._send(msg.sender_id, response)

    def _handle_vote_response(self, msg: RaftMessage):
        """Handle vote response from another node"""
        if self.state != RaftState.CANDIDATE:
            return

        if msg.term > self.current_term:
            self._step_down(msg.term)
            return

        if msg.term == self.current_term and msg.data.get('vote_granted'):
            # Track vote
            self.votes_received[msg.sender_id] = True

            # Count votes
            votes = sum(1 for granted in self.votes_received.values() if granted)

            # Check if won election (majority)
            if votes > self.cluster_size // 2:
                self._become_leader()

    def _become_leader(self):
        """Transition to leader state"""
        self.state = RaftState.LEADER
        self.leader_id = self.node_id
        self.elections_won += 1
        self.leadership_history.append((self.env.now, self.current_term))

        # Initialize leader state
        for node_id in range(self.cluster_size):
            if node_id != self.node_id:
                self.next_index[node_id] = len(self.log) + 1
                self.match_index[node_id] = 0

        # Cancel election timer
        if self.election_timer is not None:
            try:
                self.election_timer.interrupt()
            except RuntimeError:
                # Timer already finished, or we are running inside it
                pass

        # Start heartbeat timer
        self.heartbeat_timer = self.env.process(self._send_heartbeats())

    def _send_append_entries(self, node_id: int):
        """Send one AppendEntries RPC to `node_id` (heartbeat if no entries)."""
        prev_log_index = self.next_index.get(node_id, 1) - 1
        prev_log_term = self.log[prev_log_index - 1].term if prev_log_index > 0 and prev_log_index <= len(self.log) else 0

        if self.replicate_log_entries:
            entries = list(self.log[prev_log_index:])
        else:
            entries = []  # Original behaviour: heartbeat - no entries

        append_msg = RaftMessage(
            msg_type="append_entries",
            term=self.current_term,
            sender_id=self.node_id,
            data={
                'prev_log_index': prev_log_index,
                'prev_log_term': prev_log_term,
                'entries': entries,
                'leader_commit': self.commit_index
            }
        )
        self._send(node_id, append_msg)

    def _send_heartbeats(self):
        """Send periodic heartbeats (AppendEntries)"""
        try:
            while self.state == RaftState.LEADER and not self.crashed:
                # Send AppendEntries to all followers
                for node_id in range(self.cluster_size):
                    if node_id != self.node_id and node_id in self.outboxes:
                        self._send_append_entries(node_id)

                self.heartbeats_sent += 1
                yield self.env.timeout(self.heartbeat_interval)
        except simpy.Interrupt:
            # Bug fix: _step_down() interrupts this process; previously the
            # Interrupt was uncaught and would crash env.run().
            pass

    def _handle_append_entries(self, msg: RaftMessage):
        """Handle AppendEntries RPC (heartbeat or log replication)"""
        # Update term if behind
        if msg.term > self.current_term:
            self._step_down(msg.term)

        success = False

        if msg.term == self.current_term:
            # Recognize leader
            if self.state != RaftState.FOLLOWER:
                self._step_down(msg.term)

            self.leader_id = msg.sender_id
            self._reset_election_timer()

            # Check log consistency
            prev_log_index = msg.data['prev_log_index']
            prev_log_term = msg.data['prev_log_term']

            log_ok = (
                prev_log_index == 0 or
                (prev_log_index <= len(self.log) and
                 self.log[prev_log_index - 1].term == prev_log_term)
            )

            if log_ok:
                success = True

                # Append new entries
                entries = msg.data.get('entries', [])
                if self.replicate_log_entries:
                    # Raft §5.3: delete an existing entry only if it conflicts
                    # (same index, different term); append entries not yet in
                    # the log. Safe under message reordering.
                    for offset, entry in enumerate(entries):
                        idx = prev_log_index + offset + 1  # 1-based
                        if idx <= len(self.log):
                            if self.log[idx - 1].term != entry.term:
                                self.log = self.log[:idx - 1]
                                self.log.append(entry)
                                self.log_entries_replicated += 1
                        else:
                            self.log.append(entry)
                            self.log_entries_replicated += 1
                    last_new_index = prev_log_index + len(entries)
                elif entries:
                    # Delete conflicting entries and append new ones
                    self.log = self.log[:prev_log_index]
                    self.log.extend(entries)
                    self.log_entries_replicated += len(entries)

                # Update commit index
                leader_commit = msg.data['leader_commit']
                if leader_commit > self.commit_index:
                    if self.replicate_log_entries:
                        self.commit_index = max(self.commit_index,
                                                min(leader_commit, last_new_index))
                    else:
                        self.commit_index = min(leader_commit, len(self.log))

        # Send response
        if msg.sender_id in self.outboxes:
            if self.replicate_log_entries:
                match = (msg.data['prev_log_index'] + len(msg.data.get('entries', []))
                         if success else 0)
            else:
                match = len(self.log) if success else 0
            response = RaftMessage(
                msg_type="append_response",
                term=self.current_term,
                sender_id=self.node_id,
                data={
                    'success': success,
                    'match_index': match
                }
            )
            self._send(msg.sender_id, response)

    def _handle_append_response(self, msg: RaftMessage):
        """Handle AppendEntries response"""
        if self.state != RaftState.LEADER:
            return

        if msg.term > self.current_term:
            self._step_down(msg.term)
            return

        if self.replicate_log_entries and msg.term < self.current_term:
            # Stale response from an earlier term (only possible with delays)
            return

        if msg.data.get('success'):
            # Update next_index and match_index
            if self.replicate_log_entries:
                # Responses may be reordered: never move match_index backwards
                new_match = max(self.match_index.get(msg.sender_id, 0),
                                msg.data['match_index'])
                self.match_index[msg.sender_id] = new_match
                self.next_index[msg.sender_id] = new_match + 1
            else:
                self.match_index[msg.sender_id] = msg.data['match_index']
                self.next_index[msg.sender_id] = msg.data['match_index'] + 1

            # Update commit_index if majority replicated
            self._advance_commit_index()

        else:
            # Decrement next_index and retry
            self.next_index[msg.sender_id] = max(1, self.next_index[msg.sender_id] - 1)
            if self.replicate_log_entries:
                self._send_append_entries(msg.sender_id)

    def _advance_commit_index(self):
        """Leader: advance commit_index to highest current-term entry on a majority."""
        old_commit = self.commit_index
        for n in range(self.commit_index + 1, len(self.log) + 1):
            if self.log[n - 1].term == self.current_term:
                count = 1  # Self
                for node_id in range(self.cluster_size):
                    if node_id != self.node_id and self.match_index.get(node_id, 0) >= n:
                        count += 1

                if count > self.cluster_size // 2:
                    self.commit_index = n

        # Instrumentation: record commit time of newly committed entries
        for n in range(old_commit + 1, self.commit_index + 1):
            if n not in self.entry_commit_time:
                self.entry_commit_time[n] = self.env.now
            waiter = self._commit_waiters.pop(n, None)
            if waiter is not None and not waiter.triggered:
                waiter.succeed(self.env.now)

    def _step_down(self, new_term: int):
        """Step down to follower state"""
        self.current_term = new_term
        self.state = RaftState.FOLLOWER
        self.voted_for = None
        self.leader_id = None

        # Cancel timers
        if self.heartbeat_timer is not None:
            try:
                self.heartbeat_timer.interrupt()
            except RuntimeError:
                pass  # heartbeat process already finished
            self.heartbeat_timer = None

        self._reset_election_timer()

    def append_log_entry(self, operation: str, data: Dict[str, Any]) -> bool:
        """
        Append new log entry (only leader)

        Args:
            operation: Operation type (e.g., "publish", "ack", "delete")
            data: Operation data

        Returns:
            True if successfully appended (only if leader)
        """
        if self.state != RaftState.LEADER:
            return False

        # Create log entry
        entry = LogEntry(
            term=self.current_term,
            operation=operation,
            data=data,
            index=len(self.log) + 1
        )

        self.log.append(entry)
        self.entry_append_time[entry.index] = self.env.now

        if self.replicate_log_entries:
            # Replicate immediately rather than waiting for the next heartbeat
            for node_id in range(self.cluster_size):
                if node_id != self.node_id and node_id in self.outboxes:
                    self._send_append_entries(node_id)
            self._advance_commit_index()  # commits at once if cluster_size == 1
        return True

    def append_and_wait(self, operation: str, data: Dict[str, Any]) -> Optional[simpy.Event]:
        """
        Append an entry (leader only) and return a SimPy event that fires when
        the leader marks it committed (value = commit time). Returns None if
        this node is not the leader. Requires replicate_log_entries=True,
        otherwise the entry never commits (for clusters larger than 1).

        Caveat: if leadership is lost before the entry commits on this node,
        the event never fires (no client retry logic is modelled).
        """
        if not self.append_log_entry(operation, data):
            return None
        index = len(self.log)
        event = self.env.event()
        if index <= self.commit_index:
            event.succeed(self.entry_commit_time.get(index, self.env.now))
        else:
            self._commit_waiters[index] = event
        return event

    # ------------------------------------------------------------------
    # Failure injection
    # ------------------------------------------------------------------
    def crash(self):
        """
        Crash-stop this node: drop all inbound/outbound messages and stop
        timers. Persistent state (term, voted_for, log) survives; volatile
        leader state is lost.
        """
        self.crashed = True
        self.state = RaftState.FOLLOWER
        self.leader_id = None
        for proc in (self.election_timer, self.heartbeat_timer):
            if proc is not None:
                try:
                    proc.interrupt()
                except RuntimeError:
                    pass
        self.heartbeat_timer = None
        self.election_timer = None

    def recover(self):
        """Restart a crashed node as a follower with a fresh election timer."""
        if not self.crashed:
            return
        self.crashed = False
        self.state = RaftState.FOLLOWER
        self.election_timer = None
        self._reset_election_timer(interrupt_current=False)

    def is_committed(self, log_index: int) -> bool:
        """Check if log entry is committed"""
        return log_index <= self.commit_index

    def get_metrics(self) -> Dict:
        """Get Raft node metrics"""
        return {
            'node_id': self.node_id,
            'state': self.state.value,
            'term': self.current_term,
            'leader_id': self.leader_id,
            'log_size': len(self.log),
            'commit_index': self.commit_index,
            'elections_started': self.elections_started,
            'elections_won': self.elections_won,
            'heartbeats_sent': self.heartbeats_sent,
            'log_entries_replicated': self.log_entries_replicated,
        }


class RaftCluster:
    """
    Raft consensus cluster manager

    Creates and manages a cluster of Raft nodes with simulated network
    """

    def __init__(self,
                 env: simpy.Environment,
                 num_nodes: int = 3,
                 election_timeout_min: float = 10.0,
                 election_timeout_max: float = 20.0,
                 heartbeat_interval: float = 5.0,
                 network_delay: float = 0.0,
                 network_jitter: float = 0.0,
                 replicate_log_entries: bool = False):
        """
        Args:
            env: SimPy environment
            num_nodes: Number of nodes in cluster (odd number recommended)
            election_timeout_min: Minimum election timeout
            election_timeout_max: Maximum election timeout
            heartbeat_interval: Leader heartbeat interval
            network_delay: Fixed one-way message delay (default 0 = instant)
            network_jitter: Extra one-way delay ~ U[0, jitter] (default 0)
            replicate_log_entries: Actually replicate log entries (default
                False = original behaviour; see RaftNode)

        Note: defaults (10–20 s election timeout, 5 s heartbeat, zero network
        delay) are ~50x slower than typical Raft deployments (150–300 ms
        timeouts, ~50 ms heartbeats) and have instantaneous messaging.
        """
        self.env = env
        self.num_nodes = num_nodes

        # Create Raft nodes
        self.nodes: List[RaftNode] = []
        for i in range(num_nodes):
            node = RaftNode(
                env=env,
                node_id=i,
                cluster_size=num_nodes,
                election_timeout_min=election_timeout_min,
                election_timeout_max=election_timeout_max,
                heartbeat_interval=heartbeat_interval,
                network_delay=network_delay,
                network_jitter=network_jitter,
                replicate_log_entries=replicate_log_entries
            )
            self.nodes.append(node)

        # Connect nodes (simulated network)
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i != j:
                    self.nodes[i].outboxes[j] = self.nodes[j].inbox

        # Start all nodes
        for node in self.nodes:
            node.start()

    def get_leader(self) -> Optional[RaftNode]:
        """Get current leader node"""
        for node in self.nodes:
            if node.state == RaftState.LEADER:
                return node
        return None

    def get_cluster_metrics(self) -> List[Dict]:
        """Get metrics for all nodes"""
        return [node.get_metrics() for node in self.nodes]

    def get_current_leader(self) -> Optional[RaftNode]:
        """Non-crashed leader with the highest term (robust to stale leaders)."""
        leaders = [n for n in self.nodes if n.state == RaftState.LEADER and not n.crashed]
        if not leaders:
            return None
        return max(leaders, key=lambda n: n.current_term)

    def leadership_events(self) -> List[tuple]:
        """All (time, term, node_id) election wins, sorted by time."""
        events = [(t, term, n.node_id) for n in self.nodes for (t, term) in n.leadership_history]
        return sorted(events)

    def candidacy_events(self) -> List[tuple]:
        """All (time, term, node_id) elections started, sorted by time."""
        events = [(t, term, n.node_id) for n in self.nodes for (t, term) in n.candidacy_history]
        return sorted(events)

    def election_safety_violations(self) -> int:
        """Number of terms with more than one leader (Raft requires 0)."""
        from collections import Counter
        counts = Counter(term for (_, term, _) in self.leadership_events())
        return sum(1 for c in counts.values() if c > 1)
