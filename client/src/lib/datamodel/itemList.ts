import { apiUrl } from '$lib/config';
import { derived, get, writable, type Readable, type Subscriber, type Unsubscriber } from 'svelte/store';
import type { ItemConstructor } from './itemContructor';
import { importItem } from './model';

export interface Item {
    id: number | string;
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

export class ItemCollection<T extends Item> implements Readable<T[]> {
    protected readonly items: Map<number | string, T> = new Map();
    protected readonly store = writable(0);


    constructor(public readonly endpoint: string, public readonly itemConstructor: ItemConstructor<T>) {
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
}
export class MutableItemCollection<T extends Item> extends ItemCollection<T> {

    constructor(endpoint: string, itemConstructor: ItemConstructor<T>) {
        super(endpoint, itemConstructor);
    }

    async create(item: Omit<T, 'id'>): Promise<T> {
        const apiParams = this.itemConstructor.toParams(item);

        const resp = await fetch(`${apiUrl}/${this.endpoint}`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(apiParams)
        });
        const params = await resp.json();
        return importItem(this.endpoint, params) as T;
    }

    async delete(item: T, fromServer = true): Promise<void> {
        if (fromServer) {
            const url = `${apiUrl}/${this.endpoint}/${item.id}`;
            const resp = await fetch(url, { method: 'DELETE' });
            if (resp.status != 204) {
                throw new Error('Failed to delete');
            }
        }
        this.items.delete(item.id);
        this.store.update(n => n + 1);
    }
}