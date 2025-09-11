import type { components } from '../../types/openapi';
import { api } from '../api/client';
import type { InstanceMeta, Study } from '../browser/browserContext.svelte';
import { Repo, type Id } from './datamodel.svelte';

// Tasks — full CRUD
export type Task = components['schemas']['TaskGET'];
type TaskCreate = components['schemas']['TaskPUT'];
type TaskPatch = components['schemas']['TaskPATCH'];

class TasksRepoClass extends Repo<Task, Task, TaskCreate, TaskPatch> {
	protected get basePath() { return '/task'; }
}
export const TasksRepo = new TasksRepoClass('tasks');

// Tags — list/create/patch/delete (no GET by id)
export type Tag = components['schemas']['TagGET'];
type TagCreate = components['schemas']['TagPUT'];
type TagPatch = components['schemas']['TagPATCH'];

class TagsRepoClass extends Repo<Tag, Tag, TagCreate, TagPatch> {
	protected get basePath() { return '/tags'; }
	protected get capabilities() { return { list: true, create: true, update: true, delete: true, get: false }; }
}
export const TagsRepo = new TagsRepoClass('tags');

// Features — create/get/patch/delete (no list)
export type Feature = components['schemas']['FeatureGET'];
type FeatureCreate = components['schemas']['FeaturePUT'];
type FeaturePatch = components['schemas']['FeaturePATCH'];

class FeaturesRepoClass extends Repo<Feature, Feature, FeatureCreate, FeaturePatch> {
	protected get basePath() { return '/features'; }
	protected get capabilities() { return { list: false, get: true, create: true, update: true, delete: true }; }
}
export const FeaturesRepo = new FeaturesRepoClass('features');

// Instances — GET by id only + search helper
export type Instance = components['schemas']['InstanceGET'];

class InstancesRepoClass extends Repo<Instance, Instance, never, never> {
	protected get basePath() { return '/instances'; }
	protected get capabilities() { return { list: false, get: true, create: false, update: false, delete: false }; }

	async search(query: components['schemas']['SearchQuery']): Promise<components['schemas']['SearchResponse']> {
		const res = await api.POST('/instances/search', { body: query });
		if (!res.data) throw new Error('No data');
		return res.data as components['schemas']['SearchResponse'];
	}
}
export const InstancesRepo = new InstancesRepoClass('instances');

// Form Schemas — GET by id only
export type FormSchema = components['schemas']['FormSchemaGET'];

class FormSchemasRepoClass extends Repo<FormSchema, FormSchema, never, never> {
	protected get basePath() { return '/form-schemas'; }
	protected get capabilities() { return { list: false, get: true, create: false, update: false, delete: false }; }
}
export const FormSchemasRepo = new FormSchemasRepoClass('form-schemas');

// Segmentations — create (multipart), get/patch/delete + data helpers
export type Segmentation = { id: Id } & Record<string, unknown>;
type SegmentationCreate = components['schemas']['Body_create_segmentation_segmentations_post'];
type SegmentationPatch = components['schemas']['SegmentationPatch'];

class SegmentationsRepoClass extends Repo<Segmentation, Segmentation, SegmentationCreate, SegmentationPatch> {
	protected get basePath() { return '/segmentations'; }
	protected toCreateBody(body: SegmentationCreate) { return body as any; }

	async getData(segmentation_id: number, p?: { axis?: number; scan_nr?: number }): Promise<unknown> {
		const res = await api.GET('/segmentations/{segmentation_id}/data', { 
			params: { 
				path: { segmentation_id }, 
				query: { axis: p?.axis, scan_nr: p?.scan_nr } 
			} 
		});
		return res.data as unknown;
	}

