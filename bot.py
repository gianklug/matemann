import datetime
import logging
import os
import sys

import discord
import requests

client = discord.Client()
logging.basicConfig(level=logging.INFO)


def get_ctftime_events(delta=0):
    """Get CTFTime events."""
    # cloudflare blocks requests
    fake_user_agent = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    }
    # fetch next n events
    now = datetime.datetime.now().timestamp()
    timedelta = datetime.timedelta(days=delta)
    timestamp = now - timedelta.total_seconds()
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
    logging.info(f"Fetched {len(events)} CTFTime events.")
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

            logging.info(f"Created event {event['title']}.")


async def create_discord_categories(guild, events):
    """Create a discord category per ctf."""
    events = await guild.fetch_scheduled_events()
    existing_categories = [x.name[:25] for x in guild.categories]
    for event in events:
        if event.name.strip()[:25] in existing_categories:
            # Ignore already existing categories
            continue
        # Only create a category if >1 person is interested
        if event.subscriber_count <= 0:
            logging.info(f"Skipping category creation for {event.name}.")
            continue
        await guild.create_category(event.name)
        logging.info(f"Created category {event.name}.")
        await create_discord_channels(guild, event.name)


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
        logging.info(f"Created channel {channel_name} in category {category}.")


async def delete_discord_categories(guild, events):
    """Delete all categories of past CTFs without any chat activity."""
    events_past = get_ctftime_events(delta=5)
    # Merge both event list
    events.extend(events_past)
    # Get all guild categories
    categories = guild.categories
    for category in categories:
        # Don't touch default categories
        if category.name in ["Text channels", "Voice channels"]:
            continue
        # Skip categories with running CTFs
        if category.name.strip()[:25] in [x["title"].strip()[:25] for x in events]:
            continue
        # Delete all dead channels
        for channel in category.channels:
            # if channel is empty
            if not channel.last_message_id:
                await channel.delete()
                logging.info(f"Deleted channel {channel.name} in {category.name}.")
        # If no more channels, delete category
        if not category.channels:
            await category.delete()
            logging.info(f"Deleted category {category.name}.")
        else:
            # Leave already archived categories alone
            if category.name.startswith("ZZZ_"):
                continue
            # Rename the category to ZZZ_name
            await category.edit(name=f"ZZZ_{category.name}")
            logging.info(f"Archived category {category.name}.")


@client.event
async def on_ready():
    """Execute commands as soon as the bot is ready."""
    print("Connected to the bot.")

    guild = client.get_guild(int(os.environ["GUILD_ID"]))

    events = get_ctftime_events()
    # Create new events
    await create_discord_events(guild, events)
    logging.info("Events successfully created.")
    # Create categories if there is interest
    await create_discord_categories(guild, events)
    logging.info("Categories and channels successfully created.")
    # Delete / Archive old categories
    await delete_discord_categories(guild, events)
    logging.info("Old categories and channels successfully deleted / archived.")
    await client.close()
    logging.info("I'm done here. Goodbye.")
    sys.exit(0)


client.run(os.environ["BOT_TOKEN"])
