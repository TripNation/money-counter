import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from storage import storage
from card_generator import generate_progress_card

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("COMMAND_PREFIX", "!")

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


def is_owner_or_has_role(user: discord.User | discord.Member, guild: discord.Guild) -> bool:
    """
    Strictly allows ONLY:
    1. The literal Server Owner
    2. Users with a role specifically named 'Owner'
    """
    if not guild or not isinstance(user, discord.Member):
        return False
    # Check 1: Actual Server Owner
    if user.id == guild.owner_id:
        return True
    # Check 2: Has a role named 'Owner' (case-insensitive)
    for role in user.roles:
        if role.name.strip().lower() == "owner":
            return True
    return False


def build_card_file(data: dict, subtitle: str = None) -> discord.File:
    """Generates the clean card image with green progress bar."""
    goal = float(data.get("goal", 500.0))
    current = float(data.get("current", 0.0))
    title = data.get("title", "COMMUNITY FUNDING GOAL")
    currency = data.get("currency", "$")

    card_buffer = generate_progress_card(
        current=current,
        goal=goal,
        title=title,
        currency_symbol=currency,
        subtitle=subtitle
    )
    return discord.File(fp=card_buffer, filename="goal_card.png")


async def post_or_update_goal_at_bottom(
    thank_you_content: str = None,
    just_reached: bool = False,
    subtitle: str = None
) -> bool:
    """
    Ensures that any @donor thank-you message appears ABOVE the goal,
    and the Goal Bar is ALWAYS kept at the very bottom of the channel.
    """
    data = storage.get_data()
    channel_id = data.get("primary_channel_id")
    message_id = data.get("primary_message_id")

    if not channel_id:
        return False

    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return False

    # If we have a thank-you message, post it above and put goal card at bottom
    if thank_you_content:
        await channel.send(thank_you_content)

        if message_id:
            try:
                old_msg = await channel.fetch_message(message_id)
                if old_msg:
                    await old_msg.delete()
            except Exception:
                pass

        card_file = build_card_file(data, subtitle=subtitle)
        new_msg = await channel.send(file=card_file)
        storage.set_message_id(new_msg.id)

        if just_reached:
            await channel.send("@everyone 🚨 🎉 **WE HAVE REACHED OUR GOAL!** 🎉 🚨")

        return True

    # If no thank-you message, edit existing message in place
    card_file = build_card_file(data, subtitle=subtitle)
    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            if msg:
                await msg.edit(attachments=[card_file])
                if just_reached:
                    await channel.send("@everyone 🚨 🎉 **WE HAVE REACHED OUR GOAL!** 🎉 🚨")
                return True
        except (discord.NotFound, discord.HTTPException):
            pass

    # Fallback: send fresh message at bottom
    new_msg = await channel.send(file=card_file)
    storage.set_message_id(new_msg.id)
    if just_reached:
        await channel.send("@everyone 🚨 🎉 **WE HAVE REACHED OUR GOAL!** 🎉 🚨")
    return True


# ==========================================
# INTERACTIVE MODALS & VIEWS FOR /update
# ==========================================

