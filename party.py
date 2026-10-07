from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt, timedelta as delta
from typing import Any, Callable

import discord


@dataclass(frozen=True)
class PartyContext:
    """Party models' access to live application state and Discord UI factories."""

    get_guild: Callable[[], Any]
    approve_view: Callable[..., Any]
    dummy_approve_view: Callable[[], Any]

    @property
    def guild(self) -> Any:
        return self.get_guild()


class RoleInfo:
    def __init__(self, emoji:discord.Emoji, name:str, count:int):
        self.emoji:discord.Emoji = emoji
        self.name:str = name
        self.count:str = count

class PartyMember: # パーティメンバ親クラス
    def __init__(self, user:discord.Member|None, roles:set[discord.Role]):
        self.user:discord.Member|None = user
        self.roles:set[discord.Role] = roles

class Participant(PartyMember): # メンバと可能ロール
    def __init__(self, user:discord.Member, roles:set[discord.Role]):
        super().__init__(user, roles)
        self.mention:str = user.mention
        self.id = user.id
        self.display_name = user.display_name

class Guest(PartyMember): # Party class のためのダミー
    def __init__(self):
        super().__init__(user=None, roles=set())
        self.user = self
        self.roles = set()
        self.mention = 'ゲスト'
        self.id = -1
        self.display_name = 'ゲスト'

class Party: # パーティ情報 メッセージとパーティメンバ
    def __init__(self, number:int, *, context:PartyContext):
        self.context = context
        self.number:int = number
        self.message:discord.Message|None = None
        self.joins:dict[discord.Message, discord.User|discord.Member] = dict()
        self.thread:discord.Thread|None = None

class LightParty(Party):
    def __init__(self, number, players:list[Participant]=list(), free:bool=False, *, context:PartyContext):
        super().__init__(number, context=context)
        self.members:list[Participant|Guest] = players
        self.threadControlMessage:discord.Message|None = None
        self.alliance:LightParty|None = None
        self.free:bool = free

    async def addAllianceParty(self, party:LightParty):
        await self._addAlliance(party)
        await party._addAlliance(self)
        await party.message.edit(party.getPartyMessage(self.context.guild.ROLES))

    async def leaveAllianceParty(self):
        await self.alliance._removeAlliance(self)
        await self._removeAlliance(self.alliance)

    async def _addAlliance(self, party:LightParty):
        self.alliance = party
        await self.sendAllianceInfo()

    async def sendAllianceInfo(self):
        msg = f'@everyone\n## [パーティ:{self.alliance.number}]({self.alliance.message.jump_url}) と同盟'
        for member in self.alliance.members:
            msg += f'\n- {member.display_name}'
        if self.thread: await self.thread.send(msg)

    async def _removeAlliance(self, party:LightParty):
        self.alliance = None
        await self.thread.send(f'@everyone\n## パーティ:{party.number} の同盟を解除')
        await self.allianceCheck(self.context.guild.parties)
        await self.message.edit(self.getPartyMessage(self.context.guild.ROLES))

    async def allianceCheck(self, parties:list[LightParty]):
        if self.membersNum() == 4 and self.alliance is None:
            # ４人到達 アライアンス探索
            print(f'party:{self.number} alliance check')
            for party in parties:
                if party == self or not isinstance(party, LightParty): continue
                print(f'party:{party.number} -> {party.membersNum()}')
                if party.membersNum() == 4 and party.alliance is None:
                    print(f'Alliance:{self.number} <=> {party.number}')
                    await self.addAllianceParty(party)
                    break

    def membersNum(self) -> int:
        return len(self.members)

    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        msg = ''
        if self.free:
            msg += '## 途中抜けOK\n'
        msg += f'\| 【パーティ:{self.number}】'
        if self.alliance:
            msg += f'同盟 -> [パーティ{self.alliance.number}]({self.alliance.message.jump_url})'
        for player in self.members:
            msg += f'\n\| {player.mention}'
            for role in player.roles:
                msg += str(guildRolesEmoji[role].emoji)
        return msg

    async def joinRequest(self, member:discord.Member) -> bool:
        print(f'Join request Party:{self.number} {member}')
        if self.isEmpty(): # パーティが空だった
            print('パーティが空')
            participant = Participant(member, set(role for role in member.roles if role in self.context.guild.ROLES.keys()))
            await self.joinMember(participant)
            return True
        if member in map(lambda x:x.user, self.members): # 自パーティだった
            print('自パーティだった')
            await self.message.remove_reaction(self.context.guild.RECRUITING_EMOJI, member)
            msg = await self.context.guild.PARTY_CH.send(f'{member.mention}加入中のパーティには参加申請できません')
            await msg.delete(delay=5)
            return False
        print(f'Join request Done')
        requestMessage = await self.thread.send(f'@everyone {member.display_name} から加入申請', view=self.context.approve_view(duration=600))
        self.joins[requestMessage] = member

    async def removeJoinRequest(self, target:discord.Member | LightParty | None) -> bool:
        print(f'Remove join request target:{target}')
        if target == None: target = self
        if isinstance(target, discord.Member):
            for party in self.context.guild.parties:
                # LightPartyクラス以外をはじく
                if not isinstance(party, LightParty): continue
                for message, member in party.joins.items():
                    if member == target:
                        del party.joins[message]
                        await party.message.remove_reaction(self.context.guild.RECRUITING_EMOJI, target)
                        if self == party:
                            await message.edit(f'-# @everyone {member.display_name} からの加入申請', view=self.context.dummy_approve_view())
                        else:
                            # パーティ以外であれば申請取り下げ通知
                            await message.edit(f'@everyone {target.display_name} が参加取り下げ', view=self.context.dummy_approve_view())
                        break
            return True
        elif isinstance(target, LightParty):
            # ライトパーティのリクエスト全削除
            removeMembers = {member for member in target.joins.values()}
            target.joins.clear()
            for removeMember in removeMembers:
                await target.message.remove_reaction(self.context.guild.RECRUITING_EMOJI, removeMember)
            return True
        else: return False

    def addMember(self, participant:Participant|Guest) -> bool:
        self.members.append(participant)

    async def joinMember(self, participant:Participant|Guest) -> bool:
        if not isinstance(participant, Guest) and participant.user in map(lambda x:x.user, self.members): return False
        self.addMember(participant)
        if self.thread is None: return True
        print(f'PartyNumber:{self.number} JoinMember:{participant.display_name} PartyMemberNumber:{self.membersNum()} Alliance:{self.alliance}')
        if isinstance(participant, Participant): # メンバならスレッドに入れる
            await self.thread.add_user(participant.user)
            # ジョインリストから削除
            # for message, member in self.joins.items():
            #     if member == participant.user: del self.joins[message]
        await self.thread.send(f'{participant.display_name} が加入\n{self.getPartyMessage(self.context.guild.ROLES)}')
        await self.allianceCheck(self.context.guild.parties)
        if self.membersNum() >= 4: # 4人パーティ検知
            await self.removeJoinRequest(self) # 4人になったのでパーティに来ているリクエストを全削除
            await self.message.clear_reaction(self.context.guild.RECRUITING_EMOJI)
            for party in self.context.guild.parties:
                if not isinstance(party, LightParty): continue
                if party.membersNum() != 4: break
            else: await self.context.guild.PARTY_CH.send('／\nソロ周回スタートする方は\nPT新規生成ヨロシクですっ☆\n▶[新規パーティー生成](https://discord.com/channels/1246651972342386791/1379813214828630137/1380073785855705141)\n＼')
        await self.message.edit(self.getPartyMessage(self.context.guild.ROLES))
        return True

    async def removeMember(self, member:Participant|discord.Member|Guest) -> bool:
        if isinstance(member, Participant): member = member.user # ParticipantであればMemberクラスにする
        if member not in map(lambda x:x.user, self.members): return False # メンバにいなければFalseで終了
        for participant in self.members[-1::-1]: # メンバを下から捜査
            if participant.user == member:
                self.members.remove(participant)
                print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(self.context.guild.ROLES)}')
                if self.alliance and self.membersNum() < 4:
                    await self.leaveAllianceParty()
                await self.thread.starting_message.edit(self.getPartyMessage(self.context.guild.ROLES))
                if self.membersNum() < 4:
                    await self.message.add_reaction(self.context.guild.RECRUITING_EMOJI)
                return True
        return False

    async def removeGuest(self) -> bool:
        for member in self.members[-1::-1]:
            if isinstance(member, Guest):
                await self.removeMember(member)
                # self.members.remove(member)
                # print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                return True
        await self.thread.send('ゲストがいないためパーティに変更はありません')
        return False

    def isMember(self, user:discord.Member):
        return user in map(lambda x:x.user ,self.members)

    def isEmpty(self) -> bool:
        return all(map(lambda member: not isinstance(member, Participant), self.members))

