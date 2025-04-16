import type { Item } from "./itemList";
import type { DataModel } from "./model";
import { ServerProperty } from "./serverProperty.svelte";

export interface ItemMapping<T> {
    toValue: (params: any, data: DataModel, newData: any) => T,
    toParam: (params: any, value: T) => void
}
export type MappingType = string | ItemMapping<any>;

export function DateMapping(key: string): ItemMapping<Date> {
    return {
        toValue: (params: any) => new Date(params[key]),
        toParam: (params: any, value: Date) => { params[key] = value.toISOString(); }
    }
}

export function FKMapping(key: string, collectionName: string): ItemMapping<Item> {
    return {
        toValue: (params: any, data: DataModel, newData: any) => {
            const existing = data[collectionName as keyof DataModel].get(params[key])
            if (existing) {
                return existing;
            }
            const newItem = newData[collectionName]?.get(params[key]);
            if (newItem) {
                return newItem;
            }
            // no item found (happens for optional FK)            
            return null;
        },
        toParam: (params: any, value: Item | undefined | null) => { params[key] = value?.id }
    }
}


export function ServerPropertyMapping(
    serverName: string | null,
    endpoint: (params: any) => string,
    mediaType: (params: any) => string,
    autoload: boolean): ItemMapping<any> {
    return {
        toValue: (params: any) => {
            return new ServerProperty<any>({ endpoint: endpoint(params), mediaType: mediaType(params), autoload })
        },
        toParam: (params: any, value: ServerProperty<any>) => {
            if (serverName) {
                params[serverName] = value.value
            }
        }
    }
}