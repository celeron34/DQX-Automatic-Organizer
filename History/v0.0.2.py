import discord
# from discord import *
from discord.ext import tasks, commands
from dqx_ise import getTable
from datetime import datetime as dt, timedelta as delta
from asyncio import sleep
# from asyncio import get_running_loop, create_task
# from concurrent.futures import ThreadPoolExecutor
from random import shuffle, randint
from typing import Any
from time import perf_counter
from random import shuffle
from sys import argv, exc_info, executable, exit
from subprocess import Popen
from traceback import extract_tb, format_list
from re import sub, match
from os import path

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

rebootScadule:bool = False

class RoleInfo:
    def __init__(self, emoji:discord.Emoji, count:int):
        self.emoji:discord.Emoji = emoji
        self.count:int = count

class Participant: # メンバと可能ロール
    def __init__(self, user:discord.User|discord.Member, roles:set[discord.Role]):
        self.user:discord.Member|Guest = user
        self.roles:set[discord.Role] = roles
        self.mention:str = user.mention
        self.hiSpeed:bool = False
        self.id = user.id
        self.display_name = user.display_name

class Guest: # Party class のためのダミー
    def __init__(self):
        self.user = None
        self.roles = set()
        self.mention = 'ゲスト'
        self.id = -1
        self.display_name = 'ゲスト'

class Party: # パーティ情報 メッセージとパーティメンバ
    def __init__(self, number:int, players:list[discord.User|discord.Member]|set[Participant]):
        self.number:int = number
        self.message:discord.Message = None
        self.threadTopMessage:discord.Message = None
        self.members:list[discord.User|discord.Member|Guest]|set[Participant] = players
        self.joins:dict[discord.Message, discord.User|discord.Member] = dict()
        self.thread:discord.Thread = None
    def __str__(self):
        msg = f'\| 【パーティ:{self.number}】'
        if len(self.members) >= 1:
            for player in self.members:
                if type(player) in {discord.User, discord.Member, Guest}:
                    msg += f'\n\| {player.mention}'
                elif type(player) == Participant:
                    msg += f'\n\| {player.mention}'
        return msg
    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        msg = f'\| 【パーティ:{self.number}】'
        for player in self.members:
            try:
                msg += f'\n\| {player.mention}'
            except:
                msg += f'\n\| プログラムのバグの可能性あり'
                print(f'getPartyMessageでバグ {player}')
            for role in player.roles:
                msg += str(guildRolesEmoji[role].emoji)
        return msg

    def addMember(self, member:discord.Member|Participant|Guest, guild_roles:list[discord.Role]|set[discord.Role]=None):
        if type(self.members) == list:
            if type(member) == Participant or type(member) == Guest:
                self.members.append(member)
            elif type(member) == discord.Member:
                self.members.append(Participant(member, guild_roles))
        elif type(self.members) == set:
            if type(member) == Participant or type(member) == Guest:
                self.members.add(member)
            elif type(member) == discord.Member:
                self.members.add(Participant(member, guild_roles))

    def removeMember(self, member:discord.Member|Guest|Participant) -> int:
        '''残り人数を return'''
        print(f'removeMember member:{type(member)} {member.display_name}  self.members:{type(self.members)} {self.members}')
        if type(self.members) == list:
            for index in range(len(self.members)):
                if self.members[index].id == member.id:
                    del self.members[index]
                    return len(self.members)
        elif type(self.members) == set:
            for participant in self.members:
                if participant.id == member.id:
                    self.members.remove(participant)
                    return len(self.members)
    
class HispeedParty:
    def __init__(self, number, rolesNum:dict[discord.Role, int]):
        self.number:int = number
        self.message:discord.Message = None
        self.threadTopMessage:discord.Message = None
        self.members:dict[discord.Role,list[Participant|None]] = {role:[None] * num for role, num in rolesNum.items()}
        self.joins:dict[discord.Message, discord.User|discord.Member] = dict()
        self.thread:discord.Thread = None

    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        msg = f'\| <:FullParty:1345733070065500281> 高速パーティ:{self.number} <:FullParty:1345733070065500281>'
        for partyRole, members in self.members.items():
            for member in members:
                msg += f'\n{guildRolesEmoji[partyRole].emoji} \| {member.mention} '
                for memberRole in member.roles:
                    msg += str(guildRolesEmoji[memberRole].emoji)
        return msg

    def noneCount(self) -> int:
        num = 0
        for members in self.members.values():
            num += sum([None == member for member in members])
        return num

    def addMember(self, member:Participant, role:discord.Role) -> bool:
        if None in self.members[role]:
            for membersIndex in range(len(self.members.values())):
                if self.members[role][membersIndex] == None:
                    self.members[role][membersIndex] = member
                    return True
        return False
    
    def removeMember(self, role:discord.Role, member:Participant) -> bool:
        if member in self.members[role]:
            for memberIndex in range(len(self.members)):
                if member == self.members[role][memberIndex]:
                    self.members[role][memberIndex] = None
                    return True
        return False

