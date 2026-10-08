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
    getDirectoryItems, markdownEsc, printTraceback, recruitMessageReplace,
    replaces, sendDirectory,
)
from event_definition import EventDefinition, EventPhase
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
client = commands.Bot(
    debug_guilds=[1246651972342386791],
    intents=intents
    )

rebootSchedule:bool|discord.TextChannel = False

ROBIN_GUILD:Guild = None

##############################################################################################
##############################################################################################
#region イニシャライズ
@client.event
async def on_ready():
    global ROBIN_GUILD
    print(f'{dt.now()} on_ready START')

    await f_fetch()

    # コミットハッシュ取得
    script_dir = path.dirname(path.abspath(__file__)) # パス
    git_root = check_output(['git', '-C', script_dir, 'rev-parse', '--show-toplevel'], text=True).strip()
    commit_hash = check_output(['git', '-C', git_root, 'rev-parse', 'HEAD'], text=True).strip()
    await ROBIN_GUILD.DEV_CH.send(f'commit hash: {commit_hash}')

    # タイムテーブルをゲット
    timeTable = await getTimetable(False)
    ROBIN_GUILD.timeTable = timeTable
    for t in ROBIN_GUILD.timeTable:
        print(t)

    # ループの時間調整
    await client.change_presence(activity=discord.CustomActivity(name='時間同期待ち'), status=discord.Status.dnd)
    second = dt.now().second
    print(f'{dt.now()} Loop sync wait')
    await sleep(60.5 - second)
    loop.start()
    print(f'{dt.now()} loop Start')

    await client.change_presence(activity=discord.CustomActivity(name=timeTable[0].strftime("Next:%H時"))) # なぜかここにないと動かない
    print(f'{dt.now()} on_ready END')

#endregion

##############################################################################################
##############################################################################################
#region リアクション追加検知
@client.event
async def on_reaction_add(reaction:discord.Reaction, user:discord.Member|discord.User):
    global ROBIN_GUILD
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if not reaction.is_custom_emoji(): return # カスタム絵文字以外を無視

    # message = await ROBIN_GUILD.PARTY_CH.fetch_message(reaction.message.id)
    now = dt.now()
    print(f'{now} receive reaction add {user} {reaction.emoji.name}')

    # 途中参加申請
    if ROBIN_GUILD.parties != None:
        if reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI: # 参加絵文字(メッセージ判定は後)
            # 参加権チェック
            if not (await checkRoleRight(user, reaction.message.channel, {ROBIN_GUILD.MEMBER_ROLE}, '参加権がありません') and
                await checkRoleRight(user, reaction.message.channel, set(ROBIN_GUILD.ROLES.keys()), 'ロールが設定されていません')):
                await reaction.message.remove_reaction(reaction.emoji, user)
                return
            # 途中自動参加
            if reaction.message == ROBIN_GUILD.recruitingMessage:
                # パーティメンバでなければ自動参加
                if not any(map(lambda party:party.isMember(user), ROBIN_GUILD.parties)):
                    await autoJoinParticipant(user)
            # パーティメッセージ
            elif reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI:
                # 通常参加申請
                party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
                await party.joinRequest(user)
    # 通常参加申請
    elif (ROBIN_GUILD.timeTable[0] - delta(minutes=30) <= now and
          now < ROBIN_GUILD.timeTable[0] - delta(minutes=10)): # パーティ編成前
        # リアクション判定 参加リアクションを募集メッセージ
        if (reaction.message == ROBIN_GUILD.recruitingMessage and
            reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI):
            # 参加権チェック
            if not (await checkRoleRight(user, reaction.message.channel, {ROBIN_GUILD.MEMBER_ROLE}, '参加権がありません') and \
                await checkRoleRight(user, reaction.message.channel, set(ROBIN_GUILD.ROLES.keys()), 'ロールが設定されていません')):
                await reaction.message.remove_reaction(reaction.emoji, user)
                return
            if reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI:
                ROBIN_GUILD.RECRUITING_MEMBER.append(user)
                await reaction.message.edit(recruitMessageReplace(ROBIN_GUILD.recruitingMessageItems[-1].text, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECRUITING_MEMBER)))
                sendMessage = dt.now().strftime('[%y-%m-%d %H:%M:%S.%f]') + f' :green_square: {user.display_name} '
                sendMessage += str(ROBIN_GUILD.LIGHTPARTY_EMOJI) if ROBIN_GUILD.LITE_PARTY_ROLE in user.roles else ''
                for role in filter(lambda r:r in ROBIN_GUILD.ROLES.keys(), user.roles):
                    sendMessage += str(ROBIN_GUILD.ROLES[role].emoji)
                await ROBIN_GUILD.RECRUIT_LOG_CH.send(sendMessage)

