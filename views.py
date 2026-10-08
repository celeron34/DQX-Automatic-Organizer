from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
from time import perf_counter
from typing import Any, Awaitable, Callable

import discord


@dataclass(frozen=True)
class ViewContext:
    """UIが利用する状態取得・モデル・処理を起動側から受け取る。

    guild自体ではなく取得関数を渡し、ギルド再取得後も既存Viewが
    最新の状態を参照できるようにする。
    """

    get_guild: Callable[[], Any]
    get_event: Callable[[], Any]
    search_party: Callable[..., Any]
    light_party_type: type
    speed_party_type: type
    make_participant: Callable[..., Any]
    make_guest: Callable[[], Any]
    check_role_right: Callable[..., Awaitable[bool]]
    create_party: Callable[..., Awaitable[None]]
    format_recruit_message: Callable[[str, dt, int], str]
    report_error: Callable[[Exception], None]
    reboot: Callable[..., Awaitable[None]]
    stable_reboot: Callable[..., Awaitable[None]]
    schedule_reboot: Callable[[discord.TextChannel | bool], None]

    @property
    def guild(self) -> Any:
        return self.get_guild()

    @property
    def event(self) -> Any:
        return self.get_event()


class RoleManageView(discord.ui.View):
    def __init__(self, raidRoles, *items, timeout = None, disable_on_timeout = True):
        self.roleEmoji = {re['role']:re['emoji'] for re in raidRoles.values()}
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        # 動的にボタンを生成してコールバックをクロージャで捕捉する
        for roleName, roleInfo in raidRoles.items():
            btn = discord.ui.Button(label=roleName, emoji=roleInfo['emoji'], style=discord.ButtonStyle.blurple)
            # クロージャで role を固定する
            async def callback(interaction: discord.Interaction, role=roleInfo['role'], label=roleName):
                if role in [role for role in interaction.user.roles if role in self.roleEmoji.keys()]:
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

    @discord.ui.button(label='オールクリア', style=discord.ButtonStyle.red)
    async def all_clear(self, button:discord.ui.Button, interaction:discord.Interaction):
        for role in self.roleEmoji.keys():
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
        await interaction.response.send_message(f'{interaction.user.mention}全ての可能ロールを削除', ephemeral=True, delete_after=5)


