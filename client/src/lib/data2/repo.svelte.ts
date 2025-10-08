import { SvelteMap } from 'svelte/reactivity';

export type Id = string | number;

/**
 * Global registry pattern - allows items to access other repos without circular deps
 */
export abstract class GlobalRepos {
	static instance: GlobalRepos;
	
	// Subclass should declare all repo properties
	abstract instances: Repo<any, any>;
	abstract studies: Repo<any, any>;
	abstract series: Repo<any, any>;
	abstract tags: Repo<any, any>;
	abstract features: Repo<any, any>;
	abstract formSchemas: Repo<any, any>;
	abstract segmentations: Repo<any, any>;
	abstract modelSegmentations: Repo<any, any>;
	abstract formAnnotations: Repo<any, any>;
}

/**
 * Base class all repo items inherit from
 * - Holds reactive data
 * - Provides access to global repos
 * - Supports immutable updates
 */
export abstract class RepoItem<TData extends { id: Id }> {
	protected _data = $state<TData>() as TData;
	
	constructor(data: TData) {
		this._data = data;
	}
	
	get id(): Id {
		return this._data.id;
	}
	
	// Access to global repos via static singleton
	protected get repos(): GlobalRepos {
		return GlobalRepos.instance;
	}
	
	// Internal method for repo to update data (keeps immutability)
	_replaceData(newData: TData): void {
		this._data = newData;
	}
	
	// Optimistic local update (immutable pattern)
	updateLocal(patch: Partial<TData>): void {
		this._data = { ...this._data, ...patch };
	}
	
	// Save changes to server
	async save(patch?: Partial<TData>): Promise<void> {
		// Subclasses can override if they need custom save logic
		throw new Error('save() not implemented - use repo-specific methods');
	}
	
	// Delete this item
	async delete(): Promise<void> {
		throw new Error('delete() not implemented - use repo-specific methods');
	}
	
	// Refresh from server
	async refresh(): Promise<void> {
		throw new Error('refresh() not implemented - use repo-specific methods');
	}
}

/**
 * Simple reactive repository using SvelteMap
 * - Automatic reactivity from SvelteMap
 * - Items are class instances with methods
 * - Type-safe create/patch operations
 */
export class Repo<
	TData extends { id: Id },
	TItem extends RepoItem<TData>,
	TCreate = Partial<TData>,
	TPatch = Partial<TData>
> {
	// SvelteMap provides reactivity automatically!
	items = new SvelteMap<Id, TItem>();
	
	constructor(
		public readonly endpoint: string,
		private ItemClass: new (data: TData) => TItem
	) {}
	
	// Simple getters
	get all(): TItem[] {
		return Array.from(this.items.values());
	}
	
	get(id: Id): TItem | undefined {
		return this.items.get(id);  // Reactive!
	}
	
	has(id: Id): boolean {
		return this.items.has(id);
	}
	
	// Upsert: create instance or update existing (immutable data pattern)
	upsert(data: TData): TItem {
		const existing = this.items.get(data.id);
		if (existing) {
			existing._replaceData(data);  // Immutable update
			return existing;
		}
		const item = new this.ItemClass(data);
		this.items.set(data.id, item);  // Reactive!
		return item;
	}
	
	// Bulk import
	ingest(dataArray: TData[]): void {
		for (const data of dataArray) {
			this.upsert(data);
		}
		// No need for reassignment tricks - SvelteMap handles reactivity!
	}
	
	remove(id: Id): void {
		this.items.delete(id);  // Reactive!
	}
	
	clear(): void {
		this.items.clear();
	}
	
	// Helper to compute endpoint parameter name
	protected get idParam(): string {
		const last = this.endpoint.replace(/\/+$/, '').split('/').pop() ?? '';
		const singular = last.endsWith('ies') 
			? last.slice(0, -3) + 'y' 
			: last.endsWith('s') 
			? last.slice(0, -1) 
			: last;
		const snake = singular.replace(/-([a-z])/g, (_, c) => `_${c}`);
		return `${snake}_id`;
	}
	
	// API methods with proper typing
	async fetchAll(params?: Record<string, any>): Promise<TItem[]> {
		const { api } = await import('../api/client');
		const res = await api.GET(this.endpoint as any, {
			params: { query: params ?? {} } as any
		});
		this.ingest((res.data as TData[]) ?? []);
		return this.all;
	}
	
	async fetchOne(id: Id, query?: Record<string, any>): Promise<TItem> {
		const { api } = await import('../api/client');
		const res = await api.GET(`${this.endpoint}/{${this.idParam}}` as any, {
			params: { 
				path: { [this.idParam]: Number(id) },
				query: query ?? {}
			} as any
		});
		if (!res.data) throw new Error('No data');
		return this.upsert(res.data as TData);
	}
	
	async create(body: TCreate): Promise<TItem> {
		const { api } = await import('../api/client');
		const res = await api.POST(this.endpoint as any, { body } as any);
		if (!res.data) throw new Error('No data');
		return this.upsert(res.data as TData);
	}
	
	async update(id: Id, body: TPatch): Promise<TItem> {
		const { api } = await import('../api/client');
		const res = await api.PATCH(`${this.endpoint}/{${this.idParam}}` as any, {
			params: { path: { [this.idParam]: Number(id) } } as any,
			body: body as any
		});
		if (!res.data) throw new Error('No data');
		return this.upsert(res.data as TData);
	}
	
	async delete(id: Id): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE(`${this.endpoint}/{${this.idParam}}` as any, {
			params: { path: { [this.idParam]: Number(id) } } as any
		});
		this.remove(id);
	}
}

