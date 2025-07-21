import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from message import Message


class TestBatchingAndRejoinLogic(unittest.IsolatedAsyncioTestCase):
    """Test the new 30-second batching and rejoin suppression logic"""

    def setUp(self):
        """Reset Message class state before each test."""
        Message._state.reset()
        Message._target_channel = None
        Message._state.batch_delay = 30.0  # Reset to default

    def tearDown(self):
        """Clean up any running tasks after each test."""

        async def cleanup():
            if Message._state.batch_timer and not Message._state.batch_timer.done():
                Message._state.batch_timer.cancel()
            if Message._state.queued_task and not Message._state.queued_task.done():
                Message._state.queued_task.cancel()

        asyncio.run(cleanup())

    @patch("message.Message._logger")
    async def test_first_person_starts_batch_timer(self, mock_logger):
        """Test that first person joining starts a 30-second batch timer"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]

        await Message.create(member_list, 1, is_first_person=True)

        # Should start batch timer, not send immediately
        self.assertIsNotNone(Message._state.batch_timer)
        if Message._state.batch_timer is not None:
            self.assertFalse(Message._state.batch_timer.done())
        self.assertEqual(len(Message._state.pending_joins), 1)
        self.assertEqual(Message._state.pending_joins[0][1], "Alice")
        mock_channel.send.assert_not_called()

    @patch("message.Message._logger")
    async def test_second_person_added_to_batch(self, mock_logger):
        """Test that second person gets added to existing batch"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)

        # First person starts batch
        member_list1 = [(123, "Alice", None)]
        await Message.create(member_list1, 1, is_first_person=True)

        # Second person joins - should be added to batch
        member_list2 = [(123, "Alice", None), (456, "Bob", None)]
        await Message.create(member_list2, 2, is_first_person=False)

        # Should have 2 people in pending joins
        self.assertEqual(len(Message._state.pending_joins), 2)
        usernames = [member[1] for member in Message._state.pending_joins]
        self.assertIn("Alice", usernames)
        self.assertIn("Bob", usernames)
        mock_channel.send.assert_not_called()

    @patch("database.Database")
    @patch("message.Message._logger")
    async def test_batch_notification_deletes_previous_message(
        self, mock_logger, mock_db_class
    ):
        """Test that batched notification deletes previous message"""
        # Mock the database
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.get_callers.return_value = [(123, "Alice", None)]
        mock_db.get_num_callers.return_value = 1

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_old_message = AsyncMock(spec=discord.Message)
        mock_new_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_new_message

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_old_message
        Message._state.pending_joins = [(123, "Alice", None)]
        Message._state.batch_member_list = [(123, "Alice", None)]
        Message._state.batch_callers_count = 1

        # Trigger batch send with very short delay
        await Message._send_batched_notification(0.01)

        # Should delete old message and send new one
        mock_old_message.delete.assert_called_once()
        mock_channel.send.assert_called_once()
        self.assertEqual(Message._state.last_message, mock_new_message)

    @patch("message.Message._logger")
    async def test_suppressed_notification_updates_existing_message(self, mock_logger):
        """Test that suppressed notifications update existing message without sending new one"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_existing_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_existing_message
        member_list = [(123, "Alice", None)]

        await Message.create(
            member_list, 1, is_first_person=True, suppress_notification=True
        )

        # Should update existing message but not send new notification
        mock_existing_message.edit.assert_called_once_with(
            content="Alice joined voice chat"
        )
        mock_channel.send.assert_not_called()
        self.assertIsNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 0)

    @patch("time.time")
    @patch("message.Message._logger")
    async def test_batch_timer_starts_after_10_minutes(self, mock_logger, mock_time):
        """Test that batch timer starts when 10+ minutes have passed"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)

        # Set last message time to 11 minutes ago
        Message._state.last_message_time = 1000.0
        mock_time.return_value = 1660.0  # 660 seconds later (11 minutes)

        member_list = [(123, "Alice", None)]
        await Message.create(member_list, 1, is_first_person=False)

        # Should start new batch timer since >10 minutes passed
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)

    @patch("database.Database")
    @patch("message.Message._logger")
    async def test_duplicate_users_removed_from_batch(self, mock_logger, mock_db_class):
        """Test that duplicate users are removed from batch before sending"""
        # Mock the database
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.get_callers.return_value = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
        ]
        mock_db.get_num_callers.return_value = 3

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)

        # Add same user multiple times to pending joins
        Message._state.pending_joins = [
            (123, "Alice", None),
            (456, "Bob", None),
            (123, "Alice", None),  # Duplicate
            (789, "Charlie", None),
        ]
        # Set up batch member list (this is what matters now)
        Message._state.batch_member_list = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
        ]
        Message._state.batch_callers_count = 3

        # Trigger batch send
        await Message._send_batched_notification(0.01)

        # Should have called send once with all current users from database
        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args[0][0]

        # Check that message contains all users from database
        self.assertIn("Alice", call_args)
        self.assertIn("Bob", call_args)
        self.assertIn("Charlie", call_args)
        self.assertEqual(len(Message._state.pending_joins), 0)  # Should be cleared

    @patch("time.time")
    @patch("asyncio.create_task")
    @patch("message.Message._logger")
    async def test_queued_message_for_joins_within_10_minutes(
        self, mock_logger, mock_create_task, mock_time
    ):
        """Test that joins within 10-minute window get queued as before"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_task = AsyncMock()
        mock_create_task.return_value = mock_task

        Message.set_channel(mock_channel)
        Message._state.last_message_time = 1000.0  # Set previous message time
        mock_time.return_value = 1300.0  # 300 seconds later (<10 minutes)

        member_list = [(123, "Alice", None), (456, "Bob", None)]

        await Message.create(member_list, 2, is_first_person=False)

        # Should not start batch timer, should queue instead
        self.assertIsNone(Message._state.batch_timer)
        mock_create_task.assert_called_once()
        self.assertTrue(Message._state.pending_update)

    @patch("message.Message._logger")
    async def test_delete_cancels_batch_timer(self, mock_logger):
        """Test that delete() cancels batch timer and clears pending joins"""
        mock_message = AsyncMock(spec=discord.Message)
        mock_batch_timer = Mock()
        mock_batch_timer.done.return_value = False

        Message._state.last_message = mock_message
        Message._state.batch_timer = mock_batch_timer
        Message._state.pending_joins = [(123, "Alice", None)]

        await Message.delete()

        # Should cancel timer and clear state
        mock_batch_timer.cancel.assert_called_once()
        self.assertEqual(len(Message._state.pending_joins), 0)
        self.assertIsNone(Message._state.last_message)

    @patch("message.Message._logger")
    async def test_batch_timer_cancelled_gracefully(self, mock_logger):
        """Test that batch timer handles cancellation gracefully"""
        Message._state.pending_joins = [(123, "Alice", None)]

        # Create a task that will be cancelled
        task = asyncio.create_task(Message._send_batched_notification(1.0))
        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        # Should raise CancelledError and log appropriately
        with self.assertRaises(asyncio.CancelledError):
            await task

        mock_logger.info.assert_called_with("Batch notification was cancelled")


if __name__ == "__main__":
    unittest.main()
