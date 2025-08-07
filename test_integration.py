import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from joinerbot import JoinerBot
from message import Message


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Lightweight integration tests for critical end-to-end flows"""

    def setUp(self):
        """Set up integration test environment"""
        Message._state.reset()
        Message._target_channel = None
        Message.set_batch_delay(0.1)

    def tearDown(self):
        """Clean up after tests"""

        async def cleanup():
            if Message._state.batch_timer and not Message._state.batch_timer.done():
                Message._state.batch_timer.cancel()

        asyncio.run(cleanup())
        Message.set_batch_delay(30.0)

    @patch("joinerbot.Database")
    async def test_join_leave_within_batch_window_no_message(self, mock_db_class):
        """Test user joins and leaves within 30s window - no message should be sent"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message
        Message.set_channel(mock_channel)

        intents = discord.Intents.default()
        with patch.dict(
            "os.environ",
            {
                "JOINERBOT_WATCHED_CHANNEL": "test-voice",
                "JOINERBOT_TARGET_CHANNEL": "test-text",
            },
        ):
            bot = JoinerBot(intents=intents)
            bot.db = mock_db

        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_db.was_recently_connected.return_value = False
        mock_db.get_num_callers.return_value = 1
        mock_db.get_callers.return_value = [(123, "Alice", None)]

        mock_before_join = Mock()
        mock_before_join.channel = None
        mock_after_join = Mock()
        mock_after_join.channel = Mock()
        mock_after_join.channel.__str__ = Mock(return_value="test-voice")
        mock_after_join.channel.name = "test-voice"

        with patch.object(bot, "wait_until_ready"):
            await bot.on_voice_state_update(
                mock_member, mock_before_join, mock_after_join
            )

        self.assertIsNotNone(Message._state.batch_timer)
        self.assertEqual(len(Message._state.pending_joins), 1)
        mock_channel.send.assert_not_called()

        mock_db.get_num_callers.return_value = 0

        mock_before_leave = Mock()
        mock_before_leave.channel = Mock()
        mock_before_leave.channel.__str__ = Mock(return_value="test-voice")
        mock_before_leave.channel.name = "test-voice"
        mock_after_leave = Mock()
        mock_after_leave.channel = None

        with patch.object(bot, "wait_until_ready"):
            await bot.on_voice_state_update(
                mock_member, mock_before_leave, mock_after_leave
            )

        self.assertEqual(len(Message._state.pending_joins), 0)
        self.assertIsNone(Message._state.last_message)
        mock_channel.send.assert_not_called()

    @patch("joinerbot.Database")
    async def test_complete_join_flow(self, mock_db_class):
        """Test complete flow: user joins, batch timer completes, message sent"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.was_recently_connected.return_value = False
        mock_db.get_num_callers.return_value = 1
        mock_db.get_callers.return_value = [(123, "Alice", None)]

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = mock_message
        Message.set_channel(mock_channel)

        intents = discord.Intents.default()
        with patch.dict(
            "os.environ",
            {
                "JOINERBOT_WATCHED_CHANNEL": "test-voice",
                "JOINERBOT_TARGET_CHANNEL": "test-text",
            },
        ):
            bot = JoinerBot(intents=intents)
            bot.db = mock_db

        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_before = Mock()
        mock_before.channel = None

        mock_after = Mock()
        mock_after.channel = Mock()
        mock_after.channel.__str__ = Mock(return_value="test-voice")
        mock_after.channel.name = "test-voice"

        with patch.object(bot, "wait_until_ready"):
            await bot.on_voice_state_update(mock_member, mock_before, mock_after)

        batch_timer = Message._state.batch_timer
        if batch_timer:
            await batch_timer

        mock_db.log_join_leave.assert_called_with(123, "Alice", "join")
        mock_db.add_caller.assert_called_with(123, "Alice")
        mock_channel.send.assert_called_once_with("Alice joined voice chat")
        self.assertEqual(Message._state.last_message, mock_message)

    @patch("joinerbot.Database")
    async def test_rejoin_suppression_integration(self, mock_db_class):
        """Test rejoin suppression works end-to-end"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.was_recently_connected.return_value = True
        mock_db.get_num_callers.return_value = 2
        mock_db.get_callers.return_value = [(456, "Bob", None), (123, "Alice", None)]

        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(spec=discord.Message)
        Message.set_channel(mock_channel)
        Message._state.last_message = mock_message

        intents = discord.Intents.default()
        with patch.dict(
            "os.environ",
            {
                "JOINERBOT_WATCHED_CHANNEL": "test-voice",
                "JOINERBOT_TARGET_CHANNEL": "test-text",
            },
        ):
            bot = JoinerBot(intents=intents)
            bot.db = mock_db

        # Create voice state change objects for rejoin
        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_before = Mock()
        mock_before.channel = None

        mock_after = Mock()
        mock_after.channel = Mock()
        mock_after.channel.__str__ = Mock(return_value="test-voice")
        mock_after.channel.name = "test-voice"

        with patch.object(bot, "wait_until_ready"):
            await bot.on_voice_state_update(mock_member, mock_before, mock_after)

        mock_db.was_recently_connected.assert_called_with(123, 5)
        mock_db.log_join_leave.assert_called_with(123, "Alice", "join")
        mock_db.add_caller.assert_called_with(123, "Alice")

        self.assertEqual(mock_message.edit.call_count, 2)
        self.assertEqual(len(Message._state.pending_joins), 0)


if __name__ == "__main__":
    unittest.main()
