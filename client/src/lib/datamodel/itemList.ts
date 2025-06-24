import { apiUrl } from '$lib/config';
import { derived, get, writable, type Readable, type Subscriber, type Unsubscriber } from 'svelte/store';

import { importData, removeData } from './model';
export type MappingDefinition = Record<string, string | Function>;

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
    console.log('toServer', item, mapping);
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
export interface Item {
    id: number | string;
}
export abstract class BaseItem {
    abstract id: number | string;
    static endpoint: string;
    static mapping: MappingDefinition;

    get mapping(): MappingDefinition {
        return (this.constructor as BaseItemConstructor).mapping;
    }
    get endpoint(): string {
        return (this.constructor as BaseItemConstructor).endpoint;
    }
    abstract init(serverItem: any): void;

    async update(item: any) {
        console.log('update', item);
        const updateParams: any = {};
        for (const key in item) {
            console.log('key', key);
            if (key in this) {
                console.log('key in this', key);
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
        const url = `${apiUrl}/${this.endpoint}/${this.id}`
        const response = await fetch(url, {
            method: 'PATCH',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(serverParams)
        });
        if (!response.ok) {
            console.error(`failed to update ${this.endpoint} ${this.id}: ${response.statusText}`);
            return;
        }
        const data = await response.json();
        this.updateFields(data);
    }

    private updateFields(data: any) {
        this.init(data);
    }

    static async create(item: any) {
        const serverParams = toServer(item, this.mapping);
        const url = `${apiUrl}/${this.endpoint}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(serverParams)
        });

        if (!response.ok) {
            throw new Error(`Failed to create ${this.endpoint}: ${response.statusText}`);
        }

        const data = await response.json();
        const imported = importData({ [this.endpoint]: [data] })
        return imported[this.endpoint][0];        
    }

    async delete(fromServer: boolean = true) {
        if (fromServer) {
            const url = `${apiUrl}/${this.endpoint}/${this.id}`;
            const response = await fetch(url, { method: 'DELETE' });
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
}
export abstract class BaseLinkingItem implements Item {
    abstract id: string;

    static endpoint: string;
    static parentResource: string;
    static childResource: string;
    static parentIdField: string;
    static childIdField: string;

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

    constructor(
        public readonly parentId: number,
        public readonly childId: number) {
    }

    static async create(item: any) {
        const parentId = item[this.parentIdField];
        const childId = item[this.childIdField];
        const url = `${apiUrl}/${this.parentResource}/${parentId}/${this.childResource}/${childId}`;
        const response = await fetch(url, { method: 'POST' });

        if (!response.ok) {
            throw new Error(`Failed to create ${url}: ${response.statusText}`);
        }

        const data = await response.json();
        importData(data);
        return response.status;
    }

    async delete(fromServer: boolean = true) {
        if (fromServer) {
            const url = `${apiUrl}/${this.parentResource}/${this.parentId}/${this.childResource}/${this.childId}`;
            const response = await fetch(url, { method: 'DELETE' });
            if (!response.ok) {
                throw new Error(`Failed to delete ${this.endpoint} ${this.id}: ${response.statusText}`);
            }
        }
        removeData({ [this.endpoint]: [this.id] });
    }

}



export class FilterList<T> implements Readable<T[]> {

    constructor(public readonly items: Readable<T[]>) { }

    private derive<S>(fn: (items: T[]) => S[]): FilterList<S> {
        return new FilterList(derived(this.items, fn));
    }

    first(): T | undefined {
        return this.$[0];
    }

    subscribe(run: Subscriber<T[]>, invalidate?: () => void): Unsubscriber {
        return this.items.subscribe(run, invalidate);
    }

    get(index: number): Readable<T | undefined> {
        return derived(this.items, lst => lst[index]);
    }

    get$(index: number): T | undefined {
        return this.$[index];
    }

    find$(predicate: (value: T) => boolean): T | undefined {
        const items = get(this.items);
        return items.find(predicate);
    }

    filter(predicate: (value: T) => boolean): FilterList<T> {
        return this.derive(lst => lst.filter(predicate));
    }

    sort(compareFn: (a: T, b: T) => number): FilterList<T> {
        return this.derive(lst => lst.slice().sort(compareFn));
    }

    forEach$(callback: (value: T) => void): void {
        this.$.forEach(callback);
    }

    map<S>(mapFn: (value: T) => S): FilterList<S> {
        return this.derive(lst => lst.map(mapFn));
    }

    map$<S>(mapFn: (value: T) => S): S[] {
        return this.$.map(mapFn);
    }

    flatMap<S>(mapFn: (value: T) => S[]): FilterList<S> {
        return this.derive(lst => lst.flatMap(mapFn));
    }


    reduce<S>(reducer: (accumulator: S, currentValue: T) => S, initialValue: S): Readable<S> {
        return derived(this.items, lst => lst.reduce(reducer, initialValue));
    }

    collectSet<S>(mapFn?: (value: T) => S): Readable<Set<S>> {
        if (mapFn) {
            return this.reduce((set, value) => set.add(mapFn(value)), new Set());
        }
        return this.reduce((set, value) => set.add(value), new Set());
    }

    groupBy<K>(keyFn: (value: T) => K): Readable<Map<K, T[]>> {
        return derived(this.items, lst => {
            const map = new Map<K, T[]>();
            for (const item of lst) {
                const key = keyFn(item);
                if (!map.has(key)) {
                    map.set(key, []);
                }
                map.get(key)!.push(item);
            }
            return map;
        });
    }

    subscribeEach<S extends Readable<any>>(mapFn: (value: T) => S, callback: (item: T, value: any) => void): Unsubscriber {
        let unsubscribes: Unsubscriber[] = [];

        // Subscribe directly to the items store
        const unsubscribeFromItems = this.items.subscribe(items => {
            // Unsubscribe from previous item subscriptions
            unsubscribes.forEach(unsub => unsub());

            // Subscribe to each individual item's store
            unsubscribes = items.map(item => mapFn(item).subscribe(value => callback(item, value)));
        });

        // Return a function that unsubscribes from both the items store and individual item subscriptions
        return () => {
            unsubscribeFromItems(); // Unsubscribe from the items store
            unsubscribes.forEach(unsub => unsub()); // Unsubscribe from each individual item's store
        };
    }


    get $(): T[] {
        // consume the store 
        return get(this.items);
    }
}

export class ItemCollection<T extends Item> implements Readable<T[]> {
    protected readonly items: Map<number | string, T> = new Map();
    protected readonly store = writable(0);


    constructor() {
    }

    private emit() {
        this.store.update(n => n + 1);
    }

    importItems(items: T[]) {
        for (const item of items) {
            this.items.set(item.id, item);
        }
        this.emit();
    }

    clear() {
        this.items.clear();
        this.emit();
    }

    delete(id: number | string) {
        this.items.delete(id);
        this.emit();
    }

    get(id: number | string): T | undefined {
        return this.items.get(id);
    }

    has(id: number | string): boolean {
        return this.items.has(id);
    }

    first(): T | undefined {
        return this.values()[0];
    }

    subscribe(run: Subscriber<T[]>): Unsubscriber {
        return this.store.subscribe(_ => run(this.values()));
    }

    get filterlist() {
        return new FilterList(this);
    }

    filter(predicate: (value: T) => boolean): FilterList<T> {
        return this.filterlist.filter(predicate);
    }

    filter$(predicate: (value: T) => boolean): T[] {
        return this.values().filter(predicate);
    }


    values(): T[] {
        return Array.from(this.items.values());
    }

    find(predicate: (value: T) => boolean): T | undefined {
        return this.values().find(predicate);
    }

    map<S>(predicate: (value: T) => S): FilterList<S> {
        return this.filterlist.map(predicate);
    }

    flatMap<S>(predicate: (value: T) => S[]): FilterList<S> {
        return this.filterlist.flatMap(predicate);
    }


}