import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from message import Message


class TestEndToEndIntegration(unittest.IsolatedAsyncioTestCase):
    """Comprehensive end-to-end integration tests for realistic caller scenarios

    Tests the actual behavior:
    - First joins start 30-second batch timers
    - Subsequent joins within 10 minutes: immediate message update + queued notification
    - Subsequent joins after 10+ minutes: start new batch timer
    """

    def setUp(self):
        """Reset all state before each test"""
        # Reset Message class state
        Message._state.reset()
        Message._target_channel = None

        # Set fast batch delay for testing (1 second instead of 30)
        Message.set_batch_delay(1.0)

        # Set up mock Discord objects
        self.mock_channel = AsyncMock(spec=discord.TextChannel)
        self.mock_channel.name = "general"
        Message.set_channel(self.mock_channel)

        # Mock messages for tracking message lifecycle
        self.sent_messages = []
        self.deleted_messages = []
        self.edited_messages = []

        def track_send(content):
            message = Mock(spec=discord.Message)
            message.content = content
            message.edit = AsyncMock(
                side_effect=lambda content: self.edited_messages.append(content)
            )
            message.delete = AsyncMock(
                side_effect=lambda: self.deleted_messages.append(message)
            )
            self.sent_messages.append(message)
            return message

        self.mock_channel.send = AsyncMock(side_effect=track_send)

    def tearDown(self):
        """Clean up any running tasks after each test"""

        async def cleanup():
            if Message._batch_timer and not Message._batch_timer.done():
                Message._batch_timer.cancel()
            if Message._queued_task and not Message._queued_task.done():
                Message._queued_task.cancel()

        asyncio.run(cleanup())

        # Reset batch delay to default
        Message.set_batch_delay(30.0)

    @patch("time.time")
    async def test_single_caller_complete_lifecycle(self, mock_time):
        """Test complete flow: single caller joins, gets batched message, then leaves"""
        mock_time.return_value = 1000.0

        # Single caller joins (first person)
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        # Should start batch timer, no immediate message
        self.assertEqual(len(self.sent_messages), 0)
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)
        self.assertEqual(Message._pending_joins[0][1], "Alice")

        # Wait for batch timer to complete
        await Message._batch_timer

        # Should send single caller message
        self.assertEqual(len(self.sent_messages), 1)
        self.assertEqual(self.sent_messages[0].content, "Alice joined voice chat")
        self.assertIsNotNone(Message._last_message_time)

        # Caller leaves
        await Message.delete()

        # Should delete the message and clear state
        self.assertEqual(len(self.deleted_messages), 1)
        self.assertIsNone(Message._last_message)
        self.assertEqual(len(Message._pending_joins), 0)

    @patch("time.time")
    async def test_two_callers_batched_together(self, mock_time):
        """Test two callers joining within batch window get combined message"""
        mock_time.return_value = 1000.0

        # First caller starts batch
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        # Second caller joins within batch window (before 30 seconds)
        mock_time.return_value = 1015.0  # 15 seconds later
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Should have 2 pending joins, still no message sent
        self.assertEqual(len(Message._state.pending_joins), 2)
        self.assertEqual(len(self.sent_messages), 0)

        # Wait for batch timer to complete
        await Message._batch_timer

        # Should send message showing both users
        self.assertEqual(len(self.sent_messages), 1)
        content = self.sent_messages[0].content
        self.assertIn("Alice", content)
        self.assertIn("Bob", content)
        self.assertIn("are in voice chat", content)

    @patch("time.time")
    async def test_three_callers_scenario(self, mock_time):
        """Test three callers joining in sequence within batch window"""
        mock_time.return_value = 1000.0

        # First caller
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        # Second caller joins (10 seconds later)
        mock_time.return_value = 1010.0
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Third caller joins (20 seconds after first)
        mock_time.return_value = 1020.0
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
            3,
            is_first_person=False,
        )

        # All should be in pending joins
        self.assertEqual(len(Message._state.pending_joins), 3)
        usernames = [member[1] for member in Message._pending_joins]
        self.assertIn("Alice", usernames)
        self.assertIn("Bob", usernames)
        self.assertIn("Charlie", usernames)

        # Wait for batch completion
        await Message._batch_timer

        # Should send message with all 3 users
        self.assertEqual(len(self.sent_messages), 1)
        content = self.sent_messages[0].content
        self.assertIn("Alice", content)
        self.assertIn("Bob", content)
        self.assertIn("Charlie", content)
        self.assertIn("are in voice chat", content)

    @patch("time.time")
    async def test_four_callers_batch_scenario(self, mock_time):
        """Test four callers joining within batch window"""
        mock_time.return_value = 1000.0

        member_list = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
            (101, "David", None),
        ]

        # All join within 30-second batch window
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        mock_time.return_value = 1005.0
        await Message.create(member_list[:2], 2, is_first_person=False)

        mock_time.return_value = 1010.0
        await Message.create(member_list[:3], 3, is_first_person=False)

        mock_time.return_value = 1015.0
        await Message.create(member_list, 4, is_first_person=False)

        # Should have 4 people in batch
        self.assertEqual(len(Message._pending_joins), 4)

        # Wait for batch completion
        await Message._batch_timer

        # Should send message with all 4 names explicitly listed
        self.assertEqual(len(self.sent_messages), 1)
        content = self.sent_messages[0].content
        self.assertIn("Alice", content)
        self.assertIn("Bob", content)
        self.assertIn("Charlie", content)
        self.assertIn("David", content)
        self.assertIn("are in voice chat", content)

    @patch("time.time")
    async def test_seven_callers_others_format(self, mock_time):
        """Test seven callers produces correct 'others' format message"""
        mock_time.return_value = 1000.0

        member_list = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
            (101, "David", None),
            (202, "Eve", None),
            (303, "Frank", None),
            (404, "Grace", None),
        ]

        # All join within batch window
        await Message.create([member_list[0]], 1, is_first_person=True)

        for i in range(2, 8):
            mock_time.return_value = 1000.0 + (i * 2)  # 2 seconds apart
            await Message.create(member_list[:i], i, is_first_person=False)

        # Wait for batch completion
        await Message._batch_timer

        # Should send message with first 3 names + "4 others"
        self.assertEqual(len(self.sent_messages), 1)
        content = self.sent_messages[0].content
        self.assertIn("Alice", content)
        self.assertIn("Bob", content)
        self.assertIn("Charlie", content)
        self.assertIn("4 others", content)
        self.assertIn("are in voice chat", content)
        # Should not contain individual names of David, Eve, Frank, Grace
        self.assertNotIn("David", content)

    @patch("time.time")
    async def test_realistic_join_sequence_with_updates(self, mock_time):
        """Test realistic sequence: first batch, then immediate updates + queuing"""
        # Phase 1: Initial batch (Alice joins first)
        mock_time.return_value = 1000.0
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)
        await Message._batch_timer  # Complete initial batch

        self.assertEqual(len(self.sent_messages), 1)
        self.assertEqual(self.sent_messages[0].content, "Alice joined voice chat")
        Message._last_message_time = 1000.0  # Simulate message timestamp

        # Phase 2: Bob joins within 10 minutes - should update message immediately + queue notification
        mock_time.return_value = 1300.0  # 5 minutes later

        # Simulate JoinerBot behavior: first update existing message
        await Message.update([(123, "Alice", None), (456, "Bob", None)], 2)

        # Should have edited the existing message
        self.assertEqual(len(self.edited_messages), 1)
        self.assertIn("Alice and Bob are in voice chat", self.edited_messages[0])

        # Then create queued notification (this is what JoinerBot does)
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Should queue message (not start batch timer) since within 10 minutes
        self.assertTrue(Message._batch_timer is None or Message._batch_timer.done())
        self.assertIsNotNone(Message._queued_task)
        self.assertTrue(Message._pending_update)

        # Phase 3: Charlie joins - also within 10 minutes
        mock_time.return_value = 1400.0  # 6 minutes after first message

        await Message.update(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)], 3
        )
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
            3,
            is_first_person=False,
        )

        # Should have updated message again
        self.assertEqual(len(self.edited_messages), 2)
        self.assertIn(
            "Alice, Bob, and Charlie are in voice chat", self.edited_messages[1]
        )

        # Should still be queuing (old task cancelled, new one created)
        self.assertIsNotNone(Message._queued_task)

    @patch("time.time")
    async def test_new_batch_after_10_minutes(self, mock_time):
        """Test that new batch timer starts when >10 minutes have passed"""
        # Initial message
        mock_time.return_value = 1000.0
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)
        await Message._batch_timer
        Message._last_message_time = 1000.0

        # More than 10 minutes later (700 seconds = 11+ minutes)
        mock_time.return_value = 1700.0
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Should start NEW batch timer (not queue)
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertFalse(Message._batch_timer.done())
        self.assertTrue(Message._queued_task is None or Message._queued_task.done())
        self.assertFalse(Message._pending_update)
        self.assertEqual(len(Message._state.pending_joins), 1)  # New joiner (Bob)

        # Wait for new batch
        await Message._batch_timer

        # Should delete old message and send new one
        self.assertEqual(len(self.deleted_messages), 1)
        self.assertEqual(len(self.sent_messages), 2)  # Original + new batch message

    @patch("time.time")
    async def test_caller_reduction_scenarios(self, mock_time):
        """Test scenarios where callers leave (4→3→2→1→0)"""
        mock_time.return_value = 1000.0

        # Start with 4 callers in a batch
        member_lists = [
            [(123, "Alice", None)],
            [(123, "Alice", None), (456, "Bob", None)],
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
            [
                (123, "Alice", None),
                (456, "Bob", None),
                (789, "Charlie", None),
                (101, "David", None),
            ],
        ]

        for i, members in enumerate(member_lists):
            await Message.create(members, i + 1, is_first_person=(i == 0))

        await Message._batch_timer
        original_content = self.sent_messages[0].content
        self.assertIn("David", original_content)  # All 4 should be there

        # Reduce callers one by one via updates
        await Message.update(member_lists[2], 3)  # David leaves
        self.assertIn(
            "Alice, Bob, and Charlie are in voice chat", self.edited_messages[0]
        )

        await Message.update(member_lists[1], 2)  # Charlie leaves
        self.assertIn("Alice and Bob are in voice chat", self.edited_messages[1])

        await Message.update(member_lists[0], 1)  # Bob leaves
        # Note: update still uses multi-person format for consistency
        self.assertIn("Alice", self.edited_messages[2])

        await Message.update([], 0)  # Alice leaves (everyone gone)

        # Should delete message when count reaches 0
        self.assertEqual(len(self.deleted_messages), 1)
        self.assertIsNone(Message._last_message)

    @patch("time.time")
    async def test_rejoin_suppression_integration(self, mock_time):
        """Test end-to-end rejoin suppression behavior"""
        mock_time.return_value = 1000.0

        # Alice joins (not a rejoin)
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)
        await Message._batch_timer

        # Bob joins normally
        mock_time.return_value = 1100.0
        await Message.update([(123, "Alice", None), (456, "Bob", None)], 2)
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Charlie joins but it's a rejoin - should suppress notification
        await Message.update(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)], 3
        )
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
            3,
            is_first_person=False,
            suppress_notification=True,
        )

        # Should update message to include Charlie
        last_edit = self.edited_messages[-1]
        self.assertIn("Charlie", last_edit)

        # But should NOT start NEW batch timer or queue message for Charlie's rejoin
        # (But Bob's join may have created a queued task which is expected)
        self.assertTrue(Message._batch_timer is None or Message._batch_timer.done())
        self.assertEqual(
            len(Message._pending_joins), 0
        )  # No new pending joins from rejoin

    @patch("time.time")
    async def test_complex_timing_scenario(self, mock_time):
        """Test complex scenario with multiple timing windows"""
        # T=0: Alice joins (starts batch)
        mock_time.return_value = 1000.0
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        # T=10: Bob joins during batch window
        mock_time.return_value = 1010.0
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # T=30: Batch completes, sends "Alice and Bob are in voice chat"
        await Message._batch_timer
        Message._last_message_time = 1030.0  # When message was actually sent

        # T=200: Charlie joins (within 10-minute window) - should queue
        mock_time.return_value = 1230.0  # 200 seconds after batch message
        await Message.update(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)], 3
        )
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
            3,
            is_first_person=False,
        )

        # Should have queued notification, not started new batch
        self.assertTrue(Message._batch_timer is None or Message._batch_timer.done())
        self.assertIsNotNone(Message._queued_task)

        # T=800: David joins (>10 minutes after last message) - should start new batch
        mock_time.return_value = (
            1830.0  # 800 seconds after batch message (>600 second limit)
        )
        await Message.update(
            [
                (123, "Alice", None),
                (456, "Bob", None),
                (789, "Charlie", None),
                (101, "David", None),
            ],
            4,
        )
        await Message.create(
            [
                (123, "Alice", None),
                (456, "Bob", None),
                (789, "Charlie", None),
                (101, "David", None),
            ],
            4,
            is_first_person=False,
        )

        # Should start new batch timer now
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertFalse(Message._batch_timer.done())
        self.assertEqual(
            len(Message._state.pending_joins), 1
        )  # Just David (the new joiner)

        # Complete new batch
        await Message._batch_timer

        # Should have deleted old message and sent new one
        self.assertEqual(len(self.deleted_messages), 1)
        self.assertEqual(len(self.sent_messages), 2)

    @patch("time.time")
    async def test_batch_cancellation_on_everyone_leaves(self, mock_time):
        """Test that batch timer gets cancelled if everyone leaves during batch"""
        mock_time.return_value = 1000.0

        # Start batch with Alice
        await Message.create([(123, "Alice", None)], 1, is_first_person=True)

        # Bob joins during batch
        mock_time.return_value = 1010.0
        await Message.create(
            [(123, "Alice", None), (456, "Bob", None)], 2, is_first_person=False
        )

        # Verify batch is running
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertFalse(Message._batch_timer.done())

        # Everyone leaves before batch completes
        await Message.delete()

        # Should cancel batch timer and clear state
        self.assertEqual(len(Message._pending_joins), 0)
        self.assertIsNone(Message._last_message)

    @patch("time.time")
    async def test_message_formatting_in_realistic_scenarios(self, mock_time):
        """Test that message formatting works correctly in end-to-end scenarios"""
        scenarios = [
            # (member_list, expected_content_parts, expected_not_in_content)
            (
                [(123, "Alice", None)],
                ["Alice joined voice chat"],
                ["are in voice chat"],
            ),
            (
                [(123, "Alice", None), (456, "Bob", None)],
                ["Alice", "Bob", "are in voice chat"],
                ["joined voice chat"],
            ),
            (
                [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)],
                ["Alice", "Bob", "Charlie", "are in voice chat"],
                [],
            ),
            (
                [
                    (123, "Alice", None),
                    (456, "Bob", None),
                    (789, "Charlie", None),
                    (101, "David", None),
                    (202, "Eve", None),
                    (303, "Frank", None),
                    (404, "Grace", None),
                ],
                ["Alice", "Bob", "Charlie", "4 others", "are in voice chat"],
                ["David", "Eve", "Frank", "Grace"],
            ),
        ]

        for i, (member_list, expected_parts, not_expected) in enumerate(scenarios):
            with self.subTest(scenario=i + 1, callers=len(member_list)):
                # Reset state for each scenario
                self.setUp()
                mock_time.return_value = 1000.0 + (
                    i * 100
                )  # Different times for each scenario

                # Create batch message
                await Message.create(
                    member_list, len(member_list), is_first_person=True
                )
                await Message._batch_timer

                # Check message content
                self.assertEqual(len(self.sent_messages), 1)
                content = self.sent_messages[0].content

                for expected_part in expected_parts:
                    self.assertIn(
                        expected_part,
                        content,
                        f"Expected '{expected_part}' in '{content}'",
                    )

                for not_expected_part in not_expected:
                    self.assertNotIn(
                        not_expected_part,
                        content,
                        f"Did not expect '{not_expected_part}' in '{content}'",
                    )


if __name__ == "__main__":
    unittest.main()
