import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import type { InstanceMeta, SearchCondition as SearchConditionT, SearchQuery, SignatureField as SignatureFieldT, StudySearchCondition, StudySearchQuery } from '../../types/openapi_types';
import { getInstancesSignature, getStudiesSignature, InstancesRepo, searchStudies, StudiesRepo } from '../data/repos.svelte';

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

    StudiesRepo = new StudiesRepo('studies');

    InstanceRepo = new InstancesRepo('instances');

    thumbnailSize: number = $state(6);

    // Derived: depends on queryMode + signatures
    activeSignature: SignatureField[] = $derived(
        this.queryMode === 'instances' ? this.instancesSignature : this.studiesSignature
    );

    // Derived: selected instances from repo
    selectedInstances = $derived(
        this.selectedIds
            .map(id => this.InstanceRepo.store[id])
            .filter((x): x is NonNullable<typeof x> => Boolean(x))
    );

    toggleFilterMode = () => {
        this.filterMode = this.filterMode === 'basic' ? 'advanced' : 'basic';
    };

    // Helper to get allowed values (returns [] if type marker)
    getValueOptions(fieldName: string): string[] {
        const f = this.activeSignature.find(s => s.name === fieldName);
        return Array.isArray(f?.values) ? (f!.values as string[]) : [];
    }

    // Load both signatures
    loadSignatures = async () => {
        this.loading = true;
        try {
            const [inst, stud] = await Promise.all([getInstancesSignature(), getStudiesSignature()]);
            this.instancesSignature = inst ?? [];
            this.studiesSignature = stud ?? [];
        } finally {
            this.loading = false;
        }
    }

    // Reset state when queryMode changes
    resetForQueryModeChange = (queryMode: QueryMode) => {
        this.advancedConditions = [];
        this.basicCondition = null;

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

        this.InstanceRepo.clear();
        this.StudiesRepo.clear();
    }

    // Compatibility method for search with current conditions
    search = async () => {
        const query =
            this.filterMode === 'advanced'
                ? this.advancedConditions
                : (this.basicCondition ? [this.basicCondition] : []);

        if (!query.length) return;

        return this.fetch(query);
    }

    // Method to load conditions from external source (like URL)
    loadConditions = (conds: Condition[]) => {
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

    fetch = async (query: Condition[]) => {
        if (!query.length) {
            return;
        }

        // persist conditions for pagination
        this.advancedConditions = query;

        // reflect in URL
        this.updateURL(query);

        this.InstanceRepo.clear()
        this.StudiesRepo.clear()
        this.loading = true;

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
        const baseBody = {
            conditions: query,
            limit: this.limit,
            page: this.page,
            order_by: this.sortBy,
            order: this.sortDirection ?? 'ASC',
            include_count: true
        };

        if (this.queryMode === 'instances') {
            return await InstancesRepo.search(baseBody as SearchQuery);
        } else {
            return await searchStudies({
                ...baseBody,
                conditions: query as unknown as StudySearchCondition[]
            } as StudySearchQuery);
        }
    }

    private processSearchResults(res: any) {
        // Ingest data into repositories
        this.StudiesRepo.ingest(res.studies ?? []);
        this.InstanceRepo.ingest(res.instances as any[] ?? []);

        // Update result metadata
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
        const get_date = (studyId: number) => {
            return new Date(this.StudiesRepo.object(studyId)!.$.date);
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
        const encodedVariable = encodeURIComponent(condition.variable);
        const encodedOperator = encodeURIComponent(condition.operator);
        const encodedValue = encodeURIComponent(serializeValue(condition.value ?? null));
        return `${encodedVariable}:${encodedOperator}:${encodedValue}`;
    }).join(';');
}

export function decodeConditions(urlString: string): Condition[] {
    if (urlString === '') return [];
    return urlString.split(';').map((conditionString) => {
        const [variable, operator, value] = conditionString.split(':');
        return {
            variable: decodeURIComponent(variable) as Condition['variable'],
            operator: decodeURIComponent(operator) as Condition['operator'],
            value: deserializeValue(value)
        } as Condition;
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