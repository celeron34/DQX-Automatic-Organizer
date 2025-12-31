from __future__ import annotations # 再帰に必要 必ず先頭に

from discord import User, Member, Interaction, ButtonStyle, Thread, Role, Emoji
from discord.ui import View, Button, button
from datetime import datetime as dt
from time import perf_counter
from classes import *
from general import *
from formation import *


class RoleManageView(View):
    def __init__(self, raidRoles:dict[Role, Emoji], *items, timeout = None, disable_on_timeout = True):
        self.roleEmoji = raidRoles
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        # 動的にボタンを生成してコールバックをクロージャで捕捉する
        for role, emoji in self.roleEmoji.items():
            btn = Button(label=role.name, emoji=emoji, style=ButtonStyle.blurple)
            # クロージャで role を固定する
            async def callback(interaction: Interaction, role=role, label=role.name):
                if role in [r for r in interaction.user.roles if r in self.roleEmoji.keys()]:
                    await interaction.user.remove_roles(role)
                    msg = f'[{self.roleEmoji[role]}{label}] を削除\n現在のロール: '
                else:
                    await interaction.user.add_roles(role)
                    msg = f'[{self.roleEmoji[role]}{label}] を追加\n現在のロール: '
                for role in interaction.user.roles:
                    if role in self.roleEmoji.keys(): msg += str(self.roleEmoji[role])
                await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
            btn.callback = callback
            self.add_item(btn)

    @button(label='オールクリア', style=ButtonStyle.red)
    async def all_clear(self, button:Button, interaction:Interaction):
        for role in self.roleEmoji.keys():
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
        await interaction.response.send_message(f'{interaction.user.mention}全ての高速可能ロールを削除', ephemeral=True, delete_after=5)

class ApproveView(View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True):
        self.startTime = perf_counter()
        self.duration = duration
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    async def on_timeout(self):
        party = searchLightParty(self.message.channel, ROBIN_GUILD.parties)
        if party is None: return
        requestMember = party.joins[self.message]
        await self.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, party.message)
        await ROBIN_GUILD.PARTY_CH.send(f'{requestMember.mention} パーティ{party.number}の参加申請がタイムアウト', delete_after=30)
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        party = searchLightParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party is None or not party.isMember(interaction.user): # パーティが存在しないかスレッドパーティのメンバでない
            print(f'{dt.now()} ApproveView: Out of party {interaction.user}')
            await interaction.response.send_message(f'パーティ外からの操作はできません', delete_after=5, ephemeral=True)
            return False
        return True

    @button(label='承認', style=ButtonStyle.blurple)
    async def approve(self, button:Button, interaction:Interaction):
        try:
            message = interaction.message
            user = interaction.user
            print(f'{dt.now()} Approve from {user} {type(user)}')
            party = searchLightParty(message.channel, ROBIN_GUILD.parties)
            if user.id in {participant.id for participant in party.members}: # パーティメンバである
                self.disable_on_timeout = False
                self.disable_all_items()
                await interaction.response.edit_message(view=self)
                print('パーティメンバによる承認')
                thread = message.channel
                joinMember = party.joins[message]
                print(f'JoinMember: {joinMember}')
                for p in ROBIN_GUILD.parties:
                    if isinstance(p, LightParty) and p.isMember(joinMember):
                        await p.removeMember(joinMember)
                        break
                await party.removeJoinRequest(joinMember) # メンバのリクエストを全パーティから削除
                await party.joinMember(Participant(joinMember, set(role for role in joinMember.roles if role in ROBIN_GUILD.ROLES.keys())))
                # await thread.starting_message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember) # リアクション処理
                await interaction.message.edit(view=DummyApproveView())
            else:
                print('パーティメンバ以外による承認')
                await interaction.response.send_message(f'{interaction.user.mention}\nパーティメンバ以外は操作できません', ephemeral=True, delete_after=5)
                return
        except Exception as e:
            printTraceback(e)