class Guild:
    def __init__(self, guild):
        self.GUILD:discord.Guild = client.get_guild(guild) # ギルド
        self.LIGHT_FORMATION:dict[discord.Emoji, int] = {} # ライトパーティ編成枠
        self.FULL_FORMATION:dict[discord.Emoji, int] = {} # フルパーティ編成枠
        self.TRANCE_FORMATION:dict[discord.Emoji, discord.Emoji] = {} # 職変換

        self.DEV_CH:discord.TextChannel = None # デベロッパーチャンネル
        self.PARTY_CH:discord.TextChannel = None # 募集チャンネル
        self.PARTY_CH_beta:discord.TextChannel = None # ベータ版募集チャンネル
        self.COMMAND_CH:discord.TextChannel = None # コマンドチャンネル
        self.COMMAND_MSG:discord.Message = None # コマンドメッセージ
        self.PARTY_LOG:discord.TextChannel = None # パーティログチャンネル

        self.reclutingMessage:discord.Message = None # 募集メッセージ
        self.parties:set[Party] = set() # パーティ一覧
        self.timeTable:list[dt] = [] # 防衛軍タイムテーブル
        # self.timeTableThread:ThreadPoolExecutor = None # タイムテーブルスレッド

        # リアクション
        self.RECLUTING_EMOJI:discord.Emoji = None # 参加リアクション
        self.FULLPARTY_EMOJI:discord.Emoji = None
        # self.LIGHTPARTY_EMOJI:discord.Emoji = None
        
        self.ROLES:dict[discord.Role, RoleInfo] = None
        # self.ROLES:dict[discord.Role, ]

        # self.formation:Formation = None # パーティ編成クラス

ROBIN_GUILD:Guild = None

##############################################################################################
##############################################################################################
## イニシャライズ
@client.event
async def on_ready():
    global ROBIN_GUILD
    print(f'{dt.now()} on_ready START')

    # チャンネル・ギルドをゲット
    ROBIN_GUILD = Guild(1246651972342386791)

    # beta 1346195417808896041
    ROBIN_GUILD.PARTY_CH      = client.get_channel(1246662816673304587)
    ROBIN_GUILD.PARTY_CH_beta = client.get_channel(1346195417808896041)
    ROBIN_GUILD.PARTY_LOG     = client.get_channel(1353638340456484916)
    ROBIN_GUILD.DEV_CH        = client.get_channel(1246662742987772067)
    ROBIN_GUILD.COMMAND_CH    = client.get_channel(1249294452149715016)

    # 絵文字ゲット
    ROBIN_GUILD.RECLUTING_EMOJI =  client.get_emoji(1345708506111545375)
    # ROBIN_GUILD.FULLPARTY_EMOJI =  client.get_emoji(1345733070065500281)
    # ROBIN_GUILD.LIGHTPARTY_EMOJI = client.get_emoji(1345688469183266886)

    ROBIN_GUILD.ROLES = {
            ROBIN_GUILD.GUILD.get_role(1252170810144325634) : RoleInfo(client.get_emoji(1345710507398529085), 1), # 先導
            ROBIN_GUILD.GUILD.get_role(1252171064700829757) : RoleInfo(client.get_emoji(1345708117618458695), 1), # 札
            ROBIN_GUILD.GUILD.get_role(1252171128068112444) : RoleInfo(client.get_emoji(1345708094251859999), 1), # 中継
            ROBIN_GUILD.GUILD.get_role(1252170979929755718) : RoleInfo(client.get_emoji(1345708049838641234), 1), # 霧
            ROBIN_GUILD.GUILD.get_role(1252170590010478602) : RoleInfo(client.get_emoji(1345708222962470952), 1), # 魔戦
            ROBIN_GUILD.GUILD.get_role(1252172997058498580) : RoleInfo(client.get_emoji(1345708066741424138), 3), # 回復
        }
    
    await ROBIN_GUILD.COMMAND_CH.purge()

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

    # ローリングチャンネルイニシャライズ
    ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH)

    try:
        await ROBIN_GUILD.GUILD.chunk()
    except Exception:
        print('Guild.chunk missed')

    await client.change_presence(activity=discord.CustomActivity(name=timeTable[0].strftime("Next:%H時"))) # なぜかここにないと動かない
    print(f'{dt.now()} on_ready END')

