import os

import discord
from dotenv import load_dotenv

from joinerbot import JoinerBot


def main():
    # Load configuration from environment variables/.env file
    _ = load_dotenv()
    DISCORD_TOKEN = str(os.environ.get("DISCORD_TOKEN"))

    intents = discord.Intents.default()
    intents.voice_states = True
    intents.messages = True

    client = JoinerBot(intents=intents)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