class UpdateGoalModal(discord.ui.Modal, title="Update Goal Target"):
    goal_input = discord.ui.TextInput(
        label="Goal Target Amount ($)",
        placeholder="e.g. 500 or 1000",
        required=True
    )
    reset_input = discord.ui.TextInput(
        label="Reset current cash to $0? (yes/no)",
        placeholder="no",
        default="no",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can update the goal.", ephemeral=True)
            return

        try:
            new_goal = float(self.goal_input.value.replace("$", "").replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid goal amount.", ephemeral=True)
            return

        if new_goal <= 0:
            await interaction.response.send_message("❌ Goal must be greater than 0.", ephemeral=True)
            return

        reset_cash = self.reset_input.value.strip().lower() in ["yes", "y", "true"]
        storage.set_goal(goal=new_goal, reset_current=reset_cash)

        await post_or_update_goal_at_bottom(subtitle="Goal amount updated")
        await interaction.response.send_message("✅ Goal target updated!", ephemeral=True)


class AddCashAmountModal(discord.ui.Modal):
    def __init__(self, member: discord.User | discord.Member = None):
        title = f"Add Cash ({member.display_name})" if member else "Add Cash to Goal"
        super().__init__(title=title[:45])
        self.member = member

        self.amount_input = discord.ui.TextInput(
            label="Cash Amount to Add ($)",
            placeholder="e.g. 25.00 or 100",
            required=True
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can add cash.", ephemeral=True)
            return

        try:
            amt = float(self.amount_input.value.replace("$", "").replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid cash amount.", ephemeral=True)
            return

        if amt <= 0:
            await interaction.response.send_message("❌ Amount must be greater than 0.", ephemeral=True)
            return

        data, just_reached = storage.add_money(amt)
        currency = data.get("currency", "$")

        thank_you_text = None
        donor_name = "Contributor"
        if self.member:
            donor_name = self.member.display_name
            thank_you_text = (
                f"Thank you {self.member.mention} for donating **{currency}{amt:,.2f}** to help us reach our goal! 🎉"
            )

        subtitle = f"Latest: +{currency}{amt:,.2f} from {donor_name}"

        await post_or_update_goal_at_bottom(
            thank_you_content=thank_you_text,
            just_reached=just_reached,
            subtitle=subtitle
        )

        await interaction.response.send_message(
            f"✅ Recorded {currency}{amt:,.2f}! Thank you message posted above the goal.",
            ephemeral=True
        )


class SetCashModal(discord.ui.Modal, title="Set Current Cash Value"):
    amount_input = discord.ui.TextInput(
        label="Exact Current Cash ($)",
        placeholder="e.g. 250.00",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can set cash.", ephemeral=True)
            return

        try:
            new_val = float(self.amount_input.value.replace("$", "").replace(",", "").strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid cash amount.", ephemeral=True)
            return

        if new_val < 0:
            await interaction.response.send_message("❌ Amount cannot be negative.", ephemeral=True)
            return

        data, just_reached = storage.set_current_cash(new_val)
        currency = data.get("currency", "$")
        subtitle = f"Cash set to {currency}{new_val:,.2f}"

        await post_or_update_goal_at_bottom(just_reached=just_reached, subtitle=subtitle)
        await interaction.response.send_message(f"✅ Cash set to {currency}{new_val:,.2f}!", ephemeral=True)


class MemberSelectView(discord.ui.View):
    """View containing the searchable UserSelect dropdown to pick any member in the server."""
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Search & select member (type name to filter)...")
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can use this.", ephemeral=True)
            return
        selected_member = select.values[0]
        await interaction.response.send_modal(AddCashAmountModal(member=selected_member))

    @discord.ui.button(label="Skip Member (Anonymous / Manual)", style=discord.ButtonStyle.secondary)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can use this.", ephemeral=True)
            return
        await interaction.response.send_modal(AddCashAmountModal(member=None))


class UpdateMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="🎯 Update Goal Amount", style=discord.ButtonStyle.primary, emoji="🎯")
    async def update_goal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can use this.", ephemeral=True)
            return
        await interaction.response.send_modal(UpdateGoalModal())

    @discord.ui.button(label="➕ Add Cash (Tag Member)", style=discord.ButtonStyle.success, emoji="💵")
    async def add_cash_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can use this.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Select or search for the member who contributed:",
            view=MemberSelectView(),
            ephemeral=True
        )

    @discord.ui.button(label="✏️ Set Exact Cash", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def set_cash_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_owner_or_has_role(interaction.user, interaction.guild):
            await interaction.response.send_message("❌ Only the Server Owner or members with the Owner role can use this.", ephemeral=True)
            return
        await interaction.response.send_modal(SetCashModal())


# ==========================================
# BOT EVENTS
# ==========================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})", flush=True)
    try:
        from keep_alive import start_web_server
        await start_web_server()
    except Exception as e:
        print(f"[KeepAlive] {e}", flush=True)

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global slash commands.", flush=True)
        for guild in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
                print(f"Instantly synced commands to {guild.name}", flush=True)
            except Exception as ge:
                pass
    except Exception as e:
        print(f"Sync error: {e}", flush=True)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="goal | /update"))
    print("Bot is ready and listening!", flush=True)


# ==========================================
# COMMANDS (RESTRICTED TO OWNER & OWNER ROLE)
# ==========================================

@bot.tree.command(name="assignserver", description="Post the official Goal Message in this channel and link it.")
@app_commands.default_permissions(manage_guild=True)
async def slash_assignserver(interaction: discord.Interaction):
    data = storage.get_data()
    card_file = build_card_file(data)
    
    await interaction.response.send_message(file=card_file)
    msg = await interaction.original_response()
    storage.set_primary(interaction.guild_id, interaction.channel_id, msg.id)


@bot.tree.command(name="update", description="Open the menu to update Goal or add Cash with searchable member picker.")
@app_commands.default_permissions(manage_guild=True)
async def slash_update(interaction: discord.Interaction):
    view = UpdateMenuView()
    await interaction.response.send_message("Select an option to update:", view=view, ephemeral=True)


# ==========================================
# PREFIX VERSIONS (!assignserver & !update)
# ==========================================

@bot.command(name="assignserver")
async def cmd_assignserver(ctx: commands.Context):
    if not is_owner_or_has_role(ctx.author, ctx.guild):
        await ctx.send("❌ Only the **Server Owner** or members with the **Owner** role can use this command.")
        return
    data = storage.get_data()
    card_file = build_card_file(data)
    msg = await ctx.send(file=card_file)
    storage.set_primary(ctx.guild.id, ctx.channel.id, msg.id)


@bot.command(name="update")
async def cmd_update(ctx: commands.Context):
    if not is_owner_or_has_role(ctx.author, ctx.guild):
        await ctx.send("❌ Only the **Server Owner** or members with the **Owner** role can use this command.")
        return
    view = UpdateMenuView()
    await ctx.send("Select an option to update:", view=view)


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN is missing!", flush=True)
        exit(1)

    wheel_token = os.getenv("WHEEL_BOT_TOKEN")
    if wheel_token:
        print("[Combined Launcher] WHEEL_BOT_TOKEN detected! Starting both Money Counter and Wheel of Pep bots...", flush=True)
        import asyncio
        from wheel_bot import wheel_bot

        async def run_both_bots():
            await asyncio.gather(
                bot.start(TOKEN),
                wheel_bot.start(wheel_token)
            )

        asyncio.run(run_both_bots())
    else:
        bot.run(TOKEN)
