from __future__ import annotations # 必ず先頭に
version = '1.1.10'

import discord
from discord.ext import tasks, commands
from dqx_ise import getTable
from formation import speedFormation as formSpeedParties, randomFormation as formLightParties
from datetime import datetime as dt, timedelta as delta
from asyncio import sleep, create_task
# from asyncio import get_running_loop, create_task
# from concurrent.futures import ThreadPoolExecutor
from random import shuffle, randint, random
from sys import argv, exc_info, executable, exit
from subprocess import Popen, check_output
from traceback import extract_tb, format_list
from re import sub, match
from os import getcwd, path, mkdir
import json
from views import (
    ViewContext, RoleManageView, ApproveView, DummyApproveView, PartyView,
    FormationTopView, RecruitView, RebootView,
)
from party import PartyContext, RoleInfo, PartyMember, Participant, Guest, Party, LightParty, SpeedParty
from guild import Guild

from support_utils import (
    SendItem, checkRoleRight, equalEmoji, extract_emoji_id,
    getCompatibleConfigValue, getDirectoryItems, getRecruitingMessageDirectory,
    markdownEsc, printTraceback, recruitMessageReplace, replaces, sendDirectory,
)
from event_definition import EventDefinition, EventInstance, EventPhase
from commands import register_slash_commands
from event_runner import EventRuntime, run_scheduled_event


# インテント
intents = discord.Intents.all()
intents.members = True
intents.message_content = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_typing = True
intents.message_content = True
client = commands.Bot(intents=intents)

GUILDS:dict[int, Guild] = {}

##############################################################################################
##############################################################################################
#region イニシャライズ
@client.event
async def on_ready():
    print(f'{dt.now()} on_ready START')

    await f_fetch()

    # コミットハッシュ取得
    script_dir = path.dirname(path.abspath(__file__)) # パス
    git_root = check_output(['git', '-C', script_dir, 'rev-parse', '--show-toplevel'], text=True).strip()
    commit_hash = check_output(['git', '-C', git_root, 'rev-parse', 'HEAD'], text=True).strip()
    for guild in GUILDS.values():
        await guild.DEV_CH.send(f'commit hash: {commit_hash}')

    # 同じ全兵団スケジュールを各サーバーのイベント状態へ反映
    time_table = await getTimetable(False)
    for guild in GUILDS.values():
        guild.timeTable = list(time_table)
        guild.sync_events(guild.timeTable)
        for start_at in guild.timeTable:
            print(f'{guild.GUILD.name}: {start_at}')

    # ループの時間調整
    await client.change_presence(activity=discord.CustomActivity(name='時間同期待ち'), status=discord.Status.dnd)
    second = dt.now().second
    print(f'{dt.now()} Loop sync wait')
    await sleep(60.5 - second)
    if not loop.is_running():
        loop.start()
    print(f'{dt.now()} loop Start')

    if time_table:
        await client.change_presence(activity=discord.CustomActivity(name=time_table[0].strftime("Next:%H時")))
    print(f'{dt.now()} on_ready END')

#endregion

