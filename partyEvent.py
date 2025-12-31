from __future__ import annotations # 再帰に必要 必ず先頭に

from datetime import datetime as dt, timedelta as delta
from typing import Any
from discord import Guild, File, Member, Message, TextChannel, Role, Emoji, CategoryChannel, User, Thread
from discord.ui import View
from Views import ApproveView, FormationTopView
from formation import speedFormation, randomFormation
from random import shuffle
from main import client, CONFIG, config, GUILD_INFO
from general import *
from Views import *

class PartyEvent:
    def __init__(self,
                 guildID:int,
                 recruitEmoji:Emoji,
                 eventTitle:str,
                 targetChannel:TextChannel,
                 firstPartyFormation:list[dict[Role,int]],
                 recruitButton:bool=False,
                 randomPartyCapacity:int=0,
                 notificationTime:dt|delta=None,
                 notificationMessagePath:str='',
                 remindTime:dt|delta=None,
                 remindMessagePath:str='',
                 formationTime:dt=None,
                 formationMessagePath:str='',
                 endTime:dt|delta=None,
                 endMessagePath:str='',
                 endMessage:str=''
                 ):
        
        self.guildID:int = guildID
        self.recruitEmoji:Emoji = recruitEmoji
        self.eventTitle:str = eventTitle
        self.targetChannel:TextChannel = targetChannel
        self.recruitButton:bool = recruitButton
        self.recruitView:RecruitView = None
        self.firstPartyFormation:list[dict[Role,int]] = firstPartyFormation
        self.randomPartyCapacity:int = randomPartyCapacity
        self.endMessage:str = endMessage
        self.recruitMessage:Message = None
        self.partyChannel:TextChannel = None
        self.recruitMember:set[Member] = set()
        self.parties:list[SpeedParty|LightParty] = list()
        self.randomParties:list[RandomParty] = list()
        self.status:int = 0 # 0:アナウンス前 1:リマインド前 2:編成前 3:編成中 4:終了
        
        if formationTime is None: self.formationTime:dt = dt.now()
        else: self.formationTime:dt = formationTime
        self.formationMessagePath:str = formationMessagePath
        
        if isinstance(endTime, dt): self.endTime:dt = endTime
        elif isinstance(endTime, delta): self.endTime:dt = formationTime + endTime
        else: self.endTime = None
        self.endMessagePath:str = endMessagePath

        if isinstance(notificationTime, dt): self.notificationTime:dt = notificationTime
        elif isinstance(notificationTime, delta): self.notificationTime:dt = self.formationTime + notificationTime
        else:
            self.notificationTime = None
            self.status = 1 # 通知なしでリマインドへ
        self.notificationMessagePath:str = notificationMessagePath

        if isinstance(remindTime, dt): self.remindTime:dt = remindTime
        elif isinstance(remindTime, delta): self.remindTime:dt = self.formationTime + remindTime
        else:
            self.remindTime = None
            if self.status == 1: self.status = 2 # リマインドなしで編成へ
        self.remindMessagePath:str = remindMessagePath

    async def notification(self, client:Client, now:dt):
        # 編成アナウンス
        print(f'{dt.now()} Recruting {self.eventTitle}')
        sendItems = getDirectoryItems(self.notification)
        for index, sendItem in enumerate(sendItems):
            # 連続メッセージ
            if index - len(sendItems) + 1 == 0:
                # 最後のメッセージ
                if self.recruitButton:
                    self.recruitView = RecruitView(
                        duration=(self.formationTime - now).total_seconds(),
                        members=self.recruitMember
                        )
                    self.recruitMessage = await self.targetChannel.send(
                        content=self.eventTitle,
                        files=sendItem.imgs,
                        view=self.recruitButton
                        )
                else:
                    self.recruitMessage = await self.targetChannel.send(
                        content=self.eventTitle,
                        files=sendItem.imgs,
                        )
                    await self.recruitMessage.add_reaction(self.recruitEmoji) # 参加リアクション追加
            else:
                await self.targetChannel.send(
                    content=self.eventTitle,
                    files=sendItem.imgs
                    )

    async def remind(self, client:Client):
        # リマインド
        print(f'{dt.now()} Formation {self.eventTitle}')
        async with self.targetChannel.typing():
            eventRoles:set[Role] = {map(lambda party:party.keys(), self.firstPartyFormation)}
            participants:list[Participant] = list()
            self.parties = list()
            # 値取得
            if self.recruitButton:
                participants = [map(
                    lambda participant:Participant(participant, {filter(
                        lambda roles:roles in eventRoles,
                        participant.roles
                        )}
                    ), self.recruitMember)]
            else:
                self.recruitMessage = await self.targetChannel.fetch_message(self.recruitMessage.id)
                for reaction in self.recruitMessage.reactions:
                    if reaction.emoji == ROBIN_GUILD.RECLUTING_EMOJI:
                        async for user in reaction.users():
                            if user == client.user: continue
                            if ROBIN_GUILD.MEMBER_ROLE not in user.roles: continue
                            if user in map(lambda x:x.user, self.recruitMember): continue # 既に参加者リストにいるならスキップ
                            roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
                            participants.append(Participant(user, roles))
            
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

        
    async def tick(self, client:Client, nowTime:dt) -> int:
        if self.status == 0: # アナウンス時間
            if self.notificationTime <= nowTime:
                await self.notification(client, nowTime)
                if self.notificationTime is not None: self.status = 1 # リマインド時間へ
                else: self.status = 2 # リマインドなしで編成へ
            else: return None

        elif self.status == 1: # リマインド時間
            if self.eventTime + self.remindTime > nowTime:
                self.status = 2
            if self.status != 2: return None
            self.recruitingMessage = await self.partyChannel.send(self.eventTime.strftime(f'編成まであと%M分\n{self.recruitingMessage.jump_url}'))
        
        elif self.status == 2: # 編成時間
            #region 編成
            if self.eventTime + self.formationTime > nowTime:
                self.status = 3
            else: return None
            speedPartiesMember:list[dict[Role,list[Member]]] = list()
            randomPartiesMember:list[list[Member]] = list()
            with self.partyChannel.typing():                
                formationTimeStart = dt.now()
                shuffle(self.members)
                participants:dict[Member,set[Role]] = dict()
                for member in self.members:
                    participants[member] = set(role for role in self.speedPartyFormation.keys() if role in member.roles)
                speedPartiesMember = speedFormation(participants, speedFormation)
                if self.randomPartyLimit: randomPartiesMember:list[list[Member]] = randomFormation(participants, self.randomPartyLimit)
                else: randomPartiesMember:list[list[Member]] = []
                formationTimeEnd = dt.now()

                # パーティのインスタンス化
                # スピードパーティ
                partyNumber = 1
                for party in speedPartiesMember:
                    speedParty = SpeedParty(partyNumber, self.speedPartyFormation)
                    partyNumber += 1
                    for role, members in party.items():
                        for member in members:
                            speedParty.addMember(Participant(member, set(r for r in self.guildRoles.keys() if r in member.roles)), role)
                    self.speedParties.append(speedParty)
                # ランダムパーティ
                for party in randomPartiesMember:
                    partyParticipants = list()
                    for member in party:
                        partyParticipants.append(Participant(member, set(r for r in self.guildRoles.keys() if r in member.roles)))
                    self.randomParties.append(RandomParty(partyNumber, partyParticipants))
                
                viewTimeout = self.endTime if isinstance(self.endTime, delta) else self.eventTime - self.endTime
                await self.partyChannel.send(
                    self.eventTime.strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ\n原則、一番上がリーダーです' +
                                            '' if len(participants) != 8 else '\n参加者が8人ですので\n## 殲滅固定（カンダタを倒す）同盟です\n参加者は ___**サーバー3**___ へ') +
                                            f'\n-# 編成処理時間: {str((formationTimeEnd - formationTimeStart).total_seconds())}秒',
                                            view=FormationTopView(timeout=viewTimeout.seconds))
                for party in self.speedParties: # 高速パーティ通知
                    party.message = await self.partyChannel.send(party.getPartyMessage(self.guildRoles))
                for party in self.randomParties: # 通常パーティ通知
                    party.message = await self.partyChannel.send(party.getPartyMessage(self.guildRoles))
            for party in self.speedParties: # 高速パーティスレッド
                party.thread = await party.message.create_thread(name=f'SpeedParty:{party.number}', auto_archive_duration=self.threadAutoArciveDuration)
            if self.speedParties: # 高速パーティがあるときは画像を出す
                self.partyChannel.send(file=self.speedPartySendImage)
            for party in self.randomParties: # 通常パーティスレッド
                party.thread = await party.message.create_thread(name=f'Party:{party.number}', auto_archive_duration=self.threadAutoArciveDuration)
            
            # アライアンスチェック
            if self.randomAliance:
                for party in self.randomParties:
                    if party.aliance is None:
                        await party.alianceCheck(self.randomAliance)
                        party.message.edit(party.getPartyMessage(self.guildRoles))

            #endregion
        
        elif self.status == 3 and self.eventTime + self.endTime > nowTime:
            if self.endTime + self.eventTime:
                self.status = 4

