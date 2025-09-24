import type {
	FeatureGET, FeaturePATCH,
	FormAnnotationGET, FormAnnotationPUT,
	InstanceGET, InstanceMeta,
	SegmentationGET, SegmentationPATCH,
	SeriesGET, SeriesMeta,
	StudyGET, StudyMeta,
	SubTaskGET, SubTaskWithImagesGET, SubTasksResponse, SubTasksWithImagesResponse,
	TagGET, TagMeta, TagPATCH,
	TaskGET, TaskPATCH
} from '../../types/openapi_types';
import { api } from '../api/client';
import type { Repo } from './datamodel.svelte';
import { DataObject, MetaObject } from './datamodel.svelte';

// GET object classes
export class InstanceObject extends DataObject<InstanceGET, never> {
	static DefaultRepo: typeof Repo;
	async tag(tag_id: number) {
		const {data} = await api.POST('/instances/{instance_id}/tags' as any, {
			params: { path: { instance_id: Number(this.id) } } as any,
			body: { tag_id } as any
		});
		this.updateLocal({ tags: [...(this.$.tags ?? []), data] });
	}
	async untag(tag_id: number) {
		await api.DELETE('/instances/{instance_id}/tags/{tag_id}' as any, {
			params: { path: { instance_id: Number(this.id), tag_id } } as any
		});
		this.updateLocal({ tags: this.$.tags.filter((t) => t.id !== tag_id) });
	}
}

export class StudyObject extends DataObject<StudyGET, never> {
	static DefaultRepo: typeof Repo;
	async tag(tag_id: number) {
		const {data} = await api.POST('/studies/{study_id}/tags' as any, {
			params: { path: { study_id: Number(this.id) } } as any,
			body: { tag_id } as any
		});
		this.updateLocal({ tags: [...(this.$.tags ?? []), data] });
	}
	async untag(tag_id: number) {
		await api.DELETE('/studies/{study_id}/tags/{tag_id}' as any, {
			params: { path: { study_id: Number(this.id), tag_id } } as any
		});
		this.updateLocal({ tags: this.$.tags.filter((t) => t.id !== tag_id) });
	}
}

export class SeriesObject extends DataObject<SeriesGET, never> { static DefaultRepo: typeof Repo; }

export class SegmentationObject extends DataObject<SegmentationGET, SegmentationPATCH> { 
	static DefaultRepo: typeof Repo;
	async tag(tag_id: number) {
		const {data} = await api.POST('/segmentations/{segmentation_id}/tags' as any, {
			params: { path: { segmentation_id: Number(this.id) } } as any,
			body: { tag_id } as any
		});
		this.updateLocal({ tags: [...(this.$.tags ?? []), data] });
	}
	async untag(tag_id: number) {
		await api.DELETE('/segmentations/{segmentation_id}/tags/{tag_id}' as any, {
			params: { path: { segmentation_id: Number(this.id), tag_id } } as any
		});
		this.updateLocal({ tags: this.$.tags.filter((t) => t.id !== tag_id) });
	}
}

export class FormAnnotationObject extends DataObject<FormAnnotationGET, FormAnnotationPUT> {
	static DefaultRepo: typeof Repo;
	async tag(tag_id: number) {
		const {data} = await api.POST('/form-annotations/{annotation_id}/tags' as any, {
			params: { path: { annotation_id: Number(this.id) } } as any,
			body: { tag_id } as any
		});
		this.updateLocal({ tags: [...(this.$.tags ?? []), data] });
	}
	async untag(tag_id: number) {
		await api.DELETE('/form-annotations/{annotation_id}/tags/{tag_id}' as any, {
			params: { path: { annotation_id: Number(this.id), tag_id } } as any
		});
		this.updateLocal({ tags: this.$.tags.filter((t) => t.id !== tag_id) });
	}
}

export class TagObject extends DataObject<TagGET, TagPATCH> { static DefaultRepo: typeof Repo; }

export class TaskObject extends DataObject<TaskGET, TaskPATCH> { 
	static DefaultRepo: typeof Repo;
	
	async subtasks(p?: { with_images?: boolean; limit?: number; page?: number }) {
		const { api } = await import('../api/client');
		const res = await api.GET('/subtasks' as any, {
			params: {
				query: {
					task_id: Number(this.id),
					with_images: p?.with_images ?? true,
					limit: p?.limit ?? 200,
					page: p?.page ?? 0
				}
			}
		});
		return res.data as SubTasksWithImagesResponse | SubTasksResponse;
	}
}

export class FeatureObject extends DataObject<FeatureGET, FeaturePATCH> { static DefaultRepo: typeof Repo; }

export class SubTaskObject extends DataObject<SubTaskGET | SubTaskWithImagesGET, Partial<SubTaskGET | SubTaskWithImagesGET>> {
	async addImage(instance_id: number) {
		const { api } = await import('../api/client');
		await api.POST('/subtasks/{subtaskid}/images' as any, {
			params: { path: { subtaskid: Number(this.id) } } as any,
			body: { instance_id } as any
		});
	}
	async removeImage(instance_id: number) {
		const { api } = await import('../api/client');
		await api.DELETE('/subtasks/{subtaskid}/images/{instance_id}' as any, {
			params: { path: { subtaskid: Number(this.id), instance_id } } as any
		});
	}
	async setComments(comments: string) {
		const { api } = await import('../api/client');
		const { data } = await api.PATCH('/subtasks/{subtaskid}' as any, {
			params: { path: { subtaskid: Number(this.id) } } as any,
			body: { comments } as any
		});
		this.replace(data as SubTaskGET | SubTaskWithImagesGET);
	}
}

// Meta object classes (no Meta repos)
type SegmentationMeta = Pick<SegmentationGET, 'id'>;
type FormAnnotationMeta = Pick<FormAnnotationGET, 'id'>;

export class InstanceMetaObject extends MetaObject<InstanceMeta, InstanceGET> {
	protected get baseEndpoint() { return '/instances'; }
	constructor(getRepo: Repo<InstanceGET>, meta: InstanceMeta) { super(getRepo, meta); }
}

export class StudyMetaObject extends MetaObject<StudyMeta, StudyGET> {
	protected get baseEndpoint() { return '/studies'; }
	constructor(getRepo: Repo<StudyGET>, meta: StudyMeta) { super(getRepo, meta); }
}

export class SeriesMetaObject extends MetaObject<SeriesMeta, SeriesGET> {
	protected get baseEndpoint() { return '/series'; }
	constructor(getRepo: Repo<SeriesGET>, meta: SeriesMeta) { super(getRepo, meta); }
}

export class SegmentationMetaObject extends MetaObject<SegmentationMeta, SegmentationGET> {
	protected get baseEndpoint() { return '/segmentations'; }
	constructor(getRepo: Repo<SegmentationGET>, meta: SegmentationMeta) { super(getRepo, meta); }
}

export class FormAnnotationMetaObject extends MetaObject<FormAnnotationMeta, FormAnnotationGET> {
	protected get baseEndpoint() { return '/form-annotations'; }
	constructor(getRepo: Repo<FormAnnotationGET>, meta: FormAnnotationMeta) { super(getRepo, meta); }
}

export class TagMetaObject extends MetaObject<TagMeta, TagGET> {
	protected get baseEndpoint() { return '/tags'; }
	constructor(getRepo: Repo<TagGET>, meta: TagMeta) { super(getRepo, meta); }
}
