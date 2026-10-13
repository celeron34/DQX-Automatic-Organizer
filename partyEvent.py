from __future__ import annotations # 必ず先頭に

from datetime import datetime as dt, timedelta as delta
from typing import Any
from discord import Guild, File, Member, Message, TextChannel, Role, Emoji, CategoryChannel, User, Thread
from views import FormationTopView
from formation import speedFormation, randomFormation
from random import shuffle
from main import client
from party import PartyContext, Participant, LightParty, SpeedParty, RoleInfo

class PartyEvent:
    def __init__(self,
                 context:PartyContext,
                 eventTitle:str,
                 speedPartyFormation:dict[Any,int],
                 eventTime:dt,
                 endTime:delta|dt,
                 announceTime:delta|dt,
                 formationTime:delta|dt|None=None,
                 remindTime:delta|dt|None=None,
                 threadAutoArchiveDuration:int=60,
                 speedAlliance:int=0,
                 randomAlliance:int=0,
                 randomPartyLimit:int=0,
                 speedPartySendImage:File|None=None,
                 endMessage:str=''):
        self.members:list[Member] = list()
        self.speedPartyFormation:dict[Any,int] = speedPartyFormation
        self.eventTime:dt = eventTime
        self.eventTitle:str = eventTitle
        self.speedAlliance:int = speedAlliance
        self.randomAlliance:int = randomAlliance
        self.randomPartyLimit:int = randomPartyLimit
        self.speedPartySendImage:File|None = speedPartySendImage
        self.endMessage:str = endMessage
        if isinstance(formationTime, dt): self.formationTime:delta = formationTime - eventTime
        else: self.formationTime:delta = formationTime
        if isinstance(endTime, dt): self.endTime:delta = endTime - eventTime
        else: self.endTime:delta = endTime
        if isinstance(announceTime, dt): self.announceTime:delta = announceTime - eventTime
        else: self.announceTime:delta = announceTime
        if isinstance(remindTime, dt): self.remindTime:delta = remindTime - eventTime
        else: self.remindTime:delta = remindTime
        self.context:PartyContext = context
        self.guild:Guild = context.guild.GUILD
        self.roles:dict[Role,RoleInfo] = context.guild.ROLES
        self.recruitingEmoji:Emoji = context.guild.RECRUITING_EMOJI
        self.parties:list[LightParty|SpeedParty] = context.event.parties or []
        context.event.parties = self.parties
        self.recruitingMessage:Message = None
        self.partyChannel:TextChannel = None
        self.threadAutoArchiveDuration:int = threadAutoArchiveDuration
        self.speedParties:list[SpeedParty] = list()
        self.randomParties:list[LightParty] = list()
        if self.remindTime == None: self.status:int = 1
        else: self.status:int = 0
    async def tick(self, nowTime:dt):
        if self.status == 0: # アナウンス時間
            if self.eventTime + self.announceTime > nowTime:
                self.status = 1
            else: return None
            #region View書いてない
            self.partyChannel = await GUILD_INFO[self.guild].PARTY_CATEGORY.create_text_channel(self.eventTime.strftime(f'{self.eventTitle}'))
            self.recruitingMessage = await self.partyChannel.send(self.eventTime.strftime(f'【{self.eventTitle}】\n参加希望はボタンを押してください'))
            #endregion

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
                    speedParty = SpeedParty(partyNumber, self.speedPartyFormation, context=self.context)
                    partyNumber += 1
                    for role, members in party.items():
                        for member in members:
                            speedParty.addMember(Participant(member, set(r for r in self.roles.keys() if r in member.roles)), role)
                    self.speedParties.append(speedParty)
                    self.parties.append(speedParty)
                # ランダムパーティ
                for party in randomPartiesMember:
                    partyParticipants = list()
                    for member in party:
                        partyParticipants.append(Participant(member, set(r for r in self.roles.keys() if r in member.roles)))
                    lightParty = LightParty(partyNumber, partyParticipants, context=self.context)
                    self.randomParties.append(lightParty)
                    self.parties.append(lightParty)
                
                viewTimeout = self.endTime if isinstance(self.endTime, delta) else self.eventTime - self.endTime
                await self.partyChannel.send(
                    self.eventTime.strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ\n原則、一番上がリーダーです' +
                                            '' if len(participants) != 8 else '\n参加者が8人ですので\n## 殲滅固定（カンダタを倒す）同盟です\n参加者は ___**サーバー3**___ へ') +
                                            f'\n-# 編成処理時間: {str((formationTimeEnd - formationTimeStart).total_seconds())}秒',
                                            view=FormationTopView(timeout=viewTimeout.seconds))
                for party in self.speedParties: # 高速パーティ通知
                    party.message = await self.partyChannel.send(party.getPartyMessage(self.roles))
                for party in self.randomParties: # 通常パーティ通知
                    party.message = await self.partyChannel.send(party.getPartyMessage(self.roles))
            for party in self.speedParties: # 高速パーティスレッド
                party.thread = await party.message.create_thread(name=f'SpeedParty:{party.number}', auto_archive_duration=self.threadAutoArchiveDuration)
            if self.speedParties: # 高速パーティがあるときは画像を出す
                self.partyChannel.send(file=self.speedPartySendImage)
            for party in self.randomParties: # 通常パーティスレッド
                party.thread = await party.message.create_thread(name=f'Party:{party.number}', auto_archive_duration=self.threadAutoArchiveDuration)
            
            # アライアンスチェック
            if self.randomAlliance:
                for party in self.randomParties:
                    if party.alliance is None:
                        await party.allianceCheck(self.parties)
                        party.message.edit(party.getPartyMessage(self.roles))

            #endregion
        
        elif self.status == 3 and self.eventTime + self.endTime > nowTime:
            if self.endTime + self.eventTime:
                self.status = 4

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

