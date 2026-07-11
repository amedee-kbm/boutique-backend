from ninja_extra import NinjaExtraAPI

from apps.boutiques.controllers.store_admin_controller import StoreAdminController
from apps.products.controllers.storefront_controller import StorefrontController
from apps.users.controllers.admin_controller import AdminController
from apps.users.controllers.auth_controller import AuthController
from apps.users.controllers.users_controller import UserController

api = NinjaExtraAPI(
    title="Boutique API",
    version="1.0.0",
    docs_url="/docs/",
)

api.register_controllers(
    AuthController,
    UserController,
    AdminController,
    StoreAdminController,
    StorefrontController,
)
