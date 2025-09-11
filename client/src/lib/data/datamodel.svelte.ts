export type Id = string | number;

export interface Adapter<TGet, TCreate = Partial<TGet>, TPatch = Partial<TGet>, ListParams = unknown> {
	list?(params?: ListParams): Promise<TGet[]>;
	get?(id: Id): Promise<TGet>;
	create?(body: TCreate): Promise<TGet>;
	update?(id: Id, body: TPatch): Promise<TGet>;
	delete?(id: Id): Promise<void>;
}

const _tables = $state<Record<string, Record<Id, any>>>({});

export class Repo<
	TStore extends { id: Id },
	TGet = TStore,
	TCreate = Partial<TStore>,
	TPatch = Partial<TStore>,
	ListParams = unknown
> {
	constructor(
		public readonly key: string,
		public readonly adapter?: Adapter<TGet, TCreate, TPatch, ListParams>,
		private readonly toStore: (remote: TGet) => TStore = (x) => x as unknown as TStore
	) {}

	get table(): Record<Id, TStore> {
		return (_tables[this.key] ??= {});
	}

	all(): TStore[] {
		return Object.values(this.table);
	}

	getLocal(id: Id): TStore | undefined {
		return this.table[id];
	}

	upsert(remote: TGet): Row<TStore, TGet, TCreate, TPatch, ListParams> {
		const s = this.toStore(remote);
		this.table[s.id] = s;
		return new Row<TStore, TGet, TCreate, TPatch, ListParams>(this, s.id);
	}

	deleteLocal(id: Id): void {
		delete this.table[id];
	}

	wrap(id: Id): Row<TStore, TGet, TCreate, TPatch, ListParams> {
		if (!(id in this.table)) throw new Error(`No ${this.key}#${String(id)}`);
		return new Row<TStore, TGet, TCreate, TPatch, ListParams>(this, id);
	}

	ingest(list: TGet[]): void {
		for (const r of list) {
			const s = this.toStore(r);
			this.table[s.id] = s;
		}
	}

	async fetchAll(params?: ListParams): Promise<void> {
		if (!this.adapter?.list) return;
		const list = await this.adapter.list(params);
		this.ingest(list);
	}

	async fetchOne(id: Id): Promise<Row<TStore, TGet, TCreate, TPatch, ListParams>> {
		if (!this.adapter?.get) throw new Error('No get() adapter');
		const row = await this.adapter.get(id);
		return this.upsert(row);
	}

	async create(body: TCreate): Promise<Row<TStore, TGet, TCreate, TPatch, ListParams>> {
		if (!this.adapter?.create) throw new Error('No create() adapter');
		const created = await this.adapter.create(body);
		return this.upsert(created);
	}

	can(op: keyof Adapter<any, any, any, any>): boolean {
		return Boolean(this.adapter?.[op as keyof typeof this.adapter]);
	}
}

export class Row<TStore extends { id: Id }, TGet, TCreate, TPatch, ListParams> {
	constructor(private repo: Repo<TStore, TGet, TCreate, TPatch, ListParams>, public readonly id: Id) {}

	get data(): TStore {
		const row = this.repo.getLocal(this.id);
		if (!row) throw new Error(`Missing row ${String(this.id)}`);
		return row;
	}

	// Option A: make Row itself a store (usable as `$row` in Svelte)
	subscribe(run: (value: TStore) => void): () => void {
		run(this.data);
		const stop = $effect(() => {
			// row-level dependency: rerun on replace/updateLocal
			const _ = this.repo.table[this.id];
			run(this.data);
		});
		return stop;
	}

	// Option B: explicit readable store, if you prefer
	dataReadable() {
		return {
			subscribe: (run: (value: TStore) => void) => this.subscribe(run)
		};
	}

	updateLocal(patch: Partial<TStore>): TStore {
		// replace object to trigger row-level subscribers
		this.repo.table[this.id] = { ...this.repo.table[this.id], ...patch };
		return this.data;
	}

	replace(next: TStore): TStore {
		this.repo.table[this.id] = next;
		return next;
	}

	deleteLocal(): void {
		this.repo.deleteLocal(this.id);
	}

	async refresh(): Promise<TStore> {
		const r = await this.repo.fetchOne(this.id);
		return r.data;
	}

	async save(patch?: TPatch): Promise<TStore> {
		if (!this.repo.adapter?.update) throw new Error('No update() adapter');
		const updated = await this.repo.adapter.update(this.id, (patch ?? (this.data as unknown as TPatch)));
		const stored = (this.repo as unknown as { toStore(remote: TGet): TStore }).toStore(updated as unknown as TGet);
		this.replace(stored);
		return stored;
	}

	async destroy(): Promise<void> {
		if (!this.repo.adapter?.delete) throw new Error('No delete() adapter');
		await this.repo.adapter.delete(this.id);
		this.deleteLocal();
	}
}
