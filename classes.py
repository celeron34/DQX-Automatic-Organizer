from __future__ import annotations # 再帰に必要 必ず先頭に

from typing import Any
from discord import Emoji, Role, Member, Message, Thread, User, TextChannel, Guild, File
from datetime import datetime as dt, timedelta as delta
from formation import SpeedParty, LightParty

class SendItem:
    def __init__(self, text:str, imgs:list[File]):
        self.text = text
        self.imgs = imgs

class RoleInfo:
    def __init__(self, emoji:Emoji, name:str):
        self.emoji:Emoji = emoji
        self.name:str = name
        
class PartyMember: # パーティメンバ親クラス
    def __init__(self, user:Member|None, roles:set[Role]):
        self.user:Member|None = user
        self.roles:set[Role] = roles

class Participant(PartyMember): # メンバと可能ロール
    def __init__(self, user:Member, roles:set[Role]):
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

class Guild:
    def __init__(self, guild:Guild):
        self.GUILD:Guild = guild # ギルド
        self.LIGHT_FORMATION:dict[Emoji, int] = dict() # ライトパーティ編成枠
        self.FULL_FORMATION:dict[Emoji, int] = dict() # フルパーティ編成枠
        self.TRANCE_FORMATION:dict[Emoji, Emoji] = dict() # 職変換

        self.DEV_CH:TextChannel = None # デベロッパーチャンネル
        self.PARTY_CH:TextChannel = None # 募集チャンネル
        self.PARTY_CH_beta:TextChannel = None # ベータ版募集チャンネル
        self.COMMAND_CH:TextChannel = None # コマンドチャンネル
        self.COMMAND_MSG:Message = None # コマンドメッセージ
        self.PARTY_LOG:TextChannel = None # パーティログチャンネル
        self.UNAPPLIDE_CHANNEL:TextChannel = None # 参加申請チャンネル
        self.RECLUIT_LOG_CH:TextChannel = None # 募集ログチャンネル

        self.reclutingMessage:Message = None # 募集メッセージ
        self.parties:list[SpeedParty|LightParty]|None = None # パーティ一覧
        self.timeTable:list[dt] = [] # 防衛軍タイムテーブル
        # self.timeTableThread:ThreadPoolExecutor = None # タイムテーブルスレッド

        # リアクション
        self.RECLUTING_EMOJI:Emoji = None # 参加リアクション
        self.FULLPARTY_EMOJI:Emoji = None
        self.LIGHTPARTY_EMOJI:Emoji = None
        self.MEMBER_ROLE:Role = None
        self.UNAPPLIDE_MEMBER_ROLE:Role = None # 未申請メンバ
        self.PRIORITY_ROLE:Role = None # 高速動的参加優先権ロール
        self.STATIC_PRIORITY_ROLE:Role = None # 静的参加優先権ロール
        self.MASTER_ROLE:Role = None # マスターロール
        
        self.ROLES:dict[Role, RoleInfo] = None
        self.RAID_ROLES:dict[Role, int] = None
        self.RAIDS:dict[list[dict[Role, any]]] = None
        self.RECLUTING_MEMBER:set[Member] = set() # 募集参加メンバ
        # self.ROLES:dict[Role, ]

        # self.formation:Formation = None # パーティ編成クラス

        self.reclutingMessageItems:list[SendItem] = list() # 募集メッセージアイテムリスト

