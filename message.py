import asyncio
import logging
import time
from typing import Any, List, Optional, Tuple

import discord


class MessageState:
    def __init__(self):
        self.last_message: Optional[discord.Message] = None
        self.last_message_time: Optional[float] = None
        self.queued_task: Optional[asyncio.Task] = None
        self.pending_update: bool = False
        self.batch_timer: Optional[asyncio.Task] = None
        self.pending_joins: List[Tuple[int, str, Any]] = []
        self.batch_member_list: Optional[List[Tuple[int, str, Any]]] = None
        self.batch_callers_count: Optional[int] = None
        self.batch_delay: float = 30.0

    def reset(self):
        self.last_message = None
        self.last_message_time = None
        self.queued_task = None
        self.pending_update = False
        self.batch_timer = None
        self.pending_joins = []
        self.batch_member_list = None
        self.batch_callers_count = None


class Message:
    _state = MessageState()
    _target_channel: Optional[discord.TextChannel] = None
    _logger = logging.getLogger("joinerbot.message")

    # Class properties for test access - using class attributes for simplicity
    @classmethod
    def _batch_timer(cls) -> Optional[asyncio.Task]:
        return cls._state.batch_timer

    @classmethod
    def _queued_task(cls) -> Optional[asyncio.Task]:
        return cls._state.queued_task

    @classmethod
    def _pending_joins(cls) -> List[Tuple[int, str, Any]]:
        return cls._state.pending_joins

    @classmethod
    def _last_message(cls) -> Optional[discord.Message]:
        return cls._state.last_message

    @classmethod
    def _set_last_message(cls, value: Optional[discord.Message]):
        cls._state.last_message = value

    @classmethod
    def _last_message_time(cls) -> Optional[float]:
        return cls._state.last_message_time

    @classmethod
    def _set_last_message_time(cls, value: Optional[float]):
        cls._state.last_message_time = value

    @classmethod
    def _pending_update(cls) -> bool:
        return cls._state.pending_update

    @classmethod
    def set_channel(cls, channel: discord.TextChannel):
        cls._target_channel = channel

    @classmethod
    def set_batch_delay(cls, delay: float):
        """Set the batch delay for testing purposes"""
        cls._state.batch_delay = delay

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
            if cls._state.last_message:
                await cls.update(member_list, callers)
            return

        new_joiner = member_list[-1] if member_list else None

        if cls._should_start_batch(is_first_person, current_time):
            await cls._start_batch(new_joiner, member_list, callers)
        elif cls._should_queue(current_time):
            if new_joiner:
                await cls._queue_message([new_joiner], 1, current_time)
        elif cls._is_batch_active():
            await cls._add_to_batch(new_joiner, member_list, callers)

    @classmethod
    async def update(cls, member_list: List[Tuple[int, str, Any]], callers: int):
        if not cls._target_channel or not cls._state.last_message:
            return

        if callers == 0:
            await cls.delete()
            return

        message_content = cls._format_message(member_list, callers)

        try:
            await cls._state.last_message.edit(content=message_content)
            cls._logger.info(f"Updated message: {message_content}")
        except discord.NotFound:
            cls._state.last_message = None
        except discord.HTTPException as e:
            cls._logger.error(f"Failed to update message: {e}")

    @classmethod
    async def delete(cls):
        if cls._state.last_message:
            try:
                await cls._state.last_message.delete()
                cls._logger.info("Deleted voice chat message")
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                cls._logger.error(f"Failed to delete message: {e}")
            finally:
                cls._state.last_message = None

        # Clear all state when everyone leaves
        cls._state.pending_joins.clear()
        cls._state.batch_member_list = None
        cls._state.batch_callers_count = None
        if cls._state.batch_timer and not cls._state.batch_timer.done():
            cls._state.batch_timer.cancel()

    @classmethod
    async def _send_message_now(
        cls, member_list: List[Tuple[int, str, Any]], callers: int
    ):
        # Delete previous message if exists
        if cls._state.last_message:
            try:
                await cls._state.last_message.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

        message_content = cls._format_message(member_list, callers)

        if cls._target_channel is None:
            cls._logger.error("Target channel not set")
            return

        try:
            cls._state.last_message = await cls._target_channel.send(message_content)
            cls._logger.info(f"Sent message: {message_content}")
        except discord.HTTPException as e:
            cls._logger.error(f"Failed to send message: {e}")

    @classmethod
    async def _queue_message(
        cls, member_list: List[Tuple[int, str, Any]], callers: int, current_time: float
    ):
        # Cancel any existing queued task
        if cls._state.queued_task and not cls._state.queued_task.done():
            cls._state.queued_task.cancel()

        # Calculate delay until 10 minutes after last message
        if cls._state.last_message_time is None:
            cls._logger.error("Last message time not set")
            return
        delay = 600 - (current_time - cls._state.last_message_time)
        cls._state.pending_update = True

        cls._logger.info(f"Queuing message for {delay:.1f} seconds from now")

        # Create new queued task
        cls._state.queued_task = asyncio.create_task(
            cls._delayed_send(member_list, callers, delay)
        )

    @classmethod
    async def _delayed_send(
        cls, member_list: List[Tuple[int, str, Any]], callers: int, delay: float
    ):
        try:
            await asyncio.sleep(delay)
            if cls._state.pending_update and member_list:
                await cls._send_message_now(member_list, callers)
                cls._state.last_message_time = time.time()
                cls._state.pending_update = False
        except asyncio.CancelledError:
            cls._logger.info("Queued message was cancelled")
            raise

    @classmethod
    async def _send_batched_notification(cls, delay: float):
        """Send notification after batch delay"""
        try:
            await asyncio.sleep(delay)
            if cls._state.pending_joins and cls._state.batch_member_list is not None:
                await cls._send_message_now(
                    cls._state.batch_member_list, cls._state.batch_callers_count or 0
                )
                cls._state.last_message_time = time.time()
                cls._state.pending_joins.clear()
                cls._state.batch_member_list = None
                cls._state.batch_callers_count = None
        except asyncio.CancelledError:
            cls._logger.info("Batch notification was cancelled")
            raise

    @classmethod
    def _format_message(
        cls, member_list: List[Tuple[int, str, Any]], callers: int
    ) -> str:
        usernames = [username for _, username, _ in member_list]

        if not usernames:
            return f"{callers} people are in voice chat"

        if callers == 1:
            return f"{usernames[0]} joined voice chat"
        elif callers == 2:
            return f"{usernames[0]} and {usernames[1]} are in voice chat"
        elif callers in (3, 4):
            # Join all names with commas, "and" before last
            if callers == 3:
                return f"{usernames[0]}, {usernames[1]}, and {usernames[2]} are in voice chat"
            else:  # callers == 4
                return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {usernames[3]} are in voice chat"
        else:  # callers >= 5
            others_count = callers - 3
            return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {others_count} others are in voice chat"

    @classmethod
    def _should_start_batch(cls, is_first_person: bool, current_time: float) -> bool:
        """Determine if we should start a new batch timer"""
        return (
            is_first_person
            or cls._state.last_message_time is None
            or (current_time - cls._state.last_message_time) >= 600
        )

    @classmethod
    def _should_queue(cls, current_time: float) -> bool:
        """Determine if we should queue the message for later"""
        return (
            cls._state.last_message_time is not None
            and (current_time - cls._state.last_message_time) < 600
        )

    @classmethod
    def _is_batch_active(cls) -> bool:
        """Check if batch timer is currently active"""
        return bool(cls._state.batch_timer and not cls._state.batch_timer.done())

    @classmethod
    async def _start_batch(
        cls,
        new_joiner: Optional[Tuple[int, str, Any]],
        member_list: List[Tuple[int, str, Any]],
        callers: int,
    ):
        """Start a new batch timer and add the joiner"""
        if new_joiner:
            cls._state.pending_joins.append(new_joiner)

        if not cls._is_batch_active():
            cls._state.batch_timer = asyncio.create_task(
                cls._send_batched_notification(cls._state.batch_delay)
            )

        cls._state.batch_member_list = member_list.copy()
        cls._state.batch_callers_count = callers

    @classmethod
    async def _add_to_batch(
        cls,
        new_joiner: Optional[Tuple[int, str, Any]],
        member_list: List[Tuple[int, str, Any]],
        callers: int,
    ):
        """Add a new joiner to existing batch"""
        if new_joiner:
            cls._state.pending_joins.append(new_joiner)
        cls._state.batch_member_list = member_list.copy()
        cls._state.batch_callers_count = callers
