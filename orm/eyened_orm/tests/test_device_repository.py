from eyened_orm import DeviceModel
from eyened_orm.repositories.device_repository import DeviceRepository


def test_list_all_orders_by_manufacturer_then_model(session):
    # list_all returns every device sorted by manufacturer, then model name.
    session.add_all(
        [
            DeviceModel(Manufacturer="Zeiss", ManufacturerModelName="Cirrus"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Maestro"),
            DeviceModel(Manufacturer="Topcon", ManufacturerModelName="Aladdin"),
        ]
    )
    session.flush()

    result = DeviceRepository().list_all(session)

    names = [(d.Manufacturer, d.ManufacturerModelName) for d in result]
    assert names == [
        ("Topcon", "Aladdin"),
        ("Topcon", "Maestro"),
        ("Zeiss", "Cirrus"),
    ]
