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
    """Create complete role-constrained parties using recursive relocation."""
    if any(count < 0 for count in formation.values()):
        raise ValueError("formation counts must be non-negative")

    party_size = sum(formation.values())
    if party_size == 0:
        return []

    capabilities = {member: set(roles) for member, roles in participants.items()}
    remaining = list(participants)
    parties: list[dict[RoleT, list[MemberT | None]]] = [
        {role: [None] * count for role, count in formation.items()}
    ]

    while True:
        empty = _none_count(parties[-1])
        if empty > len(remaining) or (empty == 0 and len(remaining) < party_size):
            break

        if empty == 0:
            parties.append(
                {role: [None] * count for role, count in formation.items()}
            )

        for member in remaining.copy():
            if _add_member(parties, member, capabilities, frozenset()):
                remaining.remove(member)
                break
        else:
            break

    if parties and _none_count(parties[-1]):
        parties.pop()

    completed: list[Formation] = [
        {
            role: [member for member in members if member is not None]
            for role, members in party.items()
        }
        for party in parties
    ]

    assigned = {
        member
        for party in completed
        for members in party.values()
        for member in members
    }
    for member in assigned:
        participants.pop(member, None)

    return completed


def _add_member(
    parties: list[dict[RoleT, list[MemberT | None]]],
    member: MemberT,
    capabilities: Mapping[MemberT, set[RoleT]],
    visited_roles: frozenset[RoleT],
) -> bool:
    """Insert member, recursively relocating occupants across all parties."""
    member_roles = capabilities[member]
    search_roles = [
        role
        for role in member_roles
        if role in parties[-1] and role not in visited_roles
    ]
    shuffle(search_roles)

    # Prefer a free slot in the newest party.
    for role in search_roles:
        members = parties[-1][role]
        if None in members:
            members[members.index(None)] = member
            return True

    # Otherwise search newest -> oldest and move an occupant recursively.
    for party in reversed(parties):
        for role in [
            role
            for role in member_roles
            if role in party and role not in visited_roles
        ]:
            for index, occupant in enumerate(party[role]):
                if occupant is None:
                    continue

                party[role][index] = None
                if _add_member(
                    parties,
                    occupant,
                    capabilities,
                    visited_roles | frozenset(member_roles),
                ):
                    party[role][index] = member
                    return True
                party[role][index] = occupant

    return False


def _none_count(party: Mapping[RoleT, list[MemberT | None]]) -> int:
    return sum(member is None for members in party.values() for member in members)


def randomFormation(
    participants: MutableMapping[MemberT, MutableSet[RoleT]],
    party_limit: int = 4,
) -> list[list[MemberT]]:
    """Distribute members into balanced parties up to party_limit."""
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
