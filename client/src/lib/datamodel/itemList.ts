import { derived, get, writable, type Readable, type Subscriber, type Unsubscriber } from 'svelte/store';

export interface Item {
    id: number | string;
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

    find(predicate: (value: T) => boolean): Readable<T | undefined> {
        return derived(this.items, lst => lst.find(predicate));
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