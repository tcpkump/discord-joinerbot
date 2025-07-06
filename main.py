import logging
import os
import sys

import discord
from dotenv import load_dotenv

from joinerbot import JoinerBot


def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "DISCORD_TOKEN",
        "JOINERBOT_WATCHED_CHANNEL",
        "JOINERBOT_TARGET_CHANNEL",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        print(
            f"Error: Missing required environment variables: {', '.join(missing_vars)}"
        )
        sys.exit(1)


def main():
    # Load configuration from environment variables/.env file
    _ = load_dotenv()

    validate_environment()

    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    discord_log_level = getattr(logging, log_level)
    logging.getLogger("discord.gateway").setLevel(discord_log_level)
    logging.getLogger("discord.client").setLevel(discord_log_level)

    DISCORD_TOKEN = str(os.environ.get("DISCORD_TOKEN"))

    intents = discord.Intents.default()
    intents.voice_states = True
    intents.messages = True

    client = JoinerBot(intents=intents)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
