from __future__ import annotations

from typing import Any

import discord

from party import LightParty, RoleInfo, SpeedParty


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

        self.recruitingMessageItems:list[Any] = list() # 募集メッセージアイテムリスト
