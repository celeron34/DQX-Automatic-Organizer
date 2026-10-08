from __future__ import annotations # 必ず先頭に
version = '1.1.10'

import discord
from discord.ext import tasks, commands
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
import os
from views import (
    ViewContext, ApproveView, DummyApproveView, PartyView,
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
from bot_tokens import get_token
from schedule_protocol import deserialize_entries


# インテント
intents = discord.Intents.all()
intents.members = True
intents.message_content = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_typing = True
intents.message_content = True
client = commands.Bot(
    debug_guilds=[1246651972342386791],
    intents=intents
    )

rebootSchedule:bool|discord.TextChannel = False

ROBIN_GUILD:Guild = None
SCHEDULE_ENTRIES = []
_last_schedule_message_id: int | None = None

##############################################################################################
##############################################################################################
#region イニシャライズ
@client.event
async def on_ready():
    global ROBIN_GUILD
    print(f'{dt.now()} on_ready START')

    await f_fetch()
    await load_latest_schedule_message()

    # コミットハッシュ取得
    script_dir = path.dirname(path.abspath(__file__)) # パス
    git_root = check_output(['git', '-C', script_dir, 'rev-parse', '--show-toplevel'], text=True).strip()
    commit_hash = check_output(['git', '-C', git_root, 'rev-parse', 'HEAD'], text=True).strip()
    await ROBIN_GUILD.DEV_CH.send(f'commit hash: {commit_hash}')

    # タイムテーブルをゲット
    timeTable = await getTimetable(False)
    ROBIN_GUILD.timeTable = timeTable
    ROBIN_GUILD.sync_events(timeTable)
    for t in ROBIN_GUILD.timeTable:
        print(t)

    # ループの時間調整
    await client.change_presence(activity=discord.CustomActivity(name='時間同期待ち'), status=discord.Status.dnd)
    second = dt.now().second
    print(f'{dt.now()} Loop sync wait')
    await sleep(60.5 - second)
    loop.start()
    print(f'{dt.now()} loop Start')

    status = timeTable[0].strftime("Next:%H時") if timeTable else "スケジュール受信待ち"
    await client.change_presence(activity=discord.CustomActivity(name=status))
    print(f'{dt.now()} on_ready END')

#endregion

##############################################################################################
##############################################################################################
#region リアクション追加検知
@client.event
async def on_reaction_add(reaction:discord.Reaction, user:discord.Member|discord.User):
    if user == client.user or not reaction.is_custom_emoji(): return
    guild = ROBIN_GUILD
    now = dt.now()
    print(f'{now} receive reaction add {user} {reaction.emoji.name}')
    event = find_event_for_message(reaction.message)
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


def find_event_for_message(message):
    for event in ROBIN_GUILD.events:
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
    guild = ROBIN_GUILD
    if user == client.user or not reaction.is_custom_emoji(): return
    if guild.MEMBER_ROLE not in user.roles: return
    now = dt.now()
    print(f'{now} receive reaction remove {user} {reaction.emoji.name}')
    event = find_event_for_message(reaction.message)
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
#endregion

##############################################################################################
##############################################################################################
#region 定期実行 パーティ編成
        
    # if (now + delta(minutes=1)).month == now.month + 1: # 1分後が来月 -> 明日が1日の23:59
    #     members = joinLeaveMembers(ROBIN_GUILD.GUILD, 3, ROBIN_GUILD.GUILD.get_role(1246989946263306302))
    #     msg = '3か月不参加メンバ:'
    #     if members:
    #         for member in members:
    #             msg += f' {member.mention}'
    #     else:
    #         msg += '（なし）'
    #     await ROBIN_GUILD.DEV_CH

    ######################################################
    #
    # elif now + delta(minutes=60) > ROBIN_GUILD.timeTable[0]:
    #     while True:
    #         if len(ROBIN_GUILD.timeTable) == 0: break
    #         del ROBIN_GUILD.timeTable[0]
    #         if now + delta(minutes=60) <= ROBIN_GUILD.timeTable[0]: break

##############################################################################################
##############################################################################################
#endregion

#region 関数もろもろ
@tasks.loop(seconds=60)
async def loop():
    await run_scheduled_event(EVENT_RUNTIME)


async def getTimetable(updateStatus:bool=True) -> list[dt]:
    """Select future all-forces events from the latest schedule push."""
    print(f'{dt.now()} reading in-memory schedule snapshot')
    now30 = dt.now() + delta(minutes=30)
    timeTable = [
        schedule.datetime for schedule in SCHEDULE_ENTRIES
        if schedule.is_all_forces and schedule.datetime > now30
    ]
    if updateStatus and timeTable:
        await client.change_presence(activity=discord.CustomActivity(name=timeTable[0].strftime("Next:%H時")), status=discord.Status.online)
    print(f'{dt.now()} selected {len(timeTable)} future all-force events')
    return timeTable


@client.event
async def on_message(message: discord.Message):
    channel_id = os.environ.get('SCHEDULE_SYNC_CHANNEL_ID')
    schedule_bot_id = os.environ.get('SCHEDULE_BOT_USER_ID')
    if not channel_id or not schedule_bot_id:
        return
    if message.author.id != int(schedule_bot_id) or message.channel.id != int(channel_id):
        return
    if message.content != 'DQX_SCHEDULE_SYNC_V1':
        return
    await process_schedule_message(message)


async def load_latest_schedule_message() -> None:
    channel_id = os.environ.get('SCHEDULE_SYNC_CHANNEL_ID')
    schedule_bot_id = os.environ.get('SCHEDULE_BOT_USER_ID')
    if not channel_id or not schedule_bot_id:
        return
    channel = client.get_channel(int(channel_id))
    if channel is None:
        channel = await client.fetch_channel(int(channel_id))
    async for message in channel.history(limit=100):
        if (
            message.author.id == int(schedule_bot_id)
            and message.content == 'DQX_SCHEDULE_SYNC_V1'
        ):
            await process_schedule_message(message)
            return


async def process_schedule_message(message: discord.Message) -> None:
    global _last_schedule_message_id
    if message.id == _last_schedule_message_id:
        return
    attachment = next(
        (item for item in message.attachments if item.filename == 'dqx-schedule.json'),
        None,
    )
    if attachment is None:
        print(f'{dt.now()} ignored schedule bridge message without JSON attachment')
        return
    try:
        entries = deserialize_entries(json.loads((await attachment.read()).decode('utf-8')))
        if not entries:
            raise ValueError('schedule entries are empty')
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f'{dt.now()} ignored invalid schedule bridge message: {error}')
        return

    SCHEDULE_ENTRIES[:] = entries
    starts_at = await getTimetable(False)
    ROBIN_GUILD.timeTable = starts_at
    ROBIN_GUILD.sync_events(starts_at)
    if starts_at:
        await client.change_presence(
            activity=discord.CustomActivity(name=starts_at[0].strftime('Next:%H時'))
        )
    print(f'{dt.now()} received {len(entries)} schedule entries; created/updated {len(starts_at)} future events')
    _last_schedule_message_id = message.id


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
    global ROBIN_GUILD
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
    formation = {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}
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
    if set(ROBIN_GUILD.PRIORITY_ROLE, ROBIN_GUILD.STATIC_PRIORITY_ROLE) & participant.roles:
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
    roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
    newParty = LightParty(newPartyNum, [Participant(user, roles)], free=free, context=make_party_context(event))
    newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    newParty.threadControlMessage = await newParty.thread.send(view=PartyView(context=make_view_context(event), duration=((event.starts_at + delta(hours=1)) - dt.now()).total_seconds()))
    await newParty.message.add_reaction(ROBIN_GUILD.RECRUITING_EMOJI)
    event.parties.append(newParty)

