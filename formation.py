from __future__ import annotations

from collections.abc import Hashable, Mapping, MutableMapping, MutableSet
from random import shuffle
from typing import TypeVar

MemberT = TypeVar("MemberT", bound=Hashable)
RoleT = TypeVar("RoleT", bound=Hashable)

Formation = dict[RoleT, list[MemberT]]


def speedFormation(
    participants: MutableMapping[MemberT, MutableSet[RoleT]],
    formation: Mapping[RoleT, int],
) -> list[Formation]:
    """Create as many complete role-constrained parties as possible.

    participants maps each member to the roles that member can fill.
    Members assigned to a complete party are removed from participants.
    Unassigned members remain so another formation strategy can consume them.

    The allocator first uses empty slots. If a member cannot be inserted
    directly, it recursively relocates an already assigned member.
    """
    if any(count < 0 for count in formation.values()):
        raise ValueError("formation counts must be non-negative")

    party_size = sum(formation.values())
    if party_size == 0:
        return []

    capabilities = {member: set(roles) for member, roles in participants.items()}
    parties: list[Formation] = []

    while len(participants) >= party_size:
        party: dict[RoleT, list[MemberT | None]] = {
            role: [None] * count for role, count in formation.items()
        }

        remaining = list(participants)
        progress = True
        while progress and _none_count(party):
            progress = False
            for member in remaining.copy():
                if _add_member(
                    party,
                    member,
                    capabilities,
                    frozenset(),
                ):
                    remaining.remove(member)
                    progress = True
                    break

        if _none_count(party):
            break

        completed: Formation = {
            role: [member for member in members if member is not None]
            for role, members in party.items()
        }
        parties.append(completed)

        for members in completed.values():
            for member in members:
                participants.pop(member, None)

    return parties


def _add_member(
    party: dict[RoleT, list[MemberT | None]],
    member: MemberT,
    capabilities: Mapping[MemberT, set[RoleT]],
    visited_roles: frozenset[RoleT],
) -> bool:
    """Insert member, recursively relocating occupants when necessary."""
    member_roles = capabilities[member]
    search_roles = [
        role
        for role in member_roles
        if role in party and role not in visited_roles
    ]
    shuffle(search_roles)

    for role in search_roles:
        members = party[role]
        if None in members:
            members[members.index(None)] = member
            return True

    for role in search_roles:
        members = party[role]
        for index, occupant in enumerate(members):
            if occupant is None:
                continue

            members[index] = None
            if _add_member(
                party,
                occupant,
                capabilities,
                visited_roles | frozenset(member_roles),
            ):
                members[index] = member
                return True
            members[index] = occupant

    return False


def _none_count(party: Mapping[RoleT, list[MemberT | None]]) -> int:
    return sum(member is None for members in party.values() for member in members)


def randomFormation(
    participants: MutableMapping[MemberT, MutableSet[RoleT]],
    party_limit: int = 4,
) -> list[list[MemberT]]:
    """Distribute remaining members into balanced parties."""
    if party_limit <= 0:
        raise ValueError("party_limit must be greater than zero")
    if not participants:
        return []

    members = list(participants)
    party_count = (len(members) + party_limit - 1) // party_limit
    base_size, remainder = divmod(len(members), party_count)

    parties: list[list[MemberT]] = []
    offset = 0
    for index in range(party_count):
        size = base_size + (1 if index < remainder else 0)
        parties.append(members[offset:offset + size])
        offset += size

    return parties