class PartyMember: # パーティメンバ親クラス
    def __init__(self, user:Member|None, roles:set[Role]):
        self.user:Member|None = user
        self.roles:set[Role] = roles

class Participant(PartyMember): # メンバと可能ロール
    def __init__(self, user:Member, roles:set[Role]):
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
        self.message:Message|None = None
        self.joins:dict[Message, User|Member] = dict()
        self.thread:Thread|None = None

class RandomParty(Party):
    def __init__(self, number, players:list[Participant]=list(), free:bool=False):
        super().__init__(number)
        self.members:list[Participant|Guest] = players
        self.threadControlMessage:Message|None = None
        self.aliance:RandomParty|None = None
        self.free:bool = free
    
    async def addAlianceParty(self, party:RandomParty):
        await self._addAlience(party)
        await party._addAlience(self)
        await party.message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES))

    async def leaveAlianceParty(self):
        await self.aliance._removeAliance(self)
        await self._removeAliance(self.aliance)

    async def _addAlience(self, party:RandomParty):
        self.aliance = party
        await self.sendAlianceInfo()
    
    async def sendAlianceInfo(self):
        msg = f'@here\n## [パーティ:{self.aliance.number}]({self.aliance.message.jump_url}) と同盟'
        for member in self.aliance.members:
            msg += f'\n- {member.display_name}'
        if self.thread: await self.thread.send(msg)

    async def _removeAliance(self, party:RandomParty):
        self.aliance = None
        await self.thread.send(f'@here\n## パーティ:{party.number} の同盟を解除')
        await self.alianceCheck(ROBIN_GUILD.parties)
        await self.message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))

    async def alianceCheck(self, parties:list[RandomParty]):
        if self.membersNum() == 4 and self.aliance is None:
            # ４人到達 アライアンス探索
            print(f'party:{self.number} aliance check')
            for party in parties:
                if party == self or not isinstance(party, RandomParty): continue
                print(f'party:{party.number} -> {party.membersNum()}')
                if party.membersNum() == 4 and party.aliance is None:
                    print(f'Aliance:{self.number} <=> {party.number}')
                    await self.addAlianceParty(party)
                    break
    
    def membersNum(self) -> int:
        return len(self.members)

    def getPartyMessage(self, guildRolesEmoji:bidict[Role,Emoji]) -> str:
        msg = ''
        if self.free:
            msg += '## 途中抜けOK\n'
        msg += f'\| 【パーティ:{self.number}】'
        if self.aliance:
            msg += f'同盟 -> [パーティ{self.aliance.number}]({self.aliance.message.jump_url})'
        for player in self.members:
            msg += f'\n\| {player.mention}'
            for role in player.roles:
                msg += str(guildRolesEmoji[role])
        return msg
    
    async def joinRequest(self, member:Member) -> bool:
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

    async def removeJoinRequest(self, target:Member | RandomParty) -> bool:
        print(f'Remove join request target:{target}')
        if isinstance(target, Member):
            for party in ROBIN_GUILD.parties:
                if not isinstance(party, RandomParty): continue
                for message, member in party.joins.items():
                    if member == target:
                        if self != party:
                            await message.edit(f'@here\n{target.display_name} が参加取り下げ', view=DummyApproveView())
                        del party.joins[message]
                        break
            return True
        elif isinstance(target, RandomParty):
            for message, member in target.joins.items():
                del target.joins[message]
            return True
        else: return False

    def addMember(self, participant:Participant|Guest) -> bool:
        self.members.append(participant)
    
    async def joinMember(self, participant:Participant|Guest) -> bool:
        if not isinstance(participant, Guest) and participant.user in map(lambda x:x.user, self.members): return False
        self.addMember(participant)
        if self.thread is None: return True
        print(f'PartyNumber:{self.number} JoinMember:{participant.display_name} PartyMemberNumber:{self.membersNum()} Aliance:{self.aliance}')
        if isinstance(participant, Participant): # メンバならスレッドに入れる
            await self.thread.add_user(participant.user)
        await self.thread.send(f'{participant.display_name} が加入\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
        await self.alianceCheck(ROBIN_GUILD.parties)
        if self.membersNum() >= 4:
            await self.message.clear_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
        await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
        return True
    
    async def removeMember(self, member:Participant|Member|Guest) -> bool:
        if isinstance(member, Participant): member = member.user # memberであればMemberクラスにする
        if member not in map(lambda x:x.user, self.members): return False
        for participant in self.members[-1::-1]:
            if participant.user == member:
                self.members.remove(participant)
                print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
                if self.aliance and self.membersNum() < 4:
                    await self.leaveAlianceParty()
                await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
                break
            if self.membersNum() >= 4:
                self.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
        return True

    async def removeGuest(self) -> bool:
        for member in self.members[-1::-1]:
            if isinstance(member, Guest):
                await self.removeMember(member)
                # self.members.remove(member)
                # print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                # await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROBIN_GUILD.ROLES)}')
                # await self.thread.starting_message.edit(self.getPartyMessage(ROBIN_GUILD.ROLES))
                return True
        await self.thread.send('ゲストがいないためパーティに変更はありません')
        return False
    
    def isMember(self, user:Member):
        try: return user in self.members
        except Exception as e:
            printTraceback(e)
            return False
    
    def isEmpty(self) -> bool:
        return all(map(lambda member: not isinstance(member, Participant), self.members))

class SpeedParty(Party):
    def __init__(self, number, rolesNum:dict[Role, int]):
        super().__init__(number)
        self.members:dict[Role,list[Participant|None]] = {role:[None] * num for role, num in rolesNum.items()}

    def getPartyMessage(self, guildRolesEmoji:dict[Role,RoleInfo]) -> str:
        msg = f'\| <:FullParty:1345733070065500281> 高速パーティ:{self.number} <:FullParty:1345733070065500281>'
        blockCount = 0
        for partyRole, members in self.members.items():
            if blockCount == 4: msg += '\n- - - - - - - - - - - - -'
            for member in members:
                msg += f'\n{guildRolesEmoji[partyRole].emoji} \| {member.mention}'
                for memberRole in member.roles:
                    msg += str(guildRolesEmoji[memberRole].emoji)
            blockCount += 1
        return msg

    def noneCount(self) -> int:
        num = 0
        for members in self.members.values():
            num += sum([None == member for member in members])
        return num

    def addMember(self, member:Participant, role:Role) -> bool:
        if None in self.members[role]:
            for membersIndex in range(len(self.members.values())):
                if self.members[role][membersIndex] == None:
                    self.members[role][membersIndex] = member
                    return True
        return False
    
    def removeMember(self, role:Role, member:Participant) -> bool:
        if member in self.members[role]:
            for memberIndex in range(len(self.members)):
                if member == self.members[role][memberIndex]:
                    self.members[role][memberIndex] = None
                    return True
        return False

class GuildInfo:
    def __init__(self, guild:Guild):
        self.guild:Guild = guild
        self.ROLE_EMOJI:RoleEmoji = RoleEmoji()
        self.ROLE_MESSAGE:Message = None
    def setPartyCategory(self, target:CategoryChannel|int):
        if isinstance(target, CategoryChannel):
            self.PARTY_CATEGORY:CategoryChannel = target # 募集チャンネル
        elif isinstance(target, int):
            self.PARTY_CATEGORY:CategoryChannel = client.get_channel(target)
    def setRoleChannel(self, target:TextChannel):
        if isinstance(target, TextChannel|int):
            self.ROLE_CH:TextChannel = client.get_channel(target) # コマンドチャンネル
        elif isinstance(target, int):
            self.ROLE_CH = self.guild.get_channel(target)
    async def setRoleEmoji(self, role:int|Role, emoji:int|Emoji):
        if isinstance(role, int): sendRole:Role = self.guild.get_role(role)
        elif isinstance(role, Role): sendRole:Role = role
        else: raise TypeError(role)
        if isinstance(emoji, int): sendEmoji:Emoji = await self.guild.fetch_emoji(emoji)
        elif isinstance(emoji, Emoji): sendEmoji:Emoji = emoji
        else: raise TypeError(emoji)
        self.ROLE_EMOJI.addRoleEmoji(sendRole, sendEmoji)
    async def sendCommandView(self):
        self.ROLE_MESSAGE = await self.ROLE_CH.send(content=f'## 追加・削除したいロールをタップ', view=RoleManageView())

class RoleEmoji:
    def __init__(self):
        self.roleEmoji:dict[Role,Emoji] = dict()
        self.emojiRole:dict[Emoji,Role] = dict()
    def addRoleEmoji(self, left:Role|Emoji, right:Emoji|Role):
        if isinstance(left, Role) and isinstance(right, Emoji):
            self.roleEmoji[left] = right
            self.emojiRole[right] = left
        elif isinstance(left, Emoji) and isinstance(right, Role):
            self.roleEmoji[right] = left
            self.emojiRole[left] = right
    def rmRoleEmoji(self, target:Emoji|Role):
        if isinstance(target, Emoji):
            del self.roleEmoji[self.emojiRole[target]]
            del self.emojiRole[target]
        elif isinstance(target, Role):
            del self.emojiRole[self.roleEmoji[target]]
            del self.roleEmoji[target]
    def roleEmoji(self, role:Role):
        return self.roleEmoji[role]
    def emojiRole(self, emoji:Emoji):
        return self.emojiRole[emoji]

partyEvents:set[PartyEvent] = set()
GUILD_INFO:dict[Guild,GuildInfo] = dict()


###########################################################################################################
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
        sendItems = getDirectoryItems(f'guilds/{ROBIN_GUILD.GUILD.id}/recruitingMessage')
        for index, sendItem in enumerate(sendItems):
            if index - len(sendItems) + 1 == 0:
                # 最後のメッセージ
                ROBIN_GUILD.recruitingMessage = await ROBIN_GUILD.PARTY_CH.send(
                    content=recruitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs
                    )
            else:
                await ROBIN_GUILD.PARTY_CH.send(
                    content=recruitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs)
        await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI) # 参加リアクション追加
        # await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.LIGHTPARTY_EMOJI) # ライトパーティリアクション追加
        # await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.FULLPARTY_EMOJI) # フルパーティリアクション追加
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Formation:%H時")))
        
        # try: # 250611 個別表示テスト
        #     await ROBIN_GUILD.DEV_CH.send('個別表示テスト\n表示テストのみで編成等に影響しません', view=RecluteView(timeout=1800, disable_on_timeout=False))
        # except Exception as e:
        #     printTraceback(e)
    
    elif now == ROBIN_GUILD.timeTable[0] - delta(minutes=15):
        await ROBIN_GUILD.PARTY_CH.send(f'パーティ編成まで残り5分 {ROBIN_GUILD.recruitingMessage.jump_url}')

    ######################################################
    # パーティ編成をアナウンス
    elif now == ROBIN_GUILD.timeTable[0] - delta(minutes=10):
        async with ROBIN_GUILD.PARTY_CH.typing():

            print(f'#================= {dt.now()} Formation =================#')

            ROBIN_GUILD.parties = list()
            # 値取得
            await ROBIN_GUILD.GUILD.chunk()
            ROBIN_GUILD.recruitingMessage = await ROBIN_GUILD.PARTY_CH.fetch_message(ROBIN_GUILD.recruitingMessage.id)
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
            for reaction in ROBIN_GUILD.recruitingMessage.reactions:
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

        # ROBIN_GUILD.recruitingMessage = None

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
        ROBIN_GUILD.recruitingMessage = None
        
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

