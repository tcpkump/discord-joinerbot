#!/usr/bin/env python

import os

import discord
from dotenv import load_dotenv

from joinerbot import JoinerBot

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