##############################################################################################
## 
def searchLightParty(message:discord.Message, parties:list[Party]) -> LightParty|None:
    for party in parties:
        if isinstance(party, LightParty):
            print(f'target message:{message.id} party.message:{party.message.id} party.threadControlMessage:{party.threadControlMessage.id}')
            if message.id == party.message.id or message.id == party.threadControlMessage.id:
                return party
    return None

#endregion

##############################################################################################
##############################################################################################
#region リアクション削除検知
@client.event
async def on_reaction_remove(reaction:discord.Reaction, user:discord.Member|discord.User):
    global ROBIN_GUILD
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if not reaction.is_custom_emoji(): return # カスタム絵文字以外を無視
    if ROBIN_GUILD.MEMBER_ROLE not in user.roles: return

    now = dt.now()
    print(f'{now} receive reaction remove {user} {reaction.emoji.name}')

    # if reaction.message == ROBIN_GUILD.recruitingMessage: # 募集メッセージ判定
    #     if reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI:
    #         ROBIN_GUILD.formation.rmMember(user)
    #         return
    
    # 参加申請取り消し
    if ROBIN_GUILD.parties != None: # パーティズ変数が存在
        # リアクション・メッセージ判定
        # リアクションはパーティのどれかに該当
        if (reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and
            reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI):
            party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
            for delMessage, member in party.joins.items():
                # partyのjoinsにあるなら削除と通知
                if user == member:
                    del party.joins[delMessage]
                    await delMessage.edit(f'@everyone {member.display_name} が参加取り下げ', view=DummyApproveView())
                    break
    # 初期編成参加申請取り消し
    elif (ROBIN_GUILD.timeTable[0] - delta(minutes=30) <= now and
          now < ROBIN_GUILD.timeTable[0] - delta(minutes=10)): # パーティ編成前
        # リアクション・メッセージ判定
        if (reaction.message == ROBIN_GUILD.recruitingMessage and
            reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI):
            # 参加プールにいる場合辞退処理
            if user in ROBIN_GUILD.RECRUITING_MEMBER:
                ROBIN_GUILD.RECRUITING_MEMBER.remove(user)
                await reaction.message.edit(recruitMessageReplace(ROBIN_GUILD.recruitingMessageItems[-1].text, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECRUITING_MEMBER)))
            sendMessage = now.strftime('[%y-%m-%d %H:%M:%S.%f]') + f' :red_square: {user.display_name} '
            for role in filter(lambda r:r in ROBIN_GUILD.ROLES.keys(), user.roles):
                sendMessage += str(ROBIN_GUILD.ROLES[role].emoji)
            await ROBIN_GUILD.RECRUIT_LOG_CH.send(sendMessage)

#endregion
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
    if message == ROBIN_GUILD.COMMAND_MSG:
        ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH)

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


async def command_message(textch:discord.TextChannel, raidRoles) -> discord.Message:
    msg = await textch.send(content=f'## 追加・削除したいロールをタップ', view=RoleManageView(raidRoles))
    return msg

async def getTimetable(updateStatus:bool=True) -> list[dt]:
    # タイムテーブルを取りに行く
    await client.change_presence(activity=discord.CustomActivity(name='タイムスケジュール取得中'), status=discord.Status.dnd)
    print(f'{dt.now()} getting Timetable')
    timeTable:list[dt] = []
    now30 = dt.now() + delta(minutes=30)
    for t in getTable(argv[1], argv[2]):
        # 通過したものは追加しない
        if t > now30:
            timeTable.append(t)
    if updateStatus:
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
    

async def autoJoinParticipant(user:discord.Member):
    '''最小パーティに参加申請'''
    global ROBIN_GUILD
    minParty:LightParty|None = None
    for party in ROBIN_GUILD.parties:
        if isinstance(party, LightParty):
            if ((minParty == None or minParty.membersNum() + len(minParty.joins) > party.membersNum() + len(party.joins))
                and party.membersNum() + len(party.joins) < 4):
                minParty = party
    if minParty == None:
        await createNewParty(user)
    else:
        await minParty.joinRequest(user)

#endregion

