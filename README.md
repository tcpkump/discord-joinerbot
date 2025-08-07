# discord-joinerbot

A Discord bot for sending text channel notifications when people join a voice channel.
This is meant to help create inviting public spaces where people can be notified that
their friends are "online" and ready to chat/game.

## Features

- **Smart Batching**: When any user joins, starts or joins existing 30-second batch timer to collect multiple joins into a single notification
- **Comprehensive Notifications**: Messages show all current voice channel users, not just new joiners
- **Single Message Management**: Maintains one notification message, deleting previous ones when sending updates
- **Rejoin Suppression**: Users who disconnect have a 5-minute grace period to rejoin without triggering spam notifications
- **PostgreSQL Integration**: Tracks join/leave history and current voice channel participants with full audit trail

## Local Development Setup

### Option 1: Using Docker Compose (Recommended)

1. **Create environment file:**
   ```bash
   echo "DISCORD_TOKEN=your_discord_bot_token_here" > .env
   ```

2. **Start the services:**
   ```bash
   docker compose up --build
   ```

3. **Stop the services:**
   ```bash
   docker compose down
   ```

### Option 2: Using Nix

1. **Enter the Nix development shell:**
   ```bash
   nix develop
   ```

2. **Initialize PostgreSQL database (first time only):**
   ```bash
   initdb -D ./postgres_data
   ```

3. **Start PostgreSQL server:**
   ```bash
   pg_ctl -D ./postgres_data -l ./postgres.log -o "-k /tmp" start
   ```

4. **Create database (first time only):**
   ```bash
   createdb -h /tmp joinerbot
   ```

5. **Run the bot:**
   ```bash
   uv run python main.py
   ```

6. **Stop PostgreSQL when done:**
   ```bash
   pg_ctl -D ./postgres_data stop
   ```

### Option 3: Docker Only

1. **Build the image:**
   ```bash
   docker build -t discord-joinerbot .
   ```

2. **Run with external database:**
   ```bash
   docker run -e DISCORD_TOKEN=your_token -e DATABASE_URL=postgresql://user:pass@host:port/dbname discord-joinerbot
   ```

## Configuration

The bot requires these environment variables:
- `DISCORD_TOKEN`: Your Discord bot token
- `JOINERBOT_WATCHED_CHANNEL`: Voice channel for JoinerBot to watch
- `JOINERBOT_TARGET_CHANNEL`: Text channel for JoinerBot to post in
- `LOG_LEVEL`: Logging level (optional, defaults to INFO)
- `DATABASE_URL`: PostgreSQL connection string (optional, defaults to localhost)