class DummyApproveView(View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    @button(label='承認', disabled=True, style=ButtonStyle.blurple)
    async def approve(self, button:Button, interaction:Interaction):
        pass

class PartyView(View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True):
        self.startTime = perf_counter()
        self.duration = duration
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)

    async def on_timeout(self):
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if ROBIN_GUILD.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} PartyView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        party = searchLightParty(interaction.message, ROBIN_GUILD.parties)
        if party is None or not party.isMember(interaction.user): # パーティが存在しないかスレッドパーティのメンバでない
            print(f'{dt.now()} Party: Out of party {interaction.user}')
            await interaction.response.send_message(f'パーティ外からの操作はできません', delete_after=5, ephemeral=True)
            return False
        return True
        

    @button(label='パーティを抜ける', style=ButtonStyle.gray, row=2)
    async def leaveParty(self, button:Button, interaction:Interaction):
        print(f'{dt.now()} Leave party button is pressed from {interaction.user.display_name}')
        party:LightParty = searchLightParty(interaction.message, ROBIN_GUILD.parties)
        await interaction.response.defer()
        if party == None:
            print(f'非パーティメンバによるアクション')
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', delete_after=5, ephemeral=True)
            return
        if interaction.user in map(lambda x:x.user, party.members):
            # ユーザーがパーティメンバー
            thread:Thread = interaction.message.channel
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
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', delete_after=5, ephemeral=True)

    @button(label='ゲスト追加', style=ButtonStyle.green, row=1)
    async def addGuest(self, button:Button, interaction:Interaction):
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
    
    @button(label='ゲスト削除', style=ButtonStyle.red, row=1)
    async def removeGuest(self, button:Button, interaction:Interaction):
        print(f'{dt.now()} Guest remove button from {interaction.user.display_name}')
        party = searchLightParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', ephemeral=True, delete_after=5)
            return
        if interaction.user in map(lambda x:x.user, party.members): # パーティメンバである
            print('パーティメンバによるアクション')
            await interaction.response.defer()
            await party.removeGuest()

class FormationTopView(View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True):
        self.startTime = perf_counter()
        self.duration = duration
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)

    async def on_timeout(self):
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if ROBIN_GUILD.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} FormationTopView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        return True

    @button(label='新規パーティ生成', style=ButtonStyle.blurple)
    async def newPartyButton(self, button:Button, interaction:Interaction):
        print(f'{dt.now()} New Party button from {interaction.user.display_name}')
        if not await checkParticipationRight(interaction.user):
            return
        user = interaction.user
        # SpeedParty に所属しているなら新規作成を禁止
        if ROBIN_GUILD.parties and any(p.isMember(user) for p in ROBIN_GUILD.parties if isinstance(p, SpeedParty)):
            await interaction.response.send_message(f'{user.mention}\n高速パーティメンバは新規パーティを生成できません', delete_after=5, ephemeral=True)
            return

        # LightParty に所属しているなら既存パーティから抜ける（通常は1つだけ）
        if ROBIN_GUILD.parties:
            for party in list(ROBIN_GUILD.parties):
                if isinstance(party, LightParty) and party.isMember(user):
                    await party.removeMember(user)
                    break

        await createNewParty(user, free=True)

async def createNewParty(user:Member, free:bool=False):
    if len(ROBIN_GUILD.parties) == 0: newPartyNum = 1
    else: newPartyNum = max(map(lambda x:x.number, ROBIN_GUILD.parties)) + 1
    roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
    newParty = LightParty(newPartyNum, [Participant(user, roles)], free=free)
    newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    newParty.threadControlMessage = await newParty.thread.send(view=PartyView(duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))
    await newParty.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
    ROBIN_GUILD.parties.append(newParty)

