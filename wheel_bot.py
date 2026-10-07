import asyncio
import io
import logging
import random
import time
from typing import Optional, Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from wheel_duration import parse_duration, format_duration
from wheel_storage import WheelStorage
from wheel_views import SignupView, build_signup_embed
import wheel_renderer

logger = logging.getLogger("WheelOfPep")

COLOR_DEFAULT = 0x5865F2
COLOR_SUCCESS = 0x57F287
COLOR_WARNING = 0xFEE75C
COLOR_SPIN = 0xEB459E
COLOR_ERROR = 0xED4245

# Whitelisted User IDs authorized to manage the wheel
AUTHORIZED_USERS = {
    879477525879857202,   # TripNation
    1462829122769125417,  # Hector-PEP Man
    270679104620068864,   # Madytiggs
    532144104688320512,   # Tara
}

def is_authorized_user(user: discord.User | discord.Member, guild: discord.Guild = None) -> bool:
    if not user:
        return False
    if user.id in AUTHORIZED_USERS:
        return True
    if guild and user.id == guild.owner_id:
        return True
    if hasattr(user, "roles"):
        for role in user.roles:
            if role.name.strip().lower() == "owner":
                return True
    return False

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

wheel_bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# -------------------------------------------------------------
# Background Task: Check for Expired Signups
# -------------------------------------------------------------
@tasks.loop(seconds=10)
async def check_signups_task():
    try:
        now = int(time.time())
        active_signups = WheelStorage.get_all_active_signups()
        
        for guild_id, signup in active_signups:
            end_ts = signup.get("end_timestamp", 0)
            if now >= end_ts and not signup.get("closed", False):
                WheelStorage.mark_signup_closed(guild_id)
                channel_id = signup.get("channel_id")
                message_id = signup.get("message_id")
                
                channel = wheel_bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await wheel_bot.fetch_channel(channel_id)
                    except Exception:
                        continue

                entries = WheelStorage.get_entries(guild_id)
                count = len(entries)

                if channel and message_id:
                    try:
                        msg = await channel.fetch_message(message_id)
                        guild_name = msg.guild.name if msg.guild else "Server"
                        closed_embed = build_signup_embed(
                            guild_name,
                            signup.get("title", "Wheel of Pep"),
                            end_ts,
                            count,
                            closed=True
                        )
                        await msg.edit(embed=closed_embed, view=None)
                    except Exception as e:
                        logger.warning(f"Failed to edit signup message: {e}")

                if channel:
                    try:
                        await channel.send(
                            f"⏰ **Time is up!** Signups for **{signup.get('title', 'Wheel of Pep')}** have officially closed!\n"
                            f"👥 **Total Participants:** `{count}`\n"
                            f"👉 Run `/spin` or `!spin` when you are ready to spin the wheel!"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send expiration announcement: {e}")
    except Exception as e:
        logger.error(f"Error in check_signups_task: {e}", exc_info=True)

@check_signups_task.before_loop
async def before_check_signups():
    await wheel_bot.wait_until_ready()

# -------------------------------------------------------------
# Bot Events
# -------------------------------------------------------------
@wheel_bot.event
async def on_ready():
    logger.info(f"Logged in as {wheel_bot.user} (ID: {wheel_bot.user.id})")
    wheel_bot.add_view(SignupView())

    if not check_signups_task.is_running():
        check_signups_task.start()

    try:
        for guild in wheel_bot.guilds:
            try:
                wheel_bot.tree.clear_commands(guild=guild)
                await wheel_bot.tree.sync(guild=guild)
            except Exception:
                pass
        synced = await wheel_bot.tree.sync()
        logger.info(f"Successfully synced {len(synced)} application slash commands cleanly.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")

@wheel_bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == wheel_bot.user.id or not payload.guild_id:
        return

    signup = WheelStorage.get_active_signup(payload.guild_id)
    if not signup or signup.get("closed"):
        return

    if payload.message_id == signup.get("message_id"):
        guild = wheel_bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        added = WheelStorage.add_entry(payload.guild_id, member.id, member.display_name)
        if added:
            logger.info(f"Added {member.display_name} via reaction to guild {payload.guild_id}")
            try:
                channel = wheel_bot.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    entries = WheelStorage.get_entries(payload.guild_id)
                    embed = build_signup_embed(
                        guild.name,
                        signup.get("title", "Wheel of Pep"),
                        signup.get("end_timestamp", 0),
                        len(entries),
                        closed=False
                    )
                    await msg.edit(embed=embed)
            except Exception:
                pass

@wheel_bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if not payload.guild_id:
        return

    signup = WheelStorage.get_active_signup(payload.guild_id)
    if not signup or signup.get("closed"):
        return

    if payload.message_id == signup.get("message_id"):
        guild = wheel_bot.get_guild(payload.guild_id)
        if not guild:
            return

        removed = WheelStorage.remove_entry(payload.guild_id, payload.user_id)
        if removed:
            logger.info(f"Removed user {payload.user_id} via reaction remove in guild {payload.guild_id}")
            try:
                channel = wheel_bot.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    entries = WheelStorage.get_entries(payload.guild_id)
                    embed = build_signup_embed(
                        guild.name,
                        signup.get("title", "Wheel of Pep"),
                        signup.get("end_timestamp", 0),
                        len(entries),
                        closed=False
                    )
                    await msg.edit(embed=embed)
            except Exception:
                pass

# -------------------------------------------------------------
# Wheel Spin Helper Function
# -------------------------------------------------------------
async def execute_wheel_spin(
    send_target, 
    guild: discord.Guild, 
    source: Literal["entries", "server"] = "entries"
):
    candidates = []

    if source == "server":
        for m in guild.members:
            if not m.bot:
                candidates.append({"id": m.id, "name": m.display_name})
        if not candidates:
            async for m in guild.fetch_members(limit=500):
                if not m.bot:
                    candidates.append({"id": m.id, "name": m.display_name})
    else:
        candidates = WheelStorage.get_entries(guild.id)

    if not candidates:
        if source == "entries":
            embed = discord.Embed(
                title="⚠️ The Wheel is Empty!",
                description=(
                    "No one is entered on the wheel yet!\n\n"
                    "👉 Run `/signup` (e.g. `/signup duration:30m`) to let people join!\n"
                    "👉 Or use `/spin source:server` to spin among all server members!"
                ),
                color=COLOR_WARNING
            )
            await send_target(embed=embed)
        else:
            await send_target(content="❌ No members found to spin!")
        return

    winner_entry = random.choice(candidates)
    winner_name = winner_entry["name"]
    winner_id = winner_entry["id"]

    render_pool = [c["name"] for c in candidates]
    if len(render_pool) > 20:
        other_names = [c["name"] for c in candidates if c["name"] != winner_name]
        random.shuffle(other_names)
        render_pool = [winner_name] + other_names[:15]
        random.shuffle(render_pool)

    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, wheel_renderer.render_spinning_wheel_gif, render_pool, winner_name)
    file = discord.File(fp=buf, filename="wheel_spin.gif")

    spin_embed = discord.Embed(
        title="🎡 WHEEL OF PEP IS SPINNING!",
        description="🌀 *Click-click-click-click...* The wheel is in motion! Watch it spin live below!",
        color=COLOR_SPIN
    )
    spin_embed.set_image(url="attachment://wheel_spin.gif")
    spin_embed.set_footer(text=f"Spinning with {len(candidates)} total participants • Wheel of Pep")

    msg = await send_target(embed=spin_embed, file=file)

    await asyncio.sleep(3.5)

    WheelStorage.record_winner(guild.id, winner_id, winner_name)

    winner_embed = discord.Embed(
        title="🎉 WE HAVE A WINNER! 🎉",
        description=(
            f"# 🏆 <@{winner_id}>\n\n"
            f"The Wheel of Pep landed on **{winner_name}**!\n"
            f"Congratulations! 🎊🎈"
        ),
        color=COLOR_SUCCESS
    )
    winner_embed.set_image(url="attachment://wheel_spin.gif")
    winner_embed.set_footer(text=f"Spun with {len(candidates)} total participants • Wheel of Pep")

    try:
        await msg.edit(content=f"🎉 Congratulations <@{winner_id}>!", embed=winner_embed)
    except Exception:
        await msg.channel.send(content=f"🎉 Congratulations <@{winner_id}>!", embed=winner_embed)

