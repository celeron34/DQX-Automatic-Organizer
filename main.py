from __future__ import annotations # 必ず先頭に
version = '1.1.10'

import discord
from discord.ext import tasks, commands
from dqx_ise import getTable
from datetime import datetime as dt, timedelta as delta
from asyncio import sleep, create_task
# from asyncio import get_running_loop, create_task
# from concurrent.futures import ThreadPoolExecutor
from random import shuffle, randint, random
from typing import Any
from time import perf_counter
from sys import argv, exc_info, executable, exit
from subprocess import Popen, check_output
from traceback import extract_tb, format_list
from re import sub, match
from os import getcwd, path, mkdir
from glob import glob
from partyEvent import *
from formation import *
from views import *
from utils import *
import json

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

rebootScadule:bool|discord.TextChannel = False

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
    print(f'{now} recive reaction add {user} {reaction.emoji.name}')

    # 途中参加申請
    if ROBIN_GUILD.parties != None:
        if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI: # 参加絵文字(メッセージ判定は後)
            # 参加権チェック
            if not await checkParticipationRight(user, reaction.message.channel):
                await reaction.message.remove_reaction(reaction.emoji, user)
                return
            # 途中自動参加
            if reaction.message == ROBIN_GUILD.reclutingMessage:
                # パーティメンバでなければ自動参加
                if not any(map(lambda party:party.isMember(user), ROBIN_GUILD.parties)):
                    await autoJoinParticipant(user)
            # パーティメッセージ
            elif reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
                # 通常参加申請
                party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
                await party.joinRequest(user)
    # 通常参加申請
    elif (ROBIN_GUILD.timeTable[0] - delta(minutes=30) <= now and
          now < ROBIN_GUILD.timeTable[0] - delta(minutes=10)): # パーティ編成前
        # リアクション判定 参加リアクションを募集メッセージ
        if (reaction.message == ROBIN_GUILD.reclutingMessage and
            reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI):
            # 参加権チェック
            if not await checkParticipationRight(user, reaction.message.channel):
                await reaction.message.remove_reaction(reaction.emoji, user)
                return
            if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
                ROBIN_GUILD.RECLUTING_MEMBER.add(user)
                await reaction.message.edit(recluitMessageReplace(ROBIN_GUILD.reclutingMessageItems[-1].text, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECLUTING_MEMBER)))
                sendMessage = dt.now().strftime('[%y-%m-%d %H:%M]') + f' :green_square: {user.display_name}\n現在の参加者:'
                for member in ROBIN_GUILD.RECLUTING_MEMBER:
                    sendMessage += f' {member.display_name}'
                await ROBIN_GUILD.RECLUIT_LOG_CH.send(sendMessage)

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
    print(f'{now} recive reaction remove {user} {reaction.emoji.name}')

    # if reaction.message == ROBIN_GUILD.reclutingMessage: # 募集メッセージ判定
    #     if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
    #         ROBIN_GUILD.formation.rmMember(user)
    #         return
    
    # 参加申請取り消し
    if ROBIN_GUILD.parties != None: # パーティズ変数が存在
        # リアクション・メッセージ判定
        # リアクションはパーティのどれかに該当
        if (reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and
            reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI):
            party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
            for delMessage, member in party.joins.items():
                # partyのjoinsにあるなら削除と通知
                if user == member:
                    del party.joins[delMessage]
                    await delMessage.edit(f'@here {member.display_name} が参加取り下げ', view=DummyApproveView())
                    break
    # 初期編成参加申請取り消し
    elif (ROBIN_GUILD.timeTable[0] - delta(minutes=30) <= now and
          now < ROBIN_GUILD.timeTable[0] - delta(minutes=10)): # パーティ編成前
        # リアクション・メッセージ判定
        if (reaction.message == ROBIN_GUILD.reclutingMessage and
            reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI):
            # 参加プールにいる場合辞退処理
            if user in ROBIN_GUILD.RECLUTING_MEMBER:
                ROBIN_GUILD.RECLUTING_MEMBER.remove(user)
                await reaction.message.edit(recluitMessageReplace(ROBIN_GUILD.reclutingMessageItems[-1].text, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECLUTING_MEMBER)))
            sendMessage = now.strftime('[%y-%m-%d %H:%M]') + f' :red_square: {user.display_name}\n現在の参加者:'
            for member in ROBIN_GUILD.RECLUTING_MEMBER:
                sendMessage += f' {member.display_name}'
            await ROBIN_GUILD.RECLUIT_LOG_CH.send(sendMessage)

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
        ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH, ROBIN_GUILD.RAID_ROLES)

