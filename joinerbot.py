import discord

from database import Database
from message import Message


class JoinerBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = Database()
        self.watched_channel = "general (hop in!)"
        self.target_channel = "general-notifications"

    async def on_ready(self):
        if self.user is not None:
            print(f"Logged in as {self.user} (ID: {self.user.id})")

            # Set up message target channel
            if self.guilds:
                for guild in self.guilds:
                    for ch in guild.channels:
                        if (
                            isinstance(ch, discord.TextChannel)
                            and ch.name == self.target_channel
                        ):
                            Message.set_channel(ch)
                            print(f"Message target channel set to: {ch.name}")
                            break
        else:
            print("Bot user not available")

    async def on_voice_state_update(self, member, before, after):
        await self.wait_until_ready()

        if (
            str(before.channel) != self.watched_channel
            and str(after.channel) != self.watched_channel
        ):
            # Not our channel
            return

        if str(before.channel) == self.watched_channel:
            print(f"Action: {member.name} left {before.channel.name}")
            self.db.log_join_leave(member.id, member.display_name, 'leave')
            self.db.del_caller(member.id)
            callers = self.db.get_num_callers()
            if callers != 0:
                member_list = self.db.get_callers()
                await Message.update(member_list, callers)
            else:
                await Message.delete()
        elif str(after.channel) == self.watched_channel:
            print(f"Action: {member.name} joined {after.channel.name}")
            self.db.log_join_leave(member.id, member.display_name, 'join')
            self.db.add_caller(member.id, member.display_name)
            callers = self.db.get_num_callers()
            member_list = self.db.get_callers()
            await Message.create(member_list, callers)
