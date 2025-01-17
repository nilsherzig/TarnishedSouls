import discord
from discord import app_commands
from discord.ext import commands

import config
import db
from Classes.enemy import Enemy
from Classes.user import User, BASE_HEALING
from Utils import utils
from Utils.classes import class_selection

MAX_USERS = 4
STAMINA_REGEN = 7
STAMINA_COST = 45
HEAVY_STAMINA_COST = 45
RUNE_REWARD_FOR_WAVE = 450


class Fight:
    def __init__(self, users, interaction, turn_index, enemy_index, enemy_list, horde_mode = False):
        self.users = users
        self.interaction = interaction
        self.turn_index = turn_index
        self.enemy_list = enemy_list
        self.enemy_index = enemy_index
        self.horde_mode = horde_mode

    def get_current_enemy(self):
        return self.enemy_list[self.enemy_index]

    def get_is_horde_mode(self):
        return self.horde_mode

    def get_users(self):
        return self.users

    def get_interaction(self):
        return self.interaction

    def get_turn_index(self):
        return self.turn_index

    def get_current_user(self):
        return self.users[self.turn_index]

    def check_phase_change(self, enemy):
        enemy_logic = enemy.get_logic()

        # cuz phase 2 is maximum right now
        if enemy.get_phase() == 2:
            return

        match enemy_logic.get_id():
            case 1:
                # none ( do nothing )
                pass
            case 2:
                # full
                if enemy.get_health() == 0:
                    enemy.set_health(enemy.get_max_health())
                    enemy.increase_phase()
            case 3:
                # half
                if enemy.get_health() <= enemy.get_max_health() / 2:
                    enemy.increase_phase()
            case _:
                raise ValueError(f"ERROR: Invalid enemy logic ID: {enemy_logic.get_id()}")

    async def handle_enemy_death(self, enemy, users, embed):
        # It was a single enemy fight and he died.
        if not self.get_is_horde_mode():
            item_drops = enemy.get_item_rewards_random()
            item_drop_text = str()
            for item in item_drops:
                category_emoji = discord.utils.get(
                    self.interaction.client.get_guild(config.botConfig["hub-server-guild-id"]).emojis,
                    name=item.get_iconCategory())
                item_drop_text += f"Received {category_emoji} **{item.get_name()}** {item.get_count()}x \n"

            embed.colour = discord.Color.green()
            embed.set_field_at(0, name="Enemy action:", value=f"**{enemy.get_name()}** has been *defeated!*",
                               inline=False)
            embed.set_field_at(1, name="Reward:", value=f"Received **{enemy.get_runes()}** runes!\n {item_drop_text}", inline=False)

            # grant rune rewards to all players
            for user in users:
                db.increase_runes_from_user_with_id(user.get_userId(), enemy.get_runes())
                db.check_for_quest_update(idUser=users[0].get_userId(), idEnemy=enemy.get_id())
                db.check_for_quest_update(idUser=users[0].get_userId(), runes=enemy.get_runes())

                # give each user the item drops
                for item in item_drops:
                    db.add_item_to_user(user.get_userId(), item)
                    # update quest progress
                    db.check_for_quest_update(idUser=users[0].get_userId(), item=item)

            if self.get_current_enemy().is_player:
                # it's an invasion
                db.add_inv_death_to_user(idUser=self.get_current_enemy().is_player.get_userId())
                db.add_inv_kill_to_user(idUser=users[0].get_userId())

            if self.interaction.message:
                await self.interaction.message.edit(embed=embed, view=None)
            else:
                await self.interaction.edit_original_response(embed=embed, view=None)

        else:
            # no more enemies to fight!
            if self.enemy_index + 2 > len(self.enemy_list):
                total_rune_reward = int(self.enemy_index * RUNE_REWARD_FOR_WAVE)

                # grant rune reward to each user
                for user in users:
                    db.increase_runes_from_user_with_id(user.get_userId(), total_rune_reward)
                    db.update_max_horde_wave_from_user(idUser=user.get_userId(), wave=self.enemy_index + 1)

                embed.colour = discord.Color.green()
                embed.set_field_at(0, name="Enemy action:", value=f"*You killed every possible enemy!*", inline=False)
                embed.set_field_at(1, name="Reward:", value=f"Received **{total_rune_reward}** runes!", inline=False)

                if self.interaction.message:
                    await self.interaction.message.edit(embed=embed, view=None)
                else:
                    await self.interaction.edit_original_response(embed=embed, view=None)

    async def handle_all_user_death(self, embed, enemy):
        # All users died
        total_rune_reward = int(self.enemy_index * RUNE_REWARD_FOR_WAVE)

        # grant rune reward to each user
        for user in self.users:
            db.increase_runes_from_user_with_id(user.get_userId(), total_rune_reward)
            db.update_max_horde_wave_from_user(idUser=user.get_userId(), wave=self.enemy_index + 1)

        wave_text = str()
        if self.get_is_horde_mode():
            # it's horde mode
            wave_text = f"You've reached wave `{self.enemy_index + 1}`"

        if self.get_current_enemy().is_player:
            # it's an invasion
            db.add_inv_death_to_user(idUser=self.users[0].get_userId())

        embed.colour = discord.Color.red()
        embed.set_field_at(0, name="Enemy action:", value=f"**{enemy.get_name()}** has *defeated all players!*",
                           inline=False)
        embed.set_field_at(1, name="Reward:", value=f"Received **{total_rune_reward}** runes!\n {wave_text}", inline=False)

        if self.interaction.message:
            await self.interaction.message.edit(embed=embed, view=None)
        else:
            await self.interaction.edit_original_response(embed=embed, view=None)

    async def update_fight_battle_view(self, force_idle_move = False):

        # Check for phase change
        self.check_phase_change(self.get_current_enemy())

        # Check for fight end for horde mode
        if self.get_is_horde_mode():
            if self.get_current_enemy().get_health() <= 0 and self.enemy_index + 1 < len(self.enemy_list):
                self.enemy_index = self.enemy_index + 1
                force_idle_move = True

        # reset enemy dodge state
        self.get_current_enemy().reset_dodge()

        # get move from enemy
        enemy_phase = self.get_current_enemy().get_phase()

        # if we force idle, choose idle
        if force_idle_move:
            enemy_move = self.get_current_enemy().get_move_from_type(phase=enemy_phase, move_type=[5])
        else:
            # Check if enemy can use healing ( invasion )
            if self.get_current_enemy().is_player:
                if self.get_current_enemy().flask_amount == 0:
                    enemy_move = self.get_current_enemy().get_move_from_type(phase=enemy_phase, move_type=[1, 2, 4, 5])
                else:
                    enemy_move = self.get_current_enemy().get_move_from_type(phase=enemy_phase, move_type=[1, 2, 3, 4, 5])
            else:
                enemy_move = self.get_current_enemy().get_move_from_type(phase=enemy_phase, move_type=[1, 2, 3, 4, 5])

        enemy, users = enemy_move.execute(enemy=self.get_current_enemy(), users=self.users)
        self.turn_index = turn_index = self.cycle_turn_index(turn_index=self.turn_index, users=users)

        for user in users:
            user.increase_stamina(STAMINA_REGEN)
            user.reset_dodge()

        wave_text = str() if len(self.enemy_list) == 1 else f"`Wave: {self.enemy_index + 1}`"

        flask_emoji = discord.utils.get(
            self.interaction.client.get_guild(config.botConfig["hub-server-guild-id"]).emojis, name='flask')

        # add flask count if enemy is a player ( invasions )
        enemy_flask_count = str()
        if self.get_current_enemy().is_player:
            enemy_flask_count = f"{flask_emoji} {self.get_current_enemy().flask_amount}"

        embed = discord.Embed(title=f"**Fight against `{enemy.get_name()}`**",
                              description=f"{wave_text}\n"
                                          f"`{enemy.get_name()}` {enemy_flask_count}\n"
                                          f"{utils.create_health_bar(enemy.get_health(), enemy.get_max_health(), self.interaction)} `{enemy.get_health()}/{enemy.get_max_health()}` {enemy.get_last_move_text()}")

        embed.add_field(name="Enemy action:", value=f"{enemy_move.get_description()}", inline=False)

        embed.add_field(name="Turn order:", value=f"**<@{users[turn_index].get_userId()}>** please choose an action..",
                        inline=False)


        # create UI for every user
        for user in users:
            embed.add_field(name=f"**`{user.get_userName()}`** {flask_emoji} {user.get_remaining_flasks()}",
                            value=f"{utils.create_health_bar(user.get_health(), user.get_max_health(), self.interaction)} `{user.get_health()}/{user.get_max_health()}` {user.get_last_move_text()}\n"
                                  f"{utils.create_stamina_bar(user.get_stamina(), user.get_max_stamina(), self.interaction)} `{user.get_stamina()}/{user.get_max_stamina()}`",
                            inline=False)
            user.clear_last_move_text()

        enemy.clear_last_move_text()

        # Check for fight end
        if enemy.get_health() <= 0:
            # Enemy died
            await self.handle_enemy_death(enemy=enemy, embed=embed, users=users)
            return

        if len([user for user in users if user.get_health() > 0]) == 0:
            await self.handle_all_user_death(embed=embed, enemy=enemy)
            return

        if self.interaction.message:
            await self.interaction.message.edit(embed=embed, view=FightBattleView(fight=self))
        else:
            if self.interaction.response.is_done():
                await self.interaction.edit_original_response(embed=embed, view=FightBattleView(fight=self))
            else:
                await self.interaction.response.send_message(embed=embed, view=FightBattleView(fight=self))

    def cycle_turn_index(self, turn_index, users):
        party_length = len(users)

        next_index = (turn_index + 1) % party_length
        while users[next_index].get_health() <= 0:
            next_index = (next_index + 1) % party_length
            if next_index == turn_index:
                # Cycle goes back to the original, everyone else died.
                return turn_index

        # Switched turns!

        return next_index

