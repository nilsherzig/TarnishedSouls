import random

import discord
from discord import app_commands
from discord.ext import commands

import db
from Classes.enemy import Enemy
from Classes.user import User, BASE_HEALING
from Commands.fight import Fight
from Utils.classes import class_selection


class InvadeCommand(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="invade", description="Invade your current location to fight another player!")
    async def invade(self, interaction: discord.Interaction):
        if not interaction or interaction.is_expired():
            return

        try:
            await interaction.response.defer()

            self.client.add_to_activity()

            if db.validate_user(interaction.user.id):
                user = User(interaction.user.id)

                # Get a random user except himself
                enemy_user = db.get_all_user_ids_with_similar_level(user=user, range=15)

                # we couldn't find a player in that skill range so do it again but wider threshold
                if not enemy_user:
                    enemy_user = db.get_all_user_ids_with_similar_level(user=user, range=25)
                if not enemy_user:
                    enemy_user = db.get_all_user_ids_with_similar_level(user=user, range=50)
                if not enemy_user:
                    enemy_user = db.get_all_user_ids_with_similar_level(user=user, range=100)
                if not enemy_user:
                    enemy_user = db.get_all_user_ids_with_similar_level(user=user, range=400)

                if enemy_user:
                    enemy_user = User(random.choice(enemy_user))

                # Check if user has weapon equipped
                if not enemy_user.get_weapon():
                    invasionIdEnemy = db.get_enemy_id_from_name(f"invasion_unarmed")
                else:
                    # Get enemy template from weapon name
                    invasionIdEnemy = db.get_enemy_id_from_name(f"invasion_{enemy_user.get_weapon().get_iconCategory()}")

                if not invasionIdEnemy:
                    print(f"Couldn't find the invasion enemy with name: (invasion_{enemy_user.get_weapon().get_iconCategory()})")
                    return

                enemy_template = Enemy(idEnemy=invasionIdEnemy)
                enemy_template.is_player = enemy_user
                enemy_template.overwrite_moves_with_damage()
                enemy_template.overwrite_moves_with_healing(BASE_HEALING)
                enemy_template.overwrite_alL_move_descriptions(enemy_user.get_userName())
                enemy_template.set_max_health(enemy_user.get_max_health())
                enemy_template.set_name(enemy_user.get_userName())
                enemy_template.set_runes(int(enemy_user.get_max_health() / 2))
                enemy_template.flask_amount = enemy_user.get_remaining_flasks()

                fight = Fight(enemy_list=[enemy_template], users=[user], interaction=interaction, turn_index=0, enemy_index=0)
                await fight.update_fight_battle_view(force_idle_move=True)

            else:
                await class_selection(interaction=interaction)
        except Exception as e:
            await self.client.send_error_message(e)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(InvadeCommand(client))
