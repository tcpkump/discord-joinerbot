# discord-joinerbot

A Discord bot for sending text channel notifications when people join a voice channel.
This is meant to help create inviting public spaces where people can be notified that
their friends are "online" and ready to chat/game.

## Setup

# Enter the Nix development shell
nix develop

# Initialize a PostgreSQL database in your project (first time only)
initdb -D ./postgres_data

# Start PostgreSQL server
pg_ctl -D ./postgres_data -l ./postgres.log -o "-k /tmp" start

# Create a database for your project (first time only)
createdb -h /tmp joinerbot

## Running

# Start PostgreSQL server (for subsequent runs)
pg_ctl -D ./postgres_data -l ./postgres.log -o "-k /tmp" start

# When done testing, stop the server
pg_ctl -D ./postgres_data stop