#endregion

##############################################################################################
##############################################################################################
#region サーバー加入
@client.event
async def on_member_join(member:discord.Member):
    if member.bot: return
    await member.add_roles(ROBIN_GUILD.UNAPPLIDE_MEMBER_ROLE)
    thread = await ROBIN_GUILD.UNAPPLIDE_CHANNEL.create_thread(name=f'{member.display_name}', type=discord.ChannelType.private_thread, invitable=False)
    await thread.send(f'{member.mention} {ROBIN_GUILD.MASTER_ROLE.mention}')
    await sendDirectory(f'guilds/{ROBIN_GUILD.GUILD.id}/memberJoin', thread)
    
#endregion

##############################################################################################
##############################################################################################
#region メンバー情報更新
@client.event
async def on_member_update(before:discord.Member, after:discord.Member):
    global ROBIN_GUILD
    if after.bot: return # ボットを無視
    diffRole = set(after.roles) - set(before.roles)
    if diffRole:
        # ロールが増えた
        if ROBIN_GUILD.MEMBER_ROLE in diffRole:
            # メンバロール
            targetChannels = set(filter(lambda ch:after.id in map(lambda m:m.id, ch.members), ROBIN_GUILD.UNAPPLIDE_CHANNEL.threads))
            if len(targetChannels) == 1:
                await sendDirectory(f'guilds/{ROBIN_GUILD.GUILD.id}/addMemberRole', targetChannels.pop())
            elif len(targetChannels) > 1:
                print('[Error] on_member_update > メンバロール付与: 2つ以上のスレッドに一致')
#endregion

