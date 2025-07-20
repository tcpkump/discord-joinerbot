import asyncio
import logging
import time
from typing import Any, List, Optional, Tuple

import discord


class Message:
    _last_message: Optional[discord.Message] = None
    _target_channel: Optional[discord.TextChannel] = None
    _logger = logging.getLogger("joinerbot.message")
    _last_message_time: Optional[float] = None
    _queued_task: Optional[asyncio.Task] = None
    _pending_update: bool = False
    _batch_timer: Optional[asyncio.Task] = None
    _pending_joins: List[Tuple[int, str, Any]] = []

    @classmethod
    def set_channel(cls, channel: discord.TextChannel):
        cls._target_channel = channel

    @classmethod
    async def create(
        cls,
        member_list: List[Tuple[int, str, Any]],
        callers: int,
        is_first_person: bool = False,
        suppress_notification: bool = False,
    ):
        if not cls._target_channel:
            cls._logger.warning("No target channel set for messages")
            return

        current_time = time.time()

        # Handle suppressed notifications (rejoins)
        if suppress_notification:
            cls._logger.info("Suppressing notification for recent rejoin")
            # Still update the message but don't send new notifications
            if cls._last_message:
                await cls.update(member_list, callers)
            return

        # If this is the first person or 10+ minutes have passed, start 30-second batch timer
        if (
            is_first_person
            or cls._last_message_time is None
            or (current_time - cls._last_message_time) >= 600
        ):
            # Add new joiner to pending list
            new_joiner = member_list[-1]  # Latest joiner
            cls._pending_joins.append(new_joiner)

            # If no batch timer running, start one
            if not cls._batch_timer or cls._batch_timer.done():
                cls._batch_timer = asyncio.create_task(
                    cls._send_batched_notification(30)
                )
        elif (current_time - cls._last_message_time) < 600:
            # Within 10-minute window - queue for later (only new members)
            new_joiner = member_list[-1]  # Latest joiner
            await cls._queue_message([new_joiner], 1, current_time)
        else:
            # If batch timer is running (someone joined within 30 seconds), add to batch
            if cls._batch_timer and not cls._batch_timer.done():
                new_joiner = member_list[-1]  # Latest joiner
                cls._pending_joins.append(new_joiner)

    @classmethod
    async def update(cls, member_list: List[Tuple[int, str, Any]], callers: int):
        if not cls._target_channel or not cls._last_message:
            return

        if callers == 0:
            await cls.delete()
            return

        message_content = cls._format_message(member_list, callers)

        try:
            await cls._last_message.edit(content=message_content)
            cls._logger.info(f"Updated message: {message_content}")
        except discord.NotFound:
            cls._last_message = None
        except discord.HTTPException as e:
            cls._logger.error(f"Failed to update message: {e}")

    @classmethod
    async def delete(cls):
        if cls._last_message:
            try:
                await cls._last_message.delete()
                cls._logger.info("Deleted voice chat message")
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                cls._logger.error(f"Failed to delete message: {e}")
            finally:
                cls._last_message = None

        # Clear pending joins when everyone leaves
        cls._pending_joins.clear()
        if cls._batch_timer and not cls._batch_timer.done():
            cls._batch_timer.cancel()

    @classmethod
    async def _send_message_now(
        cls, member_list: List[Tuple[int, str, Any]], callers: int
    ):
        # Delete previous message if exists
        if cls._last_message:
            try:
                await cls._last_message.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

        message_content = cls._format_message(member_list, callers)

        if cls._target_channel is None:
            cls._logger.error("Target channel not set")
            return

        try:
            cls._last_message = await cls._target_channel.send(message_content)
            cls._logger.info(f"Sent message: {message_content}")
        except discord.HTTPException as e:
            cls._logger.error(f"Failed to send message: {e}")

    @classmethod
    async def _queue_message(
        cls, member_list: List[Tuple[int, str, Any]], callers: int, current_time: float
    ):
        # Cancel any existing queued task
        if cls._queued_task and not cls._queued_task.done():
            cls._queued_task.cancel()

        # Calculate delay until 10 minutes after last message
        if cls._last_message_time is None:
            cls._logger.error("Last message time not set")
            return
        delay = 600 - (current_time - cls._last_message_time)
        cls._pending_update = True

        cls._logger.info(f"Queuing message for {delay:.1f} seconds from now")

        # Create new queued task
        cls._queued_task = asyncio.create_task(
            cls._delayed_send(member_list, callers, delay)
        )

    @classmethod
    async def _delayed_send(
        cls, member_list: List[Tuple[int, str, Any]], callers: int, delay: float
    ):
        try:
            await asyncio.sleep(delay)
            if cls._pending_update and member_list:  # Only send if we have new members
                await cls._send_message_now(member_list, callers)
                cls._last_message_time = time.time()
                cls._pending_update = False
        except asyncio.CancelledError:
            cls._logger.info("Queued message was cancelled")
            raise

    @classmethod
    async def _send_batched_notification(cls, delay: float):
        """Send notification after batch delay"""
        try:
            await asyncio.sleep(delay)
            if cls._pending_joins:
                # Remove duplicates while preserving order
                unique_joins = list(
                    {member[0]: member for member in cls._pending_joins}.values()
                )
                member_count = len(unique_joins)
                await cls._send_message_now(unique_joins, member_count)
                cls._last_message_time = time.time()
                cls._pending_joins.clear()
        except asyncio.CancelledError:
            cls._logger.info("Batch notification was cancelled")
            raise

    @classmethod
    def _format_message(
        cls, member_list: List[Tuple[int, str, Any]], callers: int
    ) -> str:
        usernames = [username for _, username, _ in member_list]

        if callers == 1 and usernames:
            return f"{usernames[0]} joined voice chat"
        elif 2 <= callers <= 4 and usernames:
            if len(usernames) == 2:
                return f"{usernames[0]} and {usernames[1]} are in voice chat"
            elif len(usernames) == 3:
                return f"{usernames[0]}, {usernames[1]}, and {usernames[2]} are in voice chat"
            elif len(usernames) == 4:
                return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {usernames[3]} are in voice chat"
        elif callers >= 5 and usernames:
            others_count = callers - 3
            return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {others_count} others are in voice chat"

        return f"{callers} people are in voice chat"