# -------------------------------------------------------------
# Slash Commands
# -------------------------------------------------------------

@wheel_bot.tree.command(name="signup", description="Start a wheel signup message with a duration timer")
@app_commands.describe(
    duration="How long the signup lasts (e.g. 30m, 1h, 1d, 2 hours)",
    title="Custom title/topic for the wheel spin (optional)"
)
async def slash_signup(
    interaction: discord.Interaction,
    duration: str,
    title: Optional[str] = "Wheel of Pep Giveaway"
):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return

    if not is_authorized_user(interaction.user, interaction.guild):
        await interaction.response.send_message("❌ You are not authorized to start a wheel signup.", ephemeral=True)
        return

    sec = parse_duration(duration)
    if not sec or sec < 10:
        await interaction.response.send_message(
            "❌ Invalid duration! Please provide a time like `30m`, `1h`, `1d`, `2 hours`, or `45s` (minimum 10 seconds).",
            ephemeral=True
        )
        return

    end_ts = int(time.time()) + sec
    readable_dur = format_duration(sec)

    await interaction.response.defer()
    WheelStorage.clear_entries(interaction.guild_id)

    embed = build_signup_embed(
        interaction.guild.name,
        title,
        end_ts,
        entry_count=0,
        closed=False
    )
    view = SignupView()
    msg = await interaction.followup.send(embed=embed, view=view)

    try:
        await msg.add_reaction("🎡")
    except Exception:
        pass

    WheelStorage.set_active_signup(
        interaction.guild_id,
        {
            "channel_id": interaction.channel_id,
            "message_id": msg.id,
            "title": title,
            "end_timestamp": end_ts,
            "duration_str": readable_dur,
            "closed": False
        }
    )

