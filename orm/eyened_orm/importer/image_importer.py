from dataclasses import dataclass, field
from typing import Optional

import requests

@dataclass
class ImageImporter:
    """A class for importing images into the Eyened platform.

    This class handles authentication and provides methods to import images
    into the platform, with options to create associated metadata (projects, patients,
    studies, and series) as needed.

    Args:
        admin_username (str): Username for platform authentication
        admin_password (str): Password for platform authentication
        host (str): Host address of the platform (api / viewer)
        port (int): Port number of the platform (api / viewer)
        create_project (bool, optional): Whether to create project if not exists. Defaults to True.
        create_patients (bool, optional): Whether to create patients if not exist. Defaults to True.
        create_studies (bool, optional): Whether to create studies if not exist. Defaults to True.
        create_series (bool, optional): Whether to create series if not exist. Defaults to True.
        include_stack_trace (bool, optional): Whether to include stack trace in responses. Defaults to True.
    """

    admin_username: str
    admin_password: str
    api_url: str

    create_project: bool = True
    create_patients: bool = True
    create_studies: bool = True
    create_series: bool = True
    include_stack_trace: bool = True

    _session: Optional[requests.Session] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize paths and endpoints, and perform initial login."""
        self.image_endpoint = f"{self.api_url}/api/import/image"
        self.login_endpoint = f"{self.api_url}/api/auth/login"
        self._session = requests.Session()
        self._login()

    def _login(self) -> None:
        """Login to the platform and store session cookie for subsequent requests.

        The session cookie will be valid for 1 hour.

        Raises:
            requests.exceptions.HTTPError: If login request fails
        """
        # Technically we are an API client, but because it's easier to use a cookie-authenticated session in
        # this setting, we set 'api_client' to False.
        login_data = {
            "username": self.admin_username,
            "password": self.admin_password,
            "api_client": False,
        }
        response = self._session.post(
            self.login_endpoint,
            json=login_data,
        )
        response.raise_for_status()

    @property
    def import_options(self) -> dict:
        """Get the current import configuration options.

        Returns:
            dict: Dictionary containing all import configuration flags
        """
        return {
            "create_project": self.create_project,
            "create_patients": self.create_patients,
            "create_studies": self.create_studies,
            "create_series": self.create_series,
            "include_stack_trace": self.include_stack_trace,
        }

    def import_image(self, image_payload: dict) -> dict:
        """Import a medical image into the platform.

        Args:
            image_payload (dict): Dictionary containing image data and metadata

        Returns:
            dict: Response from the platform containing import results

        Raises:
            requests.exceptions.HTTPError: If import request fails
        """
        payload = {"data": image_payload, "options": self.import_options}
        response = self._session.post(self.image_endpoint, json=payload)
        response.raise_for_status()
        return response.json()
