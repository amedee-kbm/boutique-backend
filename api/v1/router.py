from ninja import NinjaAPI

from apps.products.api import router as products_router

api = NinjaAPI(
    version="1.0.0",
    title="Boutique API",
    description="Boutiqye web API",
    openapi_url="/openapi.json",
    docs_url="/docs/",
)

api.add_router("/products/", products_router)