##############################################################################################
##############################################################################################
## リアクション追加検知
@client.event
async def on_reaction_add(reaction:discord.Reaction, user:discord.Member|discord.User):
    global ROBIN_GUILD
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if not reaction.is_custom_emoji(): return # カスタム絵文字以外を無視

    # message = await ROBIN_GUILD.PARTY_CH.fetch_message(reaction.message.id)

    print(f'{dt.now()} recive reaction add {user} {reaction.emoji.name}')

    # 募集メッセージに対して
    # if reaction.message == ROBIN_GUILD.reclutingMessage:
    #     if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
    #         ROBIN_GUILD.formation.addMember(user)
    #         return
    #     elif reaction.emoji == ROBIN_GUILD.FULLPARTY_EMOJI:
    #         return
    #     else:
    #         # 想定しないリアクションを削除
    #         await reaction.message.remove_reaction(reaction.emoji, user)
    #     return

    
    # 途中参加申請
    if reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
        print('Join request')
        try:
            # party = searchParty(message, ROBIN_GUILD.parties, lambda x:[x.message])
            party = searchParty(reaction.message, ROBIN_GUILD.parties)
            if user.id not in map(lambda x:x.id, party.members): # 別のパーティ
                if len(party.members) > 0: # 誰か１人でもいる場合 承認要請
                    thread = reaction.message.thread
                    if thread == None:
                        message = await ROBIN_GUILD.PARTY_CH.fetch_message(reaction.message.id)
                        thread = message.thread
                    party.joins[await thread.send(f'@here {user.display_name} から加入申請', view=ApproveView(timeout=600))] = user
                else:
                    await reaction.message.remove_reaction(reaction.emoji, user)
                    await joinParticipant(Participant(user, set(role for role in user.roles if role in ROBIN_GUILD.ROLES.keys())), party)
            else:
                await reaction.message.remove_reaction(reaction.emoji, user)
                errorMessage = await reaction.message.channel.send(f'{user.mention}加入中のパーティには参加申請できません')
                await errorMessage.delete(delay=5)
        except Exception as e:
            printTraceback(e)

##############################################################################################
## 
def searchParty(message:discord.Message, parties:set[Party]) -> Party|None:
    for party in parties:
        print(f'target message:{message.id} party.message{party.message.id} party.threadTopMessage{party.threadTopMessage.id}')
        # print(f'searchParty {message.id} {party.message.id}')
        if message.id == party.message.id or message.id == party.threadTopMessage.id:
            return party
    return None

##############################################################################################
##############################################################################################
## リアクション削除検知
@client.event
async def on_reaction_remove(reaction:discord.Reaction, user:discord.Member|discord.User):
    global ROBIN_GUILD
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if not reaction.is_custom_emoji(): return # カスタム絵文字以外を無視

    print(f'{dt.now()} recive reaction remove {user} {reaction.emoji.name}')

    # if reaction.message == ROBIN_GUILD.reclutingMessage: # 募集メッセージ判定
    #     if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
    #         ROBIN_GUILD.formation.rmMember(user)
    #         return
    
    # 参加申請取り消し
    if ROBIN_GUILD.parties != None:
        if reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction == ROBIN_GUILD.RECLUTING_EMOJI:
            party = searchParty(reaction.message, ROBIN_GUILD.parties, lambda x:x.message)
            for delMessage, member in party.joins.items():
                if user == member:
                    del party.joins[delMessage]
                    await delMessage.delete()
                    break

##############################################################################################
## 
async def reply_message(message:discord.Message, send:str, accept:bool):
    msg = await message.reply(send)
    await msg.delete(delay=10)
    if accept: print(f'{message.guild.name} {message.author.display_name} command success: {message.content}')
    else: print(f'{message.guild.name} {message.author.display_name} command error: {message.content}')

##############################################################################################
##############################################################################################
## メッセージ削除
@client.event
async def on_message_delete(message):
    if message == ROBIN_GUILD.COMMAND_MSG:
        ROBIN_GUILD.COMMAND_MSG = await command_message(ROBIN_GUILD.COMMAND_CH)

