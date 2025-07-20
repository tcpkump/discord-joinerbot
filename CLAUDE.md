# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This project uses `uv` for Python dependency management:

```bash
# Run the bot locally (requires PostgreSQL)
uv run python main.py

# Run all tests (discovers all test_*.py files automatically)
uv run python -m unittest discover -s . -p "test_*.py" -v

# Run specific test file
uv run python -m unittest test_message.py -v
uv run python -m unittest test_batching_logic.py -v

# Run single test method
uv run python -m unittest test_message.TestMessage.test_format_message_single_user -v

# Type checking
basedpyright  # Run type checking (uses Nix-provided version)

# Install dependencies
uv sync

# Docker development (includes PostgreSQL)
docker compose up --build
docker compose down
```

## Architecture Overview

This Discord bot monitors voice channel joins/leaves and sends smart batched notifications to a text channel. The system handles reconnections gracefully and implements sophisticated message queuing.

### Core Components

**JoinerBot (`joinerbot.py`)**
- Discord.py client that handles voice state events
- Integrates Database and Message components
- Implements rejoin suppression logic (5-minute window)
- Main event handler: `on_voice_state_update()`

**Message (`message.py`)**
- Singleton-like class managing Discord text notifications
- Implements 30-second batching for first-time joins
- 10-minute queuing system for subsequent notifications
- State management via class variables (not thread-safe by design)
- Key methods: `create()`, `update()`, `delete()`

**Database (`database.py`)**
- PostgreSQL integration with psycopg3
- Tracks current callers and join/leave history
- Auto-creates tables on initialization
- Key methods: `add_caller()`, `del_caller()`, `was_recently_connected()`

### Message Flow Logic

1. **First Join**: Starts 30-second batch timer, collects additional joiners
2. **Batch Send**: After 30 seconds, sends single notification for all batched users
3. **Subsequent Joins**: 
   - If <10 minutes since last message: queues individual notification
   - If >10 minutes: starts new 30-second batch
4. **Rejoin Detection**: Suppresses notifications if user joined within 5 minutes
5. **Message Management**: Always maintains single message, deletes previous when sending new

### Database Schema

```sql
-- Active voice channel participants
CREATE TABLE callers (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255) NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Complete join/leave audit trail
CREATE TABLE join_leave_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('join', 'leave')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Configuration

Required environment variables:
- `DISCORD_TOKEN`: Bot authentication token
- `JOINERBOT_WATCHED_CHANNEL`: Voice channel name to monitor
- `JOINERBOT_TARGET_CHANNEL`: Text channel name for notifications
- `DATABASE_URL`: PostgreSQL connection string (optional, defaults to localhost)

### Testing Strategy

- `test_message.py`: Core Message class functionality, formatting, rate limiting
- `test_batching_logic.py`: New batching behavior, rejoin suppression, cleanup
- All tests use unittest with async support and mocking of Discord APIs
- Database tests require running PostgreSQL instance

### Key Design Patterns

- **State Machine**: Message class manages notification states (batching, queuing, idle)
- **Template Method**: `_format_message()` handles different user count scenarios
- **Facade**: JoinerBot coordinates between Database, Message, and Discord APIs
- **Singleton Behavior**: Message class uses class variables for shared state