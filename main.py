from __future__ import annotations
import discord
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
from os import getcwd

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

class RoleInfo:
    def __init__(self, emoji:discord.Emoji, count:int):
        self.emoji:discord.Emoji = emoji
        self.count:int = count
        
class PartyMember: # パーティメンバ親クラス
    def __init__(self, user:discord.Member|None, roles:set[discord.Role]):
        self.user:discord.Member|None = user
        self.roles:set[discord.Role] = roles

class Participant(PartyMember): # メンバと可能ロール
    def __init__(self, user:discord.User|discord.Member, roles:set[discord.Role]):
        super().__init__(user, roles)
        self.mention:str = user.mention
        self.id = user.id
        self.display_name = user.display_name

class Guest(PartyMember): # Party class のためのダミー
    def __init__(self):
        super().__init__(user=None, roles=set())
        # self.user = None
        # self.roles = set()
        self.mention = 'ゲスト'
        self.id = -1
        self.display_name = 'ゲスト'

class Party: # パーティ情報 メッセージとパーティメンバ
    def __init__(self, number:int):
        self.number:int = number
        self.message:discord.Message|None = None
        self.joins:dict[discord.Message, discord.User|discord.Member] = dict()
        self.thread:discord.Thread|None = None

class LightParty(Party):
    def __init__(self, number, players:list[Participant]=list()):
        super().__init__(number)
        self.members:list[Participant|Guest] = players
        self.threadTopMessage:discord.Message|None = None
        self.aliance:LightParty|None = None
    
    async def addAlianceParty(self, party:LightParty):
        await self._addAlience(party)
        await party._addAlience(self)

    async def leaveAlianceParty(self):
        await self.aliance._removeAliance(self)
        await self._removeAliance(self.aliance)

    async def _addAlience(self, party:LightParty):
        self.aliance = party
        await self.sendAlianceInfo()
    
    async def sendAlianceInfo(self):
        msg = f'@here\n## [パーティ:{self.aliance.number}]({self.aliance.message.jump_url}) と同盟'
        for member in self.aliance.members:
            msg += f'\n{member.display_name}'
        if self.thread: await self.thread.send(msg)

    async def _removeAliance(self, party:LightParty):
        self.aliance = None
        await self.thread.send(f'@here\n## パーティ:{party.number} の同盟を解除')
        await self.alianceCheck(ROBIN_GUILD.parties)
        await self.message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))

    async def alianceCheck(self, parties:list[LightParty]):
        if self.membersNum() == 4 and self.aliance is None:
            # ４人到達 アライアンス探索
            print(f'party:{self.number} aliance check')
            for party in parties:
                if party == self: continue
                print(f'party:{party.number} -> {party.membersNum()}')
                if party.membersNum() == 4 and party.aliance is None:
                    print(f'Aliance:{self.number} <=> {party.number}')
                    await self.addAlianceParty(party)
                    break
    
    def membersNum(self) -> int:
        return len(self.members)

    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        msg = f'\| 【パーティ:{self.number}】'
        if self.aliance:
            try: 
                msg += f'同盟 -> [パーティ{self.aliance.number}]({self.aliance.message.jump_url})'
            except Exception as e:
                printTraceback(e)
                msg += f'同盟 -> パーティ{self.aliance.number}'
        for player in self.members:
            msg += f'\n\| {player.mention}'
            for role in player.roles:
                msg += str(guildRolesEmoji[role].emoji)
        return msg
    
    async def joinRequest(self, member:discord.Member) -> bool:
        print(f'Join request Party:{self.number} {member}')
        if self.isEmpty(): # パーティが空だった
            print('パーティが空')
            participant = Participant(member, set(role for role in member.roles if role in ROBIN_GUILD.ROLES.keys()))
            await self.joinMember(participant)
            return True
        if member in map(lambda x:x.user, self.members): # 自パーティだった
            print('自パーティだった')
            await self.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, member)
            msg = await ROBIN_GUILD.PARTY_CH.send(f'{member.mention}加入中のパーティには参加申請できません')
            await msg.delete(delay=5)
            return False
        print(f'Join request Done')
        requestMessage = await self.thread.send(f'@here {member.display_name} から加入申請', view=ApproveView(timeout=600))
        self.joins[requestMessage] = member

    def addMember(self, participant:Participant|Guest) -> bool:
        self.members.append(participant)
    
    async def joinMember(self, participant:Participant|Guest):
        if not isinstance(participant, Guest) and participant.user in map(lambda x:x.user, self.members): return False
        self.addMember(participant)
        if self.thread is None: return True
        print(f'PartyNumber:{self.number} JoinMember:{participant.display_name} PartyMemberNumber:{self.membersNum()} Aliance:{self.aliance}')
        if isinstance(participant, Participant): # メンバならスレッドに入れる
            await self.thread.add_user(participant.user)
        await self.thread.send(f'{participant.display_name} が加入\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
        await self.alianceCheck(ROBIN_GUILD.parties)
        await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
        return True
    
    async def removeMember(self, member:Participant|discord.Member|Guest) -> bool:
        if isinstance(member, Guest):
            self.removeGuest()
        elif isinstance(member, Participant) or isinstance(member, discord.Member):
            if isinstance(member, Participant): member = member.user # memberを必ずMemberクラスにする
            if member not in map(lambda x:x.user, self.members): return False
            for participant in self.members:
                if participant.user == member:
                    self.members.remove(participant)
                    print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                    await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
                    await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
                    break
            else:
                return False
        else:
            raise TypeError(member)
        
        if self.aliance and self.membersNum() < 4:
            await self.leaveAlianceParty()
        return True

    async def removeGuest(self) -> bool:
        for member in self.members:
            if isinstance(member, Guest):
                self.members.remove(member)
                print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
                await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
                return True
        await self.thread.send('ゲストがいないためパーティに変更はありません')
        return False
    
    def isEmpty(self) -> bool:
        return all(map(lambda member: not isinstance(member, Participant), self.members))

class SpeedParty(Party):
    def __init__(self, number, rolesNum:dict[discord.Role, int]):
        super().__init__(number)
        self.members:dict[discord.Role,list[Participant|None]] = {role:[None] * num for role, num in rolesNum.items()}

    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        msg = f'\| <:FullParty:1345733070065500281> 高速パーティ:{self.number} <:FullParty:1345733070065500281>'
        for partyRole, members in self.members.items():
            for member in members:
                msg += f'\n{guildRolesEmoji[partyRole].emoji} \| {member.mention}'
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
        self.LIGHT_FORMATION:dict[discord.Emoji, int] = dict() # ライトパーティ編成枠
        self.FULL_FORMATION:dict[discord.Emoji, int] = dict() # フルパーティ編成枠
        self.TRANCE_FORMATION:dict[discord.Emoji, discord.Emoji] = dict() # 職変換

        self.DEV_CH:discord.TextChannel = None # デベロッパーチャンネル
        self.PARTY_CH:discord.TextChannel = None # 募集チャンネル
        self.PARTY_CH_beta:discord.TextChannel = None # ベータ版募集チャンネル
        self.COMMAND_CH:discord.TextChannel = None # コマンドチャンネル
        self.COMMAND_MSG:discord.Message = None # コマンドメッセージ
        self.PARTY_LOG:discord.TextChannel = None # パーティログチャンネル

        self.reclutingMessage:discord.Message = None # 募集メッセージ
        self.parties:list[SpeedParty|LightParty]|None = None # パーティ一覧
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
    if ROBIN_GUILD.parties != None:
        # 途中自動参加
        if reaction.message == ROBIN_GUILD.reclutingMessage:
            print('Join request to F')
            if not isPartyMember(user):
                minParty:LightParty|None = None
                for party in ROBIN_GUILD.parties:
                    if isinstance(party, LightParty):
                        if (minParty == None or \
                                minParty.membersNum() + len(minParty.joins) > \
                                party.membersNum() + len(party.joins)) and \
                                party.membersNum() + len(party.joins) <= 3:
                            minParty = party
                if minParty == None:
                    await createNewParty(user)
                else:
                    await minParty.joinRequest(user)

        # パーティメッセージ
        elif reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
            ####################################################################
            # party = searchLightParty(reaction.message, ROBIN_GUILD.parties)
            # party.joinRequest(user)
            ####################################################################
            try:
                # party = searchLightParty(message, ROBIN_GUILD.parties, lambda x:[x.message])
                party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
                await party.joinRequest(user)
                # if user.id not in map(lambda x:x.id, party.members): # 別のパーティ
                #     if len(party.members) > 0: # 誰か１人でもいる場合 承認要請
                #         await party.joinRequest(user)
                #         thread = reaction.message.thread
                #         if thread == None:
                #             message = await ROBIN_GUILD.PARTY_CH.fetch_message(reaction.message.id)
                #             thread = message.thread
                #         party.joins[await thread.send(f'@here {user.display_name} から加入申請', view=ApproveView(timeout=600))] = user
                #     else:
                #         await reaction.message.remove_reaction(reaction.emoji, user)
                #         await party.joinMember(Participant(user, set(role for role in user.roles if role in ROBIN_GUILD.ROLES.keys())))
                #         # await joinParticipant(Participant(user, set(role for role in user.roles if role in ROBIN_GUILD.ROLES.keys())), party)
                # else:
                #     await reaction.message.remove_reaction(reaction.emoji, user)
                #     errorMessage = await reaction.message.channel.send(f'{user.mention}加入中のパーティには参加申請できません')
                #     await errorMessage.delete(delay=5)
            except Exception as e:
                printTraceback(e)

##############################################################################################
## 
def searchLightParty(message:discord.Message, parties:list[Party]) -> Party|None:
    for party in parties:
        if isinstance(party, LightParty):
            print(f'target message:{message.id} party.message{party.message.id} party.threadTopMessage{party.threadTopMessage.id}')
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
    # if ROBIN_GUILD.parties != None:
    #     if reaction.message in map(lambda x:x.message, ROBIN_GUILD.parties) and reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
    #         party:LightParty = searchLightParty(reaction.message, ROBIN_GUILD.parties)
    #         for delMessage, member in party.joins.items():
    #             if user == member:
    #                 del party.joins[delMessage]
    #                 await delMessage.edit(f'@here {user.display_name} が加入申請を取り下げ', view=None)
    #                 break

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

            ROBIN_GUILD.parties = list()
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
                        participants.append(participant)
            participantNum = len(participants)

            print('participants')
            print([participant.display_name for participant in participants])
            
            await ROBIN_GUILD.PARTY_LOG.send(f'{ROBIN_GUILD.timeTable[0].strftime("%y-%m-%d-%H")} <:sanka:1345708506111545375> {participantNum}')

            formationStartTime = dt.now()
            # 編成
            shuffle(participants)
            print(f'shaffled: {[participant.display_name for participant in participants]}')
            if participantNum >= 10:
                for party in hispeedFormation(participants):
                    ROBIN_GUILD.parties.append(party)
            for party in lowspeedFormation(participants, len(ROBIN_GUILD.parties)):
                ROBIN_GUILD.parties.append(party)
            print(f'formation algorithm time: {dt.now() - formationStartTime}')

            try:
                # パーティ同盟チェック
                for party in ROBIN_GUILD.parties:
                    if isinstance(party, LightParty):
                        await party.alianceCheck(ROBIN_GUILD.parties)
            except Exception as e:
                printTraceback(e)

            # パーティ通知メッセージ
            await ROBIN_GUILD.PARTY_CH.send(ROBIN_GUILD.timeTable[0].strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ\n原則、一番上がリーダーです' + '' if participantNum != 8 else '\n参加者が8人ですので\n## 殲滅固定（カンダタを倒す）同盟です\n参加者は ___**サーバー3**___ へ'), \
                                            view=FormationTopView(timeout=3600))
            
            for party in ROBIN_GUILD.parties:
                party.message = await ROBIN_GUILD.PARTY_CH.send(party.getPartyMessage(ROBIN_GUILD.ROLES))

        print(f'{dt.now()} Formation END')

        print(f'{dt.now()} Create Threads')

        if any(map(lambda x:isinstance(x, SpeedParty), ROBIN_GUILD.parties)):
            await ROBIN_GUILD.PARTY_CH.send(file=discord.File('images/speedParty.png'))
        for party in ROBIN_GUILD.parties:
            if isinstance(party, SpeedParty):
                party.thread = await party.message.create_thread(name=f'SpeedParty:{party.number}', auto_archive_duration=60)
            elif isinstance(party, LightParty):
                party.thread = await party.message.create_thread(name=f'Party:{party.number}', auto_archive_duration=60)
                await party.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
                party.threadControlMessage = await party.thread.send(view=PartyView(timeout=3600))
                if party.aliance:
                    try:
                        await party.sendAlianceInfo()
                    except Exception as e:
                        printTraceback(e)
        print(f'{dt.now()} Create Threads END')
        print(f'{dt.now()} Add Log')
        with open(f'reactionLog/{ROBIN_GUILD.GUILD.name}.csv', 'a', encoding='utf8') as f:
            for participant in participants:
                f.write(f"{ROBIN_GUILD.timeTable[0].strftime('%y-%m-%d-%H')},{participant.id}\n")
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
        
        del ROBIN_GUILD.timeTable[0] # 先頭を削除
        if len(ROBIN_GUILD.timeTable) < 3:
            ROBIN_GUILD.timeTable = await getTimetable()
            for t in ROBIN_GUILD.timeTable:
                print(t)
        msg = ROBIN_GUILD.timeTable[0].strftime('## 次回の異星は %H時 です\n%H時 > ')
        msg += ROBIN_GUILD.timeTable[1].strftime('%H時 > ')
        msg += ROBIN_GUILD.timeTable[2].strftime('%H時 > [...](https://hiroba.dqx.jp/sc/tokoyami/)')
        await ROBIN_GUILD.PARTY_CH.send(msg)

        if rebootScadule:
            try: await rebootScadule.send('再起動します')
            except Exception as e:
                printTraceback(e)
            await f_reboot()
        
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
        ROBIN_GUILD.parties = None
        ROBIN_GUILD.reclutingMessage = None
        

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
def hispeedFormation(participants:list[Participant]) -> list[SpeedParty]:
    '''
    <h1>Parameter</h1>
    players: list[Participant]
    <h1>Return</h1>
    List[List[Participant]]
    '''
    parties:list[SpeedParty] = []
    parties.append(SpeedParty(len(parties)+1, {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}))
    loopFlg = True
    while loopFlg:
        partyNoneCount = parties[-1].noneCount()
        if partyNoneCount > len(participants) or partyNoneCount == 0 and len(participants) < 8: break
        if partyNoneCount == 0: # 空きのあるパーティがない 新しい空のパーティを作る
            parties.append(SpeedParty(len(parties)+1, {role:info.count for role, info in ROBIN_GUILD.ROLES.items()}))
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
                    # participants = [partyMember] + participants
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
    
def lowspeedFormation(participants:list[Participant], partyNum:int) -> list[LightParty]:
    parties_num:list[int] = [4 for _ in range(len(participants) // 4)]
    if len(participants) % 4 > 0:
        parties_num.append(len(participants) % 4)

    # パーティメンバ数例外処理
    if len(parties_num) >= 3: # 3パーティ以上
        if sum(i for i in parties_num[-3:]) == 9:
            parties_num[-1] = 3
            parties_num[-2] = 3
            parties_num[-3] = 3
    elif len(parties_num) >= 2: # 2パーティ
        parties2tailSum = sum(i for i in parties_num[-2:])
        if parties2tailSum == 5:
            parties_num[-1] = 2
            parties_num[-2] = 3
        elif parties2tailSum == 6:
            parties_num[-1] = 3
            parties_num[-2] = 3

    # パーティ割り振り人数確定
    # メンバー振り分け
    parties:list[LightParty] = []
    p = 0
    for n in parties_num:
        partyNum += 1
        parties.append(LightParty(partyNum, []))
        for _ in range(n):
            parties[-1].addMember(participants[p])
            p += 1

    return parties

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

##############################################################################################
## ビュー
class RoleManageView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    async def roleManage(self, label:str, emoji:str, user:discord.User|discord.Member):
        role = emoji2role(emoji)
        if role in user.roles:
            # ロールがあるから削除
            print(f'{dt.now()} Delete role {user} {label}')
            await user.remove_roles(role)
            rep = await ROBIN_GUILD.COMMAND_CH.send(f'{user.mention} [{label}] を削除')
        else:
            # ロールがないから追加
            print(f'{dt.now()} Add role {user} {label}')
            await user.add_roles(role)
            rep = await ROBIN_GUILD.COMMAND_CH.send(f'{user.mention} [{label}] を追加')
        await rep.delete(delay=5)

    @discord.ui.button(label='魔戦', emoji='<:magic_knight:1345708222962470952>', row=1)
    async def magicKnight(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='先導', emoji='<:boomerang:1345710507398529085>', row=1)
    async def boomerang(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='霧', emoji='<:buttarfly:1345708049838641234>', row=1)
    async def butterfly(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='札', emoji='<:card:1345708117618458695>', row=2)
    async def card(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='中継', emoji='<:relay:1345708117618458695>', row=2)
    async def way(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='回復', emoji='<:heal:1345708066741424138>', row=2)
    async def heal(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @discord.ui.button(label='オールクリア', row=3)
    async def all_clear(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        for role in ROBIN_GUILD.ROLES.keys():
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
        rep = await interaction.channel.send(f'{interaction.user.mention}全ての高速可能ロールを削除')
        await rep.delete(delay=5)

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
            party = searchLightParty(message.channel, ROBIN_GUILD.parties)
            if user.id in {participant.id for participant in party.members}: # パーティメンバである
                buttonAllDisable(self.children)
                await interaction.response.edit_message(view=self)
                print('パーティメンバによる承認')
                thread = message.channel
                joinMember = party.joins[message]
                print(f'JoinMember: {joinMember}')
                for p in {p for p in ROBIN_GUILD.parties if joinMember in p.joins.values()}: # 参加リアクション全削除
                    await p.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember)
                await thread.add_user(joinMember) # パーティへ追加
                await party.joinMember(Participant(joinMember, set(role for role in joinMember.roles if role in ROBIN_GUILD.ROLES.keys())))
                del party.joins[message] # 申請削除
                await thread.starting_message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember) # リアクション処理
            else:
                print('パーティメンバ以外による承認')
                await interaction.response.defer()
                msg = await interaction.channel.send(f'{interaction.user.mention}\nパーティメンバ以外は操作できません')
                await msg.delete(delay=5)
                return
        except Exception as e:
            printTraceback(e)

class PartyView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()

    @discord.ui.button(label='パーティを抜ける')
    async def leaveParty(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Leave party button is pressed from {interaction.user.display_name}')
        party:LightParty = searchLightParty(interaction.message, ROBIN_GUILD.parties)
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
            await party.removeMember(interaction.user)
            try:
                if party.isEmpty():
                    print('パーティが0人')
                    ROBIN_GUILD.parties.remove(party)
                    await party.message.delete()
            except Exception as e:
                printTraceback(e)
                
        else: # ユーザーが別パーティメンバ
            print('別パーティによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)

    @discord.ui.button(label='ゲスト追加')
    async def addGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest add button is pressed from {interaction.user.display_name}')
        await interaction.response.defer()
        party = searchLightParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
        elif interaction.user in map(lambda x:x.user, party.members):
            print(f'パーティメンバによるアクション')
            await party.joinMember(Guest())
    
    @discord.ui.button(label='ゲスト削除')
    async def removeGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest remove button from {interaction.user.display_name}')
        await interaction.response.defer()
        party = searchLightParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
            return
        if interaction.user in map(lambda x:x.user, party.members): # パーティメンバである
            print('パーティメンバによるアクション')
            await party.removeGuest()

class FormationTopView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()
    @discord.ui.button(label='新規パーティ生成')
    async def newPartyButton(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} New Party button from {interaction.user.display_name}')
        await interaction.response.defer()
        if all({interaction.user.id not in map(lambda party:map(lambda member:member.id, party.members), ROBIN_GUILD.parties)}):
            await createNewParty(interaction.user)
        else:
            alartMessage = await interaction.channel.send(f'{interaction.user.mention}パーティメンバは新規パーティを生成できません')
            await alartMessage.delete(delay=5)

async def createNewParty(user:discord.Member):
    if len(ROBIN_GUILD.parties) == 0: newPartyNum = 1
    else: newPartyNum = max(map(lambda x:x.number, ROBIN_GUILD.parties)) + 1
    roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
    newParty = LightParty(newPartyNum, [Participant(user, roles)])
    newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    timeout = (ROBIN_GUILD.timeTable[0] - dt.now() + delta(minutes=60))
    newParty.threadTopMessage = await newParty.thread.send(view=PartyView(timeout=timeout.seconds))
    await newParty.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
    ROBIN_GUILD.parties.append(newParty)

class RebootView(discord.ui.View):
    def __init__(self, *items, timeout=None, disable_on_timeout=True):
        super().__init__(*items, timeout=timeout, disable_on_timeout = disable_on_timeout)
    @discord.ui.button(label='次の周回終了で再起動', style=discord.ButtonStyle.green)
    async def scaduleReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        global rebootScadule
        try:
            rebootScadule = interaction.channel
        except Exception as e:
            printTraceback(e)
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
        await f_reboot(interaction)

def buttonAllDisable(children):
    for child in children:
        if isinstance(child, discord.ui.Button):
            child.disabled = True

def isPartyMember(user:discord.Member) -> bool:
    for party in ROBIN_GUILD.parties:
        if any(map(lambda x:x.user==user, party.members)):
            return False
    return True

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
    if len(ROBIN_GUILD.timeTable) == 0:
        await f_reboot(ctx)
    if ROBIN_GUILD.timeTable[0] - delta(minutes=40) < dt.now():
        await ctx.respond('パーティ機能作動中または，まもなくパーティ編成を開始します\n再起動スケジュールを選択してください', view=RebootView(timeout=60, disable_on_timeout=False))
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
    await ctx.respond(f'{min}-{max} > {randint(min,max)}')

@client.slash_command(name='f-get-participant-data', description='これまでの参加データをcsv形式で返します')
async def f_get_participant_data(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return
    with open(f'../reactionLog/{ctx.interaction.guild.name}.csv', 'r') as f:
        csvFile = discord.File(fp=f, filename=dt.now().strftime('participant_data_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`年-月-日-時,ユーザーID,希望`\n希望は "l":殲滅 "h":高速', file=csvFile)

@client.slash_command(name='f-get-participant-name', description='サーバーメンバのIDと現在の表示名の対応をcsv形式で返します')
async def f_get_participant_name(ctx:discord.ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return 
    filename = f'../reactionLog/{ctx.interaction.guild.name}_nameList.csv'
    with open(filename, 'w') as f:
        async for member in ctx.interaction.guild.fetch_members():
            f.write(f'{member.id},{member.display_name}\n')
    with open(filename, 'r') as f:
        csvFile = discord.File(fp=f, filename=dt.now().strftime('participant_name_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ユーザーID,表示名`', file=csvFile)

async def f_reboot(ctx:discord.ApplicationContext|None = None):
    if ctx: await ctx.respond('再起動します')
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()

##############################################################################################
if __name__ == '__main__':
    print(f'##################################################################################')
    print(f'{dt.now()} スクリプト起動')
    # print(f"Intents.members: {client.intents.members}")  # True ならOK
    try:
        with open('../token.csv', 'r', encoding='utf-8') as f:
            token = f.readlines()[0]
        client.run(token)
    except KeyboardInterrupt:
        exit()
