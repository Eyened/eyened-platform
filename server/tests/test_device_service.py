from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository

from server.services.device_service import DeviceService


def test_list_devices_returns_repository_rows_in_order(session):
    """The service hands back exactly what the repository returns, order intact."""
    session.add_all(
        [
            DeviceModel(Manufacturer="Zeiss", ManufacturerModelName="Cirrus"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Maestro"),
        ]
    )
    session.flush()

    service = DeviceService(DeviceRepository())
    result = service.list_devices(session)

    assert [d.Manufacturer for d in result] == ["Topcon", "Zeiss"]