#endregion

##############################################################################################
#region Emoji 関数



#endregion

##############################################################################################
#region スラッシュコマンド








async def f_reboot(ctx:discord.ApplicationContext|None = None):
    if ctx: await ctx.respond('再起動します')
    await ROBIN_GUILD.COMMAND_CH.purge()
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()

async def f_stableReboot(ctx:discord.ApplicationContext|None = None):
    if ctx: await ctx.respond('安定版再起動します')
    await ROBIN_GUILD.COMMAND_CH.purge()
    Popen(['git', 'checkout', '--force', 'main'], cwd=getcwd())
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()


async def f_fetch():
    global ROBIN_GUILD
    # チャンネル・ギルドをゲット
    with open('IDs.json') as f:
        IDs = json.load(f)

    for guildInfo in [IDs[0]]:
        ROBIN_GUILD = Guild(guildInfo['guildID'], client)

        # チャンネルゲット
        ROBIN_GUILD.PARTY_CH      = client.get_channel(guildInfo['channels']['party'])
        ROBIN_GUILD.PARTY_CH_beta = client.get_channel(guildInfo['channels']['party-beta'])
        ROBIN_GUILD.PARTY_LOG     = client.get_channel(guildInfo['channels']['party-log'])
        ROBIN_GUILD.DEV_CH        = client.get_channel(guildInfo['channels']['develop'])
        ROBIN_GUILD.COMMAND_CH    = client.get_channel(guildInfo['channels']['command'])
        # 募集ログチャンネルは新しいキーを優先し、旧キーも読み込む。
        ROBIN_GUILD.RECRUIT_LOG_CH = client.get_channel(
            getCompatibleConfigValue(guildInfo['channels'], 'recruit-log', 'recluit-log')
        )

        # 旧フォルダー名も互換性のため読み込み可能。
        ROBIN_GUILD.recruitingMessageDirectory = getRecruitingMessageDirectory(ROBIN_GUILD.GUILD.id)
        ROBIN_GUILD.recruitingMessageItems = getDirectoryItems(ROBIN_GUILD.recruitingMessageDirectory)
        
        # 絵文字ゲット
        ROBIN_GUILD.RECRUITING_EMOJI =  client.get_emoji(getCompatibleConfigValue(guildInfo['emojis'], 'recruiting', 'recluting'))
        ROBIN_GUILD.FULLPARTY_EMOJI =  client.get_emoji(guildInfo['emojis']['fullparty'])
        ROBIN_GUILD.LIGHTPARTY_EMOJI = client.get_emoji(getCompatibleConfigValue(guildInfo['emojis'], 'liteparty', 'lightparty'))

        # ロールゲット
        ROBIN_GUILD.ROLES = {
                ROBIN_GUILD.GUILD.get_role(roleInfo['role']) : \
                RoleInfo(client.get_emoji(roleInfo['emoji']), roleName, roleInfo['count']) \
                    for roleName, roleInfo in guildInfo['raidRoles'].items()
            }
        ROBIN_GUILD.MEMBER_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['member'])
        ROBIN_GUILD.PRIORITY_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['priority'])
        ROBIN_GUILD.STATIC_PRIORITY_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['staticPriority'])
        ROBIN_GUILD.MASTER_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['master'])
        ROBIN_GUILD.LITE_PARTY_ROLE = ROBIN_GUILD.GUILD.get_role(guildInfo['roles']['liteParty'])

        await ROBIN_GUILD.GUILD.chunk()

        print(f'Guild.GUILD.name: {ROBIN_GUILD.GUILD.name}: {ROBIN_GUILD.GUILD.id}')
        print(f'Guild.PARTY_CH.name: {ROBIN_GUILD.PARTY_CH.name}: {ROBIN_GUILD.PARTY_CH.id}')
        print(f'ROBIN_GUILD.PARTY_CH_beta: {ROBIN_GUILD.PARTY_CH_beta.name}: {ROBIN_GUILD.PARTY_CH_beta.id}')
        print(f'ROBIN_GUILD.DEV_CH: {ROBIN_GUILD.DEV_CH.name}: {ROBIN_GUILD.DEV_CH.id}')
        print(f'ROBIN_GUILD.COMMAND_CH: {ROBIN_GUILD.COMMAND_CH.name}: {ROBIN_GUILD.COMMAND_CH.id}')
        print(f'ROBIN_GUILD.RECRUIT_LOG_CH: {ROBIN_GUILD.RECRUIT_LOG_CH.name}: {ROBIN_GUILD.RECRUIT_LOG_CH.id}')
        print(f'ROBIN_GUILD.RECRUITING_EMOJI: {ROBIN_GUILD.RECRUITING_EMOJI.name}: {ROBIN_GUILD.RECRUITING_EMOJI.id}')
        print(f'ROBIN_GUILD.FULLPARTY_EMOJI: {ROBIN_GUILD.FULLPARTY_EMOJI.name}: {ROBIN_GUILD.FULLPARTY_EMOJI.id}')
        print(f'ROBIN_GUILD.LIGHTPARTY_EMOJI: {ROBIN_GUILD.LIGHTPARTY_EMOJI.name}: {ROBIN_GUILD.LIGHTPARTY_EMOJI.id}')
        print(f'ROBIN_GUILD.MEMBER_ROLE: {ROBIN_GUILD.MEMBER_ROLE.name}: {ROBIN_GUILD.MEMBER_ROLE.id}')
        print(f'ROBIN_GUILD.PRIORITY_ROLE: {ROBIN_GUILD.PRIORITY_ROLE.name}: {ROBIN_GUILD.PRIORITY_ROLE.id}')
        print(f'ROBIN_GUILD.STATIC_PRIORITY_ROLE: {ROBIN_GUILD.STATIC_PRIORITY_ROLE.name}: {ROBIN_GUILD.STATIC_PRIORITY_ROLE.id}')
        print(f'ROBIN_GUILD.LITE_PARTY_ROLE: {ROBIN_GUILD.LITE_PARTY_ROLE.name}: {ROBIN_GUILD.LITE_PARTY_ROLE.id}')
        print('ROBIN_GUILD.ROLES:{')
        for role, roleInfo in ROBIN_GUILD.ROLES.items():
            print(f'\trole:{role}: .name:{roleInfo.name}, .emoji:{roleInfo.emoji}, .count:{roleInfo.count}')
        print('}')
