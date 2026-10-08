"""Discord process that owns the member role-selection panel."""

from __future__ import annotations

import json

import discord

from bot_tokens import get_token
from views import RoleManageView


intents = discord.Intents.default()
intents.members = True
client = discord.Bot(debug_guilds=[1246651972342386791], intents=intents)
_guild_settings: dict | None = None
_panel_initialized = False
_panel_message: discord.Message | None = None


def load_guild_settings() -> dict:
    with open("IDs.json", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)
    if not settings:
        raise RuntimeError("IDs.json has no guild configuration")
    return settings[0]


async def publish_role_panel() -> discord.Message:
    global _panel_message
    settings = _guild_settings or load_guild_settings()
    guild = client.get_guild(settings["guildID"])
    if guild is None:
        raise RuntimeError(f"Guild {settings['guildID']} is unavailable to the role bot")
    channel = guild.get_channel(settings["channels"]["command"])
    if channel is None:
        raise RuntimeError("Role panel command channel is missing from IDs.json")
    roles = {
        entry["name"]: {
            "role": guild.get_role(entry["role"]),
            "emoji": client.get_emoji(entry["emoji"]),
        }
        for entry in settings["settingRoles"]
    }
    missing = [name for name, info in roles.items() if info["role"] is None or info["emoji"] is None]
    if missing:
        raise RuntimeError(f"Invalid role or emoji configuration for: {', '.join(missing)}")
    if _panel_message is not None:
        try:
            await _panel_message.delete()
        except discord.NotFound:
            pass
    else:
        async for message in channel.history(limit=100):
            if message.author.id == client.user.id and message.content == "## 追加・削除したいロールをタップ":
                await message.delete()
    _panel_message = await channel.send("## 追加・削除したいロールをタップ", view=RoleManageView(roles))
    return _panel_message


@client.slash_command(name="f-role-panel-refresh", description="ロール選択パネルを再生成")
async def f_role_panel_refresh(ctx: discord.ApplicationContext):
    try:
        await publish_role_panel()
    except Exception as error:
        await ctx.respond(f"ロールパネルを更新できませんでした: {error}", ephemeral=True)
        print(f"role panel refresh failed: {error}")
        return
    await ctx.respond("ロール選択パネルを更新しました", ephemeral=True)


@client.event
async def on_ready():
    global _guild_settings, _panel_initialized
    _guild_settings = load_guild_settings()
    if not _panel_initialized:
        await publish_role_panel()
        _panel_initialized = True
    print(f"role bot ready: {client.user}")


if __name__ == "__main__":
    client.run(get_token("role"))
