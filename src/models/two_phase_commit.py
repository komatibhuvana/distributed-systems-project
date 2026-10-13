"""
Two-Phase Commit (2PC) Protocol

Based on Gray & Lamport (1978) and distributed systems course material (Midterm).

Implements atomic commit protocol for distributed transactions:
- Phase 1: Prepare/Vote
- Phase 2: Commit/Abort

Used for message acknowledgments in distributed message broker to ensure
all replicas are deleted atomically.
"""

import simpy
from enum import Enum
from typing import List, Dict, Optional, Set
from dataclasses import dataclass


class TransactionState(Enum):
    """Transaction states in 2PC protocol"""
    INIT = "init"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABORTED = "aborted"


class ParticipantState(Enum):
    """Participant states"""
    READY = "ready"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABORTED = "aborted"


@dataclass
class TwoPhaseMessage:
    """Messages exchanged in 2PC protocol"""
    msg_type: str  # "prepare", "vote_yes", "vote_no", "commit", "abort"
    transaction_id: int
    sender_id: int
    data: dict = None


class TwoPhaseCoordinator:
    """
    Coordinator for Two-Phase Commit protocol

    Manages distributed transactions across participants.
    """

    def __init__(self, env: simpy.Environment, coordinator_id: int):
        """
        Args:
            env: SimPy environment
            coordinator_id: ID of this coordinator
        """
        self.env = env
        self.coordinator_id = coordinator_id

        # Transaction tracking
        self.transaction_counter = 0
        self.transactions: Dict[int, TransactionState] = {}
        self.participants: Dict[int, List[int]] = {}  # transaction_id -> list of participant IDs
        self.votes: Dict[int, Dict[int, bool]] = {}  # transaction_id -> {participant_id -> vote}

        # Communication
        self.participant_channels: Dict[int, simpy.Store] = {}

        # Metrics
        self.total_transactions = 0
        self.committed_transactions = 0
        self.aborted_transactions = 0
        self.timeout_aborts = 0
        self.decision_latencies: Dict[int, float] = {}

    def register_participant(self, participant_id: int, channel: simpy.Store):
        """Register a participant node"""
        self.participant_channels[participant_id] = channel

    def begin_transaction(self, participant_ids: List[int], operation: str, data: dict,
                          timeout: float = 10.0) -> int:
        """
        Begin a new 2PC transaction

        Args:
            participant_ids: List of participant node IDs
            operation: Operation to perform (e.g., "delete_message")
            data: Operation data
            timeout: Transaction timeout (sec)

        Returns:
            Transaction ID
        """
        # Create new transaction
        self.transaction_counter += 1
        transaction_id = self.transaction_counter

        self.transactions[transaction_id] = TransactionState.INIT
        self.participants[transaction_id] = participant_ids
        self.votes[transaction_id] = {}

        self.total_transactions += 1

        # Start 2PC protocol
        self.env.process(self._run_two_phase_commit(
            transaction_id, participant_ids, operation, data, timeout
        ))

        return transaction_id

    def _run_two_phase_commit(self, transaction_id: int, participant_ids: List[int],
                               operation: str, data: dict, timeout: float):
        """
        Execute Two-Phase Commit protocol

        Phase 1: Prepare/Vote
        1. Coordinator sends PREPARE to all participants
        2. Participants respond with VOTE_YES or VOTE_NO
        3. Coordinator collects votes (with timeout)

        Phase 2: Commit/Abort
        4. If all votes YES → send COMMIT to all
           If any vote NO or timeout → send ABORT to all
        5. Participants execute decision
        """
        # ===== PHASE 1: PREPARE =====
        self.transactions[transaction_id] = TransactionState.PREPARING

        # Send PREPARE to all participants
        for participant_id in participant_ids:
            if participant_id in self.participant_channels:
                prepare_msg = TwoPhaseMessage(
                    msg_type="prepare",
                    transaction_id=transaction_id,
                    sender_id=self.coordinator_id,
                    data={'operation': operation, **data}
                )
                self.participant_channels[participant_id].put(prepare_msg)

        # Wait for votes (with timeout)
        start_time = self.env.now
        all_votes_received = False

        while self.env.now - start_time < timeout:
            # Check if all votes received
            if len(self.votes[transaction_id]) == len(participant_ids):
                all_votes_received = True
                break

            yield self.env.timeout(0.1)  # Poll interval

        # ===== PHASE 2: COMMIT or ABORT =====
        if all_votes_received and all(self.votes[transaction_id].values()):
            # All participants voted YES → COMMIT
            decision = "commit"
            self.transactions[transaction_id] = TransactionState.COMMITTED
            self.committed_transactions += 1

        else:
            # Timeout or any NO vote → ABORT
            decision = "abort"
            self.transactions[transaction_id] = TransactionState.ABORTED
            self.aborted_transactions += 1

            if not all_votes_received:
                self.timeout_aborts += 1

        # Instrumentation: time from PREPARE to decision. NOTE: this model has
        # no network delay and collects votes by polling every 0.1 s, so this
        # latency is a polling artifact (multiples of 0.1 s), not a network
        # measurement.
        self.decision_latencies[transaction_id] = self.env.now - start_time

        # Send decision to all participants
        for participant_id in participant_ids:
            if participant_id in self.participant_channels:
                decision_msg = TwoPhaseMessage(
                    msg_type=decision,
                    transaction_id=transaction_id,
                    sender_id=self.coordinator_id,
                    data=data
                )
                self.participant_channels[participant_id].put(decision_msg)

    def record_vote(self, transaction_id: int, participant_id: int, vote: bool):
        """Record vote from participant"""
        if transaction_id in self.votes:
            self.votes[transaction_id][participant_id] = vote

    def get_transaction_state(self, transaction_id: int) -> Optional[TransactionState]:
        """Get state of transaction"""
        return self.transactions.get(transaction_id)

    def get_metrics(self) -> Dict:
        """Get coordinator metrics"""
        return {
            'coordinator_id': self.coordinator_id,
            'total_transactions': self.total_transactions,
            'committed': self.committed_transactions,
            'aborted': self.aborted_transactions,
            'timeout_aborts': self.timeout_aborts,
            'commit_rate': self.committed_transactions / self.total_transactions
            if self.total_transactions > 0 else 0,
        }


