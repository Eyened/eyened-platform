import type { components } from '../../types/openapi';
import type {
	FeatureGET,
	FeaturePATCH,
	FeaturePUT,
	FormAnnotationGET, FormAnnotationPUT,
	InstanceGET, InstanceMeta, SearchQuery, SearchResponse,
	SegmentationGET, SegmentationPATCH,
	SeriesGET,
	StudyGET,
	TagGET,
	TagPATCH,
	TagPUT
} from '../../types/openapi_types';
import { api } from '../api/client';
import { Repo } from './datamodel.svelte';

// Type aliases for backward compatibility
export type Tag = TagGET;

export class TasksRepo extends Repo<FeatureGET, FeaturePUT, FeaturePATCH> {
	protected get basePath() { return '/task'; }
}

export class TagsRepo extends Repo<TagGET, TagPUT, TagPATCH> {
	protected get basePath() { return '/tags'; }

	async star(tag_id: number) {
		try {
			await api.POST('/tags/{tag_id}/star' as any, { params: { path: { tag_id } } as any });
		} catch {
			await fetch(`/api/tags/${tag_id}/star`, { method: 'POST', credentials: 'include' });
		}
	}

	async unstar(tag_id: number) {
		try {
			await api.DELETE('/tags/{tag_id}/star' as any, { params: { path: { tag_id } } as any });
		} catch {
			await fetch(`/api/tags/${tag_id}/star`, { method: 'DELETE', credentials: 'include' });
		}
	}
}

export class InstancesRepo extends Repo<InstanceGET, never, never> {
	protected get basePath() { return '/instances'; }

	async search(query: SearchQuery): Promise<SearchResponse> {
		const res = await api.POST('/instances/search', { body: query });
		if (!res.data) throw new Error('No data');
		return res.data as SearchResponse;
	}
}

export class StudiesRepo extends Repo<StudyGET, never, never> {
	protected get basePath() { return '/studies'; }
}

export class SeriesRepo extends Repo<SeriesGET, never, never> {
	protected get basePath() { return '/series'; }
}

export class SegmentationsRepo extends Repo<SegmentationGET, {}, SegmentationPATCH> {
	protected get basePath() { return '/segmentations'; }

	async getData(segmentation_id: number, p?: { axis?: number; scan_nr?: number }) {
		const res = await api.GET('/segmentations/{segmentation_id}/data', {
			params: {
				path: { segmentation_id },
				query: { axis: p?.axis, scan_nr: p?.scan_nr }
			}
		});
		return res.data as unknown;
	}

	async updateData(segmentation_id: number, p?: { axis?: number; scan_nr?: number }, body?: unknown) {
		const res = await api.PUT('/segmentations/{segmentation_id}/data', {
			params: {
				path: { segmentation_id },
				query: { axis: p?.axis, scan_nr: p?.scan_nr }
			},
			body: body as any
		});
		return res.data as unknown;
	}
}

export type FormAnnotationsListParams = { patient_id?: number; study_id?: number; image_instance_id?: number; form_schema_id?: number; sub_task_id?: number };

export class FormAnnotationsRepo extends Repo<FormAnnotationGET, FormAnnotationPUT, FormAnnotationPUT, FormAnnotationsListParams> {
	protected get basePath() { return '/form-annotations'; }

	protected async remoteList(filters?: FormAnnotationsListParams): Promise<FormAnnotationGET[]> {
		const res = await api.GET('/form-annotations', {
			params: { query: filters ?? {} }
		});
		return (res.data as FormAnnotationGET[]) ?? [];
	}

	async getValue(id: number) {
		const res = await api.GET('/form-annotations/{form_annotation_id}/value', {
			params: { path: { form_annotation_id: id } }
		});
		return res.data as unknown;
	}

	async setValue(id: number, value: unknown) {
		await api.PUT('/form-annotations/{form_annotation_id}/value', {
			params: { path: { form_annotation_id: id } },
			body: value as any
		});
	}
}

// Legacy functions and classes for backward compatibility during transition
export async function searchStudies(query: components['schemas']['StudySearchQuery']): Promise<components['schemas']['StudySearchResponse']> {
	const res = await api.POST('/studies/search', { body: query });
	if (!res.data) throw new Error('No data');
	return res.data as components['schemas']['StudySearchResponse'];
}

export async function getInstancesSignature(): Promise<components['schemas']['SignatureField'][]> {
	const res = await api.GET('/instances/search/signature', {});
	return (res.data ?? []) as components['schemas']['SignatureField'][];
}

export async function getStudiesSignature(): Promise<components['schemas']['SignatureField'][]> {
	const res = await api.GET('/studies/search/signature', {});
	return (res.data ?? []) as components['schemas']['SignatureField'][];
}

// Legacy local repos for backward compatibility during transition
export class StudiesLocalRepo extends Repo<StudyGET, never, never> {
	protected get basePath() { return '/studies'; }
}

export class InstanceMetasLocalRepo extends Repo<InstanceMeta, never, never> {
	protected get basePath() { return '/instances'; }
}

