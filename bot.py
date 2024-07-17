import datetime
import logging
import os
import sys
import re

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
        if details["restrictions"] != "Open":
            continue
        events.append(details)
    logging.info(f"Fetched {len(events)} CTFTime events.")
    return events


def gen_topic(category, event):
    """Generate a unique channel header for the CTFTime event"""
    ctftime_url = event["ctftime_url"]
    ctf_title = event["title"]
    ctf_params = {
        "id": event["ctf_id"],
        "start": int(float(datetime.datetime.strptime(event["start"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
        "finish": int(float(datetime.datetime.strptime(event["finish"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
    }
    ctf_params_query = "&".join([f"{k}={v}" for k, v in ctf_params.items()])
    ctf_markdown = f"{ctf_title} - {category} - [View on CTFTime]({ctftime_url}?{ctf_params_query})"
    return ctf_markdown

def decode_topic(topic):
    """Decode the topic to get the CTFTime event data"""
    url = re.search(r"\[View on CTFTime\]\((.*?)\)", topic)
    if url is None:
        return None
    params = re.search(r"\?(.*)", url.group(1)).group(1).split("&")
    params_dict = {k: v for k, v in [x.split("=") for x in params]}
    return params_dict

async def create_discord_events(guild, events):
    """Create a discord event per ctf."""
    existing_events = await guild.fetch_scheduled_events()
    for event in events:
        # skip existing events
        for existing_event in existing_events:
            if event["title"].strip() == existing_event.name.strip():
                logging.info(f"Event '{event['title']}' already exists, skipping.")
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
    discord_events = await guild.fetch_scheduled_events()
    existing_categories = [x.name[:25] for x in guild.categories]
    for event in events:
        if event["title"].strip()[:25] in existing_categories:
            logging.info(f"Category {event['title']} already exists, skipping.")
            # Ignore already existing categories
            continue
        # Only create a category if >1 person is interested
        discord_event = next(e for e in discord_events if e.name == event["title"])
        print(discord_event)
        print(discord_event.subscriber_count)
        if discord_event.subscriber_count <= 0:
            logging.info(f"Skipping category creation for {event["title"]}.")
            continue
        await guild.create_category(event["title"])
        logging.info(f"Created category {event["title"]}.")
        await create_discord_channels(guild, event)


async def create_discord_channels(guild, event):
    """Create default discord channels if they don't exist."""
    channel_names = ["general", "pwn", "rev", "web", "crypto", "misc"]

    # get category id
    categories = guild.categories
    for c in categories:
        if c.name[:25] == event["title"].strip()[:25]:
            category_object = c
            break
    existing_channels = [x.name[:25] for x in category_object.channels]

    for channel_name in channel_names:
        if channel_name in existing_channels:
            continue
        await guild.create_text_channel(
            channel_name, category=category_object, topic=gen_topic(channel_name, event)
        )
        logging.info(f"Created channel {channel_name} in category {event["title"]}.")


async def delete_discord_categories(guild):
    """Delete all categories of past CTFs without any chat activity."""
    categories = guild.categories
    for category in categories:
        # Don't touch default categories
        if category.name in ["Text channels", "Voice channels"]:
            continue
        end_time = None
        for channel in category.channels:
            # get ctf data
            if not (topic := channel.topic):
                continue
            if not (ctftime_params := decode_topic(topic)):
                continue
            end_time = datetime.datetime.fromtimestamp(int(float(ctftime_params["finish"])))
            # If the CTF is still running
            if end_time > datetime.datetime.now():
                continue
            # if channel is empty
            if not channel.last_message_id:
                await channel.delete()
                logging.info(f"Deleted channel {channel.name} in {category.name}.")
        if not (end_time and end_time < datetime.datetime.now()):
            continue
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
    await delete_discord_categories(guild)
    logging.info("Old categories and channels successfully deleted / archived.")
    await client.close()
    logging.info("I'm done here. Goodbye.")
    sys.exit(0)


client.run(os.environ["BOT_TOKEN"])
