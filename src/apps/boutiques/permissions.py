import typing as t

from apps.boutiques.models import Membership

# The capabilities a membership can grant. Operational capabilities (the shop's
# day-to-day) are open to any member; governance capabilities are the OWNER's.
Capability = t.Literal[
    "work_orders",  # operational
    "work_chat",  # operational
    "manage_catalog",  # operational
    "manage_members",  # governance
    "edit_store_settings",  # governance
]

# The only place the OWNER/STAFF split is expressed. A finer permission model —
# revel-backend uses a per-membership JSON map — graduates behind has_permission()
# without touching a single caller (ADR-0013).
_GOVERNANCE: frozenset[Capability] = frozenset({"manage_members", "edit_store_settings"})


def has_permission(membership: Membership, capability: Capability) -> bool:
    """Whether ``membership`` grants ``capability`` — the authorization choke-point.

    Governance is OWNER-only; everything operational is open to any member.
    """
    if capability in _GOVERNANCE:
        return membership.is_owner
    return True
