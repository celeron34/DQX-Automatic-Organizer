"""Discord process responsible only for scraping and publishing schedules."""

from __future__ import annotations

import asyncio
import io
import json
import os
from datetime import datetime
from sys import argv

import discord
from discord.ext import tasks

from bot_tokens import get_token
from dqx_ise import getTable
from schedule_protocol import serialize_entries


client = discord.Bot(debug_guilds=[1246651972342386791], intents=discord.Intents.default())
_refresh_lock = asyncio.Lock()
_last_published_payload: str | None = None


async def send_schedule_to_formation(entries: list, *, force: bool = False) -> None:
    global _last_published_payload
    channel_id = os.environ.get("SCHEDULE_SYNC_CHANNEL_ID")
    if not channel_id:
        raise RuntimeError("Set SCHEDULE_SYNC_CHANNEL_ID for the private bot-to-bot channel")
    payload = serialize_entries(entries)
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if payload_text == _last_published_payload and not force:
        print(f"{datetime.now()} schedule unchanged; no bridge message needed")
        return

    channel = client.get_channel(int(channel_id))
    if channel is None:
        channel = await client.fetch_channel(int(channel_id))
    file = discord.File(io.BytesIO(payload_text.encode("utf-8")), filename="dqx-schedule.json")
    message = await channel.send(content="DQX_SCHEDULE_SYNC_V1", file=file)
    _last_published_payload = payload_text
    print(f"{datetime.now()} sent schedule message {message.id} to formation bridge")


async def refresh_schedule(*, publish_even_if_unchanged: bool = False) -> list:
    """Scrape off the event loop, then publish only a complete result."""
    async with _refresh_lock:
        browser_path = os.environ.get("CHROME_BINARY") or (argv[1] if len(argv) > 1 else None)
        driver_path = os.environ.get("CHROMEDRIVER") or (argv[2] if len(argv) > 2 else None)
        loop = asyncio.get_running_loop()
        entries = await loop.run_in_executor(None, getTable, browser_path, driver_path)
        if not entries:
            raise RuntimeError("Scraper returned no schedule entries; keeping the last published schedule")
        await send_schedule_to_formation(entries, force=publish_even_if_unchanged)
        return entries


async def report_refresh(ctx: discord.ApplicationContext) -> None:
    await ctx.defer(ephemeral=True)
    try:
        entries = await refresh_schedule(publish_even_if_unchanged=True)
    except Exception as error:
        await ctx.followup.send(f"タイムテーブルを更新できませんでした: {error}", ephemeral=True)
        print(f"{datetime.now()} manual schedule refresh failed: {error}")
        return
    all_force_count = sum(entry.is_all_forces for entry in entries)
    await ctx.followup.send(
        f"タイムテーブルを更新しました（全兵団 {all_force_count} 件 / 取得 {len(entries)} 件）",
        ephemeral=True,
    )


@client.slash_command(name="f-timetable", description="タイムテーブルを再取得")
async def f_timetable(ctx: discord.ApplicationContext):
    await report_refresh(ctx)


@client.slash_command(name="f-schedule-refresh", description="タイムテーブルを再取得")
async def f_schedule_refresh(ctx: discord.ApplicationContext):
    await report_refresh(ctx)


@tasks.loop(minutes=15)
async def scheduled_refresh():
    try:
        entries = await refresh_schedule()
        print(f"{datetime.now()} published {len(entries)} schedule entries")
    except Exception as error:
        print(f"{datetime.now()} schedule refresh failed: {error}")


@client.event
async def on_ready():
    if not scheduled_refresh.is_running():
        await scheduled_refresh()
        scheduled_refresh.start()
    print(f"schedule bot ready: {client.user}")


if __name__ == "__main__":
    client.run(get_token("schedule"))