class TwoPhaseParticipant:
    """
    Participant in Two-Phase Commit protocol

    Responds to coordinator's prepare and commit/abort messages.
    """

    def __init__(self, env: simpy.Environment, participant_id: int,
                 failure_rate: float = 0.0):
        """
        Args:
            env: SimPy environment
            participant_id: ID of this participant
            failure_rate: Probability of voting NO (for testing)
        """
        self.env = env
        self.participant_id = participant_id
        self.failure_rate = failure_rate

        # Transaction state
        self.prepared_transactions: Set[int] = set()
        self.voted_no_transactions: Set[int] = set()
        self.committed_transactions: Set[int] = set()
        self.aborted_transactions: Set[int] = set()

        # Communication
        self.inbox = simpy.Store(env)
        self.coordinator_channel: Optional[simpy.Store] = None

        # Metrics
        self.prepares_received = 0
        self.votes_yes = 0
        self.votes_no = 0
        self.commits_executed = 0
        self.aborts_executed = 0

    def set_coordinator_channel(self, channel: simpy.Store):
        """Set coordinator communication channel"""
        self.coordinator_channel = channel

    def start(self):
        """Start participant process"""
        self.env.process(self._run())

    def _run(self):
        """Main participant event loop"""
        while True:
            # Wait for message from coordinator
            msg = yield self.inbox.get()

            if msg.msg_type == "prepare":
                self._handle_prepare(msg)
            elif msg.msg_type == "commit":
                self._handle_commit(msg)
            elif msg.msg_type == "abort":
                self._handle_abort(msg)

    def _handle_prepare(self, msg: TwoPhaseMessage):
        """
        Handle PREPARE message from coordinator

        Participant must decide whether it can commit the transaction.
        """
        self.prepares_received += 1
        transaction_id = msg.transaction_id

        # Simulate decision (check if can commit)
        # In real system: check locks, resources, constraints, etc.
        import random
        can_commit = random.random() > self.failure_rate

        if can_commit:
            # Vote YES and prepare to commit
            self.prepared_transactions.add(transaction_id)
            vote = True
            self.votes_yes += 1
        else:
            # Vote NO - cannot commit (participant unilaterally aborts; it
            # still applies the coordinator's ABORT decision below)
            vote = False
            self.votes_no += 1
            self.voted_no_transactions.add(transaction_id)

        # Send vote to coordinator
        if self.coordinator_channel:
            vote_msg = TwoPhaseMessage(
                msg_type="vote_yes" if vote else "vote_no",
                transaction_id=transaction_id,
                sender_id=self.participant_id,
                data={'vote': vote}
            )
            self.coordinator_channel.put(vote_msg)

    def _handle_commit(self, msg: TwoPhaseMessage):
        """
        Handle COMMIT message from coordinator

        Participant commits the transaction.
        """
        transaction_id = msg.transaction_id

        if transaction_id in self.prepared_transactions:
            # Execute commit
            self.committed_transactions.add(transaction_id)
            self.prepared_transactions.discard(transaction_id)
            self.commits_executed += 1

            # In real system: actually perform the operation (e.g., delete message)

    def _handle_abort(self, msg: TwoPhaseMessage):
        """
        Handle ABORT message from coordinator

        Participant aborts the transaction and releases resources.
        """
        transaction_id = msg.transaction_id

        # Bug fix: participants that voted NO must also record the ABORT.
        # Previously only PREPARED (YES-voting) participants counted aborts,
        # so per-participant abort counts differed and the atomicity check in
        # experiments/two_phase_commit_validation.py reported False even
        # though every participant received the same decision.
        if (transaction_id in self.prepared_transactions or
                transaction_id in self.voted_no_transactions):
            # Abort transaction
            self.aborted_transactions.add(transaction_id)
            self.prepared_transactions.discard(transaction_id)
            self.voted_no_transactions.discard(transaction_id)
            self.aborts_executed += 1

            # In real system: release locks, rollback changes, etc.

    def get_metrics(self) -> Dict:
        """Get participant metrics"""
        return {
            'participant_id': self.participant_id,
            'prepares_received': self.prepares_received,
            'votes_yes': self.votes_yes,
            'votes_no': self.votes_no,
            'commits_executed': self.commits_executed,
            'aborts_executed': self.aborts_executed,
            'yes_vote_rate': self.votes_yes / self.prepares_received
            if self.prepares_received > 0 else 0,
        }


