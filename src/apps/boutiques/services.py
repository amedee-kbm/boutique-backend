from django.db.models import QuerySet

from apps.boutiques.models import Boutique, Membership


def members_of(boutique: Boutique) -> QuerySet[Membership]:
    """The boutique's members, newest first, with their user rows joined for display."""
    return boutique.memberships.select_related("user")
