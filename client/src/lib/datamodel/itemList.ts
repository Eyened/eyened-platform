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
        importData({ [this.endpoint]: [data] });
        return response.status;
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


export class FilterList<T> implements Readable<T[]> {

    constructor(public readonly items: Readable<T[]>) { }

    first(): T | undefined {
        return this.$[0];
    }

    subscribe(run: Subscriber<T[]>, invalidate?: () => void): Unsubscriber {
        return this.items.subscribe(run, invalidate);
    }

    find(predicate: (value: T) => boolean): T | undefined {
        const items = get(this.items);
        return items.find(predicate);
    }

    filter(predicate: (value: T) => boolean): FilterList<T> {
        return new FilterList(derived(this.items, lst => lst.filter(predicate)));
    }

    sort(compareFn: (a: T, b: T) => number): FilterList<T> {
        return new FilterList(derived(this.items, lst => lst.slice().sort(compareFn)));
    }

    map<S>(mapFn: (value: T) => S): FilterList<S> {
        return new FilterList(derived(this.items, lst => lst.map(mapFn)));
    }

    forEach(callback: (value: T) => void): void {
        get(this.items).forEach(callback);
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

export class ItemCollection<T extends BaseItem> implements Readable<T[]> {
    protected readonly items: Map<number | string, T> = new Map();
    protected readonly store = writable(0);


    constructor() {
    }

    clear() {
        this.items.clear();
        this.store.update(n => n + 1);
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

    importItems(items: T[]) {
        for (const item of items) {
            this.items.set(item.id, item);
        }
        this.store.update(n => n + 1);
    }

    subscribe(run: Subscriber<T[]>): Unsubscriber {
        return this.store.subscribe(_ => run(Array.from(this.items.values())));
    }

    filter(predicate: (value: T) => boolean): FilterList<T> {
        return new FilterList(this).filter(predicate);
    }

    get filterlist() {
        return new FilterList(this);
    }

    values(): T[] {
        return Array.from(this.items.values());
    }

    find(predicate: (value: T) => boolean): T | undefined {
        const items = Array.from(this.items.values());
        return items.find(predicate);
    }

    map<S>(predicate: (value: T) => S): FilterList<S> {
        return new FilterList(this).map(predicate);
    }

    delete(id: number | string) {
        this.items.delete(id);
        this.store.update(n => n + 1);
    }
}