class SpeedParty(Party):
    def __init__(self, number, rolesNum:dict[discord.Role, int], *, context:PartyContext):
        super().__init__(number, context=context)
        self.members:dict[discord.Role,list[Participant|None]] = {role:[None] * num for role, num in rolesNum.items()}

    def getPartyMessage(self, guildRolesEmoji:dict[discord.Role,RoleInfo]) -> str:
        if self.context.guild.FULLPARTY_EMOJI:
            msg = f'\| {self.context.guild.FULLPARTY_EMOJI} フルパーティ:{self.number} {self.context.guild.FULLPARTY_EMOJI}'
        else:
            msg = f'\| フルパーティ:{self.number}'
        blockCount = 0
        for partyRole, members in self.members.items():
            if blockCount == 4: msg += '\n-# = = = = = = = = = = = = = ='
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

    def isMember(self, user:discord.Member):
        return any(map(lambda members:user in map(lambda x:x.user, members), self.members.values()))

    def membersNum(self) -> int:
        result = 0
        for roleMembers in self.members.values():
            result += sum(map(lambda x:x is not None, roleMembers))
        return result

class Guild:
    def __init__(self, guild, client):
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
        self.RECRUIT_LOG_CH:discord.TextChannel = None # 募集ログチャンネル

        self.recruitingMessage:discord.Message = None # 募集メッセージ
        self.parties:list[SpeedParty|LightParty]|None = None # パーティ一覧
        self.timeTable:list[dt] = [] # 防衛軍タイムテーブル
        # self.timeTableThread:ThreadPoolExecutor = None # タイムテーブルスレッド

        # リアクション
        self.RECRUITING_EMOJI:discord.Emoji = None # 参加リアクション
        self.FULLPARTY_EMOJI:discord.Emoji = None
        self.LIGHTPARTY_EMOJI:discord.Emoji = None
        self.MEMBER_ROLE:discord.Role = None
        self.PRIORITY_ROLE:discord.Role = None # フルパーティ動的参加優先権ロール
        self.STATIC_PRIORITY_ROLE:discord.Role = None # 静的参加優先権ロール
        self.MASTER_ROLE:discord.Role = None # マスターロール
        self.LITE_PARTY_ROLE:discord.Role = None # ライトパーティロール

        self.ROLES:dict[discord.Role, RoleInfo] = None
        self.RECRUITING_MEMBER:list[discord.Member] = list() # 募集参加メンバ
        # self.ROLES:dict[discord.Role, ]

        # self.formation:Formation = None # パーティ編成クラス

        self.recruitingMessageItems:list[SendItem] = list() # 募集メッセージアイテムリスト
