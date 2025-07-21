import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from message import Message


class TestMessage(unittest.IsolatedAsyncioTestCase):
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

    def test_format_message_single_user(self):
        """Test message formatting for single user."""
        member_list = [(123, "Alice", None)]
        callers = 1
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice joined voice chat")

    def test_format_message_two_users(self):
        """Test message formatting for two users."""
        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice and Bob are in voice chat")

    def test_format_message_three_users(self):
        """Test message formatting for three users."""
        member_list = [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)]
        callers = 3
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice, Bob, and Charlie are in voice chat")

    def test_format_message_four_users(self):
        """Test message formatting for four users."""
        member_list = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
            (101, "David", None),
        ]
        callers = 4
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice, Bob, Charlie, and David are in voice chat")

    def test_format_message_five_or_more_users(self):
        """Test message formatting for five or more users."""
        member_list = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),
            (101, "David", None),
            (112, "Eve", None),
        ]
        callers = 5
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice, Bob, Charlie, and 2 others are in voice chat")

    def test_format_message_seven_users(self):
        """Test message formatting for seven users."""
        member_list = [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)]
        callers = 7
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "Alice, Bob, Charlie, and 4 others are in voice chat")

    def test_format_message_no_usernames(self):
        """Test message formatting when no usernames are available."""
        member_list = []
        callers = 3
        result = Message._format_message(member_list, callers)
        self.assertEqual(result, "3 people are in voice chat")

    def test_set_channel(self):
        """Test setting the target channel."""
        mock_channel = Mock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)
        self.assertEqual(Message._target_channel, mock_channel)

    @patch("message.Message._logger")
    async def test_create_no_channel(self, mock_logger):
        """Test create method when no target channel is set."""
        member_list = [(123, "Alice", None)]
        callers = 1
        await Message.create(member_list, callers, is_first_person=True)
        mock_logger.warning.assert_called_once_with(
            "No target channel set for messages"
        )

    @patch("message.Message._logger")
    async def test_create_with_channel_starts_batch_timer(self, mock_logger):
        """Test create method with target channel set now starts batch timer."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.create(member_list, callers, is_first_person=True)

        # Should not send immediately due to new batching logic
        mock_channel.send.assert_not_called()
        # Should start batch timer instead
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)

    @patch("message.Message._logger")
    async def test_send_message_now_deletes_previous_message(self, mock_logger):
        """Test that _send_message_now deletes previous message."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_old_message = AsyncMock(spec=discord.Message)
        mock_new_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_new_message

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_old_message

        member_list = [(123, "Alice", None)]
        callers = 1

        await Message._send_message_now(member_list, callers)

        mock_old_message.delete.assert_called_once()
        mock_channel.send.assert_called_once_with("Alice joined voice chat")
        mock_logger.info.assert_called_once_with(
            "Sent message: Alice joined voice chat"
        )
        self.assertEqual(Message._state.last_message, mock_new_message)

    @patch("message.Message._logger")
    async def test_update_zero_callers(self, mock_logger):
        """Test update method with zero callers calls delete."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        member_list = []
        callers = 0

        await Message.update(member_list, callers)

        mock_message.delete.assert_called_once()
        mock_logger.info.assert_called_once_with("Deleted voice chat message")
        self.assertIsNone(Message._state.last_message)

    @patch("message.Message._logger")
    async def test_update_with_callers(self, mock_logger):
        """Test update method with callers."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.update(member_list, callers)

        mock_message.edit.assert_called_once_with(
            content="Alice and Bob are in voice chat"
        )
        mock_logger.info.assert_called_once_with(
            "Updated message: Alice and Bob are in voice chat"
        )

    @patch("message.Message._logger")
    async def test_delete(self, mock_logger):
        """Test delete method."""
        mock_message = AsyncMock(spec=discord.Message)
        Message._state.last_message = mock_message

        await Message.delete()

        mock_message.delete.assert_called_once()
        mock_logger.info.assert_called_once_with("Deleted voice chat message")
        self.assertIsNone(Message._state.last_message)

    @patch("message.Message._logger")
    async def test_delete_no_message(self, mock_logger):
        """Test delete method when no message exists."""
        Message._set_last_message(None)

        await Message.delete()

        mock_logger.info.assert_not_called()

    @patch("message.Message._logger")
    async def test_send_message_now_http_exception(self, mock_logger):
        """Test _send_message_now method handles HTTP exceptions."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        # Create a mock response with the expected attributes
        mock_response = Mock()
        mock_response.status = 500
        mock_response.reason = "Internal Server Error"
        mock_channel.send.side_effect = discord.HTTPException(
            mock_response, "Test error"
        )

        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]
        callers = 1

        await Message._send_message_now(member_list, callers)

        # Check that error was called with a message containing "Failed to send message:"
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        self.assertTrue(error_message.startswith("Failed to send message:"))

    @patch("message.Message._logger")
    async def test_update_message_not_found(self, mock_logger):
        """Test update method handles message not found."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.edit.side_effect = discord.NotFound(Mock(), "Message not found")

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.update(member_list, callers)

        self.assertIsNone(Message._state.last_message)

    # Rate Limiting Tests
    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_first_person_starts_batch_timer(
        self, mock_logger, mock_sleep, mock_time
    ):
        """Test that first person joining starts batch timer instead of sending immediately."""
        mock_time.return_value = 1000.0
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.create(member_list, callers, is_first_person=True)

        # Should not send immediately - should start batch timer
        mock_channel.send.assert_not_called()
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_batch_timer_when_10_minutes_passed(
        self, mock_logger, mock_sleep, mock_time
    ):
        """Test batch timer starts when 10+ minutes have passed since last message."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        Message._state.last_message_time = 1000.0  # Set previous message time
        mock_time.return_value = 1700.0  # 700 seconds later (>10 minutes)

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.create(member_list, callers, is_first_person=False)

        # Should start batch timer, not send immediately
        mock_channel.send.assert_not_called()
        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)  # Latest joiner

    @patch("time.time")
    @patch("asyncio.create_task")
    @patch("message.Message._logger")
    async def test_queue_message_when_under_10_minutes(
        self, mock_logger, mock_create_task, mock_time
    ):
        """Test message queuing when less than 10 minutes have passed."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_task = AsyncMock()
        mock_create_task.return_value = mock_task

        Message.set_channel(mock_channel)
        Message._state.last_message_time = 1000.0  # Set previous message time
        mock_time.return_value = 1300.0  # 300 seconds later (<10 minutes)

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.create(member_list, callers, is_first_person=False)

        # Should not send immediately
        mock_channel.send.assert_not_called()
        # Should queue a task
        mock_create_task.assert_called_once()
        self.assertTrue(Message._state.pending_update)

    @patch("time.time")
    @patch("asyncio.create_task")
    @patch("message.Message._logger")
    async def test_queue_cancellation_on_new_message(
        self, mock_logger, mock_create_task, mock_time
    ):
        """Test that existing queued task is cancelled when new message is queued."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_old_task = Mock()
        mock_old_task.done.return_value = False
        mock_new_task = AsyncMock()
        mock_create_task.return_value = mock_new_task

        Message.set_channel(mock_channel)
        Message._state.last_message_time = 1000.0
        Message._state.queued_task = mock_old_task
        mock_time.return_value = 1300.0

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        # Call _queue_message directly to test cancellation logic
        await Message._queue_message(member_list, callers, 1300.0)

        # Should cancel old task
        mock_old_task.cancel.assert_called_once()
        # Should create new task
        mock_create_task.assert_called_once()
        self.assertEqual(Message._state.queued_task, mock_new_task)

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_delayed_send_execution(self, mock_logger, mock_sleep, mock_time):
        """Test that delayed send actually sends the message after delay."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        Message._state.pending_update = True
        mock_time.return_value = 1600.0  # Time when message is sent

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message._delayed_send(member_list, callers, 300.0)

        mock_sleep.assert_called_once_with(300.0)
        mock_channel.send.assert_called_once_with("Alice and Bob are in voice chat")
        self.assertEqual(Message._state.last_message_time, 1600.0)
        self.assertFalse(Message._state.pending_update)

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_delayed_send_cancelled(self, mock_logger, mock_sleep, mock_time):
        """Test that delayed send handles cancellation gracefully."""
        import asyncio

        mock_sleep.side_effect = asyncio.CancelledError()

        member_list = [(123, "Alice", None)]
        callers = 1

        with self.assertRaises(asyncio.CancelledError):
            await Message._delayed_send(member_list, callers, 300.0)

        mock_logger.info.assert_called_once_with("Queued message was cancelled")

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_delayed_send_no_pending_update(
        self, mock_logger, mock_sleep, mock_time
    ):
        """Test that delayed send doesn't send if no pending update."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)
        Message._state.pending_update = False  # No pending update

        member_list = [(123, "Alice", None)]
        callers = 1

        await Message._delayed_send(member_list, callers, 300.0)

        mock_sleep.assert_called_once_with(300.0)
        mock_channel.send.assert_not_called()  # Should not send

    @patch("message.Message._logger")
    async def test_update_only_edits_message(self, mock_logger):
        """Test that update method only edits the existing message."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.update(member_list, callers)

        # Should update existing message immediately
        mock_message.edit.assert_called_once_with(
            content="Alice and Bob are in voice chat"
        )
        # Should not send new message
        mock_channel.send.assert_not_called()

    @patch("message.Message._logger")
    async def test_batched_notification_shows_all_current_users(self, mock_logger):
        """Test that batched notification shows ALL current users using stored member list"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message
        Message.set_channel(mock_channel)

        # Set up stored member list (this is what the fix provides)
        all_members = [
            (123, "Alice", None),
            (456, "Bob", None),
            (789, "Charlie", None),  # Charlie was already in channel
        ]
        Message._state.batch_member_list = all_members
        Message._state.batch_callers_count = 3
        Message._state.pending_joins = [(123, "Alice", None), (456, "Bob", None)]

        # Trigger batch send
        await Message._send_batched_notification(0.01)

        # Should send message showing all 3 users from stored data
        mock_channel.send.assert_called_once()
        sent_message = mock_channel.send.call_args[0][0]

        # Message should include all three users
        self.assertIn("Alice", sent_message)
        self.assertIn("Bob", sent_message)
        self.assertIn("Charlie", sent_message)
        self.assertIn("are in voice chat", sent_message)

    @patch("message.Message._logger")
    async def test_fourth_player_batching_bug_fixed(self, mock_logger):
        """Test that the 4th player bug is fixed - batch shows all users from stored data"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message
        Message.set_channel(mock_channel)

        # Simulate the full scenario: all 4 users are in channel when Riley joins
        all_members = [
            (123, "cailin", None),
            (456, "fett32", None),
            (789, "nightwaff", None),
            (101, "Riley", None),  # Riley is the new joiner
        ]

        # This simulates what happens when Riley joins - create() stores the member list
        await Message.create(
            all_members, 4, is_first_person=False, suppress_notification=False
        )

        # Verify the batch member list was stored (this is the fix)
        self.assertEqual(Message._state.batch_member_list, all_members)
        self.assertEqual(Message._state.batch_callers_count, 4)

        # Execute the batch notification - should use stored data, not query database
        await Message._send_batched_notification(0.01)

        # Check what message was sent
        mock_channel.send.assert_called_once()
        sent_message = mock_channel.send.call_args[0][0]

        print(f"Fixed message: {sent_message}")

        # Should show all 4 players correctly
        self.assertIn("cailin", sent_message)
        self.assertIn("fett32", sent_message)
        self.assertIn("nightwaff", sent_message)
        self.assertIn("Riley", sent_message)
        self.assertIn("are in voice chat", sent_message)


if __name__ == "__main__":
    unittest.main()
