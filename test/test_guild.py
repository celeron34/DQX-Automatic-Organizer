import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import guild


class GuildStateTests(unittest.TestCase):
    def test_guild_uses_injected_client_and_main_reexports_it(self):
        server = object()
        client = SimpleNamespace(get_guild=Mock(return_value=server))

        model = guild.Guild(123, client)

        client.get_guild.assert_called_once_with(123)
        self.assertIs(model.GUILD, server)
        self.assertEqual(model.parties, None)
        import main
        self.assertIs(main.Guild, guild.Guild)


if __name__ == '__main__':
    unittest.main()