##############################################################################################
##############################################################################################
#region リアクション追加検知
@client.event
async def on_reaction_add(reaction:discord.Reaction, user:discord.Member|discord.User):
    if user == client.user or not reaction.is_custom_emoji(): return
    guild = GUILDS.get(reaction.message.guild.id)
    if guild is None: return
    now = dt.now()
    print(f'{now} receive reaction add {user} {reaction.emoji.name}')
    event = find_event_for_message(reaction.message, guild)
    if event is None or reaction.emoji != guild.RECRUITING_EMOJI: return
    if event.parties is not None:
        if not (await checkRoleRight(user, reaction.message.channel, {guild.MEMBER_ROLE}, '参加権がありません') and
                await checkRoleRight(user, reaction.message.channel, set(guild.ROLES.keys()), 'ロールが設定されていません')):
            await reaction.message.remove_reaction(reaction.emoji, user)
            return
        if reaction.message == event.recruiting_message:
            if not any(party.isMember(user) for party in event.parties):
                await autoJoinParticipant(user, event)
        elif reaction.message in map(lambda party: party.message, event.parties):
            party = searchLightParty(reaction.message, event.parties)
            if party is not None: await party.joinRequest(user)
        return
    if event.recruiting_message == reaction.message and event.starts_at - delta(minutes=30) <= now < event.starts_at - delta(minutes=10):
        if not (await checkRoleRight(user, reaction.message.channel, {guild.MEMBER_ROLE}, '参加権がありません') and
                await checkRoleRight(user, reaction.message.channel, set(guild.ROLES.keys()), 'ロールが設定されていません')):
            await reaction.message.remove_reaction(reaction.emoji, user)
            return
        if user not in event.recruiting_members:
            event.recruiting_members.append(user)
            await reaction.message.edit(recruitMessageReplace(guild.recruitingMessageItems[-1].text, event.starts_at, len(event.recruiting_members)))
        sendMessage = dt.now().strftime('[%y-%m-%d %H:%M:%S.%f]') + f' :green_square: {user.display_name} '
        sendMessage += str(guild.LIGHTPARTY_EMOJI) if guild.LITE_PARTY_ROLE in user.roles else ''
        for role in filter(lambda r:r in guild.ROLES.keys(), user.roles): sendMessage += str(guild.ROLES[role].emoji)
        await guild.RECRUIT_LOG_CH.send(sendMessage)


def find_event_for_message(message, guild=None):
    if guild is None and message.guild is not None:
        guild = GUILDS.get(message.guild.id)
    if guild is None:
        return None
    for event in guild.events:
        if event.recruiting_message == message: return event
        for party in event.parties or []:
            if message in (party.message, getattr(party, 'threadControlMessage', None)):
                return event
    return None


def searchLightParty(message:discord.Message, parties:list[Party]) -> LightParty|None:
    for party in parties:
        if isinstance(party, LightParty):
            if message.id == party.message.id or message.id == party.threadControlMessage.id: return party
    return None


@client.event
async def on_reaction_remove(reaction:discord.Reaction, user:discord.Member|discord.User):
    if user == client.user or not reaction.is_custom_emoji(): return
    guild = GUILDS.get(reaction.message.guild.id)
    if guild is None: return
    if guild.MEMBER_ROLE not in user.roles: return
    now = dt.now()
    print(f'{now} receive reaction remove {user} {reaction.emoji.name}')
    event = find_event_for_message(reaction.message, guild)
    if event is None or reaction.emoji != guild.RECRUITING_EMOJI: return
    if event.parties is not None:
        party = searchLightParty(reaction.message, event.parties)
        if party is not None:
            for delMessage, member in list(party.joins.items()):
                if user == member:
                    del party.joins[delMessage]
                    await delMessage.edit(f'@everyone {member.display_name} が参加取り下げ', view=DummyApproveView())
                    break
    elif event.recruiting_message == reaction.message and event.starts_at - delta(minutes=30) <= now < event.starts_at - delta(minutes=10):
        if user in event.recruiting_members:
            event.recruiting_members.remove(user)
            await reaction.message.edit(recruitMessageReplace(guild.recruitingMessageItems[-1].text, event.starts_at, len(event.recruiting_members)))
        sendMessage = now.strftime('[%y-%m-%d %H:%M:%S.%f]') + f' :red_square: {user.display_name} '
        for role in filter(lambda r:r in guild.ROLES.keys(), user.roles): sendMessage += str(guild.ROLES[role].emoji)
        await guild.RECRUIT_LOG_CH.send(sendMessage)

##############################################################################################
## 
async def reply_message(message:discord.Message, send:str, accept:bool):
    msg = await message.reply(send)
    await msg.delete(delay=10)
    if accept: print(f'{message.guild.name} {message.author.display_name} command success: {message.content}')
    else: print(f'{message.guild.name} {message.author.display_name} command error: {message.content}')

