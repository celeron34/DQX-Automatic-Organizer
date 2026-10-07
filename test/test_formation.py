import random
import unittest

from formation import randomFormation, speedFormation


def old_speed_formation(participants, formation):
    """main.py の旧アルゴリズムを Discord 非依存に写した比較用実装。"""
    participants = list(participants.items())
    parties = [{role: [None] * count for role, count in formation.items()}]

    def none_count(party):
        return sum(member is None for members in party.values() for member in members)

    def add_member(member, roles, visited=frozenset()):
        search_roles = [role for role in roles if role not in visited]
        random.shuffle(search_roles)
        for role in search_roles:
            if role in parties[-1] and None in parties[-1][role]:
                members = parties[-1][role]
                members[members.index(None)] = member
                return True

        for party in reversed(parties):
            for role in [role for role in roles if role not in visited and role in party]:
                for index, occupant in enumerate(party[role]):
                    party[role][index] = None
                    occupant_roles = capabilities[occupant]
                    if add_member(occupant, occupant_roles, visited | frozenset(roles)):
                        party[role][index] = member
                        return True
                    party[role][index] = occupant
        return False

    capabilities = dict(participants)
    remaining = [member for member, _ in participants]
    party_size = sum(formation.values())

    while True:
        empty = none_count(parties[-1])
        if empty > len(remaining) or (empty == 0 and len(remaining) < party_size):
            break
        if empty == 0:
            parties.append({role: [None] * count for role, count in formation.items()})

        for member in remaining.copy():
            if add_member(member, capabilities[member]):
                remaining.remove(member)
                break
        else:
            break

    if parties and none_count(parties[-1]):
        parties.pop()

    return parties, remaining


def assert_valid(testcase, source, formation, parties, remaining):
    seen = set()
    for party in parties:
        testcase.assertEqual(set(party), set(formation))
        for role, count in formation.items():
            testcase.assertEqual(len(party[role]), count)
            for member in party[role]:
                testcase.assertIn(role, source[member])
                testcase.assertNotIn(member, seen)
                seen.add(member)
    testcase.assertEqual(seen | set(remaining), set(source))
    testcase.assertFalse(seen & set(remaining))


class FormationTests(unittest.TestCase):
    def test_exact_formation(self):
        source = {"a": {"A"}, "b": {"B"}, "c": {"C"}}
        participants = {member: set(roles) for member, roles in source.items()}
        parties = speedFormation(participants, {"A": 1, "B": 1, "C": 1})
        self.assertEqual(len(parties), 1)
        assert_valid(self, source, {"A": 1, "B": 1, "C": 1}, parties, participants)

    def test_impossible_formation_keeps_everyone(self):
        source = {"a": {"A"}, "b": {"A"}, "c": {"C"}}
        participants = {member: set(roles) for member, roles in source.items()}
        parties = speedFormation(participants, {"A": 1, "B": 1, "C": 1})
        self.assertEqual(parties, [])
        self.assertEqual(set(participants), set(source))

    def test_recursive_relocation(self):
        # a が A を先に取っても、a -> B に移せば c -> A を入れられる。
        source = {"a": {"A", "B"}, "b": {"B", "C"}, "c": {"A"}}
        formation = {"A": 1, "B": 1, "C": 1}
        for seed in range(30):
            random.seed(seed)
            participants = {member: set(roles) for member, roles in source.items()}
            parties = speedFormation(participants, formation)
            self.assertEqual(len(parties), 1, f"seed={seed}")
            assert_valid(self, source, formation, parties, participants)

    def test_multiple_parties_and_remainder(self):
        source = {
            "a1": {"A"}, "b1": {"B"}, "c1": {"C"},
            "a2": {"A"}, "b2": {"B"}, "c2": {"C"},
            "extra": {"A"},
        }
        formation = {"A": 1, "B": 1, "C": 1}
        participants = {member: set(roles) for member, roles in source.items()}
        parties = speedFormation(participants, formation)
        self.assertEqual(len(parties), 2)
        self.assertEqual(set(participants), {"extra"})
        assert_valid(self, source, formation, parties, participants)

    def test_random_formation_balances_parties(self):
        participants = {i: set() for i in range(9)}
        parties = randomFormation(participants, 4)
        self.assertEqual(sorted(map(len, parties)), [3, 3, 3])
        self.assertEqual(set().union(*map(set, parties)), set(range(9)))

    def test_randomized_regression_against_old_algorithm(self):
        formation = {"A": 1, "B": 1, "C": 1, "D": 1}
        roles = tuple(formation)
        rng = random.Random(20261008)

        for case in range(10000):
            count = rng.randint(0, 20)
            source = {}
            for member in range(count):
                source[member] = {
                    role for role in roles if rng.random() < 0.45
                }

            # shuffle() はモジュールの random を使うので、両実装を同じ seed で比較。
            seed = rng.randrange(2**32)
            random.seed(seed)
            old_parties, old_remaining = old_speed_formation(source, formation)

            random.seed(seed)
            new_input = {member: set(member_roles) for member, member_roles in source.items()}
            new_parties = speedFormation(new_input, formation)

            assert_valid(self, source, formation, new_parties, new_input)
            self.assertEqual(
                len(new_parties),
                len(old_parties),
                f"case={case}, seed={seed}, source={source}, "
                f"old_remaining={old_remaining}, new_remaining={list(new_input)}",
            )


if __name__ == "__main__":
    unittest.main()