class TwoPhaseCommitCluster:
    """
    Complete 2PC cluster with coordinator and participants

    Manages distributed transactions across multiple nodes.
    """

    def __init__(self, env: simpy.Environment, num_participants: int = 3,
                 failure_rate: float = 0.0):
        """
        Args:
            env: SimPy environment
            num_participants: Number of participant nodes
            failure_rate: Probability of participant voting NO
        """
        self.env = env
        self.num_participants = num_participants

        # Create coordinator
        self.coordinator = TwoPhaseCoordinator(env, coordinator_id=0)

        # Create participants
        self.participants: List[TwoPhaseParticipant] = []
        for i in range(num_participants):
            participant = TwoPhaseParticipant(
                env, participant_id=i + 1, failure_rate=failure_rate
            )
            self.participants.append(participant)

        # Connect coordinator and participants
        coordinator_inbox = simpy.Store(env)

        for participant in self.participants:
            # Coordinator can send to participant
            self.coordinator.register_participant(participant.participant_id, participant.inbox)

            # Participant can send to coordinator
            participant.set_coordinator_channel(coordinator_inbox)

            # Start participant
            participant.start()

        # Process coordinator messages
        self.env.process(self._process_coordinator_messages(coordinator_inbox))

    def _process_coordinator_messages(self, inbox: simpy.Store):
        """Process messages to coordinator (votes from participants)"""
        while True:
            msg = yield inbox.get()

            if msg.msg_type in ["vote_yes", "vote_no"]:
                vote = msg.data.get('vote', False)
                self.coordinator.record_vote(msg.transaction_id, msg.sender_id, vote)

    def execute_transaction(self, operation: str, data: dict,
                            timeout: float = 10.0) -> int:
        """
        Execute a distributed transaction using 2PC

        Args:
            operation: Operation to perform
            data: Operation data
            timeout: Transaction timeout

        Returns:
            Transaction ID
        """
        participant_ids = [p.participant_id for p in self.participants]
        return self.coordinator.begin_transaction(
            participant_ids, operation, data, timeout
        )

    def get_metrics(self) -> Dict:
        """Get metrics for entire cluster"""
        return {
            'coordinator': self.coordinator.get_metrics(),
            'participants': [p.get_metrics() for p in self.participants],
        }
