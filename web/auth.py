# Azure AD / Entra ID authentication via OAuth2
# Usa MSAL (Microsoft Authentication Library for Python)

import os
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from nicegui import app, ui

try:
    from msal import ConfidentialClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Azure AD Configuration (from .env or environment variables)
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "ccu-trt-monitor-secret-key-change-in-production")
REDIRECT_PATH = "/auth/callback"
SCOPE = ["User.Read"]

# Auth can be disabled for development
AUTH_ENABLED = bool(AZURE_CLIENT_ID and AZURE_TENANT_ID and MSAL_AVAILABLE)

if AUTH_ENABLED:
    AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    _msal_app = ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority=AUTHORITY,
        client_credential=AZURE_CLIENT_SECRET,
    )
else:
    _msal_app = None


def setup_auth(nicegui_app):
    """Configura middleware y rutas de autenticación"""
    # Session middleware (necesario para almacenar tokens)
    nicegui_app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY)

    if not AUTH_ENABLED:
        return

    @nicegui_app.get('/auth/login')
    async def login(request):
        """Redirige a la página de login de Azure AD"""
        redirect_uri = str(request.url_for('callback'))
        auth_url = _msal_app.get_authorization_request_url(
            SCOPE,
            redirect_uri=redirect_uri,
        )
        return RedirectResponse(auth_url)

    @nicegui_app.get('/auth/callback')
    async def callback(request):
        """Callback de Azure AD después del login"""
        code = request.query_params.get("code")
        if not code:
            return RedirectResponse("/login")

        redirect_uri = str(request.url_for('callback'))
        result = _msal_app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPE,
            redirect_uri=redirect_uri,
        )

        if "access_token" in result:
            # Guardar datos del usuario en la sesión
            request.session["user"] = {
                "name": result.get("id_token_claims", {}).get("name", "Usuario"),
                "email": result.get("id_token_claims", {}).get("preferred_username", ""),
                "authenticated": True,
            }
            return RedirectResponse("/")
        else:
            return RedirectResponse("/login?error=auth_failed")

    @nicegui_app.get('/auth/logout')
    async def logout(request):
        """Cierra la sesión"""
        request.session.clear()
        return RedirectResponse("/login")


def is_authenticated() -> bool:
    """Verifica si el usuario actual está autenticado"""
    if not AUTH_ENABLED:
        return True
    user = app.storage.user.get("authenticated", False)
    return bool(user)


def get_current_user() -> dict:
    """Obtiene datos del usuario actual"""
    if not AUTH_ENABLED:
        return {"name": "Admin Local", "email": "admin@local", "authenticated": True}
    return app.storage.user.get("user", {})


def require_auth():
    """Middleware para proteger páginas. Si auth está deshabilitado, permite todo."""
    if not AUTH_ENABLED:
        return
    if not is_authenticated():
        ui.navigate.to('/login')