class LeaveButton(discord.ui.Button):
    def __init__(self, users):
        super().__init__(label='Leave Lobby', style=discord.ButtonStyle.danger)
        self.users = users

    async def callback(self, interaction: discord.Interaction):
        if db.validate_user(interaction.user.id):
            if any(int(user.get_userId()) == interaction.user.id for user in self.users):
                await interaction.response.defer()
                for user in self.users:
                    if int(user.get_userId()) == interaction.user.id:
                        self.users.remove(user)
                        break

                # If not solo lobby
                all_user_text = str()

                for user in self.users:
                    all_user_text += f"• {user.get_userName()}\n"

                message = interaction.message
                edited_embed = message.embeds[0]
                edited_embed.set_field_at(index=1, name=f"Players: **{len(self.users)}/{MAX_USERS}**", value=all_user_text, inline=False)

                await interaction.message.edit(embed=edited_embed)
            else:
                embed = discord.Embed(title=f"You're not part of this lobby..",
                                      description="",
                                      colour=discord.Color.red())
                return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)
        else:
            embed = discord.Embed(title=f"Please choose a class first",
                                  description=f"You can do that by tying any command for example `/explore` or `/character`",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)

class JoinButton(discord.ui.Button):
    def __init__(self, users, disabled=False):
        super().__init__(label='Join Lobby', style=discord.ButtonStyle.secondary, disabled=disabled)
        self.users = users

    async def callback(self, interaction: discord.Interaction):
        if db.validate_user(interaction.user.id):
            interaction_user = User(interaction.user.id)

            if any(user.get_userId() == interaction_user.get_userId() for user in self.users):
                embed = discord.Embed(title=f"You're already taking part in this fight..",
                                      description="",
                                      colour=discord.Color.red())
                return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)
            await interaction.response.defer()

            self.users.append(interaction_user)

            # If not solo lobby
            all_user_text = str()

            for user in self.users:
                all_user_text += f"• {user.get_userName()}\n"

            message = interaction.message
            edited_embed = message.embeds[0]
            edited_embed.set_field_at(index=1, name=f"Players: **{len(self.users)}/{MAX_USERS}**", value=all_user_text, inline=False)

            await interaction.message.edit(embed=edited_embed)
        else:
            embed = discord.Embed(title=f"Please choose a class first",
                                  description=f"You can do that by tying any command for example `/explore` or `/character`",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=8)


