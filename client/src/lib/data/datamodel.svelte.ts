
export type Id = string | number;

// Helper: naive singularization plus kebab->snake: e.g. "/form-schemas" -> "form_schema_id"
function inferIdParam(base: string): string {
	const last = base.replace(/\/+$/, '').split('/').pop() ?? '';
	const singular = last.endsWith('ies') ? last.slice(0, -3) + 'y' : last.endsWith('s') ? last.slice(0, -1) : last;
	const snake = singular.replace(/-([a-z])/g, (_, c) => `_${c}`);
	return `${snake}_id`;
}

// const _stores = $state<Record<string, Record<Id, any>>>({});

export abstract class Repo<
	TStore extends { id: Id },
	TGet = TStore,
	TCreate = Partial<TStore>,
	TPatch = Partial<TStore>,
	ListParams = unknown
> {
	constructor(
		public readonly key: string,
		private readonly toStore: (remote: TGet) => TStore = (x) => x as unknown as TStore
	) {}

	public store = $state<Record<string, TStore>>({});

	// Protected hooks for subclasses to override
	protected abstract get basePath(): string;

	protected get idParam(): string {
		return inferIdParam(this.basePath);
	}

	protected get capabilities(): { 
		list?: boolean; 
		get?: boolean; 
		create?: boolean; 
		update?: boolean; 
		delete?: boolean;
	} {
		return { list: true, get: true, create: true, update: true, delete: true };
	}

	// Optional serialization hooks
	protected toCreateBody(body: TCreate): unknown {
		return body;
	}

	protected toUpdateBody(body: TPatch): unknown {
		return body;
	}

	// Remote operations - can be overridden by subclasses
	protected async remoteList(params?: ListParams): Promise<TGet[]> {
		const { api } = await import('../api/client');
		const res = await api.GET(this.basePath as any);
		return (res.data as TGet[]) ?? [];
	}

	protected async remoteGet(id: Id): Promise<TGet> {
		const { api } = await import('../api/client');
		const itemPath = `${this.basePath}/{${this.idParam}}`;
		const res = await api.GET(itemPath as any, { 
			params: { path: { [this.idParam]: Number(id) } } as any 
		});
		if (!res.data) throw new Error('No data');
		return res.data as TGet;
	}

	protected async remoteCreate(body: TCreate): Promise<TGet> {
		const { api } = await import('../api/client');
		const res = await api.POST(this.basePath as any, { 
			body: this.toCreateBody(body) 
		} as any);
		if (!res.data) throw new Error('No data');
		return res.data as TGet;
	}

	protected async remoteUpdate(id: Id, body: TPatch): Promise<TGet> {
		const { api } = await import('../api/client');
		const itemPath = `${this.basePath}/{${this.idParam}}`;
		const res = await api.PATCH(itemPath as any, { 
			params: { path: { [this.idParam]: Number(id) } } as any, 
			body: this.toUpdateBody(body) 
		} as any);
		if (!res.data) throw new Error('No data');
		return res.data as TGet;
	}

	protected async remoteDelete(id: Id): Promise<void> {
		const { api } = await import('../api/client');
		const itemPath = `${this.basePath}/{${this.idParam}}`;
		await api.DELETE(itemPath as any, { 
			params: { path: { [this.idParam]: Number(id) } } as any 
		});
	}

	

	all(): TStore[] {
		return Object.values(this.store);
	}

	get(id: Id): TStore | undefined {
		return this.store[id];
	}

	upsert(remote: TGet): Row<TStore, TGet, TCreate, TPatch, ListParams> {
		const s = this.toStore(remote);
		this.store[s.id] = s;
		return new Row<TStore, TGet, TCreate, TPatch, ListParams>(this, s.id);
	}

	deleteLocal(id: Id): void {
		delete this.store[id];
	}

	wrap(id: Id): Row<TStore, TGet, TCreate, TPatch, ListParams> {
		if (!(id in this.store)) throw new Error(`No ${this.key}#${String(id)}`);
		return new Row<TStore, TGet, TCreate, TPatch, ListParams>(this, id);
	}

	ingest(list: TGet[]): void {
		for (const r of list) {
			const s = this.toStore(r);
			this.store[s.id] = s;
		}
	}

	async fetchAll(params?: ListParams): Promise<void> {
		if (!this.capabilities.list) return;
		const list = await this.remoteList(params);
		this.ingest(list);
	}

	async fetchOne(id: Id): Promise<Row<TStore, TGet, TCreate, TPatch, ListParams>> {
		if (!this.capabilities.get) throw new Error('Get operation not supported');
		const row = await this.remoteGet(id);
		return this.upsert(row);
	}

	async create(body: TCreate): Promise<Row<TStore, TGet, TCreate, TPatch, ListParams>> {
		if (!this.capabilities.create) throw new Error('Create operation not supported');
		const created = await this.remoteCreate(body);
		return this.upsert(created);
	}

	can(op: 'list' | 'get' | 'create' | 'update' | 'delete'): boolean {
		return Boolean(this.capabilities[op]);
	}
}

export class Row<TStore extends { id: Id }, TGet, TCreate, TPatch, ListParams> {
	constructor(private repo: Repo<TStore, TGet, TCreate, TPatch, ListParams>, public readonly id: Id) {}

	get data(): TStore {
		const row = this.repo.get(this.id);
		if (!row) throw new Error(`Missing row ${String(this.id)}`);
		return row;
	}

	// Option A: make Row itself a store (usable as `$row` in Svelte)
	subscribe(run: (value: TStore) => void): () => void {
		run(this.data);
		const stop = $effect(() => {
			// row-level dependency: rerun on replace/updateLocal
			const _ = this.repo.store[this.id];
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
		this.repo.store[this.id] = { ...this.repo.store[this.id], ...patch };
		return this.data;
	}

	replace(next: TStore): TStore {
		this.repo.store[this.id] = next;
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
		if (!this.repo.can('update')) throw new Error('Update operation not supported');
		const updated = await (this.repo as any).remoteUpdate(this.id, (patch ?? (this.data as unknown as TPatch)));
		const stored = (this.repo as any).toStore(updated as unknown as TGet);
		this.replace(stored);
		return stored;
	}

	async destroy(): Promise<void> {
		if (!this.repo.can('delete')) throw new Error('Delete operation not supported');
		await (this.repo as any).remoteDelete(this.id);
		this.deleteLocal();
	}
}
