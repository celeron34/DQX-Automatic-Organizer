from discord import ApplicationContext, CustomActivity, File
from main import client
from datetime import datetime as dt, timedelta as delta
from subprocess import Popen
from Views import RebootView
from os import getcwd
from sys import argv, exc_info, executable, exit


##############################################################################################
#region スラッシュコマンド
# @client.slash_command(name='f-formation', description='タイムテーブルの割り込み')
# async def f_reclute(ctx:ApplicationContext):
#     if ctx.guild == None:
#         await ctx.respond('目的のサーバー内でコマンドしてください')
#         return
#     now = dt.now()
#     print(f'{now} slash command formation from {ctx.interaction.user}')
#     ROBIN_GUILD.timeTable = [dt(now.year, now.month, now.day, now.hour, now.minute, 0) + delta(minutes=31)] + ROBIN_GUILD.timeTable
#     await ROBIN_GUILD.PARTY_CH.send('# 【動作テスト】\n開発陣の都合によりパーティ募集の動作テストを行います\nテストの参加は任意です')
#     await ctx.respond('割り込みタイムテーブルを生成しました')

# @client.slash_command(name='f-timetable', description='タイムテーブル再取得')
# async def f_timetable(ctx:ApplicationContext):
#     print(f'{dt.now()} slash command timetable from {ctx.interaction.user}')
#     ROBIN_GUILD.timeTable = await getTimetable()
#     await client.change_presence(activity=CustomActivity( \
#         name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
#     send_message = 'タイムテーブルを更新しました'
#     for t in ROBIN_GUILD.timeTable:
#         send_message += t.strftime('\n%Y-%m-%d %H')
#     await ctx.respond(send_message)

@client.slash_command(name='f-restart', description='編成員Fを再起動')
async def f_restart(ctx:ApplicationContext):
    print(f'{dt.now()} slash command restart from {ctx.interaction.user}')
    # if len(ROBIN_GUILD.timeTable) == 0:
    #     await f_reboot(ctx)
    # if ROBIN_GUILD.timeTable[0] - delta(minutes=40) < dt.now():
    #     await ctx.respond('パーティ機能作動中または，まもなくパーティ編成を開始します\n再起動スケジュールを選択してください', view=RebootView(timeout=60, disable_on_timeout=False))
    # else:
    await f_reboot(ctx)

@client.slash_command(name='f-stop', description='再起動しても改善しない場合\n編成員Fを停止します\n開発陣へ連絡')
async def f_stop(ctx:ApplicationContext):
    print(f'{dt.now()} slash command restart from {ctx.interaction.user}')
    await ctx.respond('動作を停止します')
    await client.close()
    exit()

@client.slash_command(name='f-rand', description='編成員Fが整数ランダムを生成')
async def f_rand(ctx:ApplicationContext, min:int, max:int):
    await ctx.respond(f'{min}-{max} > {randint(min,max)}')

@client.slash_command(name='f-get-participant-data', description='これまでの参加データをcsv形式で返します')
async def f_get_participant_data(ctx:ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return
    with open(f'reactionLog/{ctx.interaction.guild.name}.csv', 'r') as f:
        csvFile = File(fp=f, filename=dt.now().strftime('participant_data_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`年-月-日-時,ユーザーID,希望`\n希望は "l":殲滅 "h":高速', file=csvFile)

@client.slash_command(name='f-get-participant-name', description='サーバーメンバのIDと現在の表示名の対応をcsv形式で返します')
async def f_get_participant_name(ctx:ApplicationContext):
    if ctx.guild == None:
        await ctx.respond('目的のサーバー内でコマンドしてください')
        return 
    filename = f'reactionLog/{ctx.interaction.guild.name}_nameList.csv'
    with open(filename, 'w') as f:
        async for member in ctx.interaction.guild.fetch_members():
            f.write(f'{member.id},{member.display_name}\n')
    with open(filename, 'r') as f:
        csvFile = File(fp=f, filename=dt.now().strftime('participant_name_%y%m%d-%H%M%S.csv'))
    await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ユーザーID,表示名`', file=csvFile)

# @client.slash_command(name='f-reset-role-channel', description='ロール設定チャンネルをリセット')
# async def f_reset_role_channel(ctx:ApplicationContext):
#     await command_message

async def f_reboot(ctx:ApplicationContext|None = None):
    if ctx: await ctx.respond('再起動します')
    Popen([executable, '-u'] + argv, cwd=getcwd())  # ボットを再起動
    await client.close()  # ボットを終了
    exit()