#endregion

##############################################################################################
##############################################################################################
#region メッセージ削除
@client.event
async def on_message_delete(message):
    guild = GUILDS.get(message.guild.id) if message.guild else None
    if guild is not None and message == guild.COMMAND_MSG:
        guild.COMMAND_MSG = await command_message(guild.COMMAND_CH, guild.settingRoles)

#endregion

##############################################################################################
##############################################################################################
#region 定期実行 パーティ編成
        
    # if (now + delta(minutes=1)).month == now.month + 1: # 1分後が来月 -> 明日が1日の23:59
    #     members = joinLeaveMembers(guild.GUILD, 3, guild.GUILD.get_role(1246989946263306302))
    #     msg = '3か月不参加メンバ:'
    #     if members:
    #         for member in members:
    #             msg += f' {member.mention}'
    #     else:
    #         msg += '（なし）'
    #     await guild.DEV_CH

    ######################################################
    #
    # elif now + delta(minutes=60) > guild.timeTable[0]:
    #     while True:
    #         if len(guild.timeTable) == 0: break
    #         del guild.timeTable[0]
    #         if now + delta(minutes=60) <= guild.timeTable[0]: break

##############################################################################################
##############################################################################################
#endregion

#region 関数もろもろ
@tasks.loop(seconds=60)
async def loop():
    await run_scheduled_event(EVENT_RUNTIME)


async def command_message(textch:discord.TextChannel, raidRoles) -> discord.Message:
    msg = await textch.send(content=f'## 追加・削除したいロールをタップ', view=RoleManageView(raidRoles))
    return msg

async def getTimetable(updateStatus:bool=True) -> list[dt]:
    # タイムテーブルを取りに行く
    await client.change_presence(activity=discord.CustomActivity(name='タイムスケジュール取得中'), status=discord.Status.dnd)
    print(f'{dt.now()} getting Timetable')
    timeTable:list[dt] = []
    now30 = dt.now() + delta(minutes=30)
    for schedule in getTable(argv[1], argv[2]):
        # 編成員Fは「全兵団」の開催時刻を扱う。過ぎた時刻は除外する。
        if schedule.is_all_forces and schedule.datetime > now30:
            timeTable.append(schedule.datetime)
    if updateStatus and timeTable:
        await client.change_presence(activity=discord.CustomActivity(name=timeTable[0].strftime("Next:%H時")), status=discord.Status.online)
    print(f'{dt.now()} Timetable was get')
    return timeTable


def joinLeaveMembers(guild:discord.Guild, month:delta, exclusionRole:discord.Role|None=None):
    leaveMembers:set[discord.Member] = set(guild.members)
    # 既存のログフォルダ名 reclutionLog は互換性のため維持。
    with open(f'reclutionLog/{guild.name}.csv') as f:
        lines = f.readlines()
    for line in lines[-1::-1]:
        if line == '': continue
        element = line.strip().split(',')
        date = element[0].split('-')
        if dt('20' + date[0], date[1], date[2], date[3]) < dt.now() - month: break
        targetMember = guild.get_member(element[0])
        if not isinstance(targetMember, discord.Member): continue
        if targetMember.joined_at < dt.now() - month: continue
        if any(map(lambda role:role.position >= exclusionRole.position, targetMember.roles)): continue
        leaveMembers = leaveMembers - targetMember
    return leaveMembers






# 参加権チェック
    

async def autoJoinParticipant(user:discord.Member, event:EventInstance):
    '''最小パーティに参加申請'''
    minParty:LightParty|None = None
    for party in event.parties:
        if isinstance(party, LightParty):
            if ((minParty == None or minParty.membersNum() + len(minParty.joins) > party.membersNum() + len(party.joins))
                and party.membersNum() + len(party.joins) < 4):
                minParty = party
    if minParty == None:
        await createNewParty(user, event=event)
    else:
        await minParty.joinRequest(user)

