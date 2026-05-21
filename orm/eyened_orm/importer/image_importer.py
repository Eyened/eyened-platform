from dataclasses import dataclass, field
from typing import Optional

import requests


@dataclass
class ImageImporter:
    """HTTP client for ``POST /api/import/image``.

    Handles session login and posts one flat ``ImportRow`` per call. Missing
    hierarchy entities are created by the server when the row supplies enough
    lookup keys (same behavior as the ORM importer).
    """

    admin_username: str
    admin_password: str
    api_url: str
    include_stack_trace: bool = False

    _session: Optional[requests.Session] = field(default=None, init=False)

    def __post_init__(self):
        self.image_endpoint = f"{self.api_url}/api/import/image"
        self.login_endpoint = f"{self.api_url}/api/auth/login"
        self._session = requests.Session()
        self._login()

    def _login(self) -> None:
        """Login and store session cookie (valid ~1 hour)."""
        login_data = {
            "username": self.admin_username,
            "password": self.admin_password,
            "api_client": False,
        }
        response = self._session.post(self.login_endpoint, json=login_data)
        response.raise_for_status()

    def import_image(self, image_payload: dict) -> dict:
        """Import one image. ``image_payload`` is a flat ImportRow dict."""
        payload = {
            "data": image_payload,
            "options": {"include_stack_trace": self.include_stack_trace},
        }
        response = self._session.post(self.image_endpoint, json=payload)
        response.raise_for_status()
        return response.json()
