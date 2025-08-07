import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from joinerbot import JoinerBot


class TestJoinerBot(unittest.IsolatedAsyncioTestCase):
    """Unit tests for JoinerBot orchestration logic"""

    @patch("joinerbot.Database")
    def setUp(self, mock_database):
        """Set up test bot instance"""
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.messages = True

        self.mock_db = Mock()
        mock_database.return_value = self.mock_db

        with patch.dict(
            "os.environ",
            {
                "JOINERBOT_WATCHED_CHANNEL": "test-voice",
                "JOINERBOT_TARGET_CHANNEL": "test-text",
            },
        ):
            self.bot = JoinerBot(intents=intents)
            self.bot.db = self.mock_db

    def test_get_voice_action_join(self):
        """Test _get_voice_action detects join"""
        before = Mock()
        before.channel = None

        after = Mock()
        after.channel = Mock()
        after.channel.__str__ = Mock(return_value="test-voice")

        action = self.bot._get_voice_action(before, after)
        self.assertEqual(action, "join")

    def test_get_voice_action_leave(self):
        """Test _get_voice_action detects leave"""
        before = Mock()
        before.channel = Mock()
        before.channel.__str__ = Mock(return_value="test-voice")

        after = Mock()
        after.channel = None

        action = self.bot._get_voice_action(before, after)
        self.assertEqual(action, "leave")

    def test_get_voice_action_channel_switch(self):
        """Test _get_voice_action handles channel switches"""
        before = Mock()
        before.channel = Mock()
        before.channel.__str__ = Mock(return_value="other-voice")

        after = Mock()
        after.channel = Mock()
        after.channel.__str__ = Mock(return_value="test-voice")

        action = self.bot._get_voice_action(before, after)
        self.assertEqual(action, "join")

    def test_get_voice_action_irrelevant_channel(self):
        """Test _get_voice_action ignores irrelevant channels"""
        before = Mock()
        before.channel = Mock()
        before.channel.__str__ = Mock(return_value="other-voice")

        after = Mock()
        after.channel = Mock()
        after.channel.__str__ = Mock(return_value="another-voice")

        action = self.bot._get_voice_action(before, after)
        self.assertIsNone(action)

    @patch("joinerbot.Message")
    async def test_handle_leave_with_remaining_callers(self, mock_message_class):
        """Test _handle_leave when other callers remain"""
        mock_message_class.update = AsyncMock()
        mock_message_class.delete = AsyncMock()

        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_before = Mock()
        mock_before.channel.name = "test-voice"

        self.bot.db.get_num_callers.return_value = 2
        self.bot.db.get_callers.return_value = [(456, "Bob", None)]

        await self.bot._handle_leave(mock_member, mock_before)

        self.bot.db.log_join_leave.assert_called_once_with(123, "Alice", "leave")
        self.bot.db.del_caller.assert_called_once_with(123)

        mock_message_class.update.assert_called_once_with([(456, "Bob", None)])
        mock_message_class.delete.assert_not_called()

    @patch("joinerbot.Message")
    async def test_handle_leave_last_caller(self, mock_message_class):
        """Test _handle_leave when last caller leaves"""
        mock_message_class.update = AsyncMock()
        mock_message_class.delete = AsyncMock()

        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_before = Mock()
        mock_before.channel.name = "test-voice"

        self.bot.db.get_num_callers.return_value = 0

        await self.bot._handle_leave(mock_member, mock_before)

        self.bot.db.log_join_leave.assert_called_once_with(123, "Alice", "leave")
        self.bot.db.del_caller.assert_called_once_with(123)

        mock_message_class.delete.assert_called_once()
        mock_message_class.update.assert_not_called()

    @patch("joinerbot.Message")
    async def test_handle_join_first_person(self, mock_message_class):
        """Test _handle_join when first person joins"""
        mock_message_class.update = AsyncMock()
        mock_message_class.create = AsyncMock()

        mock_member = Mock()
        mock_member.id = 123
        mock_member.name = "Alice"
        mock_member.display_name = "Alice"

        mock_after = Mock()
        mock_after.channel.name = "test-voice"

        self.bot.db.was_recently_connected.return_value = False
        self.bot.db.get_num_callers.return_value = 1
        self.bot.db.get_callers.return_value = [(123, "Alice", None)]

        await self.bot._handle_join(mock_member, mock_after)

        self.bot.db.was_recently_connected.assert_called_once_with(123, 5)
        self.bot.db.log_join_leave.assert_called_once_with(123, "Alice", "join")
        self.bot.db.add_caller.assert_called_once_with(123, "Alice")

        mock_message_class.update.assert_not_called()
        mock_message_class.create.assert_called_once_with(
            [(123, "Alice", None)], suppress_notification=False
        )

    @patch("joinerbot.Message")
    async def test_handle_join_second_person(self, mock_message_class):
        """Test _handle_join when second person joins"""
        mock_message_class.update = AsyncMock()
        mock_message_class.create = AsyncMock()

        mock_member = Mock()
        mock_member.id = 456
        mock_member.name = "Bob"
        mock_member.display_name = "Bob"

        mock_after = Mock()
        mock_after.channel.name = "test-voice"

        self.bot.db.was_recently_connected.return_value = False
        self.bot.db.get_num_callers.return_value = 2
        self.bot.db.get_callers.return_value = [
            (123, "Alice", None),
            (456, "Bob", None),
        ]

        await self.bot._handle_join(mock_member, mock_after)

        self.bot.db.was_recently_connected.assert_called_once_with(456, 5)
        self.bot.db.log_join_leave.assert_called_once_with(456, "Bob", "join")
        self.bot.db.add_caller.assert_called_once_with(456, "Bob")

        mock_message_class.update.assert_called_once_with(
            [(123, "Alice", None), (456, "Bob", None)]
        )
        mock_message_class.create.assert_called_once_with(
            [(123, "Alice", None), (456, "Bob", None)], suppress_notification=False
        )

    @patch("joinerbot.Message")
    async def test_handle_join_recent_rejoin_suppressed(self, mock_message_class):
        """Test _handle_join suppresses notification for recent rejoins"""
        mock_message_class.update = AsyncMock()
        mock_message_class.create = AsyncMock()

        mock_member = Mock()
        mock_member.id = 456
        mock_member.name = "Bob"
        mock_member.display_name = "Bob"

        mock_after = Mock()
        mock_after.channel.name = "test-voice"

        self.bot.db.was_recently_connected.return_value = True
        self.bot.db.get_num_callers.return_value = 2
        self.bot.db.get_callers.return_value = [
            (123, "Alice", None),
            (456, "Bob", None),
        ]

        await self.bot._handle_join(mock_member, mock_after)

        self.bot.db.was_recently_connected.assert_called_once_with(456, 5)
        self.bot.db.log_join_leave.assert_called_once_with(456, "Bob", "join")
        self.bot.db.add_caller.assert_called_once_with(456, "Bob")

        mock_message_class.update.assert_called_once_with(
            [(123, "Alice", None), (456, "Bob", None)]
        )
        mock_message_class.create.assert_called_once_with(
            [(123, "Alice", None), (456, "Bob", None)], suppress_notification=True
        )

    async def test_on_voice_state_update_calls_handlers(self):
        """Test on_voice_state_update routes to correct handlers"""
        mock_member = Mock()
        mock_before = Mock()
        mock_after = Mock()

        with (
            patch.object(
                self.bot, "_get_voice_action", return_value="join"
            ) as mock_get_action,
            patch.object(self.bot, "_handle_join") as mock_handle_join,
            patch.object(self.bot, "wait_until_ready"),
        ):
            await self.bot.on_voice_state_update(mock_member, mock_before, mock_after)

            mock_get_action.assert_called_once_with(mock_before, mock_after)
            mock_handle_join.assert_called_once_with(mock_member, mock_after)

    async def test_on_voice_state_update_no_action(self):
        """Test on_voice_state_update does nothing for irrelevant actions"""
        mock_member = Mock()
        mock_before = Mock()
        mock_after = Mock()

        with (
            patch.object(
                self.bot, "_get_voice_action", return_value=None
            ) as mock_get_action,
            patch.object(self.bot, "_handle_join") as mock_handle_join,
            patch.object(self.bot, "_handle_leave") as mock_handle_leave,
            patch.object(self.bot, "wait_until_ready"),
        ):
            await self.bot.on_voice_state_update(mock_member, mock_before, mock_after)

            mock_get_action.assert_called_once_with(mock_before, mock_after)
            mock_handle_join.assert_not_called()
            mock_handle_leave.assert_not_called()


if __name__ == "__main__":
    unittest.main()