class StartButton(discord.ui.Button):
    def __init__(self, users, enemy=None, enemy_list=None):
        super().__init__(label='Start!', style=discord.ButtonStyle.primary)
        self.users = users
        self.enemy = enemy
        self.enemy_list = enemy_list

    async def callback(self, interaction: discord.Interaction):
        if len(self.users) == 0:
            embed = discord.Embed(title=f"You're not allowed to start the fight..",
                                  description="",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)
        if str(interaction.user.id) != self.users[0].get_userId():
            embed = discord.Embed(title=f"You're not allowed to start the fight.",
                                  description="",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)
        await interaction.response.defer()

        # single enemy fight
        if self.enemy:
            health_increase = 0

            if len(self.users) > 1:
                health_increase = self.enemy.get_max_health() * ((len(self.users) - 1) * 0.15)

            self.enemy.set_max_health(int(self.enemy.get_max_health() + health_increase))
            self.enemy.overwrite_alL_move_descriptions(self.enemy.get_name())

            fight = Fight(enemy_list=[self.enemy], users=self.users, interaction=interaction, turn_index=0,
                          enemy_index=0)
            await fight.update_fight_battle_view(force_idle_move=True)

        # horde mode ?
        elif self.enemy_list:
            for enemy in self.enemy_list:
                if len(self.users) > 1:
                    health_increase = enemy.get_max_health() * ((len(self.users) - 1) * 0.15)
                    enemy.set_max_health(int(enemy.get_max_health() + health_increase))

                enemy.overwrite_alL_move_descriptions(enemy.get_name())

            fight = Fight(users=self.users, interaction=interaction, turn_index=0, enemy_index=0,
                          enemy_list=self.enemy_list, horde_mode=True)
            await fight.update_fight_battle_view(force_idle_move=True)


