from __future__ import annotations

import discord
from datetime import datetime as dt
from glob import glob
from re import match
from traceback import extract_tb, format_list
from sys import exc_info
from os.path import isdir, join


def markdownEsc(line:str):
    replaceChars = {'_', '*', '>', '-', '~', '[', ']', '(', ')', '@', '#', '`'}
    line = line.replace('\\', '\\\\')
    for char in replaceChars:
        line = line.replace(char, '\\'+char)
    return line

class SendItem:
    def __init__(self, text:str, imgs:list[discord.File]):
        self.text = text
        self.imgs = imgs

async def sendDirectory(path:str, targetChannel:discord.Thread|discord.TextChannel):
    for sendItem in getDirectoryItems(path):
        await targetChannel.send(sendItem.text, files=sendItem.imgs)

def getDirectoryItems(path:str) -> list[SendItem]:
    sendItems:list[dict[str, list[discord.File]|str]] = []
    numFiles:list[str] = glob('*', root_dir=path)
    num = 1
    while True:
        imgs:list[discord.File] = []
        for p in numFiles:
            if match('^' + str(num) + '+(-[0-9]+)?[.](png|jpg|jpeg|tiff)$', p) is not None:
                imgs.append(discord.File(path + '/' + p))
        for p in imgs:
            numFiles.remove(p.filename)
        text:str = ''
        for p in numFiles:
            if match('^' + str(num) + '+(-[0-9]+)?[.](txt|md)$', p) is not None:
                with open(path + '/' + p, 'r', encoding='utf-8') as f:
                    text = f.read()
                break
        if text == '' and imgs == []: break
        sendItems.append(SendItem(text, imgs))
        num += 1
    return sendItems

def replaces(msg:str, replaceChars:dict[str,str]) -> str:
    for key, value in replaceChars.items():
        msg = msg.replace(key, value)
    return msg

def recruitMessageReplace(msg:str, time:dt, count:int=0) -> str:
    replaceChars = {
        '{hour}': time.strftime('%H'),
        '{count}': str(count)
    }
    return replaces(msg, replaceChars)

async def checkRoleRight(sender:discord.Member|discord.Interaction, channel:discord.TextChannel=None, roles:set[discord.Role]={}, errorMsg:str='') -> bool:
    global ROBIN_GUILD
    if isinstance(sender, discord.Interaction):
        member = sender.user
    else:
        member = sender
    if len(roles & set(member.roles)) == 0:
        # レスポンス
        if errorMsg != '':
            if isinstance(sender, discord.Interaction):
                await sender.response.send_message(errorMsg, ephemeral=True, delete_after=10)
            elif isinstance(sender, discord.Member) and channel is not None:
                await channel.send(f'{member.mention} {errorMsg}', delete_after=10)
        return False
    else:
        return True

def printTraceback(e):
    error_class = type(e)
    error_description = str(e)
    print('---- traceback ----')
    err_msg = '%s: %s' % (error_class, error_description)
    print(err_msg)
    tb = extract_tb(exc_info()[2])
    trace = format_list(tb)
    for line in trace:
        print(line)
    print('-------------------')


def extract_emoji_id(emoji: discord.partial_emoji.PartialEmoji | discord.Emoji | str) -> int | None:
    """絵文字 (discord.Emoji または <:emoji_name:emoji_id>) から ID を取得"""
    if isinstance(emoji, discord.Emoji):
        return emoji.id
    elif isinstance(emoji, discord.partial_emoji.PartialEmoji):
        return emoji.id
    elif isinstance(emoji, str):
        match_obj = match(r"<a?:[\w]+:(\d+)>", emoji)
        if match_obj:
            return int(match_obj.group(2))  # ID を取得
        else:
            return None
    return None

def equalEmoji(emoji1: discord.partial_emoji.PartialEmoji | discord.Emoji | str, emoji2: discord.partial_emoji.PartialEmoji | discord.Emoji | str) -> bool:
    """絵文字同士のIDが一致するか判定"""
    emoji1_id = extract_emoji_id(emoji1)
    emoji2_id = extract_emoji_id(emoji2)

    if emoji1_id is None or emoji2_id is None:
        return False  # どちらかが不正な場合は False

    return emoji1_id == emoji2_id


def getCompatibleConfigValue(config: dict, key: str, legacy_key: str):
    """Read a canonical config key, falling back to its legacy spelling."""
    if key in config:
        return config[key]
    return config[legacy_key]


def getRecruitingMessageDirectory(guild_id, root: str = 'guilds') -> str:
    """Prefer the corrected folder name while retaining existing installations."""
    guild_path = join(root, str(guild_id))
    current = join(guild_path, 'recruitingMessage')
    legacy = join(guild_path, 'recluitingMessage')
    if isdir(current) or not isdir(legacy):
        return current
    return legacy
