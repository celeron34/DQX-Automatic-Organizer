"""Slash command registration kept separate from bot startup and event handling."""

from __future__ import annotations

from datetime import datetime
from random import randint
from typing import Callable

import discord


def register_slash_commands(
    client: discord.Bot,
    *,
    get_guild_state: Callable[[], object],
    reboot: Callable[..., object],
    fetch: Callable[..., object],
    reboot_view: Callable[[], discord.ui.View],
) -> None:
    """Register the existing operator commands against injected bot services."""

    @client.slash_command(name='f-formation', description='タイムテーブルの割り込み')
    async def f_recruit(ctx: discord.ApplicationContext):
        guild = get_guild_state()
        if ctx.guild is None:
            await ctx.respond('目的のサーバー内でコマンドしてください')
            return
        now = datetime.now()
        print(f'{now} slash command formation from {ctx.interaction.user}')
        from datetime import timedelta
        guild.timeTable = [datetime(now.year, now.month, now.day, now.hour, now.minute, 0) + timedelta(minutes=31)] + guild.timeTable
        guild.sync_events(guild.timeTable)
        await guild.PARTY_CH.send('# 【動作テスト】\n開発陣の都合によりパーティ募集の動作テストを行います\nテストの参加は任意です')
        await ctx.respond('割り込みタイムテーブルを生成しました')

    @client.slash_command(name='f-restart', description='編成員Fを再起動')
    async def f_restart(ctx: discord.ApplicationContext):
        guild = get_guild_state()
        from datetime import timedelta
        print(f'{datetime.now()} slash command restart from {ctx.interaction.user}')
        if len(guild.timeTable) == 0:
            await reboot(ctx)
        if guild.timeTable[0] - timedelta(minutes=40) < datetime.now():
            await ctx.respond('パーティ機能作動中または，まもなくパーティ編成を開始します\n再起動スケジュールを選択してください', view=reboot_view())
        else:
            await reboot(ctx)

    @client.slash_command(name='f-stop', description='再起動しても改善しない場合\n編成員Fを停止します\n開発陣へ連絡')
    async def f_stop(ctx: discord.ApplicationContext):
        import sys
        print(f'{datetime.now()} slash command restart from {ctx.interaction.user}')
        await ctx.respond('動作を停止します')
        await client.close()
        sys.exit()

    @client.slash_command(name='f-rand', description='編成員Fが整数ランダムを生成')
    async def f_rand(ctx: discord.ApplicationContext, min: int, max: int):
        await ctx.respond(f'{int(min)}-{int(max)} > {randint(int(min), int(max))}')

    @client.slash_command(name='f-get-participant-data', description='これまでの参加データをcsv形式で返します')
    async def f_get_participant_data(ctx: discord.ApplicationContext):
        if ctx.guild is None:
            await ctx.respond('目的のサーバー内でコマンドしてください')
            return
        with open(f'reactionLog/{ctx.interaction.guild.name}.csv', 'r') as f:
            csv_file = discord.File(fp=f, filename=datetime.now().strftime('participant_data_%y%m%d-%H%M%S.csv'))
        await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`年-月-日-時,ユーザーID,希望`', file=csv_file)

    @client.slash_command(name='f-get-participant-name', description='サーバーメンバのIDと現在の表示名の対応をcsv形式で返します')
    async def f_get_participant_name(ctx: discord.ApplicationContext):
        if ctx.guild is None:
            await ctx.respond('目的のサーバー内でコマンドしてください')
            return
        filename = f'reactionLog/{ctx.interaction.guild.name}_nameList.csv'
        with open(filename, 'w') as f:
            async for member in ctx.interaction.guild.fetch_members():
                f.write(f'{member.id},{member.name},{member.display_name},{member.joined_at}\n')
        csv_file = discord.File(filename, filename=datetime.now().strftime('participant_name_%y%m%d-%H%M%S.csv'))
        await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ユーザーID,ユーザー名,表示名,加入時期`', file=csv_file)

    @client.slash_command(name='f-get-participant-role', description='サーバーメンバのIDとロールの対応をcsv形式で返します')
    async def f_get_participant_role(ctx: discord.ApplicationContext):
        if ctx.guild is None:
            await ctx.respond('目的のサーバー内でコマンドしてください')
            return
        guild = get_guild_state()
        target_roles = [guild.LITE_PARTY_ROLE] + list(guild.ROLES.keys())
        filename = f'reactionLog/{ctx.interaction.guild.name}_roleList.csv'
        with open(filename, 'w') as f:
            async for member in ctx.interaction.guild.fetch_members():
                if member.bot:
                    continue
                f.write(f'{member.id},{member.name},{member.display_name}')
                for role in target_roles:
                    f.write(',')
                    if role in member.roles:
                        f.write(role.name)
                f.write('\n')
        csv_file = discord.File(filename, filename=datetime.now().strftime('participant_role_%y%m%d-%H%M%S.csv'))
        role_names = ",".join(map(lambda role: role.name, target_roles))
        await ctx.respond(f'{ctx.interaction.user.mention}\nフォーマットは\n`ユーザーID,ユーザー名,表示名,{role_names}`', file=csv_file)

    @client.slash_command(name='f-fetch', description='ギルド情報再取得')
    async def f_fetch_command(ctx: discord.ApplicationContext):
        print(f'{datetime.now()} slash command fetch from {ctx.interaction.user}')
        await fetch()
        await ctx.respond('ギルド情報を再取得しました')
