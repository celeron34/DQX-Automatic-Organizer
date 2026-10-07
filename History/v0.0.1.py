import discord
from discord.ext import tasks
from dqx_ise import getTable
from datetime import datetime as dt, timedelta as delta
from AutoPartyFormation import AutoPartyFormation as Formation
from typing import Union

ROBIN_GUILD = None # ロビンギルド
class RoleEmoji:
    id:int = None
    emoji:discord.Emoji = None
    def __init__(self, id:int) -> None:
        self.id = id
    def set_emoji(self, emoji:discord.Emoji):
        self.emoji = emoji
roles = {'card':RoleEmoji(1247715201541865515),
           'monster':RoleEmoji(1247717814144471070),
           'connect':RoleEmoji(1247717037950763109),
           'magic':RoleEmoji(1247720076656906365),
           'boomerang':RoleEmoji(1247713828553228359),
           'butterfly':RoleEmoji(1247713053353443390)}

DEV_CH = None # デベロッパーチャンネル
PARTY_CH = None # 募集チャンネル
COMMAND_CH = None # コマンドチャンネル

reclutingMessage = None # 募集メッセージ
reclutingMessageTemplate = '【異星8人周回】\n8人パーティ参加希望ロールにリアクション願います' # 募集メッセージテンプレート
memberList:list[discord.Member] = [] # 募集メンバーリスト
timeTable:list[dt] = [] # 防衛軍タイムテーブル

formation:Formation = None

intents = discord.Intents.all() # インテント
intents.message_content = True 
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    global ROBIN_GUILD, DEV_CH, PARTY_CH, COMMAND_CH, timeTable, roles

    PARTY_CH = client.get_channel(1246662816673304587)
    DEV_CH = client.get_channel(1246662742987772067)
    COMMAND_CH = client.get_channel(1249294452149715016)
    ROBIN_GUILD = client.get_guild(1246651972342386791)

    for r in roles:
        roles[r].set_emoji(ROBIN_GUILD.get_emoji(roles[r].id))
    
    timeTable = getTimetable()
    for t in timeTable:
        print(t)

    await client.change_presence(activity=discord.CustomActivity(name=f'Next:{timeTable[0].strftime('%H')}時'))
    
    loop.start()

    print('Wakeup Bot')

@client.event
async def on_reaction_add(reaction:discord.Reaction, user:Union[discord.Member,discord.User]):
    global reclutingMessage, memberList, formation
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if reaction.message != reclutingMessage: return # 募集メッセージ以外を無視
    if user in memberList: return # メンバーリストに含まれていれば無視
    memberNum = formation.addMember(user, reaction.emoji) # 参加数変化なしは -1
    if memberNum >= 0: # 参加数が変わったから更新
        await reclutingMessage.edit(content=f'{reclutingMessageTemplate}\n参加数 {memberNum}人')

@client.event
async def on_reaction_remove(reaction:discord.Reaction, user:Union[discord.Member,discord.User]):
    global reclutingMessage, memberList, formation
    if user == client.user: return # 自信（ボット）のリアクションを無視
    if reaction.message != reclutingMessage: return # 募集メッセージ以外を無視
    memberNum = formation.remMember(user, reaction.emoji) # 参加数変化なしは -1
    if memberNum >= 0: # 参加数が変わったから更新
        await reclutingMessage.edit(content=f'{reclutingMessageTemplate}\n参加数 {memberNum}人')

