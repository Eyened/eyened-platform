import { browser } from '$app/environment';
import { goto } from '$app/navigation';


import { ingestInstanceMetas, ingestInstances, ingestStudies, instanceMetas, instances, studies } from '$lib/data/stores.svelte';
import type { InstanceGET, InstanceMeta, SearchCondition as SearchConditionT, SearchQuery, SignatureField as SignatureFieldT, StudyGET, StudySearchCondition, StudySearchQuery } from '../../types/openapi_types';

export type QueryMode = 'studies' | 'instances';
export type DisplayMode = 'instance' | 'study';
export type FilterMode = 'basic' | 'advanced';

export type Condition = SearchConditionT;
export type SignatureField = SignatureFieldT;
export type InstancesSortBy = SearchQuery['order_by'];
export type StudiesSortBy = StudySearchQuery['order_by'];
export type SortDirection = 'ASC' | 'DESC';


export class BrowserContext {

    // Default smallest per current mode
    getDefaultLimit(): number {
        return (this.queryMode === 'instances' && this.displayMode === 'instance') ? 100 : 10;
    }

    limitOptionsStudies = [10, 20, 30, 40, 50];
    limitOptionsInstances = [100, 200, 500, 1000];

    selectedIds: number[] = $state([]);
    queryMode: QueryMode = $state('studies');
    displayMode: DisplayMode = $state('study');
    loading: boolean = $state(false);
    filterMode: FilterMode = $state('basic');

    page: number = $state(0);
    limit: number = $state(10);
    count: number = $state(0);
    sortBy: InstancesSortBy | StudiesSortBy = $state('Study Date');
    sortDirection: SortDirection = $state('ASC');

    resultIds: Set<number> = $state(new Set());

    // NEW: ordered arrays for rendering
    orderedInstanceIds: number[] = $state([]);
    orderedStudyIds: number[] = $state([]);


    // renamed
    advancedConditions: Condition[] = $state([]);

    // new
    basicCondition: Condition | null = $state(null);

    // Signature state for dynamic filters
    instancesSignature: SignatureField[] = $state([]);
    studiesSignature: SignatureField[] = $state([]);

    thumbnailSize: string = $state('8em');

    // Derived: depends on queryMode + signatures
    activeSignature: SignatureField[] = $derived(
        this.queryMode === 'instances' ? this.instancesSignature : this.studiesSignature
    );

	selectedInstances = $derived(
		this.selectedIds
			.map(id => instanceMetas.get(id))
			.filter((x): x is InstanceMeta => x !== undefined)
	);

	// Derived: ordered instances for rendering
	orderedInstances = $derived(
	    this.orderedInstanceIds
		.map(id => instances.get(id) ?? instanceMetas.get(id))
		.filter((x): x is InstanceGET | InstanceMeta => x !== undefined)
);

	// Derived: ordered studies for rendering
	orderedStudies = $derived(
		this.orderedStudyIds
			.map(id => studies.get(id))
			.filter((x): x is StudyGET => x !== undefined)
	);

    toggleFilterMode() {
        this.filterMode = this.filterMode === 'basic' ? 'advanced' : 'basic';
    };

    // Helper to get allowed values (returns [] if type marker)
    getValueOptions(fieldName: string): string[] {
        const f = this.activeSignature.find(s => s.name === fieldName);
        return Array.isArray(f?.values) ? (f!.values as string[]) : [];
    }

    // Load both signatures
    async loadSignatures() {
        this.loading = true;
        try {
            const { api } = await import('../api/client');
            const [instRes, studRes] = await Promise.all([
                api.GET('/instances/search/signature', {}),
                api.GET('/studies/search/signature', {})
            ]);
            this.instancesSignature = (instRes.data ?? []) as SignatureField[];
            this.studiesSignature = (studRes.data ?? []) as SignatureField[];
        } finally {
            this.loading = false;
        }
    }
    
