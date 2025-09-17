
export type Id = string | number;

// Helper: naive singularization plus kebab->snake: e.g. "/form-schemas" -> "form_schema_id"
export function inferIdParam(base: string): string {
	const last = base.replace(/\/+$/, '').split('/').pop() ?? '';
	const singular = last.endsWith('ies') ? last.slice(0, -3) + 'y' : last.endsWith('s') ? last.slice(0, -1) : last;
	const snake = singular.replace(/-([a-z])/g, (_, c) => `_${c}`);
	return `${snake}_id`;
}

export abstract class Repo<
	TGet extends { id: Id },
	TCreate = Partial<TGet>,
	TPatch = Partial<TGet>,
	ListParams = unknown,
	TDataObject extends DataObject<TGet, TPatch> = DataObject<TGet, TPatch>
> {
	constructor(public readonly key: string) {}

	public store = $state<Record<Id, TGet>>({});

	public all = $derived(Object.values(this.store));

	// Protected hooks for subclasses to override
	protected abstract get basePath(): string;

	protected get idParam(): string {
		return inferIdParam(this.basePath);
	}

	// Optional object factory for subclasses
	protected createDataObject?(id: Id): TDataObject;

	public object(id: Id): TDataObject {
		return this.createDataObject ? this.createDataObject(id) : (new DataObject<TGet, TPatch>(this, id) as TDataObject);
	}

	// Optional serialization hooks
	protected toCreateBody(body: TCreate): unknown {
		return body;
	}

	protected toUpdateBody(body: TPatch): unknown {
		return body;
	}

	// Remote operations - can be overridden by subclasses, all return TGet
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

	get(id: Id): TGet | undefined {
		return this.store[id];
	}

	upsert(remote: TGet): void {
		this.store[remote.id] = remote;
	}

	deleteLocal(id: Id): void {
		delete this.store[id];
	}

	ingest(list: TGet[]): void {
		for (const r of list) {
			this.store[r.id] = r;
		}
		this.store = { ...this.store };
	}

	clear(): void {
		this.store = {};
	}

	async fetchAll(params?: ListParams): Promise<void> {
		const list = await this.remoteList(params);
		this.ingest(list);
	}

	async fetchOne(id: Id): Promise<DataObject<TGet, TPatch>> {
		const row = await this.remoteGet(id);
		this.upsert(row);
		return this.object(id);
	}

	async create(body: TCreate): Promise<DataObject<TGet, TPatch>> {
		const created = await this.remoteCreate(body);
		this.upsert(created);
		return this.object(created.id);
	}
}

export class DataObject<TGet extends { id: Id }, TPatch = Partial<TGet>> {
	// Make data reactive using $derived
	data: TGet | undefined;

	constructor(protected repo: Repo<TGet, any, TPatch, any, any>, public readonly id: Id) {
		this.data = $derived(this.repo.store[this.id] as TGet | undefined);
	}

	get required(): TGet {
		const d = this.data;
		if (!d) throw new Error(`Missing row ${String(this.id)}`);
		return d;
	}

	updateLocal(patch: Partial<TGet>): TGet | undefined {
		const curr = this.repo.store[this.id];
		if (!curr) return undefined;
		const next = { ...curr, ...patch } as TGet;
		this.repo.store[this.id] = next;
		return next;
	}

	replace(next: TGet): TGet {
		this.repo.store[this.id] = next;
		return next;
	}

	deleteLocal(): void {
		this.repo.deleteLocal(this.id);
	}

	async refresh(): Promise<TGet> {
		const obj = await this.repo.fetchOne(this.id);
		return (obj as DataObject<TGet, TPatch>).required;
	}

	async save(patch?: TPatch): Promise<TGet> {
		const updated = await (this.repo as any).remoteUpdate(this.id, (patch ?? (this.required as unknown as TPatch)));
		this.replace(updated as TGet);
		return updated as TGet;
	}

	async destroy(): Promise<void> {
		await (this.repo as any).remoteDelete(this.id);
		this.deleteLocal();
	}
}

export abstract class MetaObject<TMeta extends { id: Id }, TGet extends { id: Id }> {
	constructor(
		protected getRepo: Repo<TGet, any, any, any, DataObject<TGet>>,
		public readonly meta: Readonly<TMeta>
	) {}

	get id(): Id {
		return this.meta.id;
	}

	protected abstract get baseEndpoint(): string;

	protected get idParam(): string {
		return inferIdParam(this.baseEndpoint);
	}

	async fetch(): Promise<TGet> {
		const { api } = await import('../api/client');
		const path = `${this.baseEndpoint}/{${this.idParam}}`;
		const res = await api.GET(path as any, {
			params: { path: { [this.idParam]: Number(this.id) } } as any
		});
		if (!res.data) throw new Error('No data');
		return res.data as TGet;
	}

	async augment(): Promise<DataObject<TGet>> {
		const full = await this.fetch();
		this.getRepo.upsert(full);
		return this.getRepo.object(this.id);
	}
}
