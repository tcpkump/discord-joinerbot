#!/usr/bin/env python

import os

import discord
from dotenv import load_dotenv


class JoinerBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_voice_state_update(self, member, before, after):
        await self.wait_until_ready()

        watched_channel = "general (hop in!)"

        if (
            str(before.channel) != watched_channel
            and str(after.channel) != watched_channel
        ):
            # Not our channel
            return

        # # Dump out debug info with member name, channel, etc
        # print(f"=== Voice State Update Debug Info ===")
        # print(f"Member: {member.name}#{member.discriminator} (ID: {member.id})")
        # print(f"Guild: {member.guild.name if member.guild else 'None'}")
        #
        # # Before state
        # print(f"Before:")
        # print(f"  Channel: {before.channel.name if before.channel else 'None'}")
        # print(f"  Muted: {before.mute}")
        # print(f"  Deafened: {before.deaf}")
        # print(f"  Self Muted: {before.self_mute}")
        # print(f"  Self Deafened: {before.self_deaf}")
        # print(f"  Suppress: {before.suppress}")
        #
        # # After state
        # print(f"After:")
        # print(f"  Channel: {after.channel.name if after.channel else 'None'}")
        # print(f"  Muted: {after.mute}")
        # print(f"  Deafened: {after.deaf}")
        # print(f"  Self Muted: {after.self_mute}")
        # print(f"  Self Deafened: {after.self_deaf}")
        # print(f"  Suppress: {after.suppress}")

        if str(before.channel) == watched_channel:
            print(f"Action: {member.name} left {before.channel.name}")
        elif str(after.channel) == watched_channel:
            print(f"Action: {member.name} joined {after.channel.name}")

        # Compare member count with state (in db?)
        # If ++
        #   message.create
        # elif -- and not 0
        #   message.update
        # else
        #   message.delete


# TODO -- do I need all this?
# class Message:
#     def create(self, member):
#         # anytime a member joins
#
#         # Switch case
#         # 1 - simple join message
#         # 2,3,4 - list all members in message
#         # 5+ - add ellipses
#
#         # and delete last message
#         pass
#
#     def update(self, member):
#         # used when members LEAVE channel
#         # existing join message gets updated rather than new ones being made
#
#         # Find last bot message:
#         # Switch case
#         # 1 - simple join message
#         # 2,3,4 - list all members in message
#         # 5+ - ellipses
#         pass
#
#     def delete(self, member):
#         # called from create() or when last member in channel leaves
#         # may not be needed tbh
#         pass


def main():
    # Load configuration from environment variables/.env file
    _ = load_dotenv()
    DISCORD_TOKEN = str(os.environ.get("DISCORD_TOKEN"))

    intents = discord.Intents.default()
    intents.voice_states = True

    client = JoinerBot(intents=intents)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
