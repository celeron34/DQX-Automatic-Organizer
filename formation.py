from __future__ import annotations # 再帰に必要 必ず先頭に

from typing import Any
from discord import Guild, Role, File, Emoji, Member, Interaction, TextChannel
from math import ceil
from classes import *
from Views import *

class Party: # パーティ情報 メッセージとパーティメンバ
    def __init__(self, number:int):
        self.number:int = number
        self.message:Message|None = None
        self.joins:dict[Message, User|Member] = dict()
        self.thread:Thread|None = None
        self.partyChannel:TextChannel|None = None

class LightParty(Party):
    def __init__(self, number, guildRoleEmoji:dict[Role,Emoji], players:list[Participant]=list(), free:bool=False):
        super().__init__(number)
        self.members:list[Participant|Guest] = players
        self.threadControlMessage:Message|None = None
        self.aliance:LightParty|None = None
        self.free:bool = free
        self.guildRoleEmoji:dict[Role, Emoji] = dict()
    
    async def addAlianceParty(self, party:LightParty):
        await self._addAlience(party)
        await party._addAlience(self)
        await party.message.edit(party.getPartyMessage())

    async def leaveAlianceParty(self):
        await self.aliance._removeAliance(self)
        await self._removeAliance(self.aliance)

    async def _addAlience(self, party:LightParty):
        self.aliance = party
        await self.sendAlianceInfo()
    
    async def sendAlianceInfo(self):
        msg = f'@here\n## [パーティ:{self.aliance.number}]({self.aliance.message.jump_url}) と同盟'
        for member in self.aliance.members:
            msg += f'\n- {member.display_name}'
        if self.thread: await self.thread.send(msg)

    async def _removeAliance(self, party:LightParty):
        self.aliance = None
        await self.thread.send(f'@here\n## パーティ:{party.number} の同盟を解除')
        await self.alianceCheck(parties)
        await self.message.edit(self.getPartyMessage(ROLES))

    async def alianceCheck(self, parties:list[LightParty]):
        if self.membersNum() == 4 and self.aliance is None:
            # ４人到達 アライアンス探索
            print(f'party:{self.number} aliance check')
            for party in parties:
                if party == self or not isinstance(party, LightParty): continue
                print(f'party:{party.number} -> {party.membersNum()}')
                if party.membersNum() == 4 and party.aliance is None:
                    print(f'Aliance:{self.number} <=> {party.number}')
                    await self.addAlianceParty(party)
                    break
    
    def membersNum(self) -> int:
        return len(self.members)

    def getPartyMessage(self) -> str:
        msg = ''
        if self.free:
            msg += '## 途中抜けOK\n'
        msg += f'【パーティ:{self.number}】'
        if self.aliance:
            msg += f'同盟 -> [パーティ{self.aliance.number}]({self.aliance.message.jump_url})'
        for player in self.members:
            msg += f'\n{player.mention}'
            for role in player.roles:
                msg += str(self.guildRoleEmoji[role])
        return msg
    
    async def joinRequest(self, member:Member) -> bool:
        print(f'Join request Party:{self.number} {member}')
        if self.isEmpty(): # パーティが空だった
            print('パーティが空')
            participant = Participant(member, set(role for role in member.roles if role in self.guildRoleEmoji.keys()))
            await self.joinMember(participant)
            return True
        if member in map(lambda x:x.user, self.members): # 自パーティだった
            print('自パーティだった')
            await self.message.remove_reaction(RECLUTING_EMOJI, member)
            msg = await self.partyChannel.send(f'{member.mention}加入中のパーティには参加申請できません')
            await msg.delete(delay=5)
            return False
        print(f'Join request Done')
        requestMessage = await self.thread.send(f'@here {member.display_name} から加入申請', view=ApproveView(duration=600))
        self.joins[requestMessage] = member

    async def removeJoinRequest(self, target:Member | LightParty | None) -> bool:
        print(f'Remove join request target:{target}')
        if target == None: target = self
        if isinstance(target, Member):
            for party in parties:
                # LightPartyクラス以外をはじく
                if not isinstance(party, LightParty): continue
                for message, member in party.joins.items():
                    if member == target:
                        del party.joins[message]
                        await party.message.remove_reaction(RECLUTING_EMOJI, target)
                        if self == party:
                            await message.edit(f'-# @here {member.display_name} からの加入申請', view=DummyApproveView())
                        else:
                            # パーティ以外であれば申請取り下げ通知
                            await message.edit(f'@here {target.display_name} が参加取り下げ', view=DummyApproveView())
                        break
            return True
        elif isinstance(target, LightParty):
            # ライトパーティのリクエスト全削除
            removeMembers = {member for member in target.joins.values()}
            target.joins.clear()
            for removeMember in removeMembers:
                await target.message.remove_reaction(RECLUTING_EMOJI, removeMember)
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
            # ジョインリストから削除
            # for message, member in self.joins.items():
            #     if member == participant.user: del self.joins[message]
        await self.thread.send(f'{participant.display_name} が加入\n{self.getPartyMessage(ROLES)}')
        await self.alianceCheck(parties)
        if self.membersNum() >= 4: # 4人パーティ検知
            await self.removeJoinRequest(self) # 4人になったのでパーティに来ているリクエストを全削除
            await self.message.clear_reaction(RECLUTING_EMOJI)
            for party in parties:
                if not isinstance(party, LightParty): continue
                if party.membersNum() != 4: break
            else: await PARTY_CH.send('／\nソロ周回スタートする方は\nPT新規生成ヨロシクですっ☆\n▶[新規パーティー生成](https://com/channels/1246651972342386791/1379813214828630137/1380073785855705141)\n＼')
        await self.message.edit(self.getPartyMessage(ROLES))
        return True
    
    async def removeMember(self, member:Participant|Member|Guest) -> bool:
        if isinstance(member, Participant): member = member.user # ParticipantであればMemberクラスにする
        if member not in map(lambda x:x.user, self.members): return False # メンバにいなければFalseで終了
        for participant in self.members[-1::-1]: # メンバを下から捜査
            if participant.user == member:
                self.members.remove(participant)
                print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROLES)}')
                if self.aliance and self.membersNum() < 4:
                    await self.leaveAlianceParty()
                await self.thread.starting_message.edit(self.getPartyMessage(ROLES))
                if self.membersNum() < 4:
                    await self.message.add_reaction(RECLUTING_EMOJI)
                return True
        return False

    async def removeGuest(self) -> bool:
        for member in self.members[-1::-1]:
            if isinstance(member, Guest):
                await self.removeMember(member)
                # self.members.remove(member)
                # print(f'PartyNum: {self.number} RemoveMember: {member.display_name}')
                # await self.thread.send(f'{member.display_name} が離脱\n{self.getPartyMessage(ROLES)}')
                # await self.thread.starting_message.edit(self.getPartyMessage(ROLES))
                return True
        await self.thread.send('ゲストがいないためパーティに変更はありません')
        return False
    
    def isMember(self, user:Member):
        return user in map(lambda x:x.user ,self.members)
    
    def isEmpty(self) -> bool:
        return all(map(lambda member: not isinstance(member, Participant), self.members))

