"""
Message Ordering Modes

Implements Section 3 of Li et al. (2015) - Message Consistency Options:
1. In-order delivery (FIFO)
2. Out-of-order delivery (random sampling for performance)
"""

from collections import OrderedDict
from typing import Optional, List
import random
from .cloud_message import CloudMessage, MessageState


class MessageOrdering:
    """
    Message ordering and consistency manager

    Based on Li et al. (2015) Section 3: Message Consistency

    CRITICAL DIFFERENCE (Algorithm 4, Fig. 10, p.13):
    - In-order: Uses queue_index, consumer WAITS for specific message ID
    - Out-of-order: Random sampling, takes ANY available message (faster)
    """

    def __init__(self, mode: str = "out_of_order"):
        """
        Args:
            mode: Either "in_order" (FIFO) or "out_of_order" (random sampling)
        """
        if mode not in ["in_order", "out_of_order"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'in_order' or 'out_of_order'")

        self.mode = mode
        self.messages: OrderedDict[int, CloudMessage] = OrderedDict()
        self.sequence_number = 0

        # Queue index for in-order mode (Algorithm 4, p.13)
        # Consumer waits for message with sequence == queue_index
        self.queue_index = 0

        # Sequence numbers removed without being delivered by this buffer
        # (e.g. a replica acknowledged via another node); skipped by queue_index
        self._removed_sequences = set()

    def remove(self, message_id: int):
        """Drop a message from the buffer without delivering it"""
        message = self.messages.pop(message_id, None)
        if message is not None and self.mode == "in_order" and message.vector_clock:
            seq = message.vector_clock[0]
            if seq >= self.queue_index:
                self._removed_sequences.add(seq)
                self._skip_removed()

    def _skip_removed(self):
        while self.queue_index in self._removed_sequences:
            self._removed_sequences.discard(self.queue_index)
            self.queue_index += 1

    def enqueue(self, message: CloudMessage):
        """
        Add message with ordering guarantee

        Args:
            message: Message to enqueue
        """
        if self.mode == "in_order":
            # Maintain strict FIFO order
            # If message already has a sequence number (from producer), use it
            # Otherwise, assign one (local ordering)
            if not hasattr(message, 'vector_clock') or not message.vector_clock:
                message.vector_clock = [self.sequence_number]
                self.sequence_number += 1
            
            self.messages[message.id] = message
        else:
            # Out-of-order: no sequence guarantee
            self.messages[message.id] = message

    def dequeue(self) -> Optional[CloudMessage]:
        """
        Retrieve message based on consistency mode

        CRITICAL DIFFERENCE (Paper Algorithm 4, Fig. 10, p.13):
        - In-order: Wait for message with sequence == queue_index (causes delays!)
        - Out-of-order: Take ANY visible message (no waiting, faster)

        This is WHY out-of-order is ~50% faster in the paper's results.

        Returns:
            CloudMessage if available, None otherwise
        """
        if not self.messages:
            return None

        if self.mode == "in_order":
            # In-order delivery (Algorithm 4, p.13):
            # Consumer MUST wait for message with sequence == queue_index
            # This creates delays when messages arrive out of order

            # Search for message with the SPECIFIC queue_index
            target_message = None
            for message in self.messages.values():
                if hasattr(message, 'vector_clock') and len(message.vector_clock) > 0:
                    if message.vector_clock[0] == self.queue_index:
                        target_message = message
                        break

            if target_message is None:
                # Required message not yet arrived - consumer must WAIT
                # This is the bottleneck that makes in-order slower!
                return None

            # Found the indexed message - deliver it and advance index
            self.messages.pop(target_message.id)
            self.queue_index += 1
            self._skip_removed()
            return target_message

        else:
            # Out-of-order: Random sampling (models distributed storage)
            # Paper: "one of the nodes is randomly sampled"
            # No waiting - takes ANY available message (much faster!)
            message_id = random.choice(list(self.messages.keys()))
            return self.messages.pop(message_id)

    def peek(self) -> Optional[CloudMessage]:
        """
        View next message without removing

        Returns:
            CloudMessage if available, None otherwise
        """
        if not self.messages:
            return None

        if self.mode == "in_order":
            # In-order: Must return the NEXT EXPECTED message (queue_index)
            # If it's not here, return None (HOL Blocking)
            for message in self.messages.values():
                if hasattr(message, 'vector_clock') and len(message.vector_clock) > 0:
                    if message.vector_clock[0] == self.queue_index:
                        return message
            return None
        else:
            message_id = random.choice(list(self.messages.keys()))
            return self.messages[message_id]

    def get_visible_messages(self, current_time: float) -> List[CloudMessage]:
        """
        Get all currently visible messages

        Args:
            current_time: Current simulation time

        Returns:
            List of visible messages
        """
        visible = []
        for message in self.messages.values():
            if message.is_visible(current_time):
                visible.append(message)
        return visible

    def size(self) -> int:
        """Get number of messages in queue"""
        return len(self.messages)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.messages) == 0


class FIFOQueue(MessageOrdering):
    """FIFO (First-In-First-Out) message queue"""

    def __init__(self):
        super().__init__(mode="in_order")


class RandomSamplingQueue(MessageOrdering):
    """Random sampling queue (out-of-order for performance)"""

    def __init__(self):
        super().__init__(mode="out_of_order")