##############################################################################################
##############################################################################################
#region 定期実行 パーティ編成
@tasks.loop(seconds=60)
async def loop():
    global ROBIN_GUILD
    
    now = dt.now()
    now = dt(now.year, now.month, now.day, now.hour, now.minute) # 秒数はゼロ

    ######################################################
    # 募集開始
    if now == ROBIN_GUILD.timeTable[0] - delta(minutes=30):
        # パーティ編成クラスをインスタンス化，メッセージ送信
        print(f'################### {dt.now()} Recluting ###################')
        ROBIN_GUILD.RECLUTING_MEMBER.clear()
        sendItems = getDirectoryItems(f'guilds/{ROBIN_GUILD.GUILD.id}/recluitingMessage')
        for index, sendItem in enumerate(sendItems):
            if index - len(sendItems) + 1 == 0:
                # 最後のメッセージ
                ROBIN_GUILD.reclutingMessage = await ROBIN_GUILD.PARTY_CH.send(
                    content=recluitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs
                    )
            else:
                await ROBIN_GUILD.PARTY_CH.send(
                    content=recluitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs)
        await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI) # 参加リアクション追加
        # await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.LIGHTPARTY_EMOJI) # ライトパーティリアクション追加
        # await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.FULLPARTY_EMOJI) # フルパーティリアクション追加
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Formation:%H時")))
        
        # try: # 250611 個別表示テスト
        #     await ROBIN_GUILD.DEV_CH.send('個別表示テスト\n表示テストのみで編成等に影響しません', view=RecluteView(timeout=1800, disable_on_timeout=False))
        # except Exception as e:
        #     printTraceback(e)
    
    elif now == ROBIN_GUILD.timeTable[0] - delta(minutes=15):
        await ROBIN_GUILD.PARTY_CH.send(f'パーティ編成まで残り5分 {ROBIN_GUILD.reclutingMessage.jump_url}')

    ######################################################
    # パーティ編成をアナウンス
    elif now == ROBIN_GUILD.timeTable[0] - delta(minutes=10):
        async with ROBIN_GUILD.PARTY_CH.typing():

            print(f'#================= {dt.now()} Formation =================#')

            ROBIN_GUILD.parties = list()
            # 値取得
            await ROBIN_GUILD.GUILD.chunk()
            ROBIN_GUILD.reclutingMessage = await ROBIN_GUILD.PARTY_CH.fetch_message(ROBIN_GUILD.reclutingMessage.id)
            try:
                participants:list[Participant] = list(
                    map(
                        lambda user:Participant(user, {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}),
                        ROBIN_GUILD.RECLUTING_MEMBER
                        )
                    )
            except Exception as e:
                printTraceback(e)
                participants = []
            for reaction in ROBIN_GUILD.reclutingMessage.reactions:
                if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
                    async for user in reaction.users():
                        if user == client.user: continue
                        if ROBIN_GUILD.MEMBER_ROLE not in user.roles: continue
                        if user in map(lambda x:x.user, participants): continue # 既に参加者リストにいるならスキップ
                        roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
                        participant = Participant(user, roles)
                        participants.append(participant)
            participantNum = len(participants)
            
            formationStartTime = dt.now()
            # 編成
            shuffle(participants)
            print(f'shaffled: {[participant.display_name for participant in participants]}')
            participantsCopy = participants.copy()
            # for party in speedFormation(participants):
            #     ROBIN_GUILD.parties.append(party)
            for party in lightFormation(participants, len(ROBIN_GUILD.parties)):
                ROBIN_GUILD.parties.append(party)
            print(f'formation algorithm time: {dt.now() - formationStartTime}')

            # パーティ通知メッセージ
            await ROBIN_GUILD.PARTY_CH.send(ROBIN_GUILD.timeTable[0].strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ\n原則、一番上がリーダーです'), \
                                            view=FormationTopView(duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))
            
            for party in ROBIN_GUILD.parties:
                party.message = await ROBIN_GUILD.PARTY_CH.send(party.getPartyMessage(ROBIN_GUILD.RAID_ROLES))
            
            print(f'{dt.now()} Add Log')
            with open(f'reactionLog/{ROBIN_GUILD.GUILD.name}.csv', 'a', encoding='utf8') as f:
                for participant in participants:
                    f.write(f"{ROBIN_GUILD.timeTable[0].strftime('%y-%m-%d-%H')},{participant.id}\n")

            print('participants')
            print([participant.display_name for participant in participants])
            
            await ROBIN_GUILD.PARTY_LOG.send(f'{ROBIN_GUILD.timeTable[0].strftime("%y/%m/%d %H")} 初期編成参加数 {participantNum}')

        # typingここまで

        print(f'{dt.now()} Formation END')

        print(f'{dt.now()} Create Threads')

        if any(map(lambda x:isinstance(x, SpeedParty), ROBIN_GUILD.parties)):
            await ROBIN_GUILD.PARTY_CH.send(file=discord.File('images/speedParty.png'))
        for party in ROBIN_GUILD.parties:
            if isinstance(party, SpeedParty):
                party.thread = await party.message.create_thread(name=f'SpeedParty:{party.number}', auto_archive_duration=60)
            elif isinstance(party, LightParty):
                party.thread = await party.message.create_thread(name=f'Party:{party.number}', auto_archive_duration=60)
                if party.membersNum() < 4: # 4人以下の時はリアクション
                    await party.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
                party.threadControlMessage = await party.thread.send(
                    view=PartyView(duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))
                if party.aliance:
                    try:
                        await party.sendAlianceInfo()
                    except Exception as e:
                        printTraceback(e)
        print(f'{dt.now()} Create Threads END')
        try: # パーティ同盟チェック
            for party in ROBIN_GUILD.parties:
                if isinstance(party, LightParty):
                    await party.alianceCheck(ROBIN_GUILD.parties)
                    if party.aliance:
                        await party.message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES))
        except Exception as e:
            printTraceback(e)

        try:
            # テスト編成
            participants = []
            priorities:list[Participant] = [p for p in participantsCopy
                                            if {ROBIN_GUILD.PRIORITY_ROLE, ROBIN_GUILD.STATIC_PRIORITY_ROLE} & p.roles]
            normals:list[Participant] = list(set(participantsCopy) - set(priorities))
            if len(normals) == 0:
                bias = 0
            else:
                bias = len(priorities) / len(normals) * 2
            while True:
                participant = pickParticipant(priorities, normals, bias)
                if participant is None: break
                participants.append(participant)
            parties:list[SpeedParty|LightParty] = []
            for party in speedFormation(participants):
                parties.append(party)
            for party in lightFormation(participants, len(parties)):
                parties.append(party)
            
            sendSpeedpartyDisplayName = ''
            sendLightpartyDisplayName = ''
            for party in parties:
                if isinstance(party, LightParty):
                    for member in party.members:
                        sendLightpartyDisplayName += f'{member.display_name}\n'
                elif isinstance(party, SpeedParty):
                    for members in party.members.values():
                        for member in members:
                            sendSpeedpartyDisplayName += f'{member.display_name}\n'

            await ROBIN_GUILD.RECLUIT_LOG_CH.send('## テスト編成表示\n### 高速パーティ\n' + sendSpeedpartyDisplayName + '\n### ライトパーティ\n' + sendLightpartyDisplayName)

            # 優先権操作
            if any(map(lambda party:isinstance(party, SpeedParty) , ROBIN_GUILD.parties)):
                # 高速パーティがあるなら優先権付与
                for party in ROBIN_GUILD.parties: # パーティループ
                    if isinstance(party, SpeedParty): # 高速パーティ
                        for participants in party.members.values(): # ロールループ
                            for participant in participants: # ユーザーループ
                                if ROBIN_GUILD.STATIC_PRIORITY_ROLE not in participant.user.roles:
                                    # 静的優先権を持っているなら動的優先権は付与しない
                                    participant.user.add_roles(ROBIN_GUILD.PRIORITY_ROLE) # 動的優先権付与
                    elif isinstance(party, LightParty): # 通常パーティ
                        for participant in party.members: # ユーザーループ
                            if ROBIN_GUILD.STATIC_PRIORITY_ROLE not in participant.user.roles:
                                # 静的優先権を持っているなら動的優先権は付与しない
                                participant.user.add_roles(ROBIN_GUILD.PRIORITY_ROLE) # 動的優先権付与
        except Exception as e:
            try: await ROBIN_GUILD.RECLUIT_LOG_CH.send('優先権操作に失敗')
            except Exception: pass
            printTraceback(e)

        ROBIN_GUILD.RECLUTING_MEMBER.clear()

        print('#==================================================================#')

        # ROBIN_GUILD.reclutingMessage = None

    ######################################################
    # 0分前 タイムテーブル更新
    elif now == ROBIN_GUILD.timeTable[0]:
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Hunting:%H時")))
    ######################################################
    # 1時間後 周回終わり
    elif now == ROBIN_GUILD.timeTable[0] + delta(minutes=60):
        global rebootScadule

        try:
            memberSum = 0
            for party in ROBIN_GUILD.parties:
                memberSum += party.membersNum()
            await ROBIN_GUILD.PARTY_LOG.send(ROBIN_GUILD.timeTable[0].strftime(f'%y/%m/%d %H 最終参加数 {memberSum}'))
        except Exception as e:
            printTraceback(e)
        
        del ROBIN_GUILD.timeTable[0] # 先頭を削除
        if len(ROBIN_GUILD.timeTable) < 3:
            ROBIN_GUILD.timeTable = await getTimetable()
            for t in ROBIN_GUILD.timeTable:
                print(t)
        msg = ROBIN_GUILD.timeTable[0].strftime('## 次回の全兵団は %H時 です\n%H時 > ')
        msg += ROBIN_GUILD.timeTable[1].strftime('%H時 > ')
        msg += ROBIN_GUILD.timeTable[2].strftime('%H時 > [...](<https://hiroba.dqx.jp/sc/tokoyami/>)')
        await ROBIN_GUILD.PARTY_CH.send(msg)

        if rebootScadule:
            try: await rebootScadule.send('再起動します')
            except Exception as e:
                printTraceback(e)
            await f_reboot()
        
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
        ROBIN_GUILD.parties = None
        ROBIN_GUILD.reclutingMessage = None
        
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