    // Refresh signatures (e.g., after creating/modifying tags)
    async refreshSignatures() {
        const { api } = await import('../api/client');
        const [instRes, studRes] = await Promise.all([
            api.GET('/instances/search/signature', {}),
            api.GET('/studies/search/signature', {})
        ]);
        this.instancesSignature = (instRes.data ?? []) as SignatureField[];
        this.studiesSignature = (studRes.data ?? []) as SignatureField[];
    }


    // Reset state when queryMode changes
    async resetForQueryModeChange(queryMode: QueryMode) {
        // Keep current conditions - they may work with both modes
        const currentConditions = this.filterMode === 'advanced'
            ? this.advancedConditions
            : (this.basicCondition ? [this.basicCondition] : []);

        this.page = 0;
        this.limit = this.getDefaultLimit();
        this.count = 0;

        this.sortBy = 'Study Date';
        this.sortDirection = 'ASC';

        this.resultIds = new Set();
        this.orderedInstanceIds = [];
        this.orderedStudyIds = [];
        this.selectedIds = [];

        if (queryMode == 'instances') {
            this.displayMode = 'instance';
            this.limit = this.limitOptionsInstances[0];
        } else {
            this.displayMode = 'study';
            this.limit = this.limitOptionsStudies[0];
        }

        // Auto-search with previous conditions if we had any
        if (currentConditions.length > 0) {
            await this.fetch(currentConditions);
        }
    }

    // Compatibility method for search with current conditions
    async search() {
        const query =
            this.filterMode === 'advanced'
                ? this.advancedConditions
                : (this.basicCondition ? [this.basicCondition] : []);

        if (!query.length) return;

        return this.fetch(query);
    }

    // Method to load conditions from external source (like URL)
    loadConditions(conds: Condition[]) {
        // Preserve legacy callers; default these into advanced
        this.advancedConditions = conds ?? [];
        // If it looks like a single basic condition, also set basic
        this.basicCondition = conds?.length === 1 ? conds[0] : this.basicCondition;
    }

    toggleInstance(instance: InstanceMeta) {
        const i = this.selectedIds.indexOf(instance.id);
        if (i !== -1) {
            this.selectedIds.splice(i, 1);
        } else {
            this.selectedIds.push(instance.id);
        }
    }

    async fetch(query: Condition[], updateUrl: boolean = true) {
        if (!query.length) {
            return;
        }

        // persist conditions for pagination
        this.advancedConditions = query;

        // reflect in URL
        if (updateUrl) {
            this.updateURL(query);
        }

        this.loading = true;

        // Clear selection when performing new search
        this.selectedIds = [];

        // Repos are global and persistent - search results are added via upsert
        // resultIds will track which items are current search results

        try {
            const res = await this.executeSearch(query);
            this.processSearchResults(res);
            return res;
        } finally {
            this.loading = false;
        }
    }

    private updateURL(query: Condition[]) {
        const params = new URLSearchParams();
        params.set('page', this.page.toString());
        params.set('limit', this.limit.toString());
        params.set('conditions', encodeConditions(query));
        params.set('order_by', String(this.sortBy));
        params.set('order', this.sortDirection);
        params.set('queryMode', this.queryMode);
        params.set('displayMode', this.displayMode);
        params.set('filterMode', this.filterMode);
        goto(`?${params.toString()}`);
    }

    private async executeSearch(query: Condition[]) {
        const { api } = await import('../api/client');
        const baseBody = {
            conditions: query,
            limit: this.limit,
            page: this.page,
            order_by: this.sortBy,
            order: this.sortDirection ?? 'ASC',
            include_count: true
        };

        if (this.queryMode === 'instances') {
            const res = await api.POST('/instances/search', { body: baseBody as SearchQuery });
            return res.data;
        } else {
            const res = await api.POST('/studies/search', {
                body: {
                    ...baseBody,
                    conditions: query as unknown as StudySearchCondition[]
                } as StudySearchQuery
            });
            return res.data;
        }
    }

