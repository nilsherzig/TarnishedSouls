import platform
import time

import discord
from discord.ext import commands


import config
import db
import logging
from colorama import Back, Fore, Style

MY_GUILD = discord.Object(id=763425801391308901)

class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='.', intents=discord.Intents().all())

        self.cogsList = ["Commands.stats", "Commands.upgrade_stats"]

    async def setup_hook(self):
        for ext in self.cogsList:
            await self.load_extension(ext)

        await self.tree.sync(guild=MY_GUILD)

    async def on_ready(self):
        prfx = (Back.BLACK + Fore.GREEN + time.strftime("%H:%M:%S UTC", time.gmtime()) + Back.RESET + Fore.WHITE + Style.BRIGHT)
        print(f"{prfx} Logged in as {Fore.YELLOW} {self.user.name}")
        print(f"{prfx} Bot ID {Fore.YELLOW} {str(self.user.id)}")
        print(f"{prfx} Discord Version {Fore.YELLOW} {discord.__version__}")
        print(f"{prfx} Python Version {Fore.YELLOW} {str(platform.python_version())}")
        print(f"{prfx} Bot Version 0.1")
        await db.init_database()

        logging.warning("Now logging..")


client = Client()
client.run(config.botConfig["token"])