##############################################################################################
#region パーティ編成アルゴリズム
def createSpeedParties(participants:list[Participant]) -> list[SpeedParty]:
    """formation.py の汎用編成結果を Discord 用 SpeedParty に変換する。"""
    participantRoles = {participant:set(participant.roles) for participant in participants}
    formation = {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}
    formedParties = formSpeedParties(participantRoles, formation)

    # 旧 speedFormation と同様、成立したフルパーティの参加者を元リストから除く。
    assigned = {member for party in formedParties for members in party.values() for member in members}
    participants[:] = [participant for participant in participants if participant not in assigned]

    parties:list[SpeedParty] = []
    for partyNumber, formedParty in enumerate(formedParties, start=1):
        party = SpeedParty(partyNumber, formation, context=PARTY_CONTEXT)
        for role, members in formedParty.items():
            for member in members:
                party.addMember(member, role)
        parties.append(party)
    return parties


def createLightParties(participants:list[Participant], partyIndex:int) -> list[LightParty]:
    """formation.py の汎用均等分割結果を Discord 用 LightParty に変換する。"""
    participantRoles = {participant:set(participant.roles) for participant in participants}
    formedParties = formLightParties(participantRoles, 4)

    parties:list[LightParty] = []
    for members in formedParties:
        partyIndex += 1
        parties.append(LightParty(partyIndex, members.copy(), context=PARTY_CONTEXT))
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
async def createNewParty(user:discord.Member, free:bool=False):
    if len(ROBIN_GUILD.parties) == 0: newPartyNum = 1
    else: newPartyNum = max(map(lambda x:x.number, ROBIN_GUILD.parties)) + 1
    roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
    newParty = LightParty(newPartyNum, [Participant(user, roles)], free=free, context=PARTY_CONTEXT)
    newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    newParty.threadControlMessage = await newParty.thread.send(view=PartyView(context=VIEW_CONTEXT, duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))
    await newParty.message.add_reaction(ROBIN_GUILD.RECRUITING_EMOJI)
    ROBIN_GUILD.parties.append(newParty)

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
        # IDs.json の既存キー recluit-log / recluting は互換性のため維持。
        ROBIN_GUILD.RECRUIT_LOG_CH = client.get_channel(guildInfo['channels']['recluit-log'])

        # 既存の募集文フォルダ名 recluitingMessage は互換性のため維持。
        ROBIN_GUILD.recruitingMessageItems = getDirectoryItems(f'guilds/{ROBIN_GUILD.GUILD.id}/recluitingMessage')
        
        # 絵文字ゲット
        ROBIN_GUILD.RECRUITING_EMOJI =  client.get_emoji(guildInfo['emojis']['recluting'])
        ROBIN_GUILD.FULLPARTY_EMOJI =  client.get_emoji(guildInfo['emojis']['fullparty'])
        ROBIN_GUILD.LIGHTPARTY_EMOJI = client.get_emoji(guildInfo['emojis']['lightparty'])

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

        await roleSetting(guildInfo)

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
        print('roleSetting:{')

register_slash_commands(
    client,
    get_guild_state=lambda: ROBIN_GUILD,
    get_timetable=getTimetable,
    reboot=f_reboot,
    fetch=f_fetch,
    reboot_view=lambda: RebootView(context=VIEW_CONTEXT),
)


async def roleSetting(guildInfo):
    global ROBIN_GUILD
    # ロール設定チャンネル初期化
    settingRoles = {
        settingInfo['name']:
        {'role':ROBIN_GUILD.GUILD.get_role(settingInfo['role']), 'emoji':client.get_emoji(settingInfo['emoji'])}
        for settingInfo in guildInfo['settingRoles']
    }
    print('roleSetting:{')
    for name, value in settingRoles.items():
        print(f'\t{name}:', end='')
        for k,v in value.items():
            print(f' {k}:<{v.name}:{v.id}>', end='')
        print()
    print('}')

    await ROBIN_GUILD.COMMAND_CH.purge()
    ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH, settingRoles)


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


VIEW_CONTEXT = ViewContext(
    get_guild=lambda: ROBIN_GUILD,
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

PARTY_CONTEXT = PartyContext(
    get_guild=lambda: ROBIN_GUILD,
    approve_view=lambda **kwargs: ApproveView(context=VIEW_CONTEXT, **kwargs),
    dummy_approve_view=lambda: DummyApproveView(),
)

EVENT_RUNTIME = EventRuntime(
    get_guild=lambda: ROBIN_GUILD,
    client=client,
    get_directory_items=getDirectoryItems,
    recruit_message_replace=recruitMessageReplace,
    create_speed_parties=createSpeedParties,
    create_light_parties=createLightParties,
    formation_top_view=lambda **kwargs: FormationTopView(context=VIEW_CONTEXT, **kwargs),
    party_view=lambda **kwargs: PartyView(context=VIEW_CONTEXT, **kwargs),
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
        with open('token.json', 'r', encoding='utf-8') as f:
            token = json.load(f)['token']
        client.run(token)
    except KeyboardInterrupt:
        exit()
