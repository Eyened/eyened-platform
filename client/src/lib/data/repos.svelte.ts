import type { components } from '../../types/openapi';
import { api } from '../api/client';
import { Repo, type Id } from './datamodel.svelte';

// Helper: naive singularization plus kebab->snake: e.g. "/form-schemas" -> "form_schema_id"
function inferIdParam(base: string): string {
	const last = base.replace(/\/+$/, '').split('/').pop() ?? '';
	const singular = last.endsWith('ies') ? last.slice(0, -3) + 'y' : last.endsWith('s') ? last.slice(0, -1) : last;
	const snake = singular.replace(/-([a-z])/g, (_, c) => `_${c}`);
	return `${snake}_id`;
}

function fromOpenApiCrud<TGet, TCreate = Partial<TGet>, TPatch = Partial<TGet>>(base: string) {
	const idParam = inferIdParam(base);
	const itemPath = `${base}/{${idParam}}` as const;
	return {
		list: async (): Promise<TGet[]> => (await api.GET(base as any)).data as TGet[] ?? [],
		get: async (id: Id): Promise<TGet> => {
			const res = await api.GET(itemPath as any, { params: { path: { [idParam]: Number(id) } } as any });
			if (!res.data) throw new Error('No data');
			return res.data as TGet;
		},
		create: async (body: TCreate): Promise<TGet> => {
			const res = await api.POST(base as any, { body } as any);
			if (!res.data) throw new Error('No data');
			return res.data as TGet;
		},
		update: async (id: Id, body: TPatch): Promise<TGet> => {
			const res = await api.PATCH(itemPath as any, { params: { path: { [idParam]: Number(id) } } as any, body });
			if (!res.data) throw new Error('No data');
			return res.data as TGet;
		},
		delete: async (id: Id): Promise<void> => {
			await api.DELETE(itemPath as any, { params: { path: { [idParam]: Number(id) } } as any });
		}
	};
}

// Tasks — full CRUD
export type Task = components['schemas']['TaskGET'];
type TaskCreate = components['schemas']['TaskPUT'];
type TaskPatch = components['schemas']['TaskPATCH'];
export const Tasks = new Repo<Task, Task, TaskCreate, TaskPatch>('tasks', fromOpenApiCrud<Task, TaskCreate, TaskPatch>('/task'));

// Tags — list/create/patch/delete (no GET by id in API; just don't call fetchOne())
export type Tag = components['schemas']['TagGET'];
type TagCreate = components['schemas']['TagPUT'];
type TagPatch = components['schemas']['TagPATCH'];
export const Tags = new Repo<Tag, Tag, TagCreate, TagPatch>('tags', fromOpenApiCrud<Tag, TagCreate, TagPatch>('/tags'));

// Features — create/get/patch/delete (no list; don't call fetchAll())
export type Feature = components['schemas']['FeatureGET'];
type FeatureCreate = components['schemas']['FeaturePUT'];
type FeaturePatch = components['schemas']['FeaturePATCH'];
export const Features = new Repo<Feature, Feature, FeatureCreate, FeaturePatch>('features', fromOpenApiCrud<Feature, FeatureCreate, FeaturePatch>('/features'));

// Instances — GET by id only
export type Instance = components['schemas']['InstanceGET'];
export const Instances = new Repo<Instance, Instance, never, never>('instances', {
	get: async (id: Id) => {
		const res = await api.GET('/instances/{instance_id}', { params: { path: { instance_id: Number(id) } } });
		if (!res.data) throw new Error('No data');
		return res.data as Instance;
	}
});

// Form Schemas — GET by id only
export type FormSchema = components['schemas']['FormSchemaGET'];
export const FormSchemas = new Repo<FormSchema, FormSchema, never, never>('form-schemas', {
	get: async (id: Id) => {
		const res = await api.GET('/form-schemas/{form_schema_id}', { params: { path: { form_schema_id: Number(id) } } });
		if (!res.data) throw new Error('No data');
		return res.data as FormSchema;
	}
});

// Segmentations — create (multipart), get/patch/delete; API returns `unknown` — assume `{ id: number }` is present
export type Segmentation = { id: Id } & Record<string, unknown>;
type SegmentationCreate = components['schemas']['Body_create_segmentation_segmentations_post'];
type SegmentationPatch = components['schemas']['SegmentationPatch'];
export const Segmentations = new Repo<Segmentation, Segmentation, SegmentationCreate, SegmentationPatch>('segmentations', {
	create: async (body: SegmentationCreate) => {
		// body should be FormData for multipart; pass through as-is
		const res = await api.POST('/segmentations', { body } as any);
		if (!res.data) throw new Error('No data');
		return res.data as Segmentation;
	},
	get: async (id: Id) => {
		const res = await api.GET('/segmentations/{segmentation_id}', { params: { path: { segmentation_id: Number(id) } } });
		if (!res.data) throw new Error('No data');
		return res.data as Segmentation;
	},
	update: async (id: Id, patch: SegmentationPatch) => {
		const res = await api.PATCH('/segmentations/{segmentation_id}', {
			params: { path: { segmentation_id: Number(id) } },
			body: patch
		});
		if (!res.data) throw new Error('No data');
		return res.data as Segmentation;
	},
	delete: async (id: Id) => {
		await api.DELETE('/segmentations/{segmentation_id}', { params: { path: { segmentation_id: Number(id) } } });
	}
});

// SubTasks — nested resource; list by task_id and get/delete by (task_id, subtaskid)
export type SubTask = components['schemas']['SubTaskGET'];
type SubTasksListParams = { task_id: number; with_images?: boolean; limit?: number; page?: number };
export const SubTasks = new Repo<SubTask, SubTask, never, never, SubTasksListParams>('sub-tasks', {
	list: async (p?: SubTasksListParams) => {
		if (!p) throw new Error('task_id is required');
		const res = await api.GET('/task/{task_id}/subtasks', {
			params: {
				path: { task_id: p.task_id },
				query: { with_images: p.with_images, limit: p.limit, page: p.page }
			}
		});
		const d = res.data as components['schemas']['SubTasksWithImagesResponse'] | components['schemas']['SubTasksResponse'] | undefined;
		return d ? (d.subtasks as SubTask[]) : [];
	},
	get: async (id: Id) => {
		throw new Error('Use getSubtask(task_id, subtaskid) helper'); // nested get needs both keys
	}
});

// Optional helper for SubTasks (nested get/delete)
export async function getSubtask(task_id: number, subtaskid: number): Promise<SubTask> {
	const res = await api.GET('/task/{task_id}/subtask/{subtaskid}', { params: { path: { task_id, subtaskid } } });
	if (!res.data) throw new Error('No data');
	return res.data as SubTask;
}

export async function deleteSubtask(task_id: number, subtaskid: number): Promise<void> {
	await api.DELETE('/task/{task_id}/subtask/{subtaskid}', { params: { path: { task_id, subtaskid } } });
}
