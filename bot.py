import discord
import datetime
import requests
import os
import sys


client = discord.Client()


def get_ctftime_events():
    """Get CTFTime events."""
    # cloudflare blocks requests
    fake_user_agent = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    }
    # fetch next n events
    timestamp = datetime.datetime.now().timestamp()
    url = f"https://ctftime.org/api/v1/events/?limit=15&start={int(timestamp)}"
    r = requests.get(url, headers=fake_user_agent).json()
    events = []
    # get event details and skip onsite events
    for event in r:
        details = requests.get(
            f"https://ctftime.org/api/v1/events/{event['id']}/", headers=fake_user_agent
        ).json()
        if details["onsite"]:
            continue
        events.append(details)
    return events


async def create_discord_events(guild, events):
    """Create a discord event per ctf."""
    existing_events = await guild.fetch_scheduled_events()
    for event in events:
        # skip existing events
        for existing_event in existing_events:
            if event["title"].strip() == existing_event.name.strip():
                break
        else:
            start = datetime.datetime.strptime(event["start"], "%Y-%m-%dT%H:%M:%S%z")
            finish = datetime.datetime.strptime(event["finish"], "%Y-%m-%dT%H:%M:%S%z")

            await guild.create_scheduled_event(
                name=event["title"],
                description=event["description"][:1000],
                start_time=start,
                end_time=finish,
                location=event["url"],
            )


async def create_discord_categories(guild, events):
    """Create a discord category per ctf."""
    existing_categories = [x.name[:25] for x in guild.categories]
    for event in events:
        if not event["title"][:25] in existing_categories:
            await guild.create_category(event["title"])
        await create_discord_channels(guild, event["title"])


async def create_discord_channels(guild, category):
    """Create default discord channels if they don't exist."""
    channel_names = ["general", "pwn", "rev", "web", "crypto", "misc"]
    # get category id
    categories = guild.categories
    for c in categories:
        if c.name[:25] == category.strip()[:25]:
            category_object = c
            break
    existing_channels = [x.name[:25] for x in category_object.channels]

    for channel_name in channel_names:
        if channel_name in existing_channels:
            continue
        await guild.create_text_channel(channel_name, category=category_object)


@client.event
async def on_ready():
    """Execute commands as soon as the bot is ready."""
    print("Connected to the bot.")

    guild = client.get_guild(int(os.environ["GUILD_ID"]))

    await create_discord_categories(guild, get_ctftime_events())
    await create_discord_events(guild, get_ctftime_events())

    print("CTFTime events, channels and categories successfully created.")
    await client.close()
    sys.exit(0)


client.run(os.environ['BOT_TOKEN'])
