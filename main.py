import asyncio, httpx, time, pickle
from bs4 import BeautifulSoup
import configparser
import discord
from discord.commands import permissions


class ContactLocation:
    def __init__(self, date: str, time: str, campus: str, location: str, contact: str):
        self.date = date
        self.time = time
        self.campus = campus
        self.location = location
        self.contact = contact

    def __str__(self):
        res = f"Exposure site on *{self.date}*, at *{self.time}*.\nCampus: **{self.campus}**, Location: **{self.location}**\n"
        if self.contact != "Casual":
            res += f"***Contact Status: {self.contact}***"
        else:
            res += "Casual Contact Site"

        return res

    def __hash__(self):
        return hash((self.date, self.time, self.campus, self.location, self.contact))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return (
            self.date == other.date
            and self.time == other.time
            and self.campus == other.campus
            and self.location == other.location
            and self.contact == other.contact
        )


class MyBot(discord.Bot):
    def __init__(self) -> None:
        super().__init__()
        self.wait_time = 600.0
        self.site_url = "http://0.0.0.0"
        self.raw_post_locations: list[tuple[int, int]] = list()
        try:
            with open("servers.csv") as f:
                for line in f:
                    a, b = line.split(",")
                    self.raw_post_locations.append((int(a), int(b)))
        except FileNotFoundError:
            pass

    def set_config(self, wait_time: str, site_url: str):
        self.wait_time = wait_time
        self.site_url = site_url

    async def on_ready(self):
        print(f"Logged in as {self.user}")

        self.parsed_post_locations: list[
            tuple[discord.Guild, discord.abc.Messageable]
        ] = list()
        for guild_id, channel_id in self.raw_post_locations:
            guild = self.get_guild(guild_id)
            if guild is None:
                continue
            channel = guild.get_channel_or_thread(channel_id)
            if channel is None:
                continue
            self.parsed_post_locations.append((guild, channel))

        self.bg_task = asyncio.create_task(
            site_check_loop(self.wait_time, self.site_url, self)
        )

    async def post_contacts(self, contacts: list[ContactLocation]):
        # Go through every post location in the post location list, and go through every new item in the new contact list, and post it in each location
        # Use the ContactLocation str function to create post text
        if len(contacts) > 0 and len(self.parsed_post_locations) > 0:
            for _, channel in self.parsed_post_locations:
                for contact in contacts:
                    await channel.send(str(contact))


bot = MyBot()


@bot.slash_command()
async def add_channel(ctx):
    "Add a channel to the list of places to notify"
    # Must be in channel
    if not isinstance(ctx.author, discord.Member):
        await ctx.respond("This command can only be used in channels", ephemeral=True)
        return
    # Must be from admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("This command is for admins only", ephemeral=True)
        return

    location = (ctx.guild, ctx.channel)

    if location in ctx.bot.parsed_post_locations:
        # Already in the list
        await ctx.respond("This channel is already in the list", ephemeral=True)
        return

    # Good to go
    ctx.bot.parsed_post_locations.append(location)
    # Saving
    save_servers(ctx.bot.parsed_post_locations)
    await ctx.respond("Added this channel to the list!")


@bot.slash_command()
async def remove_channel(ctx):
    "Remove a channel from the list of places to notify"
    # Must be in channel
    if not isinstance(ctx.author, discord.Member):
        await ctx.respond("This command can only be used in channels", ephemeral=True)
        return
    # Must be from admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.respond("This command is for admins only", ephemeral=True)
        return

    location = (ctx.guild, ctx.channel)

    if location not in ctx.bot.parsed_post_locations:
        # Already in the list
        await ctx.respond("This channel isn't currently in the list", ephemeral=True)
        return

    # Good to go
    ctx.bot.parsed_post_locations.remove(location)
    # Saving
    save_servers(ctx.bot.parsed_post_locations)
    await ctx.respond("Removed this channel from the list!")


def save_servers(servers: list[tuple[discord.Guild, discord.abc.Messageable]]) -> None:
    with open("servers.csv", "wt") as f:
        for guild, channel in servers:
            f.write(str(guild.id))
            f.write(",")
            f.write(str(channel.id))
            f.write("\n")


def main() -> None:
    config = configparser.ConfigParser()
    config.read("config.ini")
    bot_token: str = config["DEFAULT"]["BOTKEY"]
    wait_time: float = config["DEFAULT"].getfloat("MinutesBetweenChecks") * 60.0
    site_url: str = config["DEFAULT"]["SiteUrl"]

    bot.set_config(wait_time, site_url)

    bot.run(bot_token)


async def site_check_loop(wait_time: float, target_url: str, bot: discord.Bot) -> None:
    prev_contacts: list[ContactLocation]
    try:
        with open("data.pickle", "rb") as f:
            prev_contacts = pickle.load(f)
    except FileNotFoundError:
        prev_contacts = list()

    while True:
        async with httpx.AsyncClient() as client:
            time_start = time.time()
            print("Checking Site")
            r = await client.get(target_url)
            contacts = parse_webpage(r)
            if contacts != prev_contacts:
                # New things!
                new_contacts = [x for x in contacts if x not in prev_contacts]
                if len(new_contacts) > 0:
                    print(f"Downloaded {len(new_contacts)} new contact locations")
                    await bot.post_contacts(list(new_contacts))
                prev_contacts = contacts
                with open("data.pickle", "wb") as f:
                    pickle.dump(contacts.f, pickle.HIGHEST_PROTOCOL)
            else:
                print("Checked, no new items")

            time_end = time.time()
            # Subtract the amount of time it took to run the loop from the time I should wait until next run
            # If the time it took was more than the wait time, continue to the next loop immediatly without waiting
            # i.e. if wait_time is 10 minutes, and it took 1 minute to run, only wait 9 minutes
            # If wait time is 1 minute, and it took 2 minutes, continue immediatly
            diff = time_end - time_start
            if diff < wait_time:
                await asyncio.sleep(wait_time - diff)


def parse_webpage(response: httpx.Response) -> list[ContactLocation]:
    soup = BeautifulSoup(response.content, "html.parser")

    locations: list[ContactLocation] = list()

    for row in soup.find(id="table_1").find("tbody").find_all("tr"):
        try:
            date = row.contents[0].get_text(strip=True)
            time = row.contents[1].get_text(strip=True)
            campus = row.contents[2].get_text(strip=True)
            location = row.contents[3].get_text(strip=True)
            contact = row.contents[4].get_text(strip=True)
            locations.append(ContactLocation(date, time, campus, location, contact))
        except AttributeError as e:
            print(f"Error parsing row: {row}\n{e=}")

    return locations


if __name__ == "__main__":
    main()