@client.event
async def on_message(message:discord.Message):
    global COMMAND_CH, DEV_CH, timeTable
    if message.author == client.user: return # 自身であれば無視
    if message.channel == COMMAND_CH: # コマンドチャンネルの場合
        msg = message.content.split(' ')
        if msg[0] in 'ロール追加':
            ranks = [message.guild.get_role(1246662449042821150),
                     message.guild.get_role(1246662345879457893),
                     message.guild.get_role(1246662293501116446)]
            if msg[1] in '初級':
                await message.author.add_roles(ranks[0])
                await message.author.remove_roles(ranks[1])
                await message.author.remove_roles(ranks[2])
            elif msg[1] in '中級':
                await message.author.remove_roles(ranks[0])
                await message.author.add_roles(ranks[1])
                await message.author.remove_roles(ranks[2])
            elif msg[1] in '上級':
                await message.author.remove_roles(ranks[0])
                await message.author.remove_roles(ranks[1])
                await message.author.add_roles(ranks[2])
            else:
                error_msg = await message.reply('[エラー] 処理は行われませんでした')
                await error_msg.delete(delay=10)
                await message.delete(delay=10)
                return
            accept_msg = await message.reply('[成功] ロールを変更しました')
            await accept_msg.delete(delay=10)
            await message.delete(delay=10)
        else:
            error_msg = await message.reply('[エラー] 処理は行われませんでした')
            await error_msg.delete(delay=10)
            await message.delete(delay=10)
    
    elif message.channel == DEV_CH:
        msg = message.content.split(' ')
        if msg[0] == '$reclute':
            now = dt.now()
            timeTable = [dt(now.year, now.month, now.day, now.hour, now.minute, 0) + delta(minutes=11)] + timeTable
            accept_msg = await message.reply(f'{timeTable[0]}')
            await accept_msg.delete(delay=10)
            await message.delete(delay=10)

@tasks.loop(seconds=60)
async def loop():
    global PARTY_CH
    global timeTable
    global reclutingMessage, reclutingMessageTemplate
    global formation, roles
    
    now = dt.now()
    now = dt(now.year, now.month, now.day, now.hour, now.minute)

    if now == timeTable[0] - delta(minutes=10): # 本募集
        formation = Formation({
            roles['boomerang'].emoji: 1,
            roles['butterfly'].emoji: 1,
            roles['magic'].emoji: 1,
            roles['card'].emoji: 1,
            roles['connect'].emoji: 1,
            roles['monster'].emoji: 3
            })
        reclutingMessage = await PARTY_CH.send(f'{reclutingMessageTemplate}\n参加数 0人')
        await sendReactions(reclutingMessage, roles)
        await client.change_presence(activity=discord.CustomActivity(name=f'Formation:{timeTable[0].strftime('%H')}時'))
    elif now == timeTable[0] - delta(minutes=5):
        parties:list[dict[discord.Emoji, Union[discord.Member,discord.User]]] = formation.formation()
        del formation
        reclutingMessage = None
        await PARTY_CH.send('編成が完了しました')
        if len(parties) == 0: await PARTY_CH.send('今回はライトパーティを編成することができませんでした')
        else:
            for party in parties:
                msg = ''
                for role in party:
                    emo = f'<:custom_emoji_name:{party[role].id}>'
                    msg += f'{emo}:{party[role].name} '
                await PARTY_CH.send(msg)
#    elif now == timeTable[0] - delta(minutes=20): # 予備募集
#        msg = await PARTY_CH.send('【テスト】異星周回 予備募集\n参加希望ロールにリアクション願います\n※パーティ編成未実装')
#        await sendReactions(msg, REACTION_EMOJIS)
#        await client.change_presence(activity=discord.CustomActivity(name=f'Pre-recluting:{timeTable[0].strftime('%H')}時'))

    elif now == timeTable[0]:
        timeTable.pop(0)
        await client.change_presence(activity=discord.CustomActivity(name=f'Next:{timeTable[0].strftime('%H')}時'))

    if len(timeTable) == 0:
        timeTable += getTimetable()
        for t in timeTable:
            print(t)
        await client.change_presence(activity=discord.CustomActivity(name=f'Next:{timeTable[0].strftime('%H')}時'))
        

async def sendReactions(message:discord.Message, roles:dict[str,RoleEmoji]):
    for r in roles:
        await message.add_reaction(roles[r].emoji)

def getTimetable():
    timeTable = []
    now30 = dt.now() + delta(minutes=15)
    for t in getTable():
        if t > now30:
            timeTable.append(t)
    return timeTable

client.run('token')