register_slash_commands(
    client,
    get_guild_state=lambda: ROBIN_GUILD,
    reboot=f_reboot,
    fetch=f_fetch,
    reboot_view=lambda: RebootView(context=VIEW_CONTEXT),
)


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
def setRebootSchedule(schedule:discord.TextChannel|bool):
    global rebootSchedule
    rebootSchedule = schedule
    ROBIN_GUILD.reboot_handled = False


def make_view_context(event=None):
    return ViewContext(
        get_guild=lambda: ROBIN_GUILD,
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
        schedule_reboot=setRebootSchedule,
    )


def make_party_context(event):
    return PartyContext(
        get_guild=lambda: ROBIN_GUILD,
        get_event=lambda: event,
        approve_view=lambda **kwargs: ApproveView(context=make_view_context(event), **kwargs),
        dummy_approve_view=lambda: DummyApproveView(),
    )


VIEW_CONTEXT = make_view_context()

EVENT_RUNTIME = EventRuntime(
    get_guild=lambda: ROBIN_GUILD,
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
    get_reboot_schedule=lambda: rebootSchedule,
    participant_type=Participant,
    speed_party_type=SpeedParty,
    light_party_type=LightParty,
)


if __name__ == '__main__':
    print(f'##################################################################################')
    print(f'{dt.now()} スクリプト起動')
    # print(f"Intents.members: {client.intents.members}")  # True ならOK
    try:
        client.run(get_token('formation'))
    except KeyboardInterrupt:
        exit()
