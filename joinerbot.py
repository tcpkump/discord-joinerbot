import discord


class JoinerBot(discord.Client):
    async def on_ready(self):
        if self.user is not None:
            print(f"Logged in as {self.user} (ID: {self.user.id})")
        else:
            print("Bot user not available")

    async def on_voice_state_update(self, member, before, after):
        await self.wait_until_ready()

        # TODO - can we expose as config option?
        watched_channel = "general (hop in!)"

        if (
            str(before.channel) != watched_channel
            and str(after.channel) != watched_channel
        ):
            # Not our channel
            return

        # # Dump out debug info with member name, channel, etc
        # print(f"=== Voice State Update Debug Info ===")
        # print(f"Member: {member.name}#{member.discriminator} (ID: {member.id})")
        # print(f"Guild: {member.guild.name if member.guild else 'None'}")
        #
        # # Before state
        # print(f"Before:")
        # print(f"  Channel: {before.channel.name if before.channel else 'None'}")
        # print(f"  Muted: {before.mute}")
        # print(f"  Deafened: {before.deaf}")
        # print(f"  Self Muted: {before.self_mute}")
        # print(f"  Self Deafened: {before.self_deaf}")
        # print(f"  Suppress: {before.suppress}")
        #
        # # After state
        # print(f"After:")
        # print(f"  Channel: {after.channel.name if after.channel else 'None'}")
        # print(f"  Muted: {after.mute}")
        # print(f"  Deafened: {after.deaf}")
        # print(f"  Self Muted: {after.self_mute}")
        # print(f"  Self Deafened: {after.self_deaf}")
        # print(f"  Suppress: {after.suppress}")

        if str(before.channel) == watched_channel:
            print(f"Action: {member.name} left {before.channel.name}")
        elif str(after.channel) == watched_channel:
            print(f"Action: {member.name} joined {after.channel.name}")

        # Compare member count with state (in db?)
        # If ++
        #   message.create
        # elif -- and not 0
        #   message.update
        # else
        #   message.delete