class RecruitView(View):
    def __init__(self, duration:float=None, members:set[Member]=set(), *items, timeout = None, disable_on_timeout = True):
        self.startTime = perf_counter()
        self.duration = duration
        # self.msg = msg
        self.members = members
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)

    async def on_timeout(self):
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if ROBIN_GUILD.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} RecruitView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        return True

    @button(label='参加 [beta]', style=ButtonStyle.green)
    async def joinReclute(self, button:Button, interaction:Interaction):
        now = dt.now()
        # 未参加であれば追加
        if interaction.user in self.members:
            # 既に参加している
            print(f'{now} Recruit button from {interaction.user.display_name} but already joined')
            await interaction.response.send_message(f'参加済です',
                ephemeral=True, delete_after=(ROBIN_GUILD.timeTable[0] - now).total_seconds() - 600.)
        else:
            print(f'{now} Recruit button from {interaction.user.display_name}')
            ROBIN_GUILD.RECLUTING_MEMBER.add(interaction.user)
            await interaction.response.send_message(
                f'参加を受け付けました\nテスト中ですので、編成に失敗する恐れがあります。\n念のために{ROBIN_GUILD.RECLUTING_EMOJI}リアクションもしておくと確実です。',
                ephemeral=True, delete_after=(ROBIN_GUILD.timeTable[0] - now).total_seconds() - 600.)
            sendMessage = now.strftime('[%y-%m-%d %H:%M]') + f' :green_square: {interaction.user.display_name}\n現在の参加者:'
            await interaction.message.edit(recluitMessageReplace(self.msg, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECLUTING_MEMBER)))
            for member in ROBIN_GUILD.RECLUTING_MEMBER:
                sendMessage += f' {member.display_name}'
            await ROBIN_GUILD.RECLUIT_LOG_CH.send(sendMessage)

    @button(label='辞退 [beta]', style=ButtonStyle.red)
    async def leaveReclute(self, button:Button, interaction:Interaction):
        # 既に参加しているなら削除
        now = dt.now()
        if interaction.user in ROBIN_GUILD.RECLUTING_MEMBER:
            print(f'{now} Reclute leave button from {interaction.user.display_name}')
            ROBIN_GUILD.RECLUTING_MEMBER.remove(interaction.user)
            await interaction.response.send_message('辞退を受け付けました', ephemeral=True, delete_after=(ROBIN_GUILD.timeTable[0] - now).total_seconds() - 600.)
            await interaction.message.edit(recluitMessageReplace(self.msg, ROBIN_GUILD.timeTable[0], len(ROBIN_GUILD.RECLUTING_MEMBER)))
            await interaction.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, interaction.user)
            sendMessage = now.strftime('[%y-%m-%d %H:%M]') + f' :red_square: {interaction.user.display_name}\n現在の参加者:'
            # 更新メッセージ
            for member in ROBIN_GUILD.RECLUTING_MEMBER:
                sendMessage += f' {member.display_name}'
            await ROBIN_GUILD.RECLUIT_LOG_CH.send(sendMessage)

        else:
            print(f'{now} Reclute leave button from {interaction.user.display_name} but not joined')
            await interaction.response.send_message('辞退済です', ephemeral=True, delete_after=(ROBIN_GUILD.timeTable[0] - now).total_seconds() - 600.)

class RebootView(View):
    def __init__(self, *items, timeout=None, disable_on_timeout=True):
        super().__init__(*items, timeout=timeout, disable_on_timeout = disable_on_timeout)
    @button(label='次の周回終了で再起動', style=ButtonStyle.green)
    async def scaduleReboot(self, button:Button, interaction:Interaction):
        global rebootScadule
        try:
            rebootScadule = interaction.channel
        except Exception as e:
            printTraceback(e)
            rebootScadule = True
        self.disable_all_items()
        print(f'{dt.now()} 再起動スケジュールが設定されました')
        await interaction.response.edit_message(view=self)
        await interaction.respond('再起動スケジュールを設定しました')
    @button(label='すぐに再起動', style=ButtonStyle.red)
    async def justReboot(self, button:Button, interaction:Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        await f_reboot(interaction)
    @button(label='安定版再起動', style=ButtonStyle.red)
    async def stableReboot(self, button:Button, interaction:Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        await f_stableReboot()
