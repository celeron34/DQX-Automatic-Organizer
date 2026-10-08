import asyncio
import runpy
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, mock_open, patch

import views


async def press(view, label, interaction):
    button = next(item for item in view.children if item.label == label)
    await button.callback(interaction)


class ViewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import main

        self.main = main
        self.member_role = object()
        self.raid_role = object()
        self.user = SimpleNamespace(
            id=42, mention='<@42>', display_name='参加者',
            roles=[self.member_role, self.raid_role],
            add_roles=AsyncMock(), remove_roles=AsyncMock(),
        )
        self.guild = SimpleNamespace(
            MEMBER_ROLE=self.member_role,
            ROLES={self.raid_role: SimpleNamespace(emoji='⚔️')},
            parties=[], RECRUITING_MEMBER=[], RECRUITING_EMOJI='✅',
            RECRUIT_LOG_CH=SimpleNamespace(send=AsyncMock()),
            PARTY_CH=SimpleNamespace(send=AsyncMock()),
            timeTable=[datetime.now() + timedelta(minutes=30)],
        )
        guild_patch = patch.object(main, 'ROBIN_GUILD', self.guild)
        guild_patch.start()
        self.addCleanup(guild_patch.stop)
        schedule_patch = patch.object(main, 'rebootSchedule', False)
        schedule_patch.start()
        self.addCleanup(schedule_patch.stop)
        self.context = main.VIEW_CONTEXT
        self.interaction = SimpleNamespace(
            user=self.user, channel=Mock(),
            message=SimpleNamespace(edit=AsyncMock(), remove_reaction=AsyncMock()),
            response=SimpleNamespace(
                send_message=AsyncMock(), edit_message=AsyncMock(), defer=AsyncMock(),
            ),
            respond=AsyncMock(),
        )

    async def test_views_import_without_loading_main(self):
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-c',
            "import sys, views; assert 'main' not in sys.modules",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        self.assertEqual(process.returncode, 0, stderr.decode())

    async def test_main_uses_extracted_views_and_registers_commands(self):
        for name in ('RoleManageView', 'ApproveView', 'DummyApproveView',
                     'PartyView', 'FormationTopView', 'RecruitView', 'RebootView'):
            self.assertIs(getattr(self.main, name), getattr(views, name))
        self.assertEqual(
            {command.name for command in self.main.client.pending_application_commands},
            {'f-formation', 'f-timetable', 'f-restart', 'f-stop', 'f-rand',
             'f-get-participant-data', 'f-get-participant-name',
             'f-get-participant-role', 'f-fetch'},
        )

    async def test_script_startup_wires_its_own_models_without_second_main(self):
        with patch('builtins.open', mock_open(read_data='{"token":"test-token"}')), \
                patch.object(type(self.main.client), 'run') as run:
            entry = runpy.run_path(self.main.__file__, run_name='__main__')
        run.assert_called_once_with('test-token')
        context = entry['VIEW_CONTEXT']
        self.assertIs(context.light_party_type, entry['LightParty'])
        self.assertIs(context.make_participant, entry['Participant'])
        self.assertIsNot(context.light_party_type, self.main.LightParty)

    async def test_existing_view_reads_reloaded_guild(self):
        view = views.PartyView(context=self.context)
        other_role = object()
        self.main.ROBIN_GUILD = SimpleNamespace(MEMBER_ROLE=other_role, parties=[])
        self.assertFalse(await view.interaction_check(self.interaction))
        self.interaction.response.send_message.assert_awaited_once_with(
            '参加権がありません', delete_after=5, ephemeral=True,
        )

    async def test_dynamic_role_buttons_capture_their_own_roles(self):
        roles = {
            'A': {'role': object(), 'emoji': '⚔️'},
            'B': {'role': object(), 'emoji': '🛡️'},
        }
        view = views.RoleManageView(roles)
        await press(view, 'A', self.interaction)
        await press(view, 'B', self.interaction)
        self.assertEqual(
            [call.args[0] for call in self.user.add_roles.await_args_list],
            [roles['A']['role'], roles['B']['role']],
        )

    async def test_create_party_button_uses_interaction_user(self):
        # 分離前は権限チェック時点で user が未代入だった。
        create_party = AsyncMock()
        view = views.FormationTopView(
            context=replace(self.context, create_party=create_party),
        )
        await press(view, '新規パーティ生成', self.interaction)
        create_party.assert_awaited_once_with(self.user, free=True)

    async def test_create_party_rejects_speed_party_member(self):
        create_party = AsyncMock()
        party = self.main.SpeedParty(1, {self.raid_role: 1})
        party.addMember(self.main.Participant(self.user, {self.raid_role}), self.raid_role)
        self.guild.parties.append(party)
        view = views.FormationTopView(
            context=replace(self.context, create_party=create_party),
        )
        await press(view, '新規パーティ生成', self.interaction)
        create_party.assert_not_awaited()
        self.assertIn('フルパーティメンバ',
                      self.interaction.response.send_message.await_args.args[0])

    async def test_party_creation_attaches_view_with_shared_context(self):
        message = Mock()
        message.add_reaction = AsyncMock()
        thread = Mock()
        thread.send = AsyncMock()
        message.create_thread = AsyncMock(return_value=thread)
        self.guild.PARTY_CH.send.return_value = message
        await self.main.createNewParty(self.user, free=True)
        party = self.guild.parties[0]
        self.assertEqual(party.number, 1)
        self.assertTrue(party.free)
        view = thread.send.await_args.kwargs['view']
        self.assertIsInstance(view, views.PartyView)
        self.assertIs(view.context, self.context)
        message.add_reaction.assert_awaited_once_with('✅')

    async def test_join_request_attaches_approve_view(self):
        member = self.main.Participant(self.user, {self.raid_role})
        party = self.main.LightParty(1, [member])
        party.thread = SimpleNamespace(send=AsyncMock())
        applicant = SimpleNamespace(id=99, display_name='申請者', roles=[self.raid_role])
        self.guild.parties.append(party)
        await party.joinRequest(applicant)
        view = party.thread.send.await_args.kwargs['view']
        self.assertIsInstance(view, views.ApproveView)
        self.assertIs(view.context, self.context)
        self.assertEqual(view.timeout, 600)

    async def test_approval_transfers_applicant_using_injected_models(self):
        applicant = SimpleNamespace(
            id=99, mention='<@99>', display_name='申請者', roles=[self.raid_role],
        )
        message = Mock(channel=self.interaction.channel)
        message.edit = AsyncMock()
        self.interaction.message = message
        target = Mock(spec=self.main.LightParty)
        target.members = [self.main.Participant(self.user, {self.raid_role})]
        target.joins = {message: applicant}
        target.removeJoinRequest = AsyncMock()
        target.joinMember = AsyncMock()
        previous = Mock(spec=self.main.LightParty)
        previous.isMember.return_value = True
        previous.removeMember = AsyncMock()
        self.guild.parties = [previous, target]
        report_error = Mock()
        context = replace(self.context, search_party=Mock(return_value=target),
                          report_error=report_error)
        view = views.ApproveView(context=context)
        await press(view, '承認', self.interaction)
        previous.removeMember.assert_awaited_once_with(applicant)
        target.removeJoinRequest.assert_awaited_once_with(applicant)
        participant = target.joinMember.await_args.args[0]
        self.assertIsInstance(participant, self.main.Participant)
        self.assertIs(participant.user, applicant)
        self.assertEqual(participant.roles, {self.raid_role})
        self.assertIsInstance(message.edit.await_args.kwargs['view'], views.DummyApproveView)
        report_error.assert_not_called()

    async def test_approval_rejects_unrelated_party(self):
        context = replace(self.context, search_party=Mock(return_value=None))
        view = views.ApproveView(context=context)
        self.assertFalse(await view.interaction_check(self.interaction))
        self.interaction.response.send_message.assert_awaited_once_with(
            'パーティ外からの操作はできません', delete_after=5, ephemeral=True,
        )

    async def test_recruit_join_and_leave_update_state_and_messages(self):
        view = views.RecruitView('参加数 {count}', context=self.context)
        await press(view, '参加 [beta]', self.interaction)
        self.assertEqual(self.guild.RECRUITING_MEMBER, [self.user])
        self.interaction.message.edit.assert_awaited_with('参加数 1')
        await press(view, '参加 [beta]', self.interaction)
        self.assertEqual(self.guild.RECRUITING_MEMBER, [self.user])
        self.guild.RECRUIT_LOG_CH.send.assert_awaited_once()
        await press(view, '辞退 [beta]', self.interaction)
        self.assertEqual(self.guild.RECRUITING_MEMBER, [])
        self.interaction.message.edit.assert_awaited_with('参加数 0')
        self.interaction.message.remove_reaction.assert_awaited_once_with('✅', self.user)

    async def test_timeout_disables_buttons(self):
        for view in (
            views.PartyView(context=self.context, duration=60),
            views.FormationTopView(context=self.context, duration=60),
            views.RecruitView('募集', context=self.context, duration=60),
        ):
            message = SimpleNamespace(edit=AsyncMock())
            view.message = message
            self.assertEqual(view.timeout, 60)
            await view.on_timeout()
            self.assertTrue(all(item.disabled for item in view.children))
            message.edit.assert_awaited_once_with(view=view)

    async def test_scheduled_reboot_updates_state_used_by_main(self):
        view = views.RebootView(context=self.context)
        await press(view, '次の周回終了で再起動', self.interaction)
        self.assertIs(self.main.rebootSchedule, self.interaction.channel)
        self.assertTrue(all(item.disabled for item in view.children))

    async def test_immediate_and_stable_reboot_delegate_to_callbacks(self):
        reboot, stable_reboot = AsyncMock(), AsyncMock()
        context = replace(self.context, reboot=reboot, stable_reboot=stable_reboot)
        await press(views.RebootView(context=context), 'すぐに再起動', self.interaction)
        reboot.assert_awaited_once_with(self.interaction)
        await press(views.RebootView(context=context), '安定版再起動', self.interaction)
        stable_reboot.assert_awaited_once_with()


if __name__ == '__main__':
    unittest.main()
