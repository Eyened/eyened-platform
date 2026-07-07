from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import DeviceModel


class DeviceRepository:
    """Data access for DeviceModel rows."""

    def list_all(self, session: Session) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return list(
            session.scalars(
                select(DeviceModel).order_by(
                    DeviceModel.Manufacturer.asc(),
                    DeviceModel.ManufacturerModelName.asc(),
                )
            ).all()
        )
