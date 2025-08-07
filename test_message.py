import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from message import Message


class TestMessage(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Message class focusing on core functionality"""

    def setUp(self):
        """Reset Message class state before each test"""
        Message._state.reset()
        Message._target_channel = None

    def tearDown(self):
        """Clean up any running tasks after each test"""
        import asyncio

        async def cleanup():
            if Message._state.batch_timer and not Message._state.batch_timer.done():
                Message._state.batch_timer.cancel()

        asyncio.run(cleanup())

    def test_format_message_single_user(self):
        """Test message formatting for single user"""
        member_list = [(123, "Alice", None)]
        result = Message._format_message(member_list, 1)
        self.assertEqual(result, "Alice joined voice chat")

    def test_format_message_two_users(self):
        """Test message formatting for two users"""
        member_list = [(123, "Alice", None), (456, "Bob", None)]
        result = Message._format_message(member_list, 2)
        self.assertEqual(result, "Alice and Bob are in voice chat")

    def test_format_message_three_users(self):
        """Test message formatting for three users"""
        member_list = [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)]
        result = Message._format_message(member_list, 3)
        self.assertEqual(result, "Alice, Bob, and Charlie are in voice chat")

    def test_format_message_five_or_more_users(self):
        """Test message formatting for five or more users"""
        member_list = [(123, "Alice", None), (456, "Bob", None), (789, "Charlie", None)]
        result = Message._format_message(member_list, 5)
        self.assertEqual(result, "Alice, Bob, Charlie, and 2 others are in voice chat")

    def test_format_message_no_usernames(self):
        """Test message formatting when no usernames are available"""
        result = Message._format_message([], 3)
        self.assertEqual(result, "3 people are in voice chat")

    def test_set_channel(self):
        """Test setting the target channel"""
        mock_channel = Mock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)
        self.assertEqual(Message._target_channel, mock_channel)

    @patch("message.Message._logger")
    async def test_create_no_channel_logs_warning(self, mock_logger):
        """Test create method when no target channel is set"""
        await Message.create([(123, "Alice", None)])
        mock_logger.warning.assert_called_once_with(
            "No target channel set for messages"
        )

    @patch("message.Message._logger")
    async def test_create_with_channel_starts_batch(self, mock_logger):
        """Test create method starts batch timer when channel is set"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        Message.set_channel(mock_channel)

        await Message.create([(123, "Alice", None)])

        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)
        mock_channel.send.assert_not_called()

    @patch("message.Message._logger")
    async def test_update_with_callers_edits_message(self, mock_logger):
        """Test update method edits existing message"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        member_list = [(123, "Alice", None), (456, "Bob", None)]
        await Message.update(member_list)

        mock_message.edit.assert_called_once_with(
            content="Alice and Bob are in voice chat"
        )

    @patch("message.Message._logger")
    async def test_update_zero_callers_deletes_message(self, mock_logger):
        """Test update method with zero callers calls delete"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        await Message.update([])

        mock_message.delete.assert_called_once()
        self.assertIsNone(Message._state.last_message)

    @patch("message.Message._logger")
    async def test_delete_removes_message(self, mock_logger):
        """Test delete method removes message"""
        mock_message = AsyncMock(spec=discord.Message)
        Message._state.last_message = mock_message

        await Message.delete()

        mock_message.delete.assert_called_once()
        self.assertIsNone(Message._state.last_message)

    @patch("message.Message._logger")
    async def test_delete_no_message_does_nothing(self, mock_logger):
        """Test delete method when no message exists"""
        Message._state.last_message = None

        await Message.delete()

        mock_logger.info.assert_not_called()

    @patch("message.Message._logger")
    async def test_send_message_handles_http_exception(self, mock_logger):
        """Test _send_message_now handles HTTP exceptions"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_response = Mock()
        mock_response.status = 500
        mock_response.reason = "Internal Server Error"
        mock_channel.send.side_effect = discord.HTTPException(
            mock_response, "Test error"
        )

        Message.set_channel(mock_channel)
        await Message._send_message_now([(123, "Alice", None)], 1)

        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        self.assertTrue(error_message.startswith("Failed to send message:"))

    @patch("message.Message._logger")
    async def test_update_handles_not_found_exception(self, mock_logger):
        """Test update method handles message not found"""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.edit.side_effect = discord.NotFound(Mock(), "Message not found")

        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        await Message.update([(123, "Alice", None)])

        self.assertIsNone(Message._state.last_message)


if __name__ == "__main__":
    unittest.main()