class ApproveView(discord.ui.View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True, context:ViewContext):
        self.context = context
        self.startTime = perf_counter()
        self.duration = duration
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    async def on_timeout(self):
        party = self.context.search_party(self.message.channel, self.context.event.parties)
        if party is None: return
        requestMember = party.joins[self.message]
        await self.message.remove_reaction(self.context.guild.RECRUITING_EMOJI, party.message)
        await self.context.guild.PARTY_CH.send(f'{requestMember.mention} パーティ{party.number}の参加申請がタイムアウト', delete_after=30)
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        party = self.context.search_party(interaction.channel.starting_message, self.context.event.parties)
        if party is None or not party.isMember(interaction.user): # パーティが存在しないかスレッドパーティのメンバでない
            print(f'{dt.now()} ApproveView: Out of party {interaction.user}')
            await interaction.response.send_message(f'パーティ外からの操作はできません', delete_after=5, ephemeral=True)
            return False
        return True

    @discord.ui.button(label='承認', style=discord.ButtonStyle.blurple)
    async def approve(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            message = interaction.message
            user = interaction.user
            print(f'{dt.now()} Approve from {user} {type(user)}')
            party = self.context.search_party(message.channel, self.context.event.parties)
            if user.id in {participant.id for participant in party.members}: # パーティメンバである
                self.disable_on_timeout = False
                self.disable_all_items()
                await interaction.response.edit_message(view=self)
                print('パーティメンバによる承認')
                thread = message.channel
                joinMember = party.joins[message]
                print(f'JoinMember: {joinMember}')
                for p in self.context.event.parties:
                    if isinstance(p, self.context.light_party_type) and p.isMember(joinMember):
                        await p.removeMember(joinMember)
                        break
                await party.removeJoinRequest(joinMember) # メンバのリクエストを全パーティから削除
                await party.joinMember(self.context.make_participant(joinMember, set(role for role in joinMember.roles if role in self.context.guild.ROLES.keys())))
                await interaction.message.edit(view=DummyApproveView())
            else:
                print('パーティメンバ以外による承認')
                await interaction.response.send_message(f'{interaction.user.mention}\nパーティメンバ以外は操作できません', ephemeral=True, delete_after=5)
                return
        except Exception as e:
            self.context.report_error(e)


class DummyApproveView(discord.ui.View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    @discord.ui.button(label='承認', disabled=True, style=discord.ButtonStyle.blurple)
    async def approve(self, button:discord.ui.Button, interaction:discord.Interaction):
        pass


class PartyView(discord.ui.View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True, context:ViewContext):
        self.context = context
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if self.context.guild.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} PartyView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        party = self.context.search_party(interaction.message, self.context.event.parties)
        if party is None or not party.isMember(interaction.user): # パーティが存在しないかスレッドパーティのメンバでない
            print(f'{dt.now()} Party: Out of party {interaction.user}')
            await interaction.response.send_message(f'パーティ外からの操作はできません', delete_after=5, ephemeral=True)
            return False
        return True


    @discord.ui.button(label='パーティを抜ける', style=discord.ButtonStyle.gray, row=2)
    async def leaveParty(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Leave party button is pressed from {interaction.user.display_name}')
        party = self.context.search_party(interaction.message, self.context.event.parties)
        await interaction.response.defer()
        if party == None:
            print(f'非パーティメンバによるアクション')
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', delete_after=5, ephemeral=True)
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
                    self.context.event.parties.remove(party)
                    await party.message.delete()
            except Exception as e:
                self.context.report_error(e)

        else: # ユーザーが別パーティメンバ
            print('別パーティによるアクション')
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', delete_after=5, ephemeral=True)

    @discord.ui.button(label='ゲスト追加', style=discord.ButtonStyle.green, row=1)
    async def addGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest add button is pressed from {interaction.user.display_name}')
        await interaction.response.defer()
        party = self.context.search_party(interaction.channel.starting_message, self.context.event.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
        elif interaction.user in map(lambda x:x.user, party.members):
            print(f'パーティメンバによるアクション')
            await party.joinMember(self.context.make_guest())

    @discord.ui.button(label='ゲスト削除', style=discord.ButtonStyle.red, row=1)
    async def removeGuest(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} Guest remove button from {interaction.user.display_name}')
        party = self.context.search_party(interaction.channel.starting_message, self.context.event.parties)
        if party == None:
            print(f'非パーティメンバによるアクション')
            await interaction.response.send_message(f'{interaction.user.mention}パーティメンバ以外は操作できません', ephemeral=True, delete_after=5)
            return
        if interaction.user in map(lambda x:x.user, party.members): # パーティメンバである
            print('パーティメンバによるアクション')
            await interaction.response.defer()
            await party.removeGuest()


class FormationTopView(discord.ui.View):
    def __init__(self, *items, duration:float=None, timeout = None, disable_on_timeout = True, context:ViewContext):
        self.context = context
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if self.context.guild.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} FormationTopView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        return True

    @discord.ui.button(label='新規パーティ生成', style=discord.ButtonStyle.blurple)
    async def newPartyButton(self, button:discord.ui.Button, interaction:discord.Interaction):
        print(f'{dt.now()} New Party button from {interaction.user.display_name}')
        user = interaction.user
        if not (await self.context.check_role_right(user, None, {self.context.guild.MEMBER_ROLE}, '参加権がありません') and
            await self.context.check_role_right(user, None, set(self.context.guild.ROLES.keys()), 'ロールが設定されていません')):
            return
        # SpeedParty に所属しているなら新規作成を禁止
        if self.context.event.parties and any(p.isMember(user) for p in self.context.event.parties if isinstance(p, self.context.speed_party_type)):
            await interaction.response.send_message(f'{user.mention}\nフルパーティメンバは新規パーティを生成できません', delete_after=5, ephemeral=True)
            return

        # LightParty に所属しているなら既存パーティから抜ける（通常は1つだけ）
        if self.context.event.parties:
            for party in list(self.context.event.parties):
                if isinstance(party, self.context.light_party_type) and party.isMember(user):
                    await party.removeMember(user)
                    break

        await self.context.create_party(user, free=True, event=self.context.event)


class RecruitView(discord.ui.View):
    def __init__(self, msg:str, duration:float=None, *items, timeout = None, disable_on_timeout = True, context:ViewContext):
        self.context = context
        self.startTime = perf_counter()
        self.duration = duration
        self.msg = msg
        # durationが指定されていればtimeoutを有効化
        if self.duration is not None:
            timeout = self.duration
            disable_on_timeout = False
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)

    async def on_timeout(self):
        self.disable_all_items()
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.timeout is not None and self.duration is not None:
            self.timeout = self.startTime + self.duration - perf_counter()
            await self.message.edit(view=self)
        if self.context.guild.MEMBER_ROLE not in interaction.user.roles:
            print(f'{dt.now()} RecruitView: {interaction.user} have not Member')
            await interaction.response.send_message(f'参加権がありません', delete_after=5, ephemeral=True)
            return False
        return True

    @discord.ui.button(label='参加 [beta]', style=discord.ButtonStyle.green)
    async def joinRecruit(self, button:discord.ui.Button, interaction:discord.Interaction):
        now = dt.now()
        # 未参加であれば追加
        if interaction.user in self.context.event.recruiting_members:
            # 既に参加している
            print(f'{now} Recruit button from {interaction.user.display_name} but already joined')
            await interaction.response.send_message(
                f'参加済です\nテスト中ですので、編成に失敗する恐れがあります。\n念のために{self.context.guild.RECRUITING_EMOJI}リアクションもしておくと確実です。',
                ephemeral=True, delete_after=(self.context.event.starts_at - now).total_seconds() - 600.)
        else:
            print(f'{now} Recruit button from {interaction.user.display_name}')
            self.context.event.recruiting_members.append(interaction.user)
            await interaction.response.send_message(
                f'参加を受け付けました\nテスト中ですので、編成に失敗する恐れがあります。\n念のために{self.context.guild.RECRUITING_EMOJI}リアクションもしておくと確実です。',
                ephemeral=True, delete_after=(self.context.event.starts_at - now).total_seconds() - 600.)
            sendMessage = now.strftime('[%y-%m-%d %H:%M]') + f' :green_square: {interaction.user.display_name}\n現在の参加者:'
            await interaction.message.edit(self.context.format_recruit_message(self.msg, self.context.event.starts_at, len(self.context.event.recruiting_members)))
            for member in self.context.event.recruiting_members:
                sendMessage += f' {member.display_name}'
            await self.context.guild.RECRUIT_LOG_CH.send(sendMessage)

    @discord.ui.button(label='辞退 [beta]', style=discord.ButtonStyle.red)
    async def leaveRecruit(self, button:discord.ui.Button, interaction:discord.Interaction):
        # 既に参加しているなら削除
        now = dt.now()
        if interaction.user in self.context.event.recruiting_members:
            print(f'{now} Recruit leave button from {interaction.user.display_name}')
            self.context.event.recruiting_members.remove(interaction.user)
            await interaction.response.send_message('辞退を受け付けました', ephemeral=True, delete_after=(self.context.event.starts_at - now).total_seconds() - 600.)
            await interaction.message.edit(self.context.format_recruit_message(self.msg, self.context.event.starts_at, len(self.context.event.recruiting_members)))
            await interaction.message.remove_reaction(self.context.guild.RECRUITING_EMOJI, interaction.user)
            sendMessage = now.strftime('[%y-%m-%d %H:%M]') + f' :red_square: {interaction.user.display_name}\n現在の参加者:'
            # 更新メッセージ
            for member in self.context.event.recruiting_members:
                sendMessage += f' {member.display_name}'
            await self.context.guild.RECRUIT_LOG_CH.send(sendMessage)

        else:
            print(f'{now} Recruit leave button from {interaction.user.display_name} but not joined')
            await interaction.response.send_message('辞退済です', ephemeral=True, delete_after=(self.context.event.starts_at - now).total_seconds() - 600.)


class RebootView(discord.ui.View):
    def __init__(self, *items, timeout=None, disable_on_timeout=True, context:ViewContext):
        self.context = context
        super().__init__(*items, timeout=timeout, disable_on_timeout = disable_on_timeout)
    @discord.ui.button(label='次の周回終了で再起動', style=discord.ButtonStyle.green)
    async def scheduleReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        try:
            self.context.schedule_reboot(interaction.channel)
        except Exception as e:
            self.context.report_error(e)
            self.context.schedule_reboot(True)
        self.disable_all_items()
        print(f'{dt.now()} 再起動スケジュールが設定されました')
        await interaction.response.edit_message(view=self)
        await interaction.respond('再起動スケジュールを設定しました')
    @discord.ui.button(label='すぐに再起動', style=discord.ButtonStyle.red)
    async def justReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        await self.context.reboot(interaction)
    @discord.ui.button(label='安定版再起動', style=discord.ButtonStyle.red)
    async def stableReboot(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        await self.context.stable_reboot()
