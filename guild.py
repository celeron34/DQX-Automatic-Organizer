from __future__ import annotations

import asyncio
from typing import Any

import discord

from party import RoleInfo
from event_definition import EventDefinition, EventInstance


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

        self.timeTable:list[dt] = [] # 防衛軍タイムテーブル
        self.events:list[EventInstance] = [] # 進行中または今後予定されているイベント
        self.timetable_lock = asyncio.Lock() # 複数イベントが同じ分に終了する際の更新保護
        self.reboot_handled = False
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
        # self.ROLES:dict[discord.Role, ]

        # self.formation:Formation = None # パーティ編成クラス

        self.recruitingMessageItems:list[Any] = list() # 募集メッセージアイテムリスト

    def sync_events(self, starts_at_list):
        """Reconcile scraped start times while preserving live state per event."""
        existing = {event.starts_at: event for event in self.events}
        starts_at_list = list(dict.fromkeys(starts_at_list))
        # A timetable refresh can omit an event whose recruitment or party
        # lifecycle has already started. Keep those instances until FINISH.
        live_events = [
            event for event in self.events
            if event.recruiting_message is not None or event.parties is not None
        ]
        for event in live_events:
            if event.starts_at not in starts_at_list:
                starts_at_list.append(event.starts_at)
        self.events = [
            existing.get(starts_at) or EventInstance(
                EventDefinition(title="防衛軍", starts_at=starts_at)
            )
            for starts_at in starts_at_list
        ]