class FightSelectView(discord.ui.View):
    def __init__(self, users, visibility):
        super().__init__()

        self.add_item(FightEnemySelect(users=users, visibility=visibility))


class BattleButton(discord.ui.Button):
    def __init__(self, fight, label, style, row):
        super().__init__(label=label, style=style, row=row)
        self.fight = fight

    async def callback(self, interaction: discord.Interaction):
        try:
            if str(interaction.user.id) != self.fight.get_current_user().get_userId():
                embed = discord.Embed(title=f"It's not your turn..",
                                      description="",
                                      colour=discord.Color.orange())
                return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)
            await interaction.response.defer()

            if self.fight.get_current_user().get_health() > 0 and self.fight.get_current_enemy().get_health() > 0:
                self.execute_action()

                await self.fight.update_fight_battle_view()
        except discord.errors.NotFound:
            pass
    def execute_action(self):
        pass


class InstaKillButton(BattleButton):
    def __init__(self, fight):
        super().__init__(fight, label=f"Attack (-99999)", style=discord.ButtonStyle.danger, row=0)

    def execute_action(self):
        self.fight.get_current_enemy().reduce_health(99999)


class AttackButton(BattleButton):
    def __init__(self, fight):
        super().__init__(fight, label=f"Attack (-{fight.get_current_user().get_damage()})",
                         style=discord.ButtonStyle.danger, row=0)

    def execute_action(self):
        if not self.fight.get_current_enemy().get_is_dodging():
            self.fight.get_current_enemy().reduce_health(self.fight.get_current_user().get_damage())

class HeavyAttackButton(BattleButton):
    def __init__(self, fight):
        super().__init__(fight, label=f"Heavy Attack (-{ int(fight.get_current_user().get_damage() * 1.25) })",
                         style=discord.ButtonStyle.danger, row=0)

        # Disable button if not enough stamina
        self.disabled = fight.get_current_user().get_stamina() < HEAVY_STAMINA_COST
    def execute_action(self):
        if not self.fight.get_current_enemy().get_is_dodging():
            self.fight.get_current_enemy().reduce_health(int(self.fight.get_current_user().get_damage() * 1.25))
        self.fight.get_current_user().reduce_stamina(HEAVY_STAMINA_COST)



class HealButton(BattleButton):
    def __init__(self, fight):
        super().__init__(fight, label=f"Heal (+{BASE_HEALING})", style=discord.ButtonStyle.success, row=1)
        # Disable button if no flasks remaining
        self.disabled = fight.get_current_user().get_remaining_flasks() == 0

    def execute_action(self):
        self.fight.get_current_user().increase_health(BASE_HEALING)


class DodgeButton(BattleButton):
    def __init__(self, fight):
        super().__init__(fight, label=f"Dodge", style=discord.ButtonStyle.primary, row=1)

        # Disable button if not enough stamina
        self.disabled = fight.get_current_user().get_stamina() < STAMINA_COST

    def execute_action(self):
        self.fight.get_current_user().dodge(STAMINA_COST)


