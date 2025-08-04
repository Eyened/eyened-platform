import { apiUrl } from '$lib/config';
import type { Item } from './itemList';
import { importData, removeData } from './model';
import { api } from '../utils/api';

export type MappingDefinition = Record<string, string | Function>;

function isStateProperty(obj: any, key: string): boolean {
    const desc = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(obj),
        key
    );
    return !!(desc && typeof desc.get === 'function' && typeof desc.set === 'function');
}
interface BaseItemConstructor {
    new(serverItem: any): BaseItem;
    mapping: MappingDefinition;
    endpoint: string;
}

export abstract class BaseItem {
    abstract id: number | string;
    primaryKey: number[] | undefined = undefined;
    static endpoint: string;
    static mapping: MappingDefinition;

    get mapping(): MappingDefinition {
        return (this.constructor as BaseItemConstructor).mapping;
    }
    get endpoint(): string {
        return (this.constructor as BaseItemConstructor).endpoint;
    }
    get idRoute(): string {
        if (this.primaryKey) {
            return `${this.endpoint}/${this.primaryKey.join('/')}`;
        }
        return `${this.endpoint}/${this.id}`;
    }
    abstract init(serverItem: any): void;

    async update(item: any) {
        const updateParams: any = {};
        for (const key in item) {
            if (key in this) {
                if (isStateProperty(this, key)) {
                    updateParams[key] = item[key];
                } else {
                    console.warn(`property ${key} is not a state property and will not be updated`);
                }
            } else {
                console.warn(`property ${key} not found`);
            }
        }
        const serverParams = toServer(updateParams, this.mapping);

        // check if serverParams has any properties
        if (Object.keys(serverParams).length === 0) {
            console.warn('no properties to update');
            return;
        }
        const url = `${apiUrl}/${this.idRoute}`
        const response = await api.patch(url, serverParams);
        if (!response.ok) {
            console.error(`failed to update ${this.endpoint} ${this.id}: ${response.statusText}`);
            return;
        }
        const data = await response.json();
        this.updateFields(data);
    }

    protected updateFields(data: any) {
        this.init(data);
    }

    static async create(item: any) {
        const serverParams = toServer(item, this.mapping);
        const url = `${apiUrl}/${this.endpoint}`;
        const response = await api.post(url, serverParams);

        if (!response.ok) {
            throw new Error(`Failed to create ${this.endpoint}: ${response.statusText}`);
        }

        const data = await response.json();
        const imported = importData({ [this.endpoint]: [data] })
        return imported[this.endpoint][0];
    }

    async delete(fromServer: boolean = true) {
        if (fromServer) {
            const url = `${apiUrl}/${this.idRoute}`;
            const response = await api.delete(url);
            if (!response.ok) {
                throw new Error(`Failed to delete ${this.endpoint} ${this.id}: ${response.statusText}`);
            }
        }
        removeData({ [this.endpoint]: [this.id] });
    }
}

interface BaseLinkingItemConstructor {
    new(parentId: number, childId: number): BaseLinkingItem;
    parentResource: string;
    childResource: string;
    parentIdField: string;
    childIdField: string;
    endpoint: string;
    mapping: MappingDefinition;
}
export abstract class BaseLinkingItem implements Item {
    abstract id: string;

    static endpoint: string;
    static parentResource: string;
    static childResource: string;
    static parentIdField: string;
    static childIdField: string;
    static mapping: MappingDefinition;

    get endpoint(): string {
        return (this.constructor as BaseLinkingItemConstructor).endpoint;
    }
    get parentResource(): string {
        return (this.constructor as BaseLinkingItemConstructor).parentResource;
    }
    get childResource(): string {
        return (this.constructor as BaseLinkingItemConstructor).childResource;
    }
    get parentIdField(): string {
        return (this.constructor as BaseLinkingItemConstructor).parentIdField;
    }
    get childIdField(): string {
        return (this.constructor as BaseLinkingItemConstructor).childIdField;
    }
    get mapping(): MappingDefinition {
        return (this.constructor as BaseLinkingItemConstructor).mapping;
    }
    constructor(
        public readonly parentId: number,
        public readonly childId: number) {
    }

    static async create(item: any) {
        const serverParams = toServer(item, this.mapping);
        const parentId = item[this.parentIdField];
        const childId = item[this.childIdField];
        const url = `${apiUrl}/${this.parentResource}/${parentId}/${this.childResource}/${childId}`;
        const response = await api.post(url, serverParams);

        if (!response.ok) {
            throw new Error(`Failed to create ${url}: ${response.statusText}`);
        }
        const data = await response.json();
        const imported = importData(data);
        return imported[this.endpoint][0];

    }

    async delete(fromServer: boolean = true) {
        if (fromServer) {
            const url = `${apiUrl}/${this.parentResource}/${this.parentId}/${this.childResource}/${this.childId}`;
            const response = await api.delete(url);
            if (!response.ok) {
                throw new Error(`Failed to delete ${this.endpoint} ${this.id}: ${response.statusText}`);
            }
        }
        removeData({ [this.endpoint]: [this.id] });
    }

}

export function parseDate(date: string): Date {
    return new Date(date);
}
export function formatDate(date: Date): string {
    return date.toISOString().slice(0, 10);
}
export function formatDateTime(date: Date): string {
    return date.toISOString();
}

export function toServer(item: any, mapping: MappingDefinition): any {
    const result: any = {};
    for (const [serverKey, localKey] of Object.entries(mapping)) {
        if (typeof localKey === 'function') {
            result[serverKey] = localKey(item);
        } else {
            result[serverKey] = item[localKey];
        }
    }
    return result;
}