from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from eyened_orm import DeviceModel
from eyened_orm.authz.scope import AccessScope


class DeviceRepository:
    """Data access for DeviceModel rows."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def list_all(self) -> list[DeviceModel]:
        """Return all device models, ordered by manufacturer then model name."""
        return list(
            self._session.scalars(
                select(DeviceModel).order_by(
                    DeviceModel.Manufacturer.asc(),
                    DeviceModel.ManufacturerModelName.asc(),
                )
            ).all()
        )
