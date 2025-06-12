import { BaseItem } from "./itemList";
import { data } from "./model";

export interface ServerDeviceModel {
    DeviceModelID: number,
    Manufacturer: string,
    ManufacturerModelName: string,
}

export class DeviceModel extends BaseItem {
    static mapping = {
        'Manufacturer': 'manufacturer',
        'ManufacturerModelName': 'model',
    };
    static endpoint = 'deviceModels';

    id: number = 0;
    manufacturer: string = $state('');
    model: string = $state('');

    constructor(serverItem: ServerDeviceModel) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerDeviceModel) {
        this.id = serverItem.DeviceModelID;
        this.manufacturer = serverItem.Manufacturer;
        this.model = serverItem.ManufacturerModelName;
    }
}

export interface ServerDevice {
    DeviceInstanceID: number,
    DeviceModelID: number,
    SerialNumber: string,
    Description: string,
}

export class Device extends BaseItem {
    static mapping = {
        'SerialNumber': 'serialNumber',
        'Description': 'description',
    };
    static endpoint = 'devices';

    id!: number;
    deviceModelId!: number;
    serialNumber: string = $state('');
    description: string = $state('');

    constructor(serverItem: ServerDevice) {
        super();
        this.init(serverItem);
    }

    init(serverItem: ServerDevice) {
        this.id = serverItem.DeviceInstanceID;
        this.deviceModelId = serverItem.DeviceModelID;
        this.serialNumber = serverItem.SerialNumber;
        this.description = serverItem.Description;
    }
    get deviceModel(): DeviceModel {
        return data.deviceModels.get(this.deviceModelId);
    }
}

