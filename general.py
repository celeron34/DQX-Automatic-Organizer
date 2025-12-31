from __future__ import annotations # 再帰に必要 必ず先頭に

from traceback import extract_tb, format_list, exc_info
from sys import argv
from subprocess import Popen
from os import getcwd, executable
from json import load
from dqx_ise import getTable
from discord import partial_emoji, Emoji, File, CustomActivity, Status, Client, ApplicationContext
from re import match
from glob import glob
from datetime import datetime as dt, timedelta as delta
from classes import *
from Views import *

def extract_emoji_id(emoji: partial_emoji.PartialEmoji | Emoji | str) -> int | None:
    """絵文字 (Emoji または <:emoji_name:emoji_id>) から ID を取得"""
    if isinstance(emoji, Emoji):
        return emoji.id
    elif isinstance(emoji, partial_emoji.PartialEmoji):
        return emoji.id
    elif isinstance(emoji, str):
        match_obj = match(r"<a?:[\w]+:(\d+)>", emoji)
        if match_obj:
            return int(match_obj.group(2))  # ID を取得
        else:
            return None
    return None

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
    return err_msg

def getDirectoryItems(path:str) -> list[SendItem]:
    sendItems:list[dict[str, list[File]|str]] = []
    numFiles:list[str] = glob('*', root_dir=path)
    num = 1
    while True:
        imgs:list[File] = []
        for p in numFiles:
            if match('^' + str(num) + '+(-[0-9]+)?[.](png|jpg|jpeg|tiff)$', p) is not None:
                imgs.append(File(path + '/' + p))
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
async def command_message(textch:TextChannel, raidRoles) -> Message:
    msg = await textch.send(content=f'## 追加・削除したいロールをタップ', view=RoleManageView(raidRoles))
    return msg

async def getTimetable(client:Client, updateStatus:bool=True) -> list[dt]:
    # タイムテーブルを取りに行く
    await client.change_presence(activity=CustomActivity(name='タイムスケジュール取得中'), status=Status.dnd)
    print(f'{dt.now()} getting Timetable')
    timeTable:list[dt] = []
    now30 = dt.now() + delta(minutes=30)
    for t in getTable(argv[1], argv[2]):
        # 通過したものは追加しない
        if t > now30:
            timeTable.append(t)
    if updateStatus:
        await client.change_presence(activity=CustomActivity(name=timeTable[0].strftime("Next:%H時")), status=Status.online)
    print(f'{dt.now()} Timetable was get')
    return timeTable

def markdownEsc(line:str):
    replaceChars = {'_', '*', '>', '-', '~', '[', ']', '(', ')', '@', '#', '`'}
    line = line.replace('\\', '\\\\')
    for char in replaceChars:
        line = line.replace(char, '\\'+char)
    return line

def joinLeaveMembers(guild:Guild, month:delta, exclusionRole:Role|None=None):
    leaveMembers:set[Member] = set(guild.members)
    with open(f'reclutionLog/{guild.name}.csv') as f:
        lines = f.readlines()
    for line in lines[-1::-1]:
        if line == '': continue
        element = line.strip().split(',')
        date = element[0].split('-')
        if dt('20' + date[0], date[1], date[2], date[3]) < dt.now() - month: break
        targetMember = guild.get_member(element[0])
        if not isinstance(targetMember, Member): continue
        if targetMember.joined_at < dt.now() - month: continue
        if any(map(lambda role:role.position >= exclusionRole.position, targetMember.roles)): continue
        leaveMembers = leaveMembers - targetMember
    return leaveMembers

async def f_fetch(client:Client):
    global ROBIN_GUILD
    # チャンネル・ギルドをゲット
    with open('IDs.json') as f:
        IDs = load(f)

    for guildInfo in [IDs[0]]:
        ROBIN_GUILD = Guild(guildInfo['guildID'])

        # チャンネルゲット
        ROBIN_GUILD.PARTY_CH      = client.get_channel(guildInfo['channels']['party'])
        ROBIN_GUILD.PARTY_CH_beta = client.get_channel(guildInfo['channels']['party-beta'])
        ROBIN_GUILD.PARTY_LOG     = client.get_channel(guildInfo['channels']['party-log'])
        ROBIN_GUILD.DEV_CH        = client.get_channel(guildInfo['channels']['develop'])
        ROBIN_GUILD.COMMAND_CH    = client.get_channel(guildInfo['channels']['command'])
        ROBIN_GUILD.UNAPPLIDE_CHANNEL = client.get_channel(guildInfo['channels']['unapplide'])
        ROBIN_GUILD.RECLUIT_LOG_CH = client.get_channel(guildInfo['channels']['recluit-log'])

        ROBIN_GUILD.reclutingMessageItems = getDirectoryItems(f'guilds/{ROBIN_GUILD.GUILD.id}/recluitingMessage')
        
        # 絵文字ゲット
        ROBIN_GUILD.RECLUTING_EMOJI =  client.get_emoji(guildInfo['emojis']['recluting'])
        ROBIN_GUILD.FULLPARTY_EMOJI =  client.get_emoji(guildInfo['emojis']['fullparty'])
        ROBIN_GUILD.LIGHTPARTY_EMOJI = client.get_emoji(guildInfo['emojis']['lightparty'])

        # ロールゲット
        ROBIN_GUILD.ROLES = {
                ROBIN_GUILD.GUILD.get_role(roleInfo['role']) : \
                RoleInfo(client.get_emoji(roleInfo['emoji']), roleName) \
                    for roleName, roleInfo in guildInfo['raidRoles'].items()
            }
        ROBIN_GUILD.MEMBER_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['member'])
        ROBIN_GUILD.UNAPPLIDE_MEMBER_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['unapplide'])
        ROBIN_GUILD.PRIORITY_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['priority'])
        ROBIN_GUILD.STATIC_PRIORITY_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['staticPriority'])
        ROBIN_GUILD.MASTER_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['master'])

        ROBIN_GUILD.RAIDS = [
            {
                'raidName':raidInfo['raidName'],
                'png': raidInfo['png'],
                'lightParty': raidInfo['lightParty'],
                'speedPartyRoles': [
                    [
                        {
                            'name':role['name'],
                            'role':ROBIN_GUILD.GUILD.get_role(role['role']),
                            'emoji':client.get_emoji(role['emoji']),
                            'count':role['count']
                        } for role in roles
                    ] for roles in raidInfo['speedPartyRoles']
                ]
            } for raidInfo in guildInfo['raids']
        ]

        ROBIN_GUILD.RAID_ROLES = {roleName:
                     {'role':ROBIN_GUILD.GUILD.get_role(roleInfo['role']), 'emoji':client.get_emoji(roleInfo['emoji'])}
                     for roleName, roleInfo in guildInfo['raidRoles'].items()
                    }
        # ローリングチャンネルイニシャライズ
        await ROBIN_GUILD.COMMAND_CH.purge()
        ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH, ROBIN_GUILD.RAID_ROLES)

        await ROBIN_GUILD.GUILD.chunk()

async def f_reboot(client:Client, ctx:ApplicationContext|None = None):
    if ctx: await ctx.respond('再起動します')
    await ROBIN_GUILD.COMMAND_CH.purge()
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()

async def f_stableReboot(client:Client, ctx:ApplicationContext|None = None):
    if ctx: await ctx.respond('安定版再起動します')
    await ROBIN_GUILD.COMMAND_CH.purge()
    Popen(['git', 'checkout', '--force', 'main'], cwd=getcwd())
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()

