from __future__ import annotations # 必ず先頭に

from datetime import datetime as dt, timedelta as delta
from typing import Any
from discord import Guild, File, Member, Message, TextChannel, Role, Emoji, CategoryChannel, User, Thread
from Views import ApproveView, FormationTopView
from formation import speedFormation, randomFormation
from random import shuffle
from main import client, CONFIG, config, GUILD_INFO

class PartyEvent:
    def __init__(self,
                 guild:Guild,
                 eventTitle:str,
                 speedPartyFormation:dict[Any,int],
                 eventTime:dt,
                 endTime:delta|dt,
                 announseTime:delta|dt,
                 formationTime:delta|dt|None=None,
                 remindTime:delta|dt|None=None,
                 threadAutoArciveDuration:int=60,
                 speedAliance:int=0,
                 randomAliance:int=0,
                 randomPartyLimit:int=0,
                 speedPartySendImage:File|None=None,
                 endMessage:str=''):
        self.members:list[Member] = list()
        self.speedPartyFormation:dict[Any,int] = speedPartyFormation
        self.eventTime:dt = eventTime
        self.eventTitle:str = eventTitle
        self.speedAliance:int = speedAliance
        self.randomAliance:int = randomAliance
        self.randomPartyLimit:int = randomPartyLimit
        self.speedPartySendImage:File|None = speedPartySendImage
        self.endMessage:str = endMessage
        if isinstance(formationTime, dt): self.formationTime:delta = formationTime - eventTime
        else: self.formationTime:delta = formationTime
        if isinstance(endTime, dt): self.endTime:delta = endTime - eventTime
        else: self.endTime:delta = endTime
        if isinstance(announseTime, dt): self.announseTime:delta = announseTime - eventTime
        else: self.announseTime:delta = announseTime
        if isinstance(remindTime, dt): self.remindTime:delta = remindTime - eventTime
        else: self.remindTime:delta = remindTime
        self.guild:GuildInfo = guild
        self.reclutingMessage:Message = None
        self.partyChannel:TextChannel = None
        self.threadAutoArciveDuration:int = threadAutoArciveDuration
        self.speedParties:list[SpeedParty] = list()
        self.randomParties:list[RandomParty] = list()
        if self.remindTime == None: self.status:int = 1
        else: self.status:int = 0
    async def tick(self, nowTime:dt):
        if self.status == 0: # アナウンス時間
            if self.eventTime + self.announseTime > nowTime:
                self.status = 1
            else: return None
            #region View書いてない
            self.partyChannel = await GUILD_INFO[self.guild].PARTY_CATEGORY.create_text_channel(self.eventTime.strftime(f'{self.eventTitle}'))
            self.reclutingMessage = await self.partyChannel.send(self.eventTime.strftime(f'【{self.eventTitle}】\n参加希望はボタンを押してください'))
            #endregion

        elif self.status == 1: # リマインド時間
            if self.eventTime + self.remindTime > nowTime:
                self.status = 2
            if self.status != 2: return None
            self.reclutingMessage = await self.partyChannel.send(self.eventTime.strftime(f'編成まであと%M分\n{self.reclutingMessage.jump_url}'))
        
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