##############################################################################################
##############################################################################################
## 定期実行 パーティ編成
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
        ROBIN_GUILD.reclutingMessage = await ROBIN_GUILD.PARTY_CH.send(ROBIN_GUILD.timeTable[0].strftime('# 【異星周回 %H時】\n参加希望は<:sanka:1345708506111545375>リアクション願います')) # 募集文
        await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI) # 参加リアクション追加
        # await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.LIGHTPARTY_EMOJI) # ライトパーティリアクション追加
        # await ROBIN_GUILD.reclutingMessage.add_reaction(ROBIN_GUILD.FULLPARTY_EMOJI) # フルパーティリアクション追加
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Formation:%H時")))
    
    ######################################################
    # パーティ編成をアナウンス
    elif now == ROBIN_GUILD.timeTable[0] - delta(minutes=10):
        async with ROBIN_GUILD.PARTY_CH.typing():

            print(f'#================= {dt.now()} Formation =================#')

            ROBIN_GUILD.parties = set()
            # 値取得
            await ROBIN_GUILD.GUILD.chunk()
            ROBIN_GUILD.reclutingMessage = await ROBIN_GUILD.PARTY_CH.fetch_message(ROBIN_GUILD.reclutingMessage.id)
            participants:list[Participant] = list()
            for reaction in ROBIN_GUILD.reclutingMessage.reactions:
                if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
                    async for user in reaction.users():
                        if user == client.user: continue
                        roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
                        participant = Participant(user, roles)
                        participant.hiSpeed = False
                        participants.append(participant)
            participantNum = len(participants)

            await ROBIN_GUILD.reclutingMessage.delete() # メッセージデリート

            print('participants')
            print([participant.display_name for participant in participants])
            
            await ROBIN_GUILD.PARTY_LOG.send(f'{ROBIN_GUILD.timeTable[0].strftime("%y-%m-%d-%H")} <:sanka:1345708506111545375> {participantNum}')

            shuffle(participants)
            parties:list[list[Participant]] = formation(participants)

            # パーティ通知メッセージ
            await ROBIN_GUILD.PARTY_CH.send(ROBIN_GUILD.timeTable[0].strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ' + '' if participantNum != 8 else '参加者が8人ですので\n## 殲滅固定（カンダタを倒す）同盟です\n参加者は ___**サーバー3**___ へ'), \
                                            view=FormationTopView(timeout=3600))
            for partyNum, partyList in enumerate(parties, start=1):
                party = Party(partyNum, partyList)
                party.message = await ROBIN_GUILD.PARTY_CH.send(party.getPartyMessage(ROBIN_GUILD.ROLES))
                ROBIN_GUILD.parties.add(party)
        print(f'{dt.now()} Formation END')

        print(f'{dt.now()} Create Threads')
        try:
            for party in ROBIN_GUILD.parties:
                party.thread = await party.message.create_thread(name=f'Party:{party.number}', auto_archive_duration=60)
                party.threadTopMessage = await party.thread.send(view=PartyView(timeout=3600))
                await party.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
        except Exception as e:
            printTraceback(e)
        
        print(f'{dt.now()} Create Threads END')
        print(f'{dt.now()} Add Log')
        with open(f'../reactionLog/{ROBIN_GUILD.GUILD.name}.csv', 'a', encoding='utf8') as f:
            for participant in participants:
                f.write(f"{ROBIN_GUILD.timeTable[0].strftime('%y-%m-%d-%H')},{participant.id}\n")
        print('#==================================================================#')

        ##################################################
        # 実験前半
        print(f'{dt.now()} 編成実験')
        try:
            hispeedParties = hispeedFormationBeta(participants)
            lightParties = lowspeedFormationBeta(len(hispeedParties), participants)

            # 結果出力
            for party in hispeedParties:
                print(party.members)
                await ROBIN_GUILD.PARTY_CH_beta.send(party.getPartyMessage(ROBIN_GUILD.ROLES))
            for party in lightParties:
                print(party.members)
                await ROBIN_GUILD.PARTY_CH_beta.send(party.getPartyMessage(ROBIN_GUILD.ROLES))

        except Exception as e:
            await ROBIN_GUILD.PARTY_CH_beta.send('エラーが起きました')
            printTraceback(e)

        print(f'#============ {dt.now()} パーティ編成実験 END ===========#')
        # 実験おわり
        ##################################################
        ROBIN_GUILD.reclutingMessage = None

    
    ######################################################
    # 0分前 タイムテーブル更新
    elif now == ROBIN_GUILD.timeTable[0]:
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Hunting:%H時")))
    ######################################################
    # 1時間後 周回終わり
    elif now == ROBIN_GUILD.timeTable[0] + delta(minutes=60):
        global rebootScadule
        if rebootScadule:
            await f_reboot()
        del ROBIN_GUILD.timeTable[0] # 先頭を削除
        if len(ROBIN_GUILD.timeTable) == 0:
            ROBIN_GUILD.timeTable = await getTimetable()
            for t in ROBIN_GUILD.timeTable:
                print(t)
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
        ROBIN_GUILD.parties = set()

    ######################################################
    #
    # elif now + delta(minutes=60) > ROBIN_GUILD.timeTable[0]:
    #     while True:
    #         if len(ROBIN_GUILD.timeTable) == 0: break
    #         del ROBIN_GUILD.timeTable[0]
    #         if now + delta(minutes=60) <= ROBIN_GUILD.timeTable[0]: break

##############################################################################################
##############################################################################################
async def command_message(textch:discord.TextChannel) -> discord.Message:
    msg = await textch.send(content=f'## 追加・削除したいロールをタップ', view=RoleManageView())
    # for r in roles.values():
    #     await msg.add_reaction(r.emoji)
    return msg