def markdownEsc(line:str):
    replaceChars = {'_', '*', '>', '-', '~', '[', ']', '(', ')', '@', '#', '`'}
    line = line.replace('\\', '\\\\')
    for char in replaceChars:
        line = line.replace(char, '\\'+char)
    return line

def joinLeaveMembers(guild:discord.Guild, month:delta, exclusionRole:discord.Role|None=None):
    leaveMembers:set[discord.Member] = set(guild.members)
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

def recluitMessageReplace(msg:str, time:dt, count:int=0) -> str:
    replaceChars = {
        '{hour}': time.strftime('%H'),
        '{count}': str(count)
    }
    return replaces(msg, replaceChars)

# 参加権チェック
async def checkParticipationRight(sender:discord.Member|discord.Interaction, channel:discord.TextChannel=None) -> bool:
    '''参加権チェック'''
    global ROBIN_GUILD
    if isinstance(sender, discord.Interaction):
        member = sender.user
    else:
        member = sender
    if ROBIN_GUILD.MEMBER_ROLE not in member.roles:
        msg = f'{member.mention} 参加権がありません'
        if isinstance(sender, discord.Interaction):
            await sender.response.send_message(msg, ephemeral=True, delete_after=10)
        elif isinstance(sender, discord.Member) and channel is not None:
            await channel.send(msg, delete_after=10)
        return False
    return True

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
def speedFormation(participants:list[Participant], formation:list[dict[discord.Role, int]]) -> list[SpeedParty]:
    '''
    <h1>Parameter</h1>
    players: list[Participant]
    <h1>Return</h1>
    List[List[Participant]]
    '''
    parties:list[SpeedParty] = []
    parties.append(SpeedParty(len(parties)+1, formation))
    loopFlg = True
    while loopFlg:
        partyNoneCount = parties[-1].noneCount()
        if partyNoneCount > len(participants) or partyNoneCount == 0 and len(participants) < 8: break
        if partyNoneCount == 0: # 空きのあるパーティがない 新しい空のパーティを作る
            parties.append(SpeedParty(len(parties)+1, {role:count for role, count in formation.items()}))
        for participantNum in range(len(participants)):
            if addHispeedParty(parties, participants[participantNum]):
                del participants[participantNum]
                break
            # 計算量短縮を図ったけどムリかも
            # if len(participants) - participantNum < partyNoneCount:
            #     loopFlg = False
            #     break
        else: loopFlg = False
    
    # 未完成パーティ or 余りが一人の場合 パーティの解体
    if any(map(lambda x:None in x, parties[-1].members.values())) or len(participants) == 1:
        for role, partyMembers in parties[-1].members.items():
            for partyMember in partyMembers:
                if isinstance(partyMember, Participant):
                    participants.insert(0, partyMember)
        del parties[-1]
    
    return parties