	async updateData(segmentation_id: number, p?: { axis?: number; scan_nr?: number }, body?: unknown): Promise<unknown> {
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
export const SegmentationsRepo = new SegmentationsRepoClass('segmentations');

// SubTasks — nested list only + helpers
export type SubTask = components['schemas']['SubTaskGET'];
type SubTasksListParams = { task_id: number; with_images?: boolean; limit?: number; page?: number };

class SubTasksRepoClass extends Repo<SubTask, SubTask, never, never, SubTasksListParams> {
	protected get basePath() { return '/task'; }
	protected get capabilities() { return { list: true, get: false, create: false, update: false, delete: false }; }

	protected async remoteList(p?: SubTasksListParams): Promise<SubTask[]> {
		if (!p?.task_id) throw new Error('task_id is required');
		const res = await api.GET('/task/{task_id}/subtasks', {
			params: {
				path: { task_id: p.task_id },
				query: { with_images: p.with_images, limit: p.limit, page: p.page }
			}
		});
		const d = res.data as components['schemas']['SubTasksWithImagesResponse'] | components['schemas']['SubTasksResponse'] | undefined;
		return d ? (d.subtasks as SubTask[]) : [];
	}

	async getSubtask(task_id: number, subtaskid: number, with_images?: boolean): Promise<SubTask> {
		const res = await api.GET('/task/{task_id}/subtask/{subtaskid}', { 
			params: { 
				path: { task_id, subtaskid }, 
				query: { with_images } 
			} 
		});
		if (!res.data) throw new Error('No data');
		return res.data as SubTask;
	}

	async deleteSubtask(task_id: number, subtaskid: number): Promise<void> {
		await api.DELETE('/task/{task_id}/subtask/{subtaskid}', { 
			params: { path: { task_id, subtaskid } } 
		});
	}
}
export const SubTasksRepo = new SubTasksRepoClass('sub-tasks');

// Form Annotations — full CRUD + filtered list + value helpers
export type FormAnnotation = components['schemas']['FormAnnotationGET'];
type FormAnnotationCreate = components['schemas']['FormAnnotationPUT'];
type FormAnnotationUpdate = components['schemas']['FormAnnotationPUT'];
type FormAnnotationsListParams = { 
	patient_id?: number; 
	study_id?: number; 
	image_instance_id?: number; 
	form_schema_id?: number; 
	sub_task_id?: number; 
};

class FormAnnotationsRepoClass extends Repo<FormAnnotation, FormAnnotation, FormAnnotationCreate, FormAnnotationUpdate, FormAnnotationsListParams> {
	protected get basePath() { return '/form-annotations'; }

	protected async remoteList(filters?: FormAnnotationsListParams): Promise<FormAnnotation[]> {
		const res = await api.GET('/form-annotations', { 
			params: { query: filters ?? {} } 
		});
		return (res.data as FormAnnotation[]) ?? [];
	}

	async getValue(id: number): Promise<unknown> {
		const res = await api.GET('/form-annotations/{form_annotation_id}/value', { 
			params: { path: { form_annotation_id: id } } 
		});
		return res.data as unknown;
	}

	async setValue(id: number, value: unknown): Promise<void> {
		await api.PUT('/form-annotations/{form_annotation_id}/value', { 
			params: { path: { form_annotation_id: id } }, 
			body: value as any 
		});
	}
}
export const FormAnnotationsRepo = new FormAnnotationsRepoClass('form-annotations');

// Studies search helper (standalone)
export async function searchStudies(query: components['schemas']['StudySearchQuery']): Promise<components['schemas']['StudySearchResponse']> {
	const res = await api.POST('/studies/search', { body: query });
	if (!res.data) throw new Error('No data');
	return res.data as components['schemas']['StudySearchResponse'];
}// Local repos for studies and instance metas (for studies search)
export class StudiesLocalRepo extends Repo<Study, Study, never, never> {
	protected get basePath() { return '/studies'; }
	protected get capabilities() { return { list: false, get: false, create: false, update: false, delete: false }; }
}

export class InstanceMetasLocalRepo extends Repo<InstanceMeta, InstanceMeta, never, never> {
	protected get basePath() { return '/instances'; }
	protected get capabilities() { return { list: false, get: false, create: false, update: false, delete: false }; }
}

