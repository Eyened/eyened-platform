from __future__ import annotations

from sqlalchemy.orm import Session

from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository


class DeviceService:
    """Business logic for device models."""

    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def list_devices(self, session: Session) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return self.repository.list_all(session)


def get_device_service() -> DeviceService:
    """Default DeviceService wiring for FastAPI ``Depends()``."""
    return DeviceService(DeviceRepository())