def addHispeedParty(parties:list[SpeedParty], participant:Participant, roles:set[discord.Role]=set()) -> bool:
    for role in [role for role in participant.roles if role not in roles]:
        if None in parties[-1].members[role]:
            # 空きがあったから入れて True返す
            if parties[-1].addMember(participant, role): return True
            else: return False

    for partyNum in range(len(parties)-1, -1, -1): # 後のパーティから走査
        for role in [r for r in participant.roles if r not in roles]: # ロール走査 ただし親ノードで走査済は無視
            for partyMemberNum in range(len(parties[partyNum].members[role])): # メンバ走査 ロールをもとに
                partyMember = parties[partyNum].members[role][partyMemberNum] # 対象のメンバ復元のために保持
                parties[partyNum].members[role][partyMemberNum] = None # 対象枠を空ける
                if addHispeedParty(parties, partyMember, roles|participant.roles): # 子ノードへ引継ぎ
                    # 成功したため追加
                    parties[partyNum].addMember(participant, role)
                    return True
                else: # 最終的に枠を空けられなかった
                    parties[partyNum].members[role][partyMemberNum] = partyMember # 保持していたメンバ返却
    else: # どのパーティでも交代できない
        return False
    
def lightFormation(participants:list[Participant], partyIndex:int) -> list[LightParty]:
    if len(participants) == 0: return []
    partiesNum = roundUp(len(participants) / 4) # Number of パーティ
    partyNum = len(participants) // partiesNum # パーティ当たりの人数
    parties_num = [partyNum] * partiesNum # パーティ当たりの人数をパーティ数分List[int]
    for i in range(len(participants) % partiesNum): # あまり人数分足す
        parties_num[i] += 1

    # パーティ割り振り人数確定
    # メンバー振り分け
    parties:list[LightParty] = []
    p = 0
    for n in parties_num:
        partyIndex += 1
        parties.append(LightParty(partyIndex, []))
        for _ in range(n):
            parties[-1].addMember(participants[p])
            p += 1

    return parties