class FightBattleView(discord.ui.View):
    def __init__(self, fight):
        super().__init__()

        self.add_item(AttackButton(fight=fight))
        self.add_item(HeavyAttackButton(fight=fight))
        self.add_item(HealButton(fight=fight))
        self.add_item(DodgeButton(fight=fight))
        #self.add_item(InstaKillButton(fight=fight))


class FightLobbyView(discord.ui.View):
    def __init__(self, users, visibility, enemy=None, enemy_list=None):
        super().__init__()

        # disable join button if reached max users
        disable = False
        if len(users) == MAX_USERS:
            disable = True

        self.add_item(StartButton(users=users, enemy=enemy, enemy_list=enemy_list))
        self.add_item(JoinButton(users=users, disabled=disable))
        self.add_item(LeaveButton(users=users))


class FightEnemySelect(discord.ui.Select):
    def __init__(self, users, visibility):
        super().__init__(placeholder="Choose an enemy")
        self.users = users
        self.visibility = visibility

        for enemy in db.get_all_enemies_from_location(idLocation=users[0].get_current_location().get_id()):
            if enemy.get_description() and enemy.get_description().upper() == "BOSS":
                self.add_option(label=f"{enemy.get_name()}", description=f"{enemy.get_description().capitalize()}",
                                value=f"{enemy.get_id()}", emoji="💀")
            else:
                self.add_option(label=f"{enemy.get_name()}", description=None, value=f"{enemy.get_id()}")

        # IF NO ENEMIES FOUND, AN ISSUE APPEARS, SHOULD NORMALLY NOT BE THE CASE IN PROD

    async def callback(self, interaction: discord.Interaction):

        if str(interaction.user.id) != self.users[0].get_userId():
            embed = discord.Embed(title=f"You're not allowed to use this action!",
                                  description="",
                                  colour=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=2)

        await interaction.response.defer()

        selected_enemy = Enemy(self.values[0])

        # If solo visible skip lobby scene
        if not self.visibility:
            selected_enemy.overwrite_alL_move_descriptions(selected_enemy.get_name())

            fight = Fight(enemy_list=[selected_enemy], users=self.users, interaction=interaction, turn_index=0, enemy_index=0)
            await fight.update_fight_battle_view(force_idle_move=True)
            return

        # If not solo lobby
        all_user_text = str()

        for user in self.users:
            all_user_text += f"• {user.get_userName()}\n"

        embed = discord.Embed(title=f" {self.users[0].get_userName()} has started a {self.visibility} lobby",
                              description="",
                              colour=discord.Color.orange())

        embed.add_field(name=f"Enemy: **{selected_enemy.get_name()}**", value="")
        embed.add_field(name=f"Players: **1/{MAX_USERS}**", value=all_user_text, inline=False)
        embed.set_footer(text="Enemy health is increased based on player count")

        await interaction.message.edit(embed=embed, view=FightLobbyView(users=self.users, enemy=selected_enemy, visibility=self.visibility, enemy_list=None))


class FightCommand(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="fight", description="Choose an enemy to fight in your current location")
    @app_commands.choices(visibility=[
        app_commands.Choice(name="Public", value="public"),
        app_commands.Choice(name="More soon..", value="public")
    ])
    async def fight(self, interaction: discord.Interaction, visibility: app_commands.Choice[str] = None):
        if not interaction or interaction.is_expired():
            return

        try:
            await interaction.response.defer()

            self.client.add_to_activity()

            if db.validate_user(interaction.user.id):

                user = User(interaction.user.id)
                selected_visibility = None

                if visibility:
                    selected_visibility = visibility.value

                embed = discord.Embed(title=f" {user.get_userName()} is choosing an enemy to fight..",
                                      description=f"The enemies below are all from `{user.get_current_location().get_name()}`\n"
                                                  f"*You can fight different enemies if you change your location with* `/travel`",
                                      colour=discord.Color.orange())

                await interaction.followup.send(embed=embed, view=FightSelectView(users=[user], visibility=selected_visibility))
            else:
                await class_selection(interaction=interaction)
        except Exception as e:
            await self.client.send_error_message(e)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(FightCommand(client))
