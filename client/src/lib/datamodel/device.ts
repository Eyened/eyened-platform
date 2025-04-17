import { ItemConstructor, DerivedProperty } from "./itemContructor";
import type { Item } from "./itemList";
import { FKMapping } from './mapping';

export interface Device extends Item {
    id: number,
    deviceModel: DeviceModel,
    serialnumber: string,
    description: string,
    model: string,
}

export interface DeviceModel extends Item {
    id: number,
    manufacturer: string,
    model: string,

}

export const DeviceConstructor = new ItemConstructor<Device>('DeviceInstanceID', {
    deviceModel: FKMapping('DeviceModelID', 'deviceModels'),
    serialnumber: 'SerialNumber',
    description: 'Description',

    model: new DerivedProperty((self: Device) => self.deviceModel.model)
});

export const DeviceModelConstructor = new ItemConstructor<DeviceModel>('DeviceModelID', {
    manufacturer: 'Manufacturer',
    model: 'ManufacturerModelName'
});