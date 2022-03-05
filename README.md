# Curtin Contact Site Monitor

Monitors the Curtin Contact Sites and posts them to Discord when new ones are published.

## Setup Instructions

The bot can be run on Python 3.8+, and installed by first running `pip install -U pip && pip install -U -r requirements.txt` to install dependencies.

Next, open `config.ini`. Follow a guide such as the one at https://discordjs.guide/preparations/setting-up-a-bot-application.html to create a discord bot, and get a token for it. Place the token after the `BotKey = ` line in the config file. You can also modify the amount of time between checking the website.

Once you've done this, run the both with `python3 main.py` to start it. It should connect to discord and check the website automatically. Invite the bot to your servers, and then add or remove any channels you want to notify with /add_channel or /remove_channel. Note that only server admins can run this command, and it can't be run in DMs. Also note that due to Discord constraints slash commands can take up to an hour after your bot starts to become available everywhere.
