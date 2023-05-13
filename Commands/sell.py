import discord
from discord import app_commands
from discord.ext import commands

import config
import db
from Classes.user import User
from Utils.classes import class_selection


class SellButton(discord.ui.Button):
    def __init__(self, user, item, amount, disabled=False):
        super().__init__(label=f"Sell {amount}x ({item.get_price() * amount} runes)", style=discord.ButtonStyle.danger,
                         disabled=disabled)
        self.user = user
        self.item = item
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != int(self.user.get_userId()):
                embed = discord.Embed(title=f"You're not allowed to use this action!",
                                      description="",
                                      colour=discord.Color.red())
                return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)

            await interaction.response.defer()

            sell_item = db.get_item_from_user_with_id_rel(idUser=self.user.get_userId(), idRel=self.item.get_idRel())
            if sell_item:
                if sell_item.get_count() >= self.amount:
                    db.decrease_item_from_user(idUser=self.user.get_userId(), relId=sell_item.get_idRel(),
                                               amount=self.amount)
                    db.increase_runes_from_user_with_id(self.user.get_userId(), self.item.get_price() * self.amount)
                    db.check_for_quest_update(idUser=self.user.get_userId(), runes=self.item.get_price() * self.amount)
                    message = interaction.message
                    edited_embed = message.embeds[0]
                    edited_embed.colour = discord.Color.green()

                    if sell_item.get_count() - self.amount > 0:
                        edited_embed.title = f"**{sell_item.get_name()}** {sell_item.get_count() - self.amount}x `id: {sell_item.get_idRel()}`"
                        await interaction.message.edit(embed=edited_embed,
                                                       view=SellView(user=self.user, item=self.item))
                    else:
                        # completely sold
                        edited_embed.title = f"**{sell_item.get_name()}**"
                        edited_embed.description = "Completely sold this item!"
                        await interaction.message.edit(embed=edited_embed, view=None)
                else:
                    message = interaction.message
                    edited_embed = message.embeds[0]
                    edited_embed.colour = discord.Color.red()
                    edited_embed.set_footer(text="This item no longer exists with that item quantity..")

                    await interaction.message.edit(embed=edited_embed, view=None)
            else:
                message = interaction.message
                edited_embed = message.embeds[0]
                edited_embed.colour = discord.Color.red()
                edited_embed.set_footer(text="This item no longer exists..")

                await interaction.message.edit(embed=edited_embed, view=None)
        except discord.errors.NotFound:
            pass


class SellView(discord.ui.View):

    def __init__(self, user, item):
        super().__init__()
        self.user = user.update_user()
        item = db.get_item_from_user_with_id_rel(user.get_userId(), item.get_idRel())
        self.add_item(SellButton(user=user, item=item, amount=1, disabled=False if item.get_count() >= 1 else True))
        self.add_item(SellButton(user=user, item=item, amount=5, disabled=False if item.get_count() >= 5 else True))


class Sell(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="sell", description="Sell one of your items")
    @app_commands.describe(item_id="Enter an item id")
    @app_commands.rename(item_id='id')
    async def sell(self, interaction: discord.Interaction, item_id: int = None):
        try:
            await interaction.response.defer()

            self.client.add_to_activity()

            if db.validate_user(interaction.user.id):
                user = User(interaction.user.id)
                item = db.get_item_from_user_with_id_rel(user.get_userId(), item_id)
                if item is None:
                    embed = discord.Embed(title=f"I couldn't find the correct Item..",
                                          description=f"You can find your Item Id inside your inventory. Access it with `/inventory`",
                                          colour=discord.Color.red())
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    embed = discord.Embed(title=f"**{item.get_name()}** {item.get_count()}x `id: {item.get_idRel()}`",
                                          description=f"Do you want to sell this item?")

                    if item.get_icon_url() is not None and item.get_icon_url() != 'None':
                        embed.set_thumbnail(url=f"{item.get_icon_url()}")

                    value_name = str()

                    match item.get_item_type():
                        case 'Weapon':
                            embed.add_field(name="", value=f"**Statistics:** \n"
                                                           f"`Damage:` **{item.get_total_value(user)}** `Weight:` **{item.get_weight()}**",
                                            inline=False)
                        case 'Armor':
                            embed.add_field(name="", value=f"**Statistics:** \n"
                                                           f"`Armor:` **{item.get_total_value(user)}** `Weight:` **{item.get_weight()}**",
                                            inline=False)

                    embed.colour = discord.Color.orange()

                    await interaction.followup.send(embed=embed, view=SellView(user=user, item=item))
            else:
                await class_selection(interaction=interaction)
        except Exception as e:
            await self.client.send_error_message(e)

    @app_commands.command(name="sell_all", description="Sell all except equipped of your items")
    @app_commands.choices(choices=[
        app_commands.Choice(name="Weapons", value="weapons"),
        app_commands.Choice(name="Armor", value="armor"),
        app_commands.Choice(name="Items", value="items")
    ])
    async def sell_all(self, interaction: discord.Interaction, choices: app_commands.Choice[str]):
        match choices.value:
            case "weapons":
                print("test")
                return
        embed = discord.Embed(title="Sell all items")
        embed.description = "Below are your equipped items listed"

        user = User(userId=interaction.user.id)
        items = []
        if user.get_weapon(): items.append(user.get_weapon())
        if user.get_head(): items.append(user.get_head())
        if user.get_chest(): items.append(user.get_chest())
        if user.get_gauntlet(): items.append(user.get_gauntlet())
        if user.get_legs(): items.append(user.get_legs())

        for item in items:
            level_text = str()
            if item.get_level() > 0:
                level_text = f"+{item.get_level()}"

            extra_val_text = str() if item.get_extra_value() == 0 else f"(*+{item.get_extra_value()}*)"

            level_val_text = str() if item.get_level_value() == 0 else f"(**+{item.get_level_value()}**)"
            if item.get_item_type() == "weapon":
                embed.add_field(name=f"{item.get_name()} {level_text} `id: {item.get_idRel()}`",
                                value=f"**Statistics:** \n"
                                      f"`Damage:` **{item.get_value_with_scaling(user)}** {extra_val_text} {level_val_text}`Weight:` **{item.get_weight()}**\n"
                                      f"**Requirements:** \n"
                                      f"{item.get_requirement_text()}\n"
                                      f"**Scaling:** \n"
                                      f"{item.get_scaling_text()}")
            else:
                embed.add_field(name=f"{item.get_name()} {level_text} `id: {item.get_idRel()}`",)

        await interaction.response.send_message(embed=embed)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Sell(client), guild=discord.Object(id=config.botConfig["hub-server-guild-id"]))
