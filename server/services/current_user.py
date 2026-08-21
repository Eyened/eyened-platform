"""The request's authenticated identity, resolved from the JWT.

Lives under ``server/services/`` rather than in ``server/routes/auth.py``
because ``server/services/access_scope.py`` needs ``CurrentUser`` and
``get_current_user``, and importing them from a route module closed a cycle:
``from ..routes.auth import ...`` first executes ``server/routes/__init__.py``,
whose first line is ``from . import segmentations``, which imports back into
``server.services``. The ``services -> routes`` edge is the defect; deleting it
is the fix, and a function-local import inside a factory would only hide it.

``server/routes/auth.py`` re-exports these names **by import**, so its existing
importers are unchanged and there is still exactly one function object per
name -- FastAPI's ``dependency_overrides`` keys on object identity, so a second
definition would make every test override silently miss.

Not a framework-neutral module: it is FastAPI-facing by design. It is kept
under ``server/services/`` so the two AST guards in
``test_no_session_in_service_or_route_signatures.py`` keep scanning it --
``get_current_user`` legitimately holds a ``Session`` and stays a *declared*
exception rather than becoming invisible to the guard.
"""
from __future__ import annotations

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from eyened_orm import Creator
from eyened_orm.authz.bootstrap import ensure_admin

from ..config import settings
from ..db import get_db

# The bypass bootstraps its account once per process. ensure_admin is a write
# path, and repeating it per request does work no later request can need --
# it also skews any local measurement taken against the bypass. The id is
# cached; the *right* to use it is not, so the row is still read every request
# and a deactivated account is still rejected.
_BYPASS_CREATOR_ID: int | None = None


class CurrentUser:
    def __init__(self, creator_id: int, username: str):
        self.id = creator_id
        self.username = username

    def get_creator(self, session: Session) -> Creator:
        return session.query(Creator).where(Creator.CreatorID == self.id).first()


def _decode_token_or_401(token: str, *, detail: str | None = None) -> dict:
    """Decode JWT; raise 401 when invalid."""
    try:
        return jwt.decode(
            token, settings.secret_key_value, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return _decode_token_or_401(token)


async def get_current_user(
    authorization: str = Header(None),
    jwt_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
    session: Session = Depends(get_db),
) -> CurrentUser:
    """Get the current authenticated user from either Authorization header or cookies."""
    # Bypass authentication if disabled (development mode)
    if settings.public_auth_disabled:
        global _BYPASS_CREATOR_ID
        if _BYPASS_CREATOR_ID is None:
            # ensure_admin, not a bare lookup: the account is a data superuser
            # only if it is an administrator, and any dump taken before cutover
            # has IsAdmin false on every row. No password is passed: the
            # bypass never authenticates with one, and passing one through
            # would overwrite any password an operator set on this account on
            # every single request.
            creator, _ = ensure_admin(session, settings.admin_username, None)
            _BYPASS_CREATOR_ID = creator.CreatorID
        else:
            creator = session.get(Creator, _BYPASS_CREATOR_ID)
        if creator is None or creator.Inactive:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return CurrentUser(creator_id=creator.CreatorID, username=creator.CreatorName)

    # Try Authorization header first (for API clients)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = verify_token(token)
        if payload.get("type") == "access":
            return CurrentUser(
                creator_id=int(payload["sub"]),
                username=payload["username"],
            )

    # Try access token cookie (for web clients)
    if jwt_token:
        try:
            payload = verify_token(jwt_token)
            if payload.get("type") == "access":
                return CurrentUser(
                    creator_id=int(payload["sub"]),
                    username=payload["username"],
                )
        except:
            pass  # Access token failed, try refresh

    # Try refresh token
    if refresh_token:
        try:
            payload = verify_token(refresh_token)
            if payload.get("type") == "refresh":
                # This will be handled by the refresh endpoint
                # For now, we'll let the client handle the 401 and call refresh
                pass
        except:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
    )
