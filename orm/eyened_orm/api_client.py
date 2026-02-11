from eyened_orm.config import load_api_settings
from typing import Any, Mapping, Optional

import requests


class APIClient:
    """
    Simple API client with a cached authenticated session and automatic
    re-login on 401/403 responses.
    """

    def __init__(self) -> None:
        self._api_settings = load_api_settings()
        self._session: Optional[requests.Session] = None

    def _build_url(self, path: str) -> str:
        base = self._api_settings.url.rstrip("/")
        rel = path.lstrip("/")
        return f"{base}/{rel}"

    def _ensure_session(self) -> requests.Session:
        if self._session is None:
            s = requests.Session()
            resp = s.post(
                self._build_url("/api/auth/login"),
                json={
                    "username": self._api_settings.username,
                    "password": self._api_settings.password.get_secret_value(),
                    "remember_me": False,
                },
            )
            resp.raise_for_status()
            self._session = s
        return self._session

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        data: Any = None,
        files: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Perform an API request.

        If the server responds with 401/403 (likely expired session),
        the session is reset and the request is retried once.
        """

        def _do_request(sess: requests.Session) -> requests.Response:
            return sess.request(
                method=method.upper(),
                url=self._build_url(path),
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
                allow_redirects=allow_redirects,
                **kwargs,
            )

        response: requests.Response

        for _ in range(2):
            session = self._ensure_session()
            response = _do_request(session)
            if response.status_code not in (401, 403):
                break
            # Session likely expired – reset and retry once.
            self._session = None

        return response

    def get(
        self,
        path: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        return self.request(
            "GET",
            path,
            headers=headers,
            params=params,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )

    def post(
        self,
        path: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        data: Any = None,
        files: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        return self.request(
            "POST",
            path,
            headers=headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )

    def put(
        self,
        path: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        data: Any = None,
        files: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        return self.request(
            "PUT",
            path,
            headers=headers,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=allow_redirects,
            **kwargs,
        )


_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """
    Get a singleton APIClient instance.
    """
    global _client
    if _client is None:
        _client = APIClient()
    return _client