#endregion

##############################################################################################
#region パーティ編成アルゴリズム
def createSpeedParties(participants:list[Participant], event:EventInstance) -> list[SpeedParty]:
    """formation.py の汎用編成結果を Discord 用 SpeedParty に変換する。"""
    participantRoles = {participant:set(participant.roles) for participant in participants}
    guild = event.guild
    formation = {role:info.count for role, info in guild.ROLES.items()}
    formedParties = formSpeedParties(participantRoles, formation)

    # 旧 speedFormation と同様、成立したフルパーティの参加者を元リストから除く。
    assigned = {member for party in formedParties for members in party.values() for member in members}
    participants[:] = [participant for participant in participants if participant not in assigned]

    parties:list[SpeedParty] = []
    for partyNumber, formedParty in enumerate(formedParties, start=1):
        party = SpeedParty(partyNumber, formation, context=make_party_context(event))
        for role, members in formedParty.items():
            for member in members:
                party.addMember(member, role)
        parties.append(party)
    return parties


def createLightParties(participants:list[Participant], partyIndex:int, event:EventInstance) -> list[LightParty]:
    """formation.py の汎用均等分割結果を Discord 用 LightParty に変換する。"""
    participantRoles = {participant:set(participant.roles) for participant in participants}
    formedParties = formLightParties(participantRoles, 4)

    parties:list[LightParty] = []
    for members in formedParties:
        partyIndex += 1
        parties.append(LightParty(partyIndex, members.copy(), context=make_party_context(event)))
    return parties


def pickParticipant(priorityPool:list[Participant], normalPool:list[Participant], bias:int) -> Participant:
    if len(priorityPool) == 0:
        if len(normalPool) == 0:
            return None
        return normalPool.pop(0)
    if len(normalPool) == 0:
        return priorityPool.pop(0)
    if random() > 1 / (bias + 1):
        # 優先側
        return priorityPool.pop(0)
    else:
        return normalPool.pop(0)
    
def revertParticipant(priorityPool:list[Participant], normalPool:list[Participant], participant:Participant):
    guild = GUILDS.get(participant.user.guild.id)
    if guild and {guild.PRIORITY_ROLE, guild.STATIC_PRIORITY_ROLE} & participant.roles:
        priorityPool.insert(0, participant)
    else:
        normalPool.insert(0, participant)

##############################################################################################
## エラーキャッチ

#endregion

##############################################################################################
#region パーティ生成
async def createNewParty(user:discord.Member, free:bool=False, event:EventInstance=None):
    if event is None: raise ValueError("Party creation requires its event instance")
    if len(event.parties) == 0: newPartyNum = 1
    else: newPartyNum = max(map(lambda x:x.number, event.parties)) + 1
    guild = event.guild
    roles = {role for role in user.roles if role in guild.ROLES.keys()}
    newParty = LightParty(newPartyNum, [Participant(user, roles)], free=free, context=make_party_context(event))
    newParty.message = await guild.PARTY_CH.send(newParty.getPartyMessage(guild.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    newParty.threadControlMessage = await newParty.thread.send(view=PartyView(context=make_view_context(event), duration=((event.starts_at + delta(hours=1)) - dt.now()).total_seconds()))
    await newParty.message.add_reaction(guild.RECRUITING_EMOJI)
    event.parties.append(newParty)

#endregion

##############################################################################################
#region Emoji 関数



#endregion

##############################################################################################
#region スラッシュコマンド








async def f_reboot(ctx:discord.ApplicationContext|None = None):
    if ctx:
        await ctx.respond('再起動します')
        guild = GUILDS.get(ctx.guild.id) if ctx.guild else None
        if guild:
            await guild.COMMAND_CH.purge()
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()


async def f_stableReboot(ctx:discord.ApplicationContext|None = None):
    if ctx:
        await ctx.respond('安定版再起動します')
        guild = GUILDS.get(ctx.guild.id) if ctx.guild else None
        if guild:
            await guild.COMMAND_CH.purge()
    Popen(['git', 'checkout', '--force', 'main'], cwd=getcwd())
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()


async def f_fetch():
    # チャンネル・ギルドをゲット。既存インスタンスを再利用してイベント状態を保つ。
    with open('IDs.json') as f:
        guild_configs = json.load(f)

    configured_guilds:dict[int, Guild] = {}
    for guild_info in guild_configs:
        guild_id = int(guild_info['guildID'])
        guild = GUILDS.get(guild_id) or Guild(guild_id, client)
        if guild.GUILD is None:
            print(f'Configured guild is not available: {guild_id}')
            continue

        channels = guild_info['channels']
        guild.PARTY_CH = client.get_channel(channels['party'])
        guild.PARTY_CH_beta = client.get_channel(channels['party-beta'])
        guild.PARTY_LOG = client.get_channel(channels['party-log'])
        guild.DEV_CH = client.get_channel(channels['develop'])
        guild.COMMAND_CH = client.get_channel(channels['command'])
        guild.RECRUIT_LOG_CH = client.get_channel(
            getCompatibleConfigValue(channels, 'recruit-log', 'recluit-log')
        )

        guild.recruitingMessageDirectory = getRecruitingMessageDirectory(guild_id)
        guild.recruitingMessageItems = getDirectoryItems(guild.recruitingMessageDirectory)

        emojis = guild_info['emojis']
        guild.RECRUITING_EMOJI = client.get_emoji(getCompatibleConfigValue(emojis, 'recruiting', 'recluting'))
        guild.FULLPARTY_EMOJI = client.get_emoji(emojis['fullparty'])
        guild.LIGHTPARTY_EMOJI = client.get_emoji(getCompatibleConfigValue(emojis, 'liteparty', 'lightparty'))

        guild.ROLES = {
            guild.GUILD.get_role(role_info['role']):
            RoleInfo(client.get_emoji(role_info['emoji']), role_name, role_info['count'])
            for role_name, role_info in guild_info['raidRoles'].items()
        }
        guild.MEMBER_ROLE = guild.GUILD.get_role(guild_info['roles']['member'])
        guild.PRIORITY_ROLE = guild.GUILD.get_role(guild_info['roles']['priority'])
        guild.STATIC_PRIORITY_ROLE = guild.GUILD.get_role(guild_info['roles']['staticPriority'])
        guild.MASTER_ROLE = guild.GUILD.get_role(guild_info['roles']['master'])
        guild.LITE_PARTY_ROLE = guild.GUILD.get_role(guild_info['roles']['liteParty'])

        await roleSetting(guild, guild_info)
        await guild.GUILD.chunk()
        configured_guilds[guild_id] = guild

        print(f'Guild: {guild.GUILD.name}: {guild.GUILD.id}')
        print(f'PARTY_CH: {guild.PARTY_CH.name}: {guild.PARTY_CH.id}')
        print(f'PARTY_CH_beta: {guild.PARTY_CH_beta.name}: {guild.PARTY_CH_beta.id}')
        print(f'DEV_CH: {guild.DEV_CH.name}: {guild.DEV_CH.id}')
        print(f'COMMAND_CH: {guild.COMMAND_CH.name}: {guild.COMMAND_CH.id}')
        print(f'RECRUIT_LOG_CH: {guild.RECRUIT_LOG_CH.name}: {guild.RECRUIT_LOG_CH.id}')

    GUILDS.clear()
    GUILDS.update(configured_guilds)


register_slash_commands(
    client,
    get_guild_state=lambda guild_id: GUILDS.get(guild_id),
    get_timetable=getTimetable,
    reboot=f_reboot,
    fetch=f_fetch,
    reboot_view=lambda guild_id: RebootView(context=make_view_context(guild_id=guild_id)),
)


async def roleSetting(guild:Guild, guild_info):
    # ロール設定チャンネル初期化
    guild.settingRoles = {
        setting_info['name']: {
            'role': guild.GUILD.get_role(setting_info['role']),
            'emoji': client.get_emoji(setting_info['emoji']),
        }
        for setting_info in guild_info['settingRoles']
    }

    await guild.COMMAND_CH.purge()
    guild.COMMAND_MSG = await command_message(guild.COMMAND_CH, guild.settingRoles)


# @client.slash_command(name='f-get-leave-month', description='任意の月間不参加者抽出')
# async def f_get_leave_month(ctx:discord.ApplicationContext, month:int):
#     leaveMembers = joinLeaveMembers(ctx.interaction.guild, delta(month=month), {1246661252147576842, 1246661367658840178, 1246989946263306302, 1393529338053267557, 1362429512909979778})
#     filename = f'cache/{ctx.interaction.guild.name}.csv'
#     with open(filename, 'w') as f:
#         for member in leaveMembers:
#             f.write(f'{member.id},{member.display_name}\n')
#     csvFile = discord.File(filename, filename=dt.now().strftime('leaveMembers_%y%m%d-%H%M%S.csv'))
#     await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ID,表示名`', file=csvFile)
    
#endregion

##############################################################################################
#region main
def setRebootSchedule(guild_id:int, schedule:discord.TextChannel|bool):
    guild = GUILDS.get(guild_id)
    if guild is None:
        raise KeyError(f'Guild is not configured: {guild_id}')
    guild.reboot_schedule = schedule
    guild.reboot_handled = False


def make_view_context(event=None, guild_id:int|None=None):
    def resolve_guild():
        if event is not None:
            return event.guild
        return GUILDS.get(guild_id)

    return ViewContext(
        get_guild=resolve_guild,
        get_event=lambda: event,
        search_party=searchLightParty,
        light_party_type=LightParty,
        speed_party_type=SpeedParty,
        make_participant=Participant,
        make_guest=Guest,
        check_role_right=checkRoleRight,
        create_party=createNewParty,
        format_recruit_message=recruitMessageReplace,
        report_error=printTraceback,
        reboot=f_reboot,
        stable_reboot=f_stableReboot,
        schedule_reboot=lambda schedule: setRebootSchedule(resolve_guild().GUILD.id, schedule),
    )


def make_party_context(event):
    return PartyContext(
        get_guild=lambda: event.guild,
        get_event=lambda: event,
        approve_view=lambda **kwargs: ApproveView(context=make_view_context(event), **kwargs),
        dummy_approve_view=lambda: DummyApproveView(),
        formation_top_view=lambda **kwargs: FormationTopView(context=make_view_context(event), **kwargs),
    )


EVENT_RUNTIME = EventRuntime(
    get_guilds=lambda: tuple(GUILDS.values()),
    client=client,
    get_directory_items=getDirectoryItems,
    recruit_message_replace=recruitMessageReplace,
    create_speed_parties=createSpeedParties,
    create_light_parties=createLightParties,
    formation_top_view=lambda event, **kwargs: FormationTopView(context=make_view_context(event), **kwargs),
    party_view=lambda event, **kwargs: PartyView(context=make_view_context(event), **kwargs),
    print_traceback=printTraceback,
    pick_participant=pickParticipant,
    get_timetable=getTimetable,
    reboot=f_reboot,
    get_reboot_schedule=lambda guild: guild.reboot_schedule,
    participant_type=Participant,
    speed_party_type=SpeedParty,
    light_party_type=LightParty,
)

if __name__ == '__main__':
    print(f'##################################################################################')
    print(f'{dt.now()} スクリプト起動')
    # print(f"Intents.members: {client.intents.members}")  # True ならOK
    try:
        with open('token.json', 'r', encoding='utf-8') as f:
            token = json.load(f)['token']
        client.run(token)
    except KeyboardInterrupt:
        exit()
