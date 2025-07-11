from __future__ import annotations # 必ず先頭に

from discord import User, Member, Interaction, ButtonStyle, Thread
from discord.ui import View, Button, button
from datetime import datetime as dt
from time import perf_counter


class RoleManageView(View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
    async def roleManage(self, label:str, emoji:str, user:User|Member):
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

    @button(label='魔戦', emoji='<:magic_knight:1345708222962470952>', row=1)
    async def magicKnight(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='先導', emoji='<:boomerang:1345710507398529085>', row=1)
    async def boomerang(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='霧', emoji='<:buttarfly:1345708049838641234>', row=1)
    async def butterfly(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='札', emoji='<:card:1345708117618458695>', row=2)
    async def card(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='中継', emoji='<:relay:1345708094251859999>', row=2)
    async def way(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='回復', emoji='<:heal:1345708066741424138>', row=2)
    async def heal(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        await self.roleManage(button.label, button.emoji, interaction.user)
    @button(label='オールクリア', row=3)
    async def all_clear(self, button:Button, interaction:Interaction):
        await interaction.response.defer()
        for role in ROBIN_GUILD.ROLES.keys():
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
        rep = await interaction.channel.send(f'{interaction.user.mention}全ての高速可能ロールを削除')
        await rep.delete(delay=5)

class ApproveView(View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()
    @button(label='承認')
    async def approve(self, button:Button, interaction:Interaction):
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
                for p in ROBIN_GUILD.parties:
                    if isinstance(p, RandomParty) and p.isMember(joinMember):
                        p.removeMember(joinMember)
                for p in {p for p in ROBIN_GUILD.parties if joinMember in p.joins.values()}: # 参加リアクション全削除
                    await p.message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember)
                await party.joinMember(Participant(joinMember, set(role for role in joinMember.roles if role in ROBIN_GUILD.ROLES.keys())))
                await party.removeJoinRequest(joinMember)
                await thread.starting_message.remove_reaction(ROBIN_GUILD.RECLUTING_EMOJI, joinMember) # リアクション処理
            else:
                print('パーティメンバ以外による承認')
                await interaction.response.defer()
                msg = await interaction.channel.send(f'{interaction.user.mention}\nパーティメンバ以外は操作できません')
                await msg.delete(delay=5)
                return
        except Exception as e:
            printTraceback(e)

class DummyApproveView(ApproveView):
    def __init__(self):
        super().__init__()
    @button(label='承認', disabled=True)
    async def approve(self, button:Button, interaction:Interaction):
        pass

class PartyView(View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()

    @button(label='パーティを抜ける')
    async def leaveParty(self, button:Button, interaction:Interaction):
        print(f'{dt.now()} Leave party button is pressed from {interaction.user.display_name}')
        party:RandomParty = searchLightParty(interaction.message, ROBIN_GUILD.parties)
        await interaction.response.defer()
        if party == None:
            print(f'非パーティメンバによるアクション')
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)
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
            msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
            await msg.delete(delay=5)

    @button(label='ゲスト追加')
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
    
    # @button(label='ゲスト削除')
    # async def removeGuest(self, button:Button, interaction:Interaction):
    #     print(f'{dt.now()} Guest remove button from {interaction.user.display_name}')
    #     await interaction.response.defer()
    #     party = searchLightParty(interaction.channel.starting_message, ROBIN_GUILD.parties)
    #     if party == None:
    #         print(f'非パーティメンバによるアクション')
    #         msg = await interaction.channel.send(f'{interaction.user.mention}パーティメンバ以外は操作できません')
    #         await msg.delete(delay=5)
    #         return
    #     if interaction.user in map(lambda x:x.user, party.members): # パーティメンバである
    #         print('パーティメンバによるアクション')
    #         await party.removeGuest()

class FormationTopView(View):
    def __init__(self, *items, timeout = None, disable_on_timeout = True):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.startTime = perf_counter()
    @button(label='新規パーティ生成')
    async def newPartyButton(self, button:Button, interaction:Interaction):
        print(f'{dt.now()} New Party button from {interaction.user.display_name}')
        await interaction.response.defer()
        if all({interaction.user.id not in map(lambda party:map(lambda member:member.id, party.members), ROBIN_GUILD.parties)}):
            await createNewParty(interaction.user, free=True)
        else:
            alartMessage = await interaction.channel.send(f'{interaction.user.mention}パーティメンバは新規パーティを生成できません')
            await alartMessage.delete(delay=5)

async def createNewParty(user:Member, free:bool=False):
    if len(ROBIN_GUILD.parties) == 0: newPartyNum = 1
    else: newPartyNum = max(map(lambda x:x.number, ROBIN_GUILD.parties)) + 1
    roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
    newParty = RandomParty(newPartyNum, [Participant(user, roles)], free=free)
    newParty.message = await ROBIN_GUILD.PARTY_CH.send(newParty.getPartyMessage(ROBIN_GUILD.ROLES))
    newParty.thread = await newParty.message.create_thread(name=f'Party:{newParty.number}', auto_archive_duration=60)
    timeout = (ROBIN_GUILD.timeTable[0] - dt.now() + delta(minutes=60))
    newParty.threadControlMessage = await newParty.thread.send(view=PartyView(timeout=timeout.seconds))
    await newParty.message.add_reaction(ROBIN_GUILD.RECLUTING_EMOJI)
    ROBIN_GUILD.parties.append(newParty)

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
        buttonAllDisable(self.children)
        print(f'{dt.now()} 再起動スケジュールが設定されました')
        await interaction.response.edit_message(view=self)
        await interaction.respond('再起動スケジュールを設定しました')
    @button(label='すぐに再起動', style=ButtonStyle.red)
    async def justReboot(self, button:Button, interaction:Interaction):
        button.disabled = True
        buttonAllDisable(self.children)
        await interaction.response.edit_message(view=self)
        await f_reboot(interaction)

# class RecluteView(View):
#     def __init__(self, *items, timeout=None, disable_on_timeout=True, disable01=False, disable02=False):
#         super().__init__(*items, timeout=timeout, disable_on_timeout = disable_on_timeout)
#         self.disable01 = disable01
#         self.disable02 = disable02
#     @button(label='Button01', style=ButtonStyle.green)
#     async def reclute01(self, button:Button, interaction:Interaction):
#         await interaction.response.send_message(f'個別表示テスト {button.label} が押されました', ephemeral=True, view=RecluteView(disable01=True, timeout=180, disable_on_timeout=False))
#         print(f'{dt.now()} {interaction.user} {button.label}')
#     @button(label='Button01', style=ButtonStyle.red)
#     async def reclute02(self, button:Button, interaction:Interaction):
#         await interaction.response.send_message(f'個別表示テスト {button.label} が押されました', ephemeral=True, view=RecluteView(disable02=True, timeout=180, disable_on_timeout=False))
#         print(f'{dt.now()} {interaction.user} {button.label}')

def buttonAllDisable(children):
    for child in children:
        if isinstance(child, Button):
            child.disabled = True

def isPartyMember(user:Member) -> bool:
    for party in ROBIN_GUILD.parties:
        if any(map(lambda x:x.user==user, party.members)):
            return False
    return True
