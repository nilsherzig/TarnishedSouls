import discord
from discord import app_commands
from discord.ext import commands
import db
from Classes.user import User
from Utils.classes import class_selection


class FinishQuest(discord.ui.Button):
    def __init__(self, user, current_quest):
        super().__init__(label='Complete Quest', style=discord.ButtonStyle.success)
        self.user = user
        self.current_quest = current_quest
    async def callback(self, interaction: discord.Interaction):

        if interaction.user.id != int(self.user.get_userId()):
            embed = discord.Embed(title=f"You're not allowed to use this action!",
                                  description="",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)

        await interaction.response.defer()

        # Grant rewards to user
        if self.current_quest.get_quest().get_rune_reward() > 0:
            db.increase_runes_from_user_with_id(idUser=self.user.get_userId(), amount=self.current_quest.get_quest().get_rune_reward())
        if self.current_quest.get_quest().get_location_reward():
            db.update_max_location_from_user(idUser=self.user.get_userId(), idLocation=self.current_quest.get_quest().get_location_reward().get_id())

        # Edit quest message
        message = interaction.message
        edited_embed = message.embeds[0]
        edited_embed.colour = discord.Color.green()

        db.remove_quest_from_user_with_quest_id(idUser=self.user.get_userId(), idQuest=self.current_quest.get_quest().get_id())
        db.add_quest_to_user(idUser=self.user.get_userId(), idQuest=self.current_quest.get_quest().get_id() + 1)

        await interaction.message.edit(embed=edited_embed, view=None)

class QuestView(discord.ui.View):
    def __init__(self, user, current_quest):
        super().__init__()
        self.user = user.update_user()
        self.add_item(FinishQuest(user=user, current_quest=current_quest))

class Quest(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="quest", description="Try completing the quest-line")
    async def quest(self, interaction: discord.Interaction):
        if db.validate_user(interaction.user.id):
            user = User(interaction.user.id)

            current_quest = db.get_user_quest_with_user_id(idUser=user.get_userId())

            if current_quest is None:
                # create new quest rel
                current_quest = db.add_init_quest_to_user(idUser=user.get_userId())

            embed = discord.Embed(title=f"{user.get_userName()}'s current quest:",
                                  description=f"**{current_quest.quest.get_title()}** \n{current_quest.quest.get_description()}")

            embed.add_field(name="Progress:", value=current_quest.get_quest_progress_text(), inline=False)

            if current_quest.has_rewards():
                embed.add_field(name="Rewards:", value=current_quest.get_quest_reward_text(), inline=False)

            if current_quest.is_finished():
                await interaction.response.send_message(embed=embed, view=QuestView(user=user, current_quest=current_quest))
            else:
                await interaction.response.send_message(embed=embed)
        else:
            await class_selection(interaction=interaction)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Quest(client), guild=discord.Object(id=763425801391308901))