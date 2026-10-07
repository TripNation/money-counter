import discord
from wheel_storage import WheelStorage

COLOR_DEFAULT = 0x5865F2
COLOR_WARNING = 0xFEE75C

def build_signup_embed(
    guild_name: str,
    title: str,
    end_timestamp: int,
    entry_count: int,
    closed: bool = False
) -> discord.Embed:
    color = COLOR_WARNING if not closed else COLOR_DEFAULT
    
    embed = discord.Embed(
        title=f"🎡 {title}",
        color=color
    )
    
    if not closed:
        embed.description = (
            f"**Ready for the spin?** Join the wheel using the buttons below or react with 🎡!\n\n"
            f"⏳ **Ends:** <t:{end_timestamp}:R> (<t:{end_timestamp}:F>)\n"
            f"👥 **Current Entries:** `{entry_count}` players\n"
        )
        embed.set_footer(text="Click '🎡 Join Wheel' or react with 🎡 to enter • Host can run /spin anytime")
    else:
        embed.description = (
            f"🛑 **Signups are now CLOSED!**\n\n"
            f"🏁 **Final Entries:** `{entry_count}` players\n"
            f"Ready for the spin! Run `/spin` or `!spin` to spin the wheel!"
        )
        embed.set_footer(text="Wheel of Pep • Ready to spin!")

    return embed

class SignupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎡 Join Wheel",
        style=discord.ButtonStyle.success,
        custom_id="wheel_of_pep:join"
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        signup = WheelStorage.get_active_signup(interaction.guild_id)
        if signup and signup.get("closed"):
            await interaction.response.send_message("❌ This wheel signup has already closed!", ephemeral=True)
            return

        added = WheelStorage.add_entry(interaction.guild_id, interaction.user.id, interaction.user.display_name)
        entries = WheelStorage.get_entries(interaction.guild_id)
        
        try:
            if signup:
                embed = build_signup_embed(
                    interaction.guild.name,
                    signup.get("title", "Wheel of Pep"),
                    signup.get("end_timestamp", 0),
                    len(entries),
                    closed=signup.get("closed", False)
                )
                await interaction.message.edit(embed=embed)
        except Exception:
            pass

        if added:
            await interaction.response.send_message(
                f"🎉 **{interaction.user.display_name}**, you've been added to the Wheel of Pep! (Total: {len(entries)})",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ You are already entered in this wheel spin! (Total entries: {len(entries)})",
                ephemeral=True
            )

    @discord.ui.button(
        label="❌ Leave",
        style=discord.ButtonStyle.secondary,
        custom_id="wheel_of_pep:leave"
    )
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        signup = WheelStorage.get_active_signup(interaction.guild_id)
        if signup and signup.get("closed"):
            await interaction.response.send_message("❌ This wheel signup is already closed.", ephemeral=True)
            return

        removed = WheelStorage.remove_entry(interaction.guild_id, interaction.user.id)
        entries = WheelStorage.get_entries(interaction.guild_id)

        try:
            if signup:
                embed = build_signup_embed(
                    interaction.guild.name,
                    signup.get("title", "Wheel of Pep"),
                    signup.get("end_timestamp", 0),
                    len(entries),
                    closed=signup.get("closed", False)
                )
                await interaction.message.edit(embed=embed)
        except Exception:
            pass

        if removed:
            await interaction.response.send_message(
                f"👋 You have been removed from the wheel. (Remaining entries: {len(entries)})",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ You were not on the wheel.",
                ephemeral=True
            )

    @discord.ui.button(
        label="👥 View Entries",
        style=discord.ButtonStyle.primary,
        custom_id="wheel_of_pep:view_entries"
    )
    async def view_entries_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        entries = WheelStorage.get_entries(interaction.guild_id)
        if not entries:
            await interaction.response.send_message("ℹ️ No one has entered the wheel yet! Be the first!", ephemeral=True)
            return

        names_list = "\n".join([f"• **{e['name']}**" for e in entries[:40]])
        if len(entries) > 40:
            names_list += f"\n*...and {len(entries) - 40} more!*"

        embed = discord.Embed(
            title=f"📋 Wheel Entries ({len(entries)} total)",
            description=names_list,
            color=COLOR_DEFAULT
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
