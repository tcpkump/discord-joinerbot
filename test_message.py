import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from message import Message


class TestMessage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Reset Message class state before each test."""
        Message._last_message = None
        Message._target_channel = None
        Message._last_message_time = None
        Message._queued_task = None
        Message._pending_update = False

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
    async def test_create_with_channel(self, mock_logger):
        """Test create method with target channel set."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.create(member_list, callers, is_first_person=True)

        mock_channel.send.assert_called_once_with("Alice joined voice chat")
        mock_logger.info.assert_called_once_with(
            "Sent message: Alice joined voice chat"
        )
        self.assertEqual(Message._last_message, mock_message)

    @patch("message.Message._logger")
    async def test_create_deletes_previous_message(self, mock_logger):
        """Test create method deletes previous message."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_old_message = AsyncMock(spec=discord.Message)
        mock_new_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_new_message

        Message.set_channel(mock_channel)
        Message._last_message = mock_old_message

        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.create(member_list, callers, is_first_person=True)

        mock_old_message.delete.assert_called_once()
        mock_channel.send.assert_called_once_with("Alice joined voice chat")
        self.assertEqual(Message._last_message, mock_new_message)

    @patch("message.Message._logger")
    async def test_update_zero_callers(self, mock_logger):
        """Test update method with zero callers calls delete."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._last_message = mock_message

        member_list = []
        callers = 0

        await Message.update(member_list, callers)

        mock_message.delete.assert_called_once()
        mock_logger.info.assert_called_once_with("Deleted voice chat message")
        self.assertIsNone(Message._last_message)

    @patch("message.Message._logger")
    async def test_update_with_callers(self, mock_logger):
        """Test update method with callers."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._last_message = mock_message

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
        Message._last_message = mock_message

        await Message.delete()

        mock_message.delete.assert_called_once()
        mock_logger.info.assert_called_once_with("Deleted voice chat message")
        self.assertIsNone(Message._last_message)

    @patch("message.Message._logger")
    async def test_delete_no_message(self, mock_logger):
        """Test delete method when no message exists."""
        Message._last_message = None

        await Message.delete()

        mock_logger.info.assert_not_called()

    @patch("message.Message._logger")
    async def test_create_http_exception(self, mock_logger):
        """Test create method handles HTTP exceptions."""
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

        await Message.create(member_list, callers, is_first_person=True)

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
        Message._last_message = mock_message

        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.update(member_list, callers)

        self.assertIsNone(Message._last_message)

    # Rate Limiting Tests
    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_first_person_sends_immediately(
        self, mock_logger, mock_sleep, mock_time
    ):
        """Test that first person joining sends message immediately."""
        mock_time.return_value = 1000.0
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        member_list = [(123, "Alice", None)]
        callers = 1

        await Message.create(member_list, callers, is_first_person=True)

        mock_channel.send.assert_called_once_with("Alice joined voice chat")
        mock_sleep.assert_not_called()  # No queuing for first person
        self.assertEqual(Message._last_message_time, 1000.0)

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_immediate_send_when_10_minutes_passed(
        self, mock_logger, mock_sleep, mock_time
    ):
        """Test immediate send when 10+ minutes have passed since last message."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        Message._last_message_time = 1000.0  # Set previous message time
        mock_time.return_value = 1700.0  # 700 seconds later (>10 minutes)

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.create(member_list, callers, is_first_person=False)

        mock_channel.send.assert_called_once_with("Alice and Bob are in voice chat")
        mock_sleep.assert_not_called()  # No queuing when enough time has passed
        self.assertEqual(Message._last_message_time, 1700.0)

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
        Message._last_message_time = 1000.0  # Set previous message time
        mock_time.return_value = 1300.0  # 300 seconds later (<10 minutes)

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.create(member_list, callers, is_first_person=False)

        # Should not send immediately
        mock_channel.send.assert_not_called()
        # Should queue a task
        mock_create_task.assert_called_once()
        self.assertTrue(Message._pending_update)

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
        Message._last_message_time = 1000.0
        Message._queued_task = mock_old_task
        mock_time.return_value = 1300.0

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        # Call _queue_message directly to test cancellation logic
        await Message._queue_message(member_list, callers, 1300.0)

        # Should cancel old task
        mock_old_task.cancel.assert_called_once()
        # Should create new task
        mock_create_task.assert_called_once()
        self.assertEqual(Message._queued_task, mock_new_task)

    @patch("time.time")
    @patch("asyncio.sleep")
    @patch("message.Message._logger")
    async def test_delayed_send_execution(self, mock_logger, mock_sleep, mock_time):
        """Test that delayed send actually sends the message after delay."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message

        Message.set_channel(mock_channel)
        Message._pending_update = True
        mock_time.return_value = 1600.0  # Time when message is sent

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message._delayed_send(member_list, callers, 300.0)

        mock_sleep.assert_called_once_with(300.0)
        mock_channel.send.assert_called_once_with("Alice and Bob are in voice chat")
        self.assertEqual(Message._last_message_time, 1600.0)
        self.assertFalse(Message._pending_update)

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
        Message._pending_update = False  # No pending update

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
        Message._last_message = mock_message

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        callers = 2

        await Message.update(member_list, callers)

        # Should update existing message immediately
        mock_message.edit.assert_called_once_with(
            content="Alice and Bob are in voice chat"
        )
        # Should not send new message
        mock_channel.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
