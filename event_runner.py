from __future__ import annotations

from datetime import datetime as dt, timedelta as delta
from dataclasses import dataclass
from typing import Any, Callable
import discord

from event_definition import EventPhase


@dataclass(frozen=True)
class EventRuntime:
    get_guild: Callable[[], Any]
    client: Any
    get_directory_items: Callable[..., Any]
    recruit_message_replace: Callable[..., Any]
    create_speed_parties: Callable[..., Any]
    create_light_parties: Callable[..., Any]
    formation_top_view: Any
    party_view: Any
    print_traceback: Callable[..., Any]
    pick_participant: Callable[..., Any]
    get_timetable: Callable[..., Any]
    reboot: Callable[..., Any]
    get_reboot_schedule: Callable[[], Any]
    participant_type: Any
    speed_party_type: Any
    light_party_type: Any
    event_phase: Any = EventPhase


async def run_scheduled_event(runtime):

    ROBIN_GUILD = runtime.get_guild()
    client = runtime.client
    getDirectoryItems = runtime.get_directory_items
    recruitMessageReplace = runtime.recruit_message_replace
    createSpeedParties = runtime.create_speed_parties
    createLightParties = runtime.create_light_parties
    FormationTopView = runtime.formation_top_view
    PartyView = runtime.party_view
    printTraceback = runtime.print_traceback
    pickParticipant = runtime.pick_participant
    getTimetable = runtime.get_timetable
    f_reboot = runtime.reboot
    rebootSchedule = runtime.get_reboot_schedule()
    EventPhase = runtime.event_phase
    Participant = runtime.participant_type
    SpeedParty = runtime.speed_party_type
    LightParty = runtime.light_party_type

    now = dt.now()
    now = dt(now.year, now.month, now.day, now.hour, now.minute) # 秒数はゼロ
    phase = EventPhase.at(now, ROBIN_GUILD.timeTable[0])

    ######################################################
    # 募集開始
    if phase is EventPhase.RECRUITING:
        # パーティ編成クラスをインスタンス化，メッセージ送信
        print(f'################### {dt.now()} Recruiting ###################')
        ROBIN_GUILD.RECRUITING_MEMBER.clear()
        # 既存の募集文フォルダ名 recluitingMessage は互換性のため維持。
        sendItems = getDirectoryItems(f'guilds/{ROBIN_GUILD.GUILD.id}/recluitingMessage')
        for index, sendItem in enumerate(sendItems):
            if index - len(sendItems) + 1 == 0:
                # 最後のメッセージ
                ROBIN_GUILD.recruitingMessage = await ROBIN_GUILD.PARTY_CH.send(
                    content=recruitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs
                    )
            else:
                await ROBIN_GUILD.PARTY_CH.send(
                    content=recruitMessageReplace(sendItem.text, ROBIN_GUILD.timeTable[0]),
                    files=sendItem.imgs)
        await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.RECRUITING_EMOJI) # 参加リアクション追加
        # await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.LIGHTPARTY_EMOJI) # ライトパーティリアクション追加
        # await ROBIN_GUILD.recruitingMessage.add_reaction(ROBIN_GUILD.FULLPARTY_EMOJI) # フルパーティリアクション追加
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Formation:%H時")))

        # try: # 250611 個別表示テスト
        #     await ROBIN_GUILD.DEV_CH.send('個別表示テスト\n表示テストのみで編成等に影響しません', view=RecruitView(timeout=1800, disable_on_timeout=False))
        # except Exception as e:
        #     printTraceback(e)

    elif phase is EventPhase.REMINDER:
        await ROBIN_GUILD.PARTY_CH.send(f'パーティ編成まで残り5分 {ROBIN_GUILD.recruitingMessage.jump_url}')

    ######################################################
    # パーティ編成をアナウンス
    elif phase is EventPhase.FORMATION:
        async with ROBIN_GUILD.PARTY_CH.typing():

            print(f'#================= {dt.now()} Formation =================#')

            ROBIN_GUILD.parties = list()
            # 値取得
            await ROBIN_GUILD.GUILD.chunk()
            ROBIN_GUILD.recruitingMessage = await ROBIN_GUILD.PARTY_CH.fetch_message(ROBIN_GUILD.recruitingMessage.id)
            try:
                participants:list[Participant] = list(
                    map(
                        lambda user:Participant(user, {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}),
                        ROBIN_GUILD.RECRUITING_MEMBER
                        )
                    )
            except Exception as e:
                printTraceback(e)
                participants = []
            for reaction in ROBIN_GUILD.recruitingMessage.reactions:
                if reaction.emoji == ROBIN_GUILD.RECRUITING_EMOJI:
                    async for user in reaction.users():
                        if user == client.user: continue
                        if ROBIN_GUILD.MEMBER_ROLE not in user.roles: continue
                        if user in map(lambda x:x.user, participants): continue # 既に参加者リストにいるならスキップ
                        roles = {role for role in user.roles if role in ROBIN_GUILD.ROLES.keys()}
                        participant = Participant(user, roles)
                        participants.append(participant)
            participantNum = len(participants)

            formationStartTime = dt.now()
            # 編成
            print(f'FullParty participants: {[participant.display_name for participant in participants]}')
            # shuffle(participants)
            # print(f'shaffled: {[participant.display_name for participant in participants]}')
            participantsCopy = participants.copy()
            for party in createSpeedParties(participants):
                ROBIN_GUILD.parties.append(party)
            participants = list(filter(lambda p:ROBIN_GUILD.LITE_PARTY_ROLE in p.user.roles, participants))
            print(f'LiteParty particiapnts: {[participant.display_name for participant in participants]}')
            for party in createLightParties(participants, len(ROBIN_GUILD.parties)):
                ROBIN_GUILD.parties.append(party)
            print(f'formation algorithm time: {dt.now() - formationStartTime}')

            # パーティ通知メッセージ
            await ROBIN_GUILD.PARTY_CH.send(ROBIN_GUILD.timeTable[0].strftime('## %H時のパーティ編成が完了しました\n参加者は ___**サーバー3**___ へ\n原則、一番上がリーダーです'), \
                                            view=FormationTopView(duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))

            for party in ROBIN_GUILD.parties:
                party.message = await ROBIN_GUILD.PARTY_CH.send(party.getPartyMessage(ROBIN_GUILD.ROLES))

            print(f'{dt.now()} Add Log')
            with open(f'reactionLog/{ROBIN_GUILD.GUILD.name}.csv', 'a', encoding='utf8') as f:
                for participant in participants:
                    f.write(f"{ROBIN_GUILD.timeTable[0].strftime('%y-%m-%d-%H')},{participant.id}\n")

            print('participants')
            print([participant.display_name for participant in participants])

            await ROBIN_GUILD.PARTY_LOG.send(f'{ROBIN_GUILD.timeTable[0].strftime("%y/%m/%d %H")} 初期編成参加数 {participantNum}')

        # typingここまで

        print(f'{dt.now()} Formation END')

        print(f'{dt.now()} Create Threads')

        # if any(map(lambda x:isinstance(x, SpeedParty), ROBIN_GUILD.parties)):
        #     await ROBIN_GUILD.PARTY_CH.send(file=discord.File('images/speedParty.png'))
        for party in ROBIN_GUILD.parties:
            if isinstance(party, SpeedParty):
                party.thread = await party.message.create_thread(name=f'FullParty:{party.number}', auto_archive_duration=60)
            elif isinstance(party, LightParty):
                party.thread = await party.message.create_thread(name=f'LiteParty:{party.number}', auto_archive_duration=60)
                if party.membersNum() < 4: # 4人以下の時はリアクション
                    await party.message.add_reaction(ROBIN_GUILD.RECRUITING_EMOJI)
                party.threadControlMessage = await party.thread.send(
                    view=PartyView(duration=((ROBIN_GUILD.timeTable[0] + delta(hours=1)) - dt.now()).total_seconds()))
                if party.alliance:
                    try:
                        await party.sendAllianceInfo()
                    except Exception as e:
                        printTraceback(e)
        print(f'{dt.now()} Create Threads END')
        try: # パーティ同盟チェック
            for party in ROBIN_GUILD.parties:
                if isinstance(party, LightParty):
                    await party.allianceCheck(ROBIN_GUILD.parties)
                    if party.alliance:
                        await party.message.edit(party.getPartyMessage(ROBIN_GUILD.ROLES))
        except Exception as e:
            printTraceback(e)

        try:
            # テスト編成
            participants = []
            priorities:list[Participant] = [p for p in participantsCopy
                                            if {ROBIN_GUILD.PRIORITY_ROLE, ROBIN_GUILD.STATIC_PRIORITY_ROLE} & p.roles]
            normals:list[Participant] = list(set(participantsCopy) - set(priorities))
            if len(normals) == 0:
                bias = 0
            else:
                bias = len(priorities) / len(normals) * 2
            while True:
                participant = pickParticipant(priorities, normals, bias)
                if participant is None: break
                participants.append(participant)
            parties:list[SpeedParty|LightParty] = []
            for party in createSpeedParties(participants):
                parties.append(party)
            for party in createLightParties(participants, len(parties)):
                parties.append(party)

            sendSpeedpartyDisplayName = ''
            sendLightpartyDisplayName = ''
            for party in parties:
                if isinstance(party, LightParty):
                    for member in party.members:
                        sendLightpartyDisplayName += f'{member.display_name}\n'
                elif isinstance(party, SpeedParty):
                    for members in party.members.values():
                        for member in members:
                            sendSpeedpartyDisplayName += f'{member.display_name}\n'

            print('## テスト編成表示\n### フルパーティ\n' + sendSpeedpartyDisplayName + '\n### ライトパーティ\n' + sendLightpartyDisplayName)

            # 優先権操作
            if any(map(lambda party:isinstance(party, SpeedParty) , ROBIN_GUILD.parties)):
                # フルパーティがあるなら優先権付与
                for party in ROBIN_GUILD.parties: # パーティループ
                    if isinstance(party, SpeedParty): # フルパーティ
                        for participants in party.members.values(): # ロールループ
                            for participant in participants: # ユーザーループ
                                if ROBIN_GUILD.STATIC_PRIORITY_ROLE not in participant.user.roles:
                                    # 静的優先権を持っているなら動的優先権は付与しない
                                    participant.user.add_roles(ROBIN_GUILD.PRIORITY_ROLE) # 動的優先権付与
                    elif isinstance(party, LightParty): # 通常パーティ
                        for participant in party.members: # ユーザーループ
                            if ROBIN_GUILD.STATIC_PRIORITY_ROLE not in participant.user.roles:
                                # 静的優先権を持っているなら動的優先権は付与しない
                                participant.user.add_roles(ROBIN_GUILD.PRIORITY_ROLE) # 動的優先権付与
        except Exception as e:
            try: print('優先権操作に失敗')
            except Exception: pass
            printTraceback(e)

        ROBIN_GUILD.RECRUITING_MEMBER.clear()

        print('#==================================================================#')

        # ROBIN_GUILD.recruitingMessage = None

    ######################################################
    # 0分前 タイムテーブル更新
    elif phase is EventPhase.START:
        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Hunting:%H時")))
    ######################################################
    # 1時間後 周回終わり
    elif phase is EventPhase.FINISH:

        try:
            memberSum = 0
            for party in ROBIN_GUILD.parties:
                memberSum += party.membersNum()
            await ROBIN_GUILD.PARTY_LOG.send(ROBIN_GUILD.timeTable[0].strftime(f'%y/%m/%d %H 最終参加数 {memberSum}'))
        except Exception as e:
            printTraceback(e)

        del ROBIN_GUILD.timeTable[0] # 先頭を削除
        if len(ROBIN_GUILD.timeTable) < 3:
            ROBIN_GUILD.timeTable = await getTimetable()
            for t in ROBIN_GUILD.timeTable:
                print(t)
        msg = ROBIN_GUILD.timeTable[0].strftime('## 次回の全兵団は %H時 です\n%H時 > ')
        msg += ROBIN_GUILD.timeTable[1].strftime('%H時 > ')
        msg += ROBIN_GUILD.timeTable[2].strftime('%H時 > [...](<https://hiroba.dqx.jp/sc/tokoyami/>)')
        await ROBIN_GUILD.PARTY_CH.send(msg)

        if rebootSchedule:
            try: await rebootSchedule.send('再起動します')
            except Exception as e:
                printTraceback(e)
            await f_reboot()

        await client.change_presence(activity=discord.CustomActivity(name=ROBIN_GUILD.timeTable[0].strftime("Next:%H時")))
        ROBIN_GUILD.parties = None
        ROBIN_GUILD.recruitingMessage = None
