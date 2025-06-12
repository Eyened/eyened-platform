type Deferred<T> = {
    promise: Promise<T>;
    resolve: (value: T | PromiseLike<T>) => void;
    reject: (reason?: any) => void;
};

function createDeferred<T>(): Deferred<T> {
    let resolve!: Deferred<T>["resolve"];
    let reject!: Deferred<T>["reject"];
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

export class DeferredMap<K, V> {
    private values = new Map<K, V>();
    private waiters = new Map<K, Deferred<V>[]>();

    get(key: K): Promise<V> {
        if (this.values.has(key)) {
            return Promise.resolve(this.values.get(key)!);
        }

        const deferred = createDeferred<V>();
        const existing = this.waiters.get(key);
        if (existing) {
            existing.push(deferred);
        } else {
            this.waiters.set(key, [deferred]);
        }

        return deferred.promise;
    }

    getSync(key: K): V | undefined {
        return this.values.get(key);
    }

    set(key: K, value: V): void {
        if (this.values.has(key)) {
            console.warn("DeferredMap.set: key already exists", key);
            return;
        }

        this.values.set(key, value);

        const deferreds = this.waiters.get(key);
        if (deferreds) {
            for (const d of deferreds) {
                d.resolve(value);
            }
            this.waiters.delete(key);
        }
    }

    has(key: K): boolean {
        return this.values.has(key);
    }

    clear(): void {
        this.values.clear();
        this.waiters.clear();
    }
}