	private processSearchResults(res: any) {
		// Add/update search results in GLOBAL repos
		ingestStudies(res.studies ?? []);
		
		// Important: Instance type depends on query mode!
		if (this.queryMode === 'instances') {
			// SearchResponse has instances: InstanceGET[] (full data)
			ingestInstances(res.instances ?? []);
		} else {
			// StudySearchResponse has instances: InstanceMeta[] (lightweight references)
			ingestInstanceMetas(res.instances ?? []);
		}

		// Track which items are current search results
		this.resultIds = new Set(res.result_ids ?? []);
		this.count = res.count ?? 0;

		// Set ordered IDs based on query mode
		let studyIds;
		if (this.queryMode === 'instances') {
			this.orderedInstanceIds = res.result_ids ?? [];
			studyIds = (res.studies ?? []).map((s: any) => s.id);
		} else {
			studyIds = res.result_ids ?? [];
			this.orderedInstanceIds = [];
		}

		// Sort studies by date
		const get_date = (studyId: number) => {
			const study = studies.get(studyId);
			return study ? new Date(study.date).getTime() : 0;
		}
		this.orderedStudyIds = studyIds.sort((a: number, b: number) => get_date(b) - get_date(a));
	}

    openTab(instances: number[]) {
        const suffix_string = `?instances=${instances}`;
        const url = `${window.location.origin}/view${suffix_string}`;
        window.open(url, '_blank')?.focus();
    }
}

// Encoding helpers for URL round-trip
function serializeValue(value: string | number | string[] | null): string {
    // JSON string; do NOT pre-encode elements; callers will URI-encode once
    return JSON.stringify(value);
}

function deserializeValue(encoded: string): string | number | string[] | null {
    // First-level decode of the whole JSON payload
    const raw = decodeURIComponent(encoded);
    return JSON.parse(raw);

}

export function encodeConditions(conditions: Condition[]): string {
    return conditions.map((condition) => {
        const encodedVariable = encodeURIComponent((condition as any).variable);
        const encodedOperator = encodeURIComponent((condition as any).operator);
        const encodedValue = encodeURIComponent(serializeValue((condition as any).value ?? null));
        const encodedType = encodeURIComponent((condition as any).type ?? 'default');
        const encodedModel = encodeURIComponent(((condition as any).type === 'attribute' ? (condition as any).model ?? '' : ''));
        return `${encodedVariable}:${encodedOperator}:${encodedValue}:${encodedType}:${encodedModel}`;
    }).join(';');
}

export function decodeConditions(urlString: string): Condition[] {
    if (urlString === '') return [];
    return urlString.split(';').map((conditionString) => {
        const parts = conditionString.split(':');
        const [v, o, val, t, m] = parts;
        const variable = decodeURIComponent(v);
        const operator = decodeURIComponent(o) as Condition['operator'];
        const value = deserializeValue(val);
        const type = t ? (decodeURIComponent(t) as any) : 'default';
        const model = m ? decodeURIComponent(m) : undefined;
        if (type === 'attribute') {
            return { type: 'attribute', variable, operator: operator as any, value, model } as any;
        }
        return { type: 'default', variable: variable as any, operator: operator as any, value } as any;
    });
}

// URL param helpers for component compatibility
export function getSearchParams(): URLSearchParams {
    const src = browser ? window.location.search : '';
    return new URLSearchParams(src);
}

export async function setParam(key: string, value: string | null) {
    const params = getSearchParams();
    params.delete(key);
    if (value !== null && value !== '') params.set(key, value);
    await goto(`?${params.toString()}`);
}

export async function removeParam(key: string, value?: string) {
    const params = getSearchParams();
    if (value === undefined) {
        params.delete(key);
    } else {
        const values = params.getAll(key).filter((v) => v !== value);
        params.delete(key);
        values.forEach((v) => params.append(key, v));
    }
    await goto(`?${params.toString()}`);
}

export async function toggleParam(key: string, value: string) {
    const params = getSearchParams();
    const values = new Set(params.getAll(key));
    if (values.has(value)) {
        values.delete(value);
    } else {
        values.add(value);
    }
    params.delete(key);
    Array.from(values).forEach((v) => params.append(key, v));
    await goto(`?${params.toString()}`);
}