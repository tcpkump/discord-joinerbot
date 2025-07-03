import discord
from typing import Optional, List, Tuple


class Message:
    _last_message: Optional[discord.Message] = None
    _target_channel: Optional[discord.TextChannel] = None
    
    @classmethod
    def set_channel(cls, channel: discord.TextChannel):
        cls._target_channel = channel
    
    @classmethod
    async def create(cls, member_list: List[Tuple[int, str, any]], callers: int):
        if not cls._target_channel:
            print("Warning: No target channel set for messages")
            return
        
        # Delete previous message if exists
        if cls._last_message:
            try:
                await cls._last_message.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass
        
        message_content = cls._format_message(member_list, callers)
        
        try:
            cls._last_message = await cls._target_channel.send(message_content)
            print(f"Sent message: {message_content}")
        except discord.HTTPException as e:
            print(f"Failed to send message: {e}")
    
    @classmethod
    async def update(cls, member_list: List[Tuple[int, str, any]], callers: int):
        if not cls._target_channel or not cls._last_message:
            return
        
        if callers == 0:
            await cls.delete()
            return
        
        message_content = cls._format_message(member_list, callers)
        
        try:
            await cls._last_message.edit(content=message_content)
            print(f"Updated message: {message_content}")
        except discord.NotFound:
            cls._last_message = None
        except discord.HTTPException as e:
            print(f"Failed to update message: {e}")
    
    @classmethod
    async def delete(cls):
        if cls._last_message:
            try:
                await cls._last_message.delete()
                print("Deleted voice chat message")
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")
            finally:
                cls._last_message = None
    
    @classmethod
    def _format_message(cls, member_list: List[Tuple[int, str, any]], callers: int) -> str:
        usernames = [username for user_id, username, joined_at in member_list]
        
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