def roundUp(value:float):
    roundValue = round(value)
    if value - roundValue > 0: roundValue += 1
    return roundValue

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

#endregion

#region Emoji 関数
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

#endregion

##############################################################################################
#region スラッシュコマンド
@client.slash_command(name='f-formation', description='タイムテーブルの割り込み')
async def f_reclute(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return
    now = dt.now()
    print(f'{now} slash command formation from {ctx.interaction.user}')
    ROBIN_GUILD.timeTable = [dt(now.year, now.month, now.day, now.hour, now.minute, 0) + delta(minutes=31)] + ROBIN_GUILD.timeTable
    await ROBIN_GUILD.PARTY_CH.send('# 【動作テスト】\n開発陣の都合によりパーティ募集の動作テストを行います\nテストの参加は任意です')
    await ctx.respond('割り込みタイムテーブルを生成しました')

@client.slash_command(name='f-timetable', description='タイムテーブル再取得')
async def f_timetable(ctx:discord.ApplicationContext):
    print(f'{dt.now()} slash command timetable from {ctx.interaction.user}')
    ROBIN_GUILD.timeTable = await getTimetable()
    await client.change_presence(activity=discord.CustomActivity( \
        name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
    send_message = 'タイムテーブルを更新しました'
    for t in ROBIN_GUILD.timeTable:
        send_message += t.strftime('\n%Y-%m-%d %H')
    await ctx.respond(send_message)

@client.slash_command(name='f-restart', description='編成員Fを再起動')
async def f_restart(ctx:discord.ApplicationContext):
    print(f'{dt.now()} slash command restart from {ctx.interaction.user}')
    if len(ROBIN_GUILD.timeTable) == 0:
        await f_reboot(ctx)
    if ROBIN_GUILD.timeTable[0] - delta(minutes=40) < dt.now():
        await ctx.respond('パーティ機能作動中または，まもなくパーティ編成を開始します\n再起動スケジュールを選択してください', view=RebootView())
    else:
        await f_reboot(ctx)

@client.slash_command(name='f-stop', description='再起動しても改善しない場合\n編成員Fを停止します\n開発陣へ連絡')
async def f_stop(ctx:discord.ApplicationContext):
    print(f'{dt.now()} slash command restart from {ctx.interaction.user}')
    await ctx.respond('動作を停止します')
    await client.close()
    exit()

@client.slash_command(name='f-rand', description='編成員Fが整数ランダムを生成')
async def f_rand(ctx:discord.ApplicationContext, min:int, max:int):
    min = int(min)
    max = int(max)
    await ctx.respond(f'{min}-{max} > {randint(min,max)}')

@client.slash_command(name='f-get-participant-data', description='これまでの参加データをcsv形式で返します')
async def f_get_participant_data(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return
    with open(f'reactionLog/{ctx.interaction.guild.name}.csv', 'r') as f:
        csvFile = discord.File(fp=f, filename=dt.now().strftime('participant_data_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`年-月-日-時,ユーザーID,希望`', file=csvFile)

@client.slash_command(name='f-get-participant-name', description='サーバーメンバのIDと現在の表示名の対応をcsv形式で返します')
async def f_get_participant_name(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return 
    filename = f'reactionLog/{ctx.interaction.guild.name}_nameList.csv'
    with open(filename, 'w') as f:
        async for member in ctx.interaction.guild.fetch_members():
            f.write(f'{member.id},{member.name},{member.display_name},{member.joined_at}\n')
    csvFile = discord.File(filename, filename=dt.now().strftime('participant_name_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ユーザーID,ユーザー名,表示名,加入時期`', file=csvFile)

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

@client.slash_command(name='f-fetch', description='ギルド情報再取得')
async def f_fetch_commanc(ctx:discord.ApplicationContext):
    print(f'{dt.now()} slash command fetch from {ctx.interaction.user}')
    await f_fetch()
    await ctx.respond('ギルド情報を再取得しました')

async def f_fetch():
    global ROBIN_GUILD
    # チャンネル・ギルドをゲット
    with open('IDs.json') as f:
        IDs = json.load(f)

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
