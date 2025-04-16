import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Type, Union

import jwt
from anyio.to_thread import run_sync
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED

from .utils import ordered_partial

SECRET_TYPE = Union[str, bytes]
CUSTOM_EXCEPTION = Union[Type[Exception], Exception]


InvalidCredentialsException = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

InsufficientScopeException = HTTPException(
    status_code=HTTP_400_BAD_REQUEST,
    detail="Insufficient scope",
    headers={"WWW-Authenticate": "Bearer"},
)


class LoginManager(OAuth2PasswordBearer):
    """
    From: https://github.com/MushroomMaula/fastapi_login/blob/master/fastapi_login/fastapi_login.py
    """

    def __init__(
        self,
        secret: Union[SECRET_TYPE, Dict[str, SECRET_TYPE]],
        token_url: str,
        algorithm="HS256",
        use_cookie=False,
        use_header=True,
        access_cookie_name: str = "access-token",
        refresh_cookie_name: str = "refresh-token",
        not_authenticated_exception: CUSTOM_EXCEPTION = InvalidCredentialsException,
        access_token_expiry: timedelta = timedelta(minutes=15),
        refresh_token_expiry: timedelta = timedelta(days=7),
    ):
        """
        Initializes LoginManager

        Args:
            algorithm (str): Should be "HS256" or "RS256" used to decrypt the JWT
            token_url (str): The url where the user can login to get the token
            use_cookie (bool): Set if cookies should be checked for the token
            use_header (bool): Set if headers should be checked for the token
            access_cookie_name (str): Name of the cookie to check for the access token
            refresh_cookie_name (str): Name of the cookie to check for the refresh token
            not_authenticated_exception (Union[Type[Exception], Exception]): Exception to raise when the user is not authenticated
                this defaults to `fastapi_login.exceptions.InvalidCredentialsException`
            access_token_expiry (datetime.timedelta): The default expiry time of the access token, defaults to 15 minutes
            refresh_token_expiry (datetime.timedelta): The default expiry time of the refresh token, defaults to 7 days
        """
        if use_cookie is False and use_header is False:
            raise AttributeError(
                "use_cookie and use_header are both False one of them needs to be True"
            )
        if isinstance(secret, str):
            secret = secret.encode()

        self.secret = secret
        self.algorithm = algorithm
        self.oauth_scheme = None
        self.use_cookie = use_cookie
        self.use_header = use_header
        self.access_cookie_name = access_cookie_name
        self.refresh_cookie_name = refresh_cookie_name
        self.access_token_expiry = access_token_expiry
        self.refresh_token_expiry = refresh_token_expiry

        # private
        self._user_callback: Optional[ordered_partial] = None
        self._not_authenticated_exception = not_authenticated_exception

        # we take over the exception raised possibly by setting auto_error to False
        super().__init__(tokenUrl=token_url, auto_error=False)

    @property
    def not_authenticated_exception(self):
        """
        Exception raised when no (valid) token is present.
        Defaults to `fastapi_login.exceptions.InvalidCredentialsException`
        """
        return self._not_authenticated_exception

    def user_loader(self, *args, **kwargs) -> Union[Callable, Callable[..., Awaitable]]:
        """
        This sets the callback to retrieve the user.
        The function should take an unique identifier like an email
        and return the user object or None.

        Basic usage:

            >>> from fastapi import FastAPI
            >>> from fastapi_login import LoginManager

            >>> app = FastAPI()
            >>> # use import secrets; print(secrets.token_hex(24)) to get a suitable secret key
            >>> SECRET = "super-secret"

            >>> manager = LoginManager(SECRET, token_url="Login")

            >>> manager.user_loader()(get_user)

            >>> @manager.user_loader(...)  # Arguments and keyword arguments declared here are passed on
            >>> def get_user(user_identifier, ...):
            ...     # get user logic here

        Args:
            args: Positional arguments to pass on to the decorated method
            kwargs: Keyword arguments to pass on to the decorated method

        Returns:
            The callback
        """

        def decorator(callback: Union[Callable, Callable[..., Awaitable]]):
            """
            The actual setter of the load_user callback
            Args:
                callback (Callable or Awaitable): The callback which returns the user

            Returns:
                Partial of the callback with given args and keyword arguments already set
            """
            self._user_callback = ordered_partial(callback, *args, **kwargs)
            return callback

        return decorator

    def _get_userid(self, token: str) -> Dict[str, Any]:
        """
        Returns the decoded token payload.
        If failed, raises `LoginManager.not_authenticated_exception`

        Args:
            token (str): The token to decode

        Returns:
            Payload of the token

        Raises:
            LoginManager.not_authenticated_exception: The token is invalid or None was returned by `_load_user`
        """
        try:
            payload = jwt.decode(token, self.secret,
                                 algorithms=[self.algorithm])
            user_identifier = int(payload.get("sub"))
            return user_identifier

        # This includes all errors raised by pyjwt
        except jwt.PyJWTError:
            raise self.not_authenticated_exception

    async def get_current_user(self, user_identifier: int) -> Any:
        """
        Combines `_get_payload` and `_get_current_user` to get the user object

        Args:
            token (str): The encoded jwt token

        Returns:
            The user object returned by the instances `_user_callback`

        Raises:
            LoginManager.not_authenticated_exception: The token is invalid or None was returned by `_load_user`
        """
        user = await self._load_user(user_identifier)
        if user is None:
            raise self.not_authenticated_exception
        return user

    async def _load_user(self, identifier: Any):
        """
        This loads the user using the user_callback

        Args:
            identifier (Any): The user identifier expected by `_user_callback`

        Returns:
            The user object returned by `_user_callback` or None

        Raises:
            Exception: When no ``user_loader`` has been set
        """
        if self._user_callback is None:
            raise Exception("Missing user_loader callback")

        if inspect.iscoroutinefunction(self._user_callback):
            user = await self._user_callback(identifier)
        else:
            user = await run_sync(self._user_callback, identifier)

        return user

    def create_access_token(
        self, *, data: dict, expires: Optional[timedelta] = None
    ) -> str:
        """
        Helper function to create the encoded access token using
        the provided secret and the algorithm of the LoginManager instance

        Args:
            data (dict): The data which should be stored in the token
            expires (datetime.timedelta):  An optional timedelta in which the token expires.
                Defaults to 15 minutes

        Returns:
            The encoded JWT with the data and the expiry. The expiry is
            available under the 'exp' key
        """

        to_encode = data.copy()

        if expires:
            expires_in = datetime.now(timezone.utc) + expires
        else:
            expires_in = datetime.now(timezone.utc) + self.access_token_expiry

        to_encode.update({"exp": expires_in})

        token = jwt.encode(to_encode, self.secret, self.algorithm)
        return token

    def create_refresh_token(
        self, *, data: dict, expires: Optional[timedelta] = None
    ) -> str:
        """
        Helper function to create the encoded refresh token using
        the provided secret and the algorithm of the LoginManager instance

        Args:
            data (dict): The data which should be stored in the token
            expires (datetime.timedelta):  An optional timedelta in which the token expires.
                Defaults to 7 days

        Returns:
            The encoded JWT with the data and the expiry. The expiry is
            available under the 'exp' key
        """

        to_encode = data.copy()

        if expires:
            expires_in = datetime.now(timezone.utc) + expires
        else:
            expires_in = datetime.now(timezone.utc) + self.refresh_token_expiry

        to_encode.update({"exp": expires_in})

        return jwt.encode(to_encode, self.secret, self.algorithm)

    def set_access_cookie(self, response: Response, token: str) -> None:
        """
        Utility function to set a cookie containing the access token on the response

        Args:
            response (fastapi.Response): The response which is sent back
            token (str): The created JWT
        """
        response.set_cookie(key=self.access_cookie_name,
                            value=token, httponly=True)

    def set_refresh_cookie(self, response: Response, token: str) -> None:
        """
        Utility function to set a cookie containing the refresh token on the response

        Args:
            response (fastapi.Response): The response which is sent back
            token (str): The created JWT
        """
        response.set_cookie(key=self.refresh_cookie_name,
                            value=token, httponly=True)

    def _token_from_cookie(self, request: Request, cookie_name: str) -> Optional[str]:
        """
        Checks the request's cookies for a cookie with the specified name

        Args:
            request (fastapi.Request): The request to the route, normally filled in automatically
            cookie_name (str): The name of the cookie to check for the token

        Returns:
            The token found in the cookies of the request or None
        """
        return request.cookies.get(cookie_name) or None

    async def _get_token(self, request: Request, cookie_name: str):
        """
        Tries to extract the token from the request, based on self.use_header and self.use_cookie

        Args:
            request: The request containing the token
            cookie_name: The name of the cookie to check for the token

        Returns:
            The encoded JWT token found in the request

        Raises:
            LoginManager.not_authenticated_exception if no token is present
        """
        token = None
        if self.use_cookie:
            token = self._token_from_cookie(request, cookie_name)

        if not token and self.use_header:
            token = await super(LoginManager, self).__call__(request)

        if not token:
            raise self.not_authenticated_exception

        return token

    async def __call__(
        self,
        request: Request,
        _: SecurityScopes = None,  # type: ignore
    ):
        """
        Provides the functionality to act as a Dependency

        Args:
            request (fastapi.Request):The incoming request, this is set automatically
                by FastAPI

        Returns:
            The user_id or None

        Raises:
            LoginManager.not_authenticated_exception: If set by the user and `self.auto_error` is set to False

        """
        token = await self._get_token(request, self.access_cookie_name)
        user_id = self._get_userid(token)

        # there was no exception: user is correctly authenticated
        return user_id

    async def optional(self, request: Request, security_scopes: SecurityScopes = None):  # type: ignore
        """
        Acts as a dependency which catches all errors and returns `None` instead
        """
        try:
            user = await self.__call__(request, security_scopes)
        except Exception:
            return None
        else:
            return user

    def attach_middleware(self, app: FastAPI):
        """
        Add the instance as a middleware, which adds the user object, if present,
        to the request state

        Args:
            app (fastapi.FastAPI): FastAPI application
        """

        async def __set_user(request: Request, call_next):
            try:
                request.state.user = await self.__call__(request)
            except Exception:
                # An error occurred while getting the user
                # as middlewares are called for every incoming request
                # it's not a good idea to return the Exception
                # so we set the user to None
                request.state.user = None

            return await call_next(request)

        app.add_middleware(BaseHTTPMiddleware, dispatch=__set_user)
