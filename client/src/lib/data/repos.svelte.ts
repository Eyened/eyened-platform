import type { components } from '../../types/openapi';
import type {
	FeatureGET,
	FeaturePATCH,
	FeaturePUT,
	FormAnnotationGET, FormAnnotationPUT,
	FormSchemaGET,
	InstanceGET,
	ModelSegmentationGET,
	SearchQuery, SearchResponse,
	SegmentationGET, SegmentationPATCH,
	SeriesGET,
	StudyGET,
	SubTaskGET, SubTaskWithImagesGET, SubTasksResponse, SubTasksWithImagesResponse,
	TagGET,
	TagPATCH,
	TagPUT,
	TaskGET,
	TaskPATCH,
	TaskPUT
} from '../../types/openapi_types';
import { api } from '../api/client';
import { Repo } from './datamodel.svelte';
import { FeatureObject, FormAnnotationObject, FormSchemaObject, InstanceObject, ModelSegmentationObject, SegmentationObject, SeriesObject, StudyObject, SubTaskObject, TagObject, TaskObject } from './objects.svelte';

// Type aliases for backward compatibility
export type Tag = TagGET;

export class TasksRepo extends Repo<TaskGET, TaskPUT, TaskPATCH, unknown, TaskObject> {
	public static path = '/task';
	protected createDataObject(obj: TaskGET): TaskObject { return new TaskObject(obj, this); }
}

type SubTaskAny = SubTaskGET | SubTaskWithImagesGET;

export class SubTasksRepo extends Repo<SubTaskAny, never, Partial<SubTaskAny>, { task_id: number; with_images?: boolean; limit?: number; page?: number }, SubTaskObject> {
	public static path = '/subtasks';
	constructor(key: string) { super(key); }

	public paging = $state({ limit: 200, page: 0, count: 0 });

	protected createDataObject(obj: SubTaskAny): SubTaskObject { return new SubTaskObject(obj, this as any); }

	protected async remoteList(params?: { task_id: number; with_images?: boolean; limit?: number; page?: number }): Promise<SubTaskAny[]> {
		const { api } = await import('../api/client');
		if (!params?.task_id) throw new Error('task_id is required');
		const res = await api.GET('/subtasks' as any, {
			params: {
				query: {
					task_id: params.task_id,
					with_images: params?.with_images ?? true,
					limit: params?.limit ?? this.paging.limit,
					page: params?.page ?? this.paging.page
				}
			}
		});
		const data = (res.data ?? {}) as SubTasksWithImagesResponse | SubTasksResponse;
		if ('limit' in data && 'page' in data) this.paging = { limit: data.limit, page: data.page, count: (data as any).count ?? 0 };
		return data.subtasks ?? [];
	}
}

export class FeaturesRepo extends Repo<FeatureGET, FeaturePUT, FeaturePATCH, unknown, FeatureObject> {
	public static path = '/features';
	protected createDataObject(obj: FeatureGET): FeatureObject { return new FeatureObject(obj, this); }
}

export class TagsRepo extends Repo<TagGET, TagPUT, TagPATCH, unknown, TagObject> {
	public static path = '/tags';
	protected createDataObject(obj: TagGET): TagObject { return new TagObject(obj, this); }

	public studyTags = $derived(this.all.filter(t => t.tag_type === 'Study'));
	public imageInstanceTags = $derived(this.all.filter(t => t.tag_type === 'ImageInstance'));
	public formAnnotationTags = $derived(this.all.filter(t => t.tag_type === 'Annotation'));

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

export class InstancesRepo extends Repo<InstanceGET, never, never, unknown, InstanceObject> {
	public static path = '/instances';
	protected createDataObject(obj: InstanceGET): InstanceObject { return new InstanceObject(obj, this); }

	static async search(query: SearchQuery): Promise<SearchResponse> {
		const res = await api.POST('/instances/search', { body: query });
		if (!res.data) throw new Error('No data');
		return res.data as SearchResponse;
	}
}

export class StudiesRepo extends Repo<StudyGET, never, never, unknown, StudyObject> {
	public static path = '/studies';
	protected createDataObject(obj: StudyGET): StudyObject { return new StudyObject(obj, this); }
}

export class SeriesRepo extends Repo<SeriesGET, never, never, unknown, SeriesObject> {
	public static path = '/series';
	protected createDataObject(obj: SeriesGET): SeriesObject { return new SeriesObject(obj, this); }
}

export class SegmentationsRepo extends Repo<SegmentationGET, {}, SegmentationPATCH, unknown, SegmentationObject> {
	public static path = '/segmentations';
	protected createDataObject(obj: SegmentationGET): SegmentationObject { return new SegmentationObject(obj, this); }

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

export class ModelSegmentationsRepo extends Repo<ModelSegmentationGET, never, never, unknown, ModelSegmentationObject> {
	public static path = '/model-segmentations';
	protected createDataObject(obj: ModelSegmentationGET): ModelSegmentationObject { return new ModelSegmentationObject(obj, this); }

	async getData(segmentation_id: number, p?: { axis?: number; scan_nr?: number }) {
		const res = await api.GET('/model-segmentations/{segmentation_id}/data', {
			params: {
				path: { segmentation_id },
				query: { axis: p?.axis, scan_nr: p?.scan_nr }
			}
		});
		return res.data as unknown;
	}
}

export type FormAnnotationsListParams = { patient_id?: number; study_id?: number; image_instance_id?: number; form_schema_id?: number; sub_task_id?: number };

export class FormAnnotationsRepo extends Repo<FormAnnotationGET, FormAnnotationPUT, FormAnnotationPUT, FormAnnotationsListParams, FormAnnotationObject> {
	public static path = '/form-annotations';
	protected createDataObject(obj: FormAnnotationGET): FormAnnotationObject { return new FormAnnotationObject(obj, this); }

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

export class FormSchemasRepo extends Repo<FormSchemaGET, never, never, unknown, FormSchemaObject> {
	public static path = '/form-schemas';
	protected createDataObject(obj: FormSchemaGET): FormSchemaObject { return new FormSchemaObject(obj, this); }
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

// DefaultRepo wiring
InstanceObject.DefaultRepo = InstancesRepo;
StudyObject.DefaultRepo = StudiesRepo;
SeriesObject.DefaultRepo = SeriesRepo;
SegmentationObject.DefaultRepo = SegmentationsRepo;
FormAnnotationObject.DefaultRepo = FormAnnotationsRepo;
FormSchemaObject.DefaultRepo = FormSchemasRepo;
TagObject.DefaultRepo = TagsRepo;
TaskObject.DefaultRepo = TasksRepo;
FeatureObject.DefaultRepo = FeaturesRepo;