@wheel_bot.tree.command(name="spin", description="Spin the wheel! Pick a winner from entered participants or server members")
@app_commands.describe(
    source="Who to spin: 'entries' for people who signed up, or 'server' for everyone in the server"
)
async def slash_spin(
    interaction: discord.Interaction,
    source: Literal["entries", "server"] = "entries"
):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return

    if not is_authorized_user(interaction.user, interaction.guild):
        await interaction.response.send_message("❌ You are not authorized to spin the wheel.", ephemeral=True)
        return

    await interaction.response.defer()

    async def send_fn(**kwargs):
        return await interaction.followup.send(**kwargs)

    await execute_wheel_spin(send_fn, interaction.guild, source=source)

@wheel_bot.tree.command(name="reset", description="Reset the wheel and clear all entered names")
async def slash_reset(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return

    if not is_authorized_user(interaction.user, interaction.guild):
        await interaction.response.send_message("❌ You are not authorized to reset the wheel.", ephemeral=True)
        return

    cleared = WheelStorage.clear_entries(interaction.guild_id)
    WheelStorage.clear_active_signup(interaction.guild_id)

    embed = discord.Embed(
        title="🔄 Wheel of Pep Reset!",
        description=(
            f"Successfully cleared **{cleared}** entries from the wheel.\n\n"
            "The wheel is now fresh and ready for a new spin!\n"
            "• Use `/signup <duration>` to start a new signup\n"
            "• Or use `/spin source:server` to spin all server members"
        ),
        color=COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

@wheel_bot.tree.command(name="entries", description="View current list of participants on the wheel")
async def slash_entries(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        return

    entries = WheelStorage.get_entries(interaction.guild_id)
    if not entries:
        await interaction.response.send_message("ℹ️ No one is currently on the wheel. Run `/signup` to let people enter!", ephemeral=True)
        return

    names_list = "\n".join([f"{i+1}. **{e['name']}**" for i, e in enumerate(entries[:40])])
    if len(entries) > 40:
        names_list += f"\n*...plus {len(entries) - 40} more players!*"

    embed = discord.Embed(
        title=f"📋 Wheel of Pep - Current Entries ({len(entries)})",
        description=names_list,
        color=COLOR_DEFAULT
    )
    await interaction.response.send_message(embed=embed)

@wheel_bot.tree.command(name="wheel_add", description="Manually add a user to the wheel")
@app_commands.describe(user="The member to add to the wheel")
async def slash_wheel_add(interaction: discord.Interaction, user: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ Server only.", ephemeral=True)
        return

    if not is_authorized_user(interaction.user, interaction.guild):
        await interaction.response.send_message("❌ You are not authorized to manage wheel entries.", ephemeral=True)
        return

    added = WheelStorage.add_entry(interaction.guild_id, user.id, user.display_name)
    total = len(WheelStorage.get_entries(interaction.guild_id))
    if added:
        await interaction.response.send_message(f"✅ Added **{user.display_name}** to the wheel! (Total: {total})")
    else:
        await interaction.response.send_message(f"ℹ️ **{user.display_name}** is already on the wheel. (Total: {total})")

@wheel_bot.tree.command(name="wheel_remove", description="Manually remove a user from the wheel")
@app_commands.describe(user="The member to remove from the wheel")
async def slash_wheel_remove(interaction: discord.Interaction, user: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("❌ Server only.", ephemeral=True)
        return

    if not is_authorized_user(interaction.user, interaction.guild):
        await interaction.response.send_message("❌ You are not authorized to manage wheel entries.", ephemeral=True)
        return

    removed = WheelStorage.remove_entry(interaction.guild_id, user.id)
    total = len(WheelStorage.get_entries(interaction.guild_id))
    if removed:
        await interaction.response.send_message(f"✅ Removed **{user.display_name}** from the wheel. (Remaining: {total})")
    else:
        await interaction.response.send_message(f"ℹ️ **{user.display_name}** was not on the wheel.")

@wheel_bot.tree.command(name="wheel_help", description="Show help and instructions for Wheel of Pep")
async def slash_wheel_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎡 Wheel of Pep - Command Guide",
        description="Welcome to Wheel of Pep! Easily spin a wheel for giveaways, server games, or random picks.",
        color=COLOR_DEFAULT
    )
    embed.add_field(
        name="⏳ 1. Create a Signup Message",
        value=(
            "**`/signup <duration> [title]`**\n"
            "Sets up a signup message where users can click **🎡 Join Wheel** or react with **🎡** to enter.\n"
            "• Examples: `/signup duration:30m`, `/signup duration:1d title:VIP Giveaway`\n"
            "• When the time expires, signups automatically close!"
        ),
        inline=False
    )
    embed.add_field(
        name="🎡 2. Spin the Wheel",
        value=(
            "**`/spin`**\n"
            "Spins the wheel with a suspenseful live animation and colorful rendered graphic!\n"
            "• `/spin` - Spins among entered players\n"
            "• `/spin source:server` - Spins among all members in the Discord server"
        ),
        inline=False
    )
    embed.add_field(
        name="🔄 3. Reset the Wheel",
        value=(
            "**`/reset`**\n"
            "Clears all names from the wheel so you can start a brand new spin."
        ),
        inline=False
    )
    embed.add_field(
        name="📋 4. View or Manage Entries",
        value=(
            "• **`/entries`** - View who is currently entered\n"
            "• **`/wheel_add @user`** - Manually add someone\n"
            "• **`/wheel_remove @user`** - Manually remove someone"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed)
