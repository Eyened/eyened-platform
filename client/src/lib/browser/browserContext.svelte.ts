import { goto } from '$app/navigation';
import type { Writable } from 'svelte/store';
import { get, writable } from 'svelte/store';
import type { components } from '../../types/openapi';
import { InstanceMetasLocalRepo, InstancesRepo, searchStudies, StudiesLocalRepo } from '../data/repos.svelte';

export type QueryMode = 'studies' | 'instances';
export type DisplayMode = 'instance' | 'partialStudy' | 'fullStudy';

type Instance = components['schemas']['InstanceGET'];
export type Study = components['schemas']['StudyGET'];
export type InstanceMeta = components['schemas']['InstanceMeta'];
export type Condition = components['schemas']['SearchCondition'];



export class BrowserContext {

	queryMode = writable<QueryMode>('instances');
	displayMode = writable<'instance' | 'partialStudy' | 'fullStudy'>('instance');
	loading = writable(false);

	page = writable(0);
	limit = writable(10);
	count = writable(0);
	sort = writable<string|undefined>(undefined);
	sortDirection = writable<'ASC'|'DESC'|undefined>('ASC');

	resultIds = writable<Set<number>>(new Set());

	// normalized API conditions
	conditions: Writable<Condition[]> = writable([]);

	StudiesRepo = new StudiesLocalRepo('studies');

	InstanceRepo = new InstanceMetasLocalRepo('instance-metas');

	thumbnailSize: number = $state(6);

	loadConditions = (conditions: Condition[]) => {
		this.conditions.set(conditions ?? []);
	};

	search = async () => {
		this.page.set(0);
		return await this.fetch(get(this.conditions));
	};

	fetch = async (query: Condition[]) => {
		if (!query.length) {
			return;
		}

		// reflect in URL
		const params = new URLSearchParams();
		const page = get(this.page);
		const limit = get(this.limit);
		params.set('page', page.toString());
		params.set('limit', limit.toString());
		params.set('conditions', encodeConditions(query));
		goto(`?${params.toString()}`);

		this.loading.set(true);
		try {
			let result_ids: number[] = [];
			let count = 0;

			if (get(this.queryMode) === 'instances') {
				const body: components['schemas']['SearchQuery'] = {
					conditions: query,
					limit,
					page,
					order_by: undefined,
					order: (get(this.sortDirection) ?? 'ASC'),
					include_count: true
				};
				

				const res = await InstancesRepo.search(body);
				InstancesRepo.ingest(res.instances ?? []);
				result_ids = res.result_ids ?? [];
				count = res.count ?? 0;
				this.resultIds.set(new Set(result_ids));
				this.count.set(count);
				return res;
			} else {
				const body: components['schemas']['StudySearchQuery'] = {
					conditions: query as unknown as components['schemas']['StudySearchCondition'][],
					limit,
					page,
					order_by: undefined,
					order: (get(this.sortDirection) ?? 'ASC'),
					include_count: true
				};

				const res = await searchStudies(body);
				this.StudiesRepo.ingest(res.studies ?? []);
				this.InstanceRepo.ingest(res.instances ?? []);
				result_ids = res.result_ids ?? [];
				count = res.count ?? 0;
				this.resultIds.set(new Set(result_ids));
				this.count.set(count);
				return res;
			}
		} finally {
			this.loading.set(false);
		}
	}

	openTab(instances: number[]) {

        const suffix_string = `?instances=${instances}`;
        const url = `${window.location.origin}/view${suffix_string}`;
        window.open(url, '_blank')?.focus();
    }
}

// Encoding helpers for URL round-trip
function encodeValue(value: string | number | null): string {
	return value === null || value === undefined ? '' : value.toString();
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