import logging
import os

import discord

from database import Database
from message import Message


class JoinerBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = Database()
        self.watched_channel = os.environ.get("JOINERBOT_WATCHED_CHANNEL")
        self.target_channel = os.environ.get("JOINERBOT_TARGET_CHANNEL")
        self.logger = logging.getLogger("joinerbot")

    async def on_ready(self):
        if self.user is not None:
            self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

            # Set up message target channel
            if self.guilds:
                for guild in self.guilds:
                    for ch in guild.channels:
                        if (
                            isinstance(ch, discord.TextChannel)
                            and ch.name == self.target_channel
                        ):
                            Message.set_channel(ch)
                            self.logger.info(
                                f"Message target channel set to: {ch.name}"
                            )
                            break
        else:
            self.logger.error("Bot user not available")

    async def on_voice_state_update(self, member, before, after):
        await self.wait_until_ready()

        action = self._get_voice_action(before, after)
        if not action:
            return

        if action == "leave":
            await self._handle_leave(member, before)
        else:  # join
            await self._handle_join(member, after)

    def _get_voice_action(self, before, after):
        """Determine what voice action occurred"""
        before_watched = str(before.channel) == self.watched_channel
        after_watched = str(after.channel) == self.watched_channel

        if not before_watched and not after_watched:
            return None  # Not our channel
        elif before_watched and not after_watched:
            return "leave"
        elif after_watched and not before_watched:
            return "join"
        return None

    async def _handle_leave(self, member, before):
        """Handle member leaving the watched channel"""
        self.logger.info(f"Action: {member.name} left {before.channel.name}")
        self.db.log_join_leave(member.id, member.display_name, "leave")
        self.db.del_caller(member.id)

        callers = self.db.get_num_callers()
        if callers > 0:
            member_list = self.db.get_callers()
            await Message.update(member_list, callers)
        else:
            await Message.delete()

    async def _handle_join(self, member, after):
        """Handle member joining the watched channel"""
        self.logger.info(f"Action: {member.name} joined {after.channel.name}")

        # Check if this is a recent rejoin (within 5 minutes)
        is_recent_rejoin = self.db.was_recently_connected(member.id, 5)

        self.db.log_join_leave(member.id, member.display_name, "join")
        self.db.add_caller(member.id, member.display_name)

        # Get current state
        callers = self.db.get_num_callers()
        member_list = self.db.get_callers()
        is_first_person = callers == 1

        # Always update existing message first if not first person
        if not is_first_person:
            await Message.update(member_list, callers)

        # Send notification (batched or queued)
        await Message.create(
            member_list,
            callers,
            is_first_person=is_first_person,
            suppress_notification=is_recent_rejoin,
        )