async def getTimetable(updateStatus:bool=True) -> list[dt]:
    # タイムテーブルを取りに行く
    await client.change_presence(activity=discord.CustomActivity(name='タイムスケジュール取得中'), status=discord.Status.dnd)
    print(f'{dt.now()} getting Timetable')
    timeTable = []
    now30 = dt.now() + delta(minutes=30)
    for t in getTable(argv[1], argv[2]):
        # 通過したものは追加しない
        if t > now30:
            timeTable.append(t)
    if updateStatus:
        await client.change_presence(activity=discord.CustomActivity(name=timeTable[0].strftime("Next:%H時")), status=discord.Status.online)
    print(f'{dt.now()} Timetable was got')
    return timeTable

def markdownEsc(line:str):
    replaceChars = {'_', '*', '>', '-', '~', '[', ']', '(', ')', '@', '#', '`'}
    line = line.replace('\\', '\\\\')
    for char in replaceChars:
        line = line.replace(char, '\\'+char)
    return line

##############################################################################################
## パーティ編成アルゴリズム
def formation(participants:list[Participant]) -> list[list[Any]]:
    parties_num:list[int] = [4 for _ in range(len(participants) // 4)]
    if len(participants) % 4 > 0:
        parties_num.append(len(participants) % 4)

    # if len(parties_num) > 1:
    #     # 2パーティ以上完成する
    #     if parties_num[-1] + parties_num[-2] == 5 or parties_num[-1] + parties_num[-2] == 6:
    #         # _:4:1(=5) -> _:3:2 / _4:2(=6) -> _:3:3
    #         parties_num[-1] += 1
    #         parties_num[-2] -= 1
    #     if parties_num[-1] == 2:
    #         if parties_num[-2] == 4:
    #             # _:4:2 -> _:3:3
    #             parties_num[-1] += 1
    #             parties_num[-2] -= 1
    #         elif len(parties_num) > 2:
    #             # _:4:3:2 -> _:3:3:3
    #             parties_num[-1] += 1
    #             parties_num[-3] -= 1

    # パーティメンバ数例外処理
    if len(parties_num) >= 3: # 3パーティ以上
        if sum(i for i in parties_num[-3:]) == 9:
            parties_num[-1] = 3
            parties_num[-2] = 3
            parties_num[-3] = 3
    elif len(parties_num) >= 2: # 2パーティ
        parties2tailSum = sum(i for i in parties_num[-2:])
        # if len(parties_num) == 2 and parties2tailSum == 8:
        #     parties_num[-2] = 3
        #     parties_num[-1] = 3
        #     parties_num.append(2)
        if parties2tailSum == 5:
            parties_num[-1] = 2
            parties_num[-2] = 3
        elif parties2tailSum == 6:
            parties_num[-1] = 3
            parties_num[-2] = 3


    # パーティ割り振り人数確定
    # メンバー振り分け
    parties:list[list[set[Any]]] = []
    p = 0
    for n in parties_num:
        parties.append([])
        for _ in range(n):
            parties[-1].append(participants[p])
            p += 1
    
    return parties

def hispeedFormationBeta(participants:list[Participant]) -> list[HispeedParty]:
    '''
    <h1>Parameter</h1>
    players: list[Participant]
    <h1>Return</h1>
    List[List[Participant]]
    '''
    parties:list[HispeedParty] = []
    parties.append(HispeedParty(len(parties)+1, {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}))
    loopFlg = True
    while loopFlg:
        partyNoneCount = parties[-1].noneCount()
        if partyNoneCount > len(participants) or partyNoneCount == 0 and len(participants) < 8: break
        if partyNoneCount == 0: # 空きのあるパーティがない 新しい空のパーティを作る
            parties.append(HispeedParty(len(parties)+1, {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}))
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
                if type(partyMember) == Participant:
                    participants.insert(0, partyMember)
                    # participants = [partyMember] + participants
        del parties[-1]
    
    return parties

def addHispeedParty(parties:list[HispeedParty], participant:Participant, roles:set[discord.Role]=set()) -> bool:
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
                    parties[partyNum].addMember(participant,role)
                    return True
                else: # 最終的に枠を空けられなかった
                    parties[partyNum].members[role][partyMemberNum] = partyMember # 保持していたメンバ返却
    else: # どのパーティでも交代できない
        return False
    
def lowspeedFormationBeta(partyNum:int, participants:list[Participant]) -> list[Party]:
    parties_num:list[int] = [4 for _ in range(len(participants) // 4)]
    if len(participants) % 4 > 0:
        parties_num.append(len(participants) % 4)

    # パーティメンバ数例外処理
    if len(parties_num) >= 3: # 3パーティ以上
        if sum(i for i in parties_num[-3:]) == 9:
            parties_num[-1] = 3
            parties_num[-2] = 3
            parties_num[-3] = 3
    elif len(parties_num) == 2: # 2パーティ
        parties2tailSum = sum(i for i in parties_num[-2:])
        # if len(parties_num) == 2 and parties2tailSum == 8:
        #     parties_num[-2] = 3
        #     parties_num[-1] = 3
        #     parties_num.append(2)
        if parties2tailSum == 5:
            parties_num[-1] = 2
            parties_num[-2] = 3
        elif parties2tailSum == 6:
            parties_num[-1] = 3
            parties_num[-2] = 3

    # パーティ割り振り人数確定
    # メンバー振り分け
    parties:list[Party] = []
    p = 0
    for n in parties_num:
        partyNum += 1
        parties.append(Party(partyNum, set()))
        for _ in range(n):
            parties[-1].addMember(participants[p])
            p += 1
    return parties

##############################################################################################
## エラーキャッチ
# @client.event
# async def on_error(event, args, kwargs):
#     marimo = client.get_user(224407617856864256)
#     ROBIN_GUILD.PARTY_CH.send(f'エラー出てます たぶん動きません {marimo.mention}')
#     print(f'{event} でエラーでたンゴ')
#     print(f'{args}')
#     print(f'{kwargs}')
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

##############################################################################################
## ビュー
class RoleManageView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    async def roleManage(self, label:str, emoji:str, user:discord.User|discord.Member):
        role = emoji2role(emoji)
        if role in user.roles:
            # ロールがあるから削除
            await user.remove_roles(role)
            rep = await ROBIN_GUILD.COMMAND_CH.send(f'{user.mention} [{label}] を削除')
        else:
            # ロールがないから追加
            await user.add_roles(role)
            rep = await ROBIN_GUILD.COMMAND_CH.send(f'{user.mention} [{label}] を追加')
        await rep.delete(delay=5)

    @discord.ui.button(label='魔戦', emoji='<:magic_knight:1345708222962470952>', row=1)
    async def magicKnight(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)
    @discord.ui.button(label='先導', emoji='<:boomerang:1345710507398529085>', row=1)
    async def boomerang(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)
    @discord.ui.button(label='霧', emoji='<:buttarfly:1345708049838641234>', row=1)
    async def butterfly(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)
    @discord.ui.button(label='札', emoji='<:relay:1345708117618458695>', row=2)
    async def card(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)
    @discord.ui.button(label='中継', emoji='<:way:1345708094251859999>', row=2)
    async def way(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)
    @discord.ui.button(label='回復', emoji='<:heal:1345708066741424138>', row=2)
    async def heal(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            await self.roleManage(button.label, button.emoji, interaction.user)
            await interaction.response.edit_message(view=self)
        except Exception as e:
            printTraceback(e)

class ApproveView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()
    @discord.ui.button(label='承認')
    async def approve(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            message = interaction.message
            user = interaction.user
            print(f'{dt.now()} Approve from {user} {type(user)}')
            party = searchParty(message.channel, ROBIN_GUILD.parties)
            if user.id in {participant.id for participant in party.members}: # パーティメンバである
                print('パーティメンバによる承認')
                await interaction.response.edit_message(view=self)
                thread = message.channel
                joinMember = party.joins[message]
                print(f'JoinMember: {joinMember}')
                for p in {p for p in ROBIN_GUILD.parties if joinMember in p.joins.values()}: # 参加リアクション全削除
                    await p.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember)
                await thread.add_user(joinMember) # パーティへ追加
                party.addMember(Participant(joinMember, set(role for role in joinMember.roles if role in ROBIN_GUILD.ROLES.keys())))
                ################################################################
                ## joins のメッセージをすべて Disable にしたい
                ################################################################
                del party.joins[message] # 申請削除
                await thread.starting_message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES)) # スレッドトップ更新
                await thread.starting_message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember) # リアクション処理
                await thread.send(f'{joinMember.display_name} が加入\n{party.getPartyMessage(ROBIN_GUILD.ROLES)}')
                buttonAllDisable(self.children)
                if type(self.timeout) == float: self.timeout += self.startTime - perf_counter()
            else:
                print('パーティメンバ以外による承認')
                await interaction.response.defer()
                msg = await interaction.channel.send(f'{interaction.user.mention}\nパーティメンバ以外は操作できません')
                msg.delete(delay=5)
                # if type(self.timeout) == float: self.timeout+= self.startTime - perf_counter()
                # await interaction.response.edit_message(content='パーティメンバ以外は承認できません', view=self)
                return
        except Exception as e:
            printTraceback(e)
            await interaction.response.defer()

class PartyView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()

    @discord.ui.button(label='パーティを抜ける')
    async def leaveParty(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Leave party button is pressed from {interaction.user.display_name}')
        party = searchParty(interaction.message, ROBIN_GUILD.parties)
        await interaction.response.defer()
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
            return
        if interaction.user in map(lambda x:x.user, party.members):
            # ユーザーがパーティメンバー
            thread:discord.Thread = interaction.message.channel
            print(f'thread: {type(thread)} {thread.id}')
            await thread.remove_user(interaction.user)
            # party.members.remove(interaction.user)
            partyMemberNum = party.removeMember(interaction.user)

            await leaveParty(interaction.user, party)
            # if partyMemberNum == 0:
            #     print('パーティが0人なのでパーティ情報とそのスレッドを削除')
            #     try:
            #         ROBIN_GUILD.parties.remove(party)
            #     except Exception as e:
            #         printTraceback(e)
            #     finally:
            #         try:
            #             await party.message.delete()
            #         except Exception as e:
            #             printTraceback(e)
            #         finally:
            #             return
            # else:
            #     await thread.send(f'{interaction.user.display_name} が離脱\n{party.getPartyMessage(ROBIN_GUILD.ROLES)}')
            #     await thread.starting_message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES))
        else: # ユーザーが別パーティメンバ
            print('別パーティによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)

    @discord.ui.button(label='ゲスト追加')
    async def addGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest add button is pressed from {interaction.user.display_name}')
        await interaction.response.defer()
        party = searchParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
            return
        if interaction.user in map(lambda x:x.user, party.members):
        # if interaction.user in party.members: # パーティメンバである
            print(f'パーティメンバによるアクション')
            # joinMember = Guest()
            # party.addMember(joinMember)
            await joinParticipant(Guest(), party)
    
    @discord.ui.button(label='ゲスト削除')
    async def removeGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest remove button from {interaction.user.display_name}')
        await interaction.response.defer()
        party = searchParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
            return
        if interaction.user in map(lambda x:x.user, party.members): # パーティメンバである
            print('パーティメンバによるアクション')
            thread:discord.Thread = interaction.message.channel
            for member in party.members:
                if type(member) == Guest:
                    # party.removeMember(member)
                    await leaveParty(member, party)
                    break
            else:
                await thread.send(f'ゲストがいませんでした')
                return
            await thread.starting_message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES))
            await thread.send(f'ゲスト が離脱\n{party.getPartyMessage(ROBIN_GUILD.ROLES)}')

class FormationTopView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()
    @discord.ui.button(label='新規パーティ生成')
    async def newPartyButton(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} New Party button from {interaction.user.display_name}')
        await interaction.response.defer()
        # if type(self.timeout) == float: self.timeout += self.startTime - perf_counter()
        if all({interaction.user.id not in map(lambda party:map(lambda member:member.id, party.members), ROBIN_GUILD.parties)}):
            newPartyNum = 1
            while newPartyNum in map(lambda x:x.number, ROBIN_GUILD.parties):
                newPartyNum += 1
            roles = {role for role in interaction.user.roles if role in ROBIN_GUILD.ROLES.keys()}
            newParty = Party(newPartyNum, {Participant(interaction.user, roles)})
            newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
            newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
            timeout = (ROBIN_GUILD.timeTable[0] - dt.now() + delta(minutes=60))
            newParty.threadTopMessage = await newParty.thread.send(view=PartyView(timeout=timeout.seconds))
            await newParty.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
            ROBIN_GUILD.parties.add(newParty)

        else:
            alartMessage = await interaction.channel.send(f'{interaction.user.mention}パーティメンバは新規パーティを生成できません')
            await alartMessage.delete(delay=5)
            if type(self.timeout) == float: self.timeout += self.startTime - perf_counter()
    
class RebootViwe(discord.ui.View):
    def __init__(self, *items, timeout=None, disable_on_timeout=True):
        super().__init__(*items, timeout=timeout, disable_on_timeout = disable_on_timeout)
    @discord.ui.button(label='次の周回終了で再起動', style=discord.ButtonStyle.green)
    async def scaduleReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        global rebootScadule
        rebootScadule = True
        buttonAllDisable(self.children)
        print(f'{dt.now()} 再起動スケジュールが設定されました')
        await interaction.response.edit_message(view=self)
        await interaction.respond('再起動スケジュールを設定しました')
    @discord.ui.button(label='すぐに再起動', style=discord.ButtonStyle.red)
    async def justReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        button.disabled = True
        buttonAllDisable(self.children)
        await interaction.response.edit_message(view=self)
        await interaction.respond('再起動します')
        await f_reboot()
        

async def leaveParty(participant:Participant|Guest|discord.Member|discord.User, targetParty:Party):
    '''離脱処理からメッセージまで'''
    if type(participant) in (discord.User, discord.Member):
        for member in targetParty.members:
            if member.id == participant.id:
                participant = member
                break
        else: pass # このパーティに当てはまるIDがない
    if targetParty.removeMember(participant) == 0:
        print('パーティが0人なのでスレッド削除 (予定)')
    await targetParty.thread.send(f'{participant.display_name} が離脱\n{targetParty.getPartyMessage(ROBIN_GUILD.ROLES)}')
    await targetParty.thread.starting_message.edit(targetParty.getPartyMessage(ROBIN_GUILD.ROLES))
    if type(participant) == Participant:
        await targetParty.thread.remove_user(participant.user)

async def joinParticipant(participant:Participant|Guest, targetParty:Party):
    '''コルーチン
    加入処理からメッセージ生成まで'''
    for party in ROBIN_GUILD.parties:
        if participant in party.members:
            # 別のパーティに加入していた
            await leaveParty(participant, party)
    targetParty.addMember(participant)
    print(f'PartyNum: {targetParty.number} JoinMember: {participant.display_name}')
    await targetParty.thread.send(f'{participant.display_name} が加入\n{targetParty.getPartyMessage(ROBIN_GUILD.ROLES)}')
    await targetParty.thread.starting_message.edit(targetParty.getPartyMessage(ROBIN_GUILD.ROLES))
    if type(participant) == Participant:
        await targetParty.thread.add_user(participant.user)

def buttonAllDisable(children):
    for child in children:
        if isinstance(child, discord.ui.Button):
            child.disabled = True

# class PartyTopView(discord.ui.View):
#     def __init__(self, *items, timeout = None, disable_on_timeout = True):
#         super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
#         self.startTime = perf_counter()
#     @discord.ui.button(label='新しいパーティを作る')
#     async def add_party(self, button:discord.ui.Button, interaction:discord.Interaction):
#         print(f'{dt.now()} New Party button {interaction.user.name}')
#         if interaction.user in map(lambda party:map(lambda ), ROBIN_GUILD.parties):


##############################################################################################
## Emoji 関数
def emoji2role(emoji: discord.partial_emoji.PartialEmoji | discord.Emoji | str) -> list[discord.Role] | discord.Role | None:
    roles = [r for r, info in ROBIN_GUILD.ROLES.items() if equalEmoji(emoji, info.emoji)]
    if len(roles) == 1: return roles[0]
    elif len(roles) == 0: return None
    else: return roles

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

##############################################################################################
## スラッシュコマンド
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
    if ROBIN_GUILD.timeTable[0] - delta(minutes=40) < dt.now():
        await ctx.respond('パーティ機能作動中か，まもなくパーティ編成を開始します\n再起動スケジュールを選択してください', view=RebootViwe(timeout=60, disable_on_timeout=False))
    else:
        await ctx.respond('再起動します')
        await f_reboot()

@client.slash_command(name='f-stop', description='再起動しても改善しない場合\n編成員Fを停止します\n開発陣へ連絡')
async def f_stop(ctx:discord.ApplicationContext):
    print(f'{dt.now()} slash command restart from {ctx.interaction.user}')
    await ctx.respond('動作を停止します')
    await client.close()
    exit()

@client.slash_command(name='f-rand', description='編成員Fが整数ランダムを生成')
async def f_rand(ctx:discord.ApplicationContext, min:int, max:int):
    await ctx.respond(f'{min}-{max} > {randint(min,max)}')

@client.slash_command(name='f-get-participant-data', description='これまでの参加データをcsv形式で返します')
async def f_get_participant_data(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return
    with open(f'../reactionLog/{ctx.interaction.guild.name}.csv', 'r') as f:
        csvFile = discord.File(fp=f, filename=dt.now().strftime('participant_data_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`年-月-日-時,ユーザーID,希望`\n希望は "l":殲滅 "h":高速', file=csvFile)

async def f_reboot():
    Popen([executable, '-u'] + argv)  # ボットを再起動
    await client.close()  # ボットを終了
    exit()


# @client.slash_command(name='f-get-member-id', description='メンバIDとメンバ表示名を紐づけたファイルを返します')
# async def f_get_memberID(ctx:discord.ApplicationContext):
#     if ctx.guild == None:
#         await ctx.respond('目的のサーバー内でコマンドしてください')
#         return
#     with open('memberID.csv', 'w', encoding='utf-8-sig') as f:
#         for member in ctx.guild.members:
#             f.write(f'{member.id},{member.display_name}\n')
#     with open('memberID.csv', 'r', encoding='utf-8-sig') as f:
#         retFile = discord.File(fp=f, filename='memberID.csv')
#     await ctx.respond(f'{ctx.user.mention}', file=retFile)

##############################################################################################
if __name__ == '__main__':
    print(f'##################################################################################')
    print(f'{dt.now()} スクリプト起動')
    # print(f"Intents.members: {client.intents.members}")  # True ならOK
    try:
        client.run('token')
    except KeyboardInterrupt:
        exit()
