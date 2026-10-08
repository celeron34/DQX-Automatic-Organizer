import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import party


class PartyModelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import main

        self.main = main
        self.guild = SimpleNamespace(
            ROLES={}, parties=[], PARTY_CH=SimpleNamespace(send=AsyncMock()),
            RECRUITING_EMOJI='✅', FULLPARTY_EMOJI='⚔️',
        )
        guild_patch = patch.object(main, 'ROBIN_GUILD', self.guild)
        guild_patch.start()
        self.addCleanup(guild_patch.stop)

    async def test_party_module_imports_without_main(self):
        process = await asyncio_subprocess(
            sys.executable, '-c', "import sys, party; assert 'main' not in sys.modules",
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    async def test_main_reexports_extracted_models(self):
        for name in ('RoleInfo', 'PartyMember', 'Participant', 'Guest', 'Party',
                     'LightParty', 'SpeedParty'):
            self.assertIs(getattr(self.main, name), getattr(party, name))

    async def test_participant_and_guest_models_keep_public_fields(self):
        user = SimpleNamespace(id=27, mention='<@27>', display_name='参加者')
        member = party.Participant(user, {'healer'})
        guest = party.Guest()
        self.assertEqual((member.id, member.mention, member.display_name),
                         (27, '<@27>', '参加者'))
        self.assertIs(member.user, user)
        self.assertEqual(member.roles, {'healer'})
        self.assertIs(guest.user, guest)
        self.assertEqual((guest.id, guest.mention, guest.display_name),
                         (-1, 'ゲスト', 'ゲスト'))

    async def test_party_factories_receive_live_application_context(self):
        user = SimpleNamespace(id=27, mention='<@27>', display_name='参加者')
        participant = party.Participant(user, set())
        light_party = party.LightParty(1, [participant], context=self.main.PARTY_CONTEXT)
        speed_party = party.SpeedParty(2, {'healer': 1}, context=self.main.PARTY_CONTEXT)
        self.assertIs(light_party.context.guild, self.guild)
        self.assertIs(speed_party.context.guild, self.guild)
        self.assertEqual(light_party.getPartyMessage({}), "\\| 【パーティ:1】\n\\| <@27>")
        speed_party.addMember(participant, 'healer')
        self.assertEqual(speed_party.membersNum(), 1)

    async def test_join_request_creates_approve_view_through_context(self):
        user = SimpleNamespace(id=27, mention='<@27>', display_name='既存参加者')
        existing = party.Participant(user, set())
        model = party.LightParty(1, [existing], context=self.main.PARTY_CONTEXT)
        request_message = Mock()
        model.thread = SimpleNamespace(send=AsyncMock(return_value=request_message))
        applicant = SimpleNamespace(id=28, mention='<@28>', display_name='申請者', roles=[])
        await model.joinRequest(applicant)
        self.assertEqual(model.joins, {request_message: applicant})
        view = model.thread.send.await_args.kwargs['view']
        self.assertIsInstance(view, self.main.ApproveView)
        self.assertEqual(view.duration, 600)


async def asyncio_subprocess(*args):
    import asyncio

    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return SimpleNamespace(returncode=process.returncode,
                           stdout=stdout.decode(), stderr=stderr.decode())


if __name__ == '__main__':
    unittest.main()
