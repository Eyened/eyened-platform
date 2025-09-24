
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

	// Static helpers that concrete repos inherit
	static get idParam(): string {
		const p = (this as any).path as string;
		if (!p) throw new Error('Missing static path on Repo subclass');
		return inferIdParam(p);
	}

	static async remoteList<ListParams = unknown, T = unknown>(params?: ListParams): Promise<T[]> {
		const { api } = await import('../api/client');
		const res = await api.GET((this as any).path as any, { params: { query: (params as any) ?? {} } as any });
		return (res.data as T[]) ?? [];
	}

	static async remoteGet<T = unknown>(id: Id, query?: Record<string, any>): Promise<T> {
		const { api } = await import('../api/client');
		const itemPath = `${(this as any).path}/{${(this as any).idParam}}`;
		const res = await api.GET(itemPath as any, {
			params: { path: { [(this as any).idParam]: Number(id) }, query: (query ?? {}) } as any
		});
		if (!res.data) throw new Error('No data');
		return res.data as T;
	}

	static async remoteCreate<T = unknown, B = unknown>(body: B): Promise<T> {
		const { api } = await import('../api/client');
		const res = await api.POST((this as any).path as any, { body } as any);
		if (!res.data) throw new Error('No data');
		return res.data as T;
	}

	static async remoteUpdate<T = unknown, B = unknown>(id: Id, body: B): Promise<T> {
		const { api } = await import('../api/client');
		const itemPath = `${(this as any).path}/{${(this as any).idParam}}`;
		const res = await api.PATCH(itemPath as any, { params: { path: { [(this as any).idParam]: Number(id) } } as any, body } as any);
		if (!res.data) throw new Error('No data');
		return res.data as T;
	}

	static async remoteDelete(id: Id): Promise<void> {
		const { api } = await import('../api/client');
		const itemPath = `${(this as any).path}/{${(this as any).idParam}}`;
		await api.DELETE(itemPath as any, { params: { path: { [(this as any).idParam]: Number(id) } } as any });
	}

	// Protected hooks for subclasses to override or inherit
	protected get basePath(): string {
		return (this.constructor as any).path as string;
	}

	protected get idParam(): string {
		return inferIdParam(this.basePath);
	}

	// Optional object factory for subclasses (now takes a row)
	protected createDataObject?(obj: TGet): TDataObject;

	public object(id: Id): TDataObject {
		const found = this.get(id as Id);
		if (!found) throw new Error(`Missing row ${String(id)}`);
		return this.createDataObject ? this.createDataObject(found) : (new DataObject<TGet, TPatch>(found, this) as TDataObject);
	}

	// Optional serialization hooks
	protected toCreateBody(body: TCreate): unknown {
		return body;
	}

	protected toUpdateBody(body: TPatch): unknown {
		return body;
	}

	// Remote operations - delegate to static versions
	protected async remoteList(params?: ListParams): Promise<TGet[]> {
		return (this.constructor as typeof Repo).remoteList<ListParams, TGet>(params as any);
	}

	protected async remoteGet(id: Id, query?: Record<string, any>): Promise<TGet> {
		return (this.constructor as typeof Repo).remoteGet<TGet>(id, query);
	}

	protected async remoteCreate(body: TCreate): Promise<TGet> {
		return (this.constructor as typeof Repo).remoteCreate<TGet, TCreate>(this.toCreateBody(body) as any);
	}

	protected async remoteUpdate(id: Id, body: TPatch): Promise<TGet> {
		return (this.constructor as typeof Repo).remoteUpdate<TGet, TPatch>(id, this.toUpdateBody(body) as any);
	}

	protected async remoteDelete(id: Id): Promise<void> {
		return (this.constructor as typeof Repo).remoteDelete(id);
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

	async fetchOne(id: Id, query?: Record<string, any>): Promise<DataObject<TGet, TPatch>> {
		const row = await this.remoteGet(id, query);
		this.upsert(row);
		return this.object(row.id);
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
	$: TGet
	protected repo: Repo<TGet, any, TPatch, any, any> | undefined;
	public readonly id: Id;
	private _local: TGet | undefined = $state(undefined);

	constructor( obj: TGet, _repo?: Repo<TGet, any, TPatch, any, any>) {
		this.repo = _repo;
		this.id = obj.id;
		if (!this.repo) {
			this._local = obj;
		}
		this.data = $derived(this.repo ? this.repo.store[this.id] : this._local);
		this.$ = $derived(this.data as TGet);
	}

	// Static factory method to create instance from ID
	static async fromId<TGet>(this: (new (obj: TGet, repo?: any) => any) & { DefaultRepo: typeof Repo }, id: Id): Promise<InstanceType<typeof this>> {
		const RepoClass = (this as any).DefaultRepo as typeof Repo;
		if (!RepoClass) throw new Error('DefaultRepo not set on object class');
		const row = await RepoClass.remoteGet<TGet>(id);
		return new (this as any)(row) as InstanceType<typeof this>;
	}

	// get $(): TGet {
	// 	const d = this.data;
	// 	if (!d) throw new Error(`Missing row ${String(this.id)}`);
	// 	return d;
	// }

	updateLocal(patch: Partial<TGet>): TGet | undefined {
		if (this.repo) {
			const curr = this.repo.store[this.id];
			if (!curr) return undefined;
			const next = { ...curr, ...patch } as TGet;
			this.repo.store[this.id] = next;
			return next;
		}
		if (!this._local) return undefined;
		this._local = { ...this._local, ...patch } as TGet;
		return this._local;
	}

	replace(next: TGet): TGet {
		if (this.repo) {
			this.repo.store[this.id] = next;
			return next;
		}
		this._local = next;
		return next;
	}

	deleteLocal(): void {
		if (this.repo) {
			this.repo.deleteLocal(this.id);
			return;
		}
		this._local = undefined;
	}

	async refresh(): Promise<TGet> {
		if (this.repo) return (await this.repo.fetchOne(this.id)).$ as TGet;
		const RepoClass = (this.constructor as any).DefaultRepo as typeof Repo;
		const next = await RepoClass.remoteGet<TGet>(this.id);
		this._local = next;
		return next;
	}

	async save(patch?: TPatch): Promise<TGet> {
		if (this.repo) {
			const updated = await (this.repo as any).remoteUpdate(this.id, (patch ?? (this.$ as unknown as TPatch)));
			this.replace(updated as TGet);
			return updated as TGet;
		}
		const RepoClass = (this.constructor as any).DefaultRepo as typeof Repo;
		const updated = await RepoClass.remoteUpdate<TGet, TPatch>(this.id, (patch ?? (this.$ as unknown as TPatch)));
		this.replace(updated as TGet);
		return updated as TGet;
	}

	async destroy(): Promise<void> {
		if (this.repo) {
			await (this.repo as any).remoteDelete(this.id);
			this.deleteLocal();
			return;
		}
		const RepoClass = (this.constructor as any).DefaultRepo as typeof Repo;
		await RepoClass.remoteDelete(this.id);
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
