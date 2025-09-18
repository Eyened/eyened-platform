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
	selection: number[] = $state([]);
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
        if (this.selection.includes(instance.id)) {
            this.selection.splice(this.selection.indexOf(instance.id), 1);
        } else {
            this.selection.push(instance.id);
        }
    }

	fetch = async (query: Condition[]) => {
		if (!query.length) {
			return;
		}

		// persist conditions for pagination
		this.advancedConditions = query;

		// reflect in URL
		const params = new URLSearchParams();
		const page = this.page;
		const limit = this.limit;
		params.set('page', page.toString());
		params.set('limit', limit.toString());
		params.set('conditions', encodeConditions(query));
		params.set('query', this.queryMode); // 'studies' | 'instances'
		params.set('order_by', String(this.sortBy));
		params.set('order', this.sortDirection);
		goto(`?${params.toString()}`);

		this.InstanceRepo.clear()
		this.StudiesRepo.clear()
		this.loading = true;
		try {
			let result_ids: number[] = [];
			let count = 0;

			if (this.queryMode === 'instances') {
				const body: SearchQuery = {
					conditions: query,
					limit,
					page,
					order_by: this.sortBy,
					order: this.sortDirection ?? 'ASC',
					include_count: true
				};
				

				const res = await InstancesRepo.search(body);
				this.StudiesRepo.ingest(res.studies ?? []);
				this.InstanceRepo.ingest(res.instances as any[] ?? []);
				result_ids = res.result_ids ?? [];
				count = res.count ?? 0;
				this.resultIds = new Set(result_ids);
				this.count = count;
				return res;
			} else {
				const body: StudySearchQuery = {
					conditions: query as unknown as StudySearchCondition[],
					limit,
					page,
					order_by: this.sortBy,
					order: this.sortDirection ?? 'ASC',
					include_count: true
				};

				const res = await searchStudies(body);
				this.StudiesRepo.ingest(res.studies ?? []);
				this.InstanceRepo.ingest(res.instances as any[] ?? []);
				result_ids = res.result_ids ?? [];
				count = res.count ?? 0;
				this.resultIds = new Set(result_ids);
				this.count = count;
				return res;
			}
		} finally {
			this.loading = false;
		}
	}

	openTab(instances: number[]) {

        const suffix_string = `?instances=${instances}`;
        const url = `${window.location.origin}/view${suffix_string}`;
        window.open(url, '_blank')?.focus();
    }
}

// Encoding helpers for URL round-trip
function encodeValue(value: string | number | string[] | null): string {
	if (value === null || value === undefined) return '';
	if (Array.isArray(value)) return value.map(v => encodeURIComponent(String(v))).join(',');
	return value.toString();
}

function decodeValue(value: string): string | number | null {
	if (value === '') return null;
	return isNaN(Number(value)) ? value : Number(value);
}

export function encodeConditions(conditions: Condition[]): string {
	const encodedConditions = conditions.map((condition) => {
		const encodedVariable = encodeURIComponent(condition.variable);
		const encodedOperator = encodeURIComponent(condition.operator);
		const encodedValue = encodeURIComponent(encodeValue(condition.value ?? null));
		return `${encodedVariable}:${encodedOperator}:${encodedValue}`;
	});
	return encodedConditions.join(';');
}

export function decodeConditions(urlString: string): Condition[] {
	if (urlString === '') return [];
	const conditions = urlString.split(';').map((conditionString) => {
		const [variable, operator, value] = conditionString.split(':');
		return {
			variable: decodeURIComponent(variable) as Condition['variable'],
			operator: decodeURIComponent(operator) as Condition['operator'],
			value: decodeValue(decodeURIComponent(value))
		} as Condition;
	});
	return conditions;
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