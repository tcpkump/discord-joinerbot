import asyncio
import logging
import time
from typing import Any, List, Optional, Tuple

import discord


class MessageState:
    def __init__(self):
        self.last_message: Optional[discord.Message] = None
        self.last_message_time: Optional[float] = None
        self.batch_timer: Optional[asyncio.Task] = None
        self.pending_joins: List[Tuple[int, str, Any]] = []
        self.batch_member_list: Optional[List[Tuple[int, str, Any]]] = None
        self.batch_callers_count: Optional[int] = None
        self.batch_delay: float = 30.0

    def reset(self):
        self.last_message = None
        self.last_message_time = None
        self.batch_timer = None
        self.pending_joins = []
        self.batch_member_list = None
        self.batch_callers_count = None


class Message:
    _state = MessageState()
    _target_channel: Optional[discord.TextChannel] = None
    _logger = logging.getLogger("joinerbot.message")

    @classmethod
    def _batch_timer(cls) -> Optional[asyncio.Task]:
        return cls._state.batch_timer

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
        suppress_notification: bool = False,
    ):
        if not cls._target_channel:
            cls._logger.warning("No target channel set for messages")
            return

        callers = len(member_list)

        if suppress_notification:
            cls._logger.info("Suppressing notification for recent rejoin")
            if cls._state.last_message:
                await cls.update(member_list)
            return

        new_joiner = member_list[-1] if member_list else None

        await cls._add_to_batch(new_joiner, member_list, callers)

    @classmethod
    async def update(cls, member_list: List[Tuple[int, str, Any]]):
        if not cls._target_channel or not cls._state.last_message:
            return

        callers = len(member_list)
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

        cls._state.pending_joins.clear()
        cls._state.batch_member_list = None
        cls._state.batch_callers_count = None
        if cls._state.batch_timer and not cls._state.batch_timer.done():
            cls._state.batch_timer.cancel()
            cls._state.batch_timer = None

    @classmethod
    async def _send_message_now(
        cls, member_list: List[Tuple[int, str, Any]], callers: int
    ):
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
            if callers == 3:
                return f"{usernames[0]}, {usernames[1]}, and {usernames[2]} are in voice chat"
            else:
                return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {usernames[3]} are in voice chat"
        else:
            others_count = callers - 3
            return f"{usernames[0]}, {usernames[1]}, {usernames[2]}, and {others_count} others are in voice chat"

    @classmethod
    def _is_batch_active(cls) -> bool:
        """Check if batch timer is currently active"""
        return bool(cls._state.batch_timer and not cls._state.batch_timer.done())

    @classmethod
    async def _add_to_batch(
        cls,
        new_joiner: Optional[Tuple[int, str, Any]],
        member_list: List[Tuple[int, str, Any]],
        callers: int,
    ):
        """Add a new joiner to batch, starting new batch timer if needed"""
        if new_joiner:
            cls._state.pending_joins.append(new_joiner)

        if not cls._is_batch_active():
            cls._state.batch_timer = asyncio.create_task(
                cls._send_batched_notification(cls._state.batch_delay)
            )

        cls._state.batch_member_list = member_list.copy()
        cls._state.batch_callers_count = callers
