import discord
from discord import app_commands
from discord.ext import commands

class LinkButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Invite me!', style=discord.ButtonStyle.link, url="https://discord.com/api/oauth2/authorize?client_id=1088961569431502932&permissions=2147839040&scope=bot")

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer()

class InviteView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.add_item(LinkButton())

class Invite(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="invite", description="Invite this bot to your server!")
    @app_commands.checks.has_permissions(manage_messages=True, embed_links=True, add_reactions=True,
                                         external_emojis=True, read_message_history=True, read_messages=True,
                                         send_messages=True, use_application_commands=True, use_external_emojis=True)
    async def invite(self, interaction: discord.Interaction):
        if not interaction or interaction.is_expired():
            return

        try:
            await interaction.response.defer()

            self.client.add_to_activity()

            embed = discord.Embed(title=f"Invite TarnishedSouls",
                                  description=f"Thanks in case you want to invite me to your server! 💕\n"
                                              f"*Don't worry!* your progress is universal!")

            await interaction.followup.send(embed=embed, view=InviteView())
        except Exception as e:
            await self.client.send_error_message(e)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Invite(client))
