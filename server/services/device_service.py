from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository

from ..db import get_db


class DeviceService:
    """Business logic for device models."""

    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def list_devices(self) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return self.repository.list_all()


def get_device_service(db: Session = Depends(get_db)) -> DeviceService:
    """Default DeviceService wiring for FastAPI ``Depends()``."""
    return DeviceService(DeviceRepository(db))