class SpeedParty(Party):
    def __init__(self, number, formation:list[dict[Role, int]]):
        super().__init__(number)
        self.members:list[dict[Role,list[Participant|None]]] = [{role:[None] * num for role, num in party.items()} for party in formation]

    def getPartyMessage(self, guildRolesEmoji:dict[Role, Emoji]) -> str:
        msg = f'高速パーティ:{self.number}'
        for partyCount, party in enumerate(self.members):
            for partyRole, members in party.items():
                if partyCount > 0: msg += '\n-# = = = = = = = = = = = = = ='
                for member in members:
                    msg += f'\n{guildRolesEmoji[partyRole]} {member.mention}'
                    for memberRole in member.roles:
                        msg += str(guildRolesEmoji[memberRole])
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

    def isMember(self, user:Member):
        return any(map(lambda members:user in map(lambda x:x.user, members), self.members.values()))
    
    def membersNum(self) -> int:
        result = 0
        for roleMembers in self.members.values():
            result += sum(map(lambda x:x is not None, roleMembers))
        return result

def speedFormation(participants:list[Participant], formation:list[dict[Role, int]]) -> list[SpeedParty]:
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

def addHispeedParty(parties:list[SpeedParty], participant:Participant, roles:set[Role]=set()) -> bool:
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

async def checkParticipationRight(sender:Member|Interaction, channel:TextChannel=None) -> bool:
    '''参加権チェック'''
    global ROBIN_GUILD
    if isinstance(sender, Interaction):
        member = sender.user
    else:
        member = sender
    if ROBIN_GUILD.MEMBER_ROLE not in member.roles:
        msg = f'{member.mention} 参加権がありません'
        if isinstance(sender, Interaction):
            await sender.response.send_message(msg, ephemeral=True, delete_after=10)
        elif isinstance(sender, Member) and channel is not None:
            await channel.send(msg, delete_after=10)
        return False
    return True

async def autoJoinParticipant(user:Member):
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
