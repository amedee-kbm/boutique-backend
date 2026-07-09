from django.http import HttpRequest
from ninja import Router

# Not yet mounted on the API. The catalog endpoints arrive with Phase 2 of the
# build plan (docs: backend-build.md); until then this router has one probe on it
# and reaching it would require registering the router in api/v1/api.py.
router = Router(tags=["products"])


@router.get("/")
def health(request: HttpRequest) -> dict[str, str]:
    """Liveness probe for the products router. Carries no catalog data yet."""
    return {"message": "success"}
