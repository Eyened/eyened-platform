import { api } from '../api/client';
import type { TagGET, FeatureGET, FormSchemaGET, InstanceGET, StudyGET, TaskGET } from '../../types/openapi_types';
import { 
	ingestTags, 
	ingestFeatures, 
	ingestFormSchemas,
	ingestInstances,
	ingestInstanceMetas,
	ingestStudies,
	ingestSegmentations,
	ingestModelSegmentations,
	ingestFormAnnotations,
	ingestTasks,
	ingestSubTasks,
	formAnnotations,
	segmentations
} from './stores.svelte';

// ===== Fetch Functions =====

export async function fetchTags() {
	const res = await api.GET('/tags', {});
	const data = (res.data ?? []) as TagGET[];
	ingestTags(data);
	return data;
}

export async function fetchFeatures(params?: { with_counts?: boolean }) {
	const res = await api.GET('/features', { 
		params: { query: params ?? {} } as any 
	});
	const data = (res.data ?? []) as FeatureGET[];
	ingestFeatures(data);
	return data;
}

export async function fetchFormSchemas() {
	const res = await api.GET('/form-schemas', {});
	const data = (res.data ?? []) as FormSchemaGET[];
	ingestFormSchemas(data);
	return data;
}

export async function fetchInstance(id: number, options?: {
	with_segmentations?: boolean;
	with_form_annotations?: boolean;
	with_model_segmentations?: boolean;
	with_tag_metadata?: boolean;
}) {
	const res = await api.GET('/instances/{instance_id}' as any, {
		params: { 
			path: { instance_id: id },
			query: { 
				with_tag_metadata: true,
				...options
			}
		} as any
	});
	if (res.data) {
		const instance = res.data as any;
		
		// Ingest the instance
		ingestInstances([instance]);
		
		// Ingest embedded data if present
		if (instance.form_annotations) {
			ingestFormAnnotations(instance.form_annotations);
		}
		if (instance.segmentations) {
			ingestSegmentations(instance.segmentations);
		}
		if (instance.model_segmentations) {
			ingestModelSegmentations(instance.model_segmentations);
		}
	}
	return res.data as any;
}

export async function fetchStudy(id: number) {
	const res = await api.GET('/studies/{study_id}' as any, {
		params: { path: { study_id: id } } as any
	});
	if (res.data) {
		const study = res.data as StudyGET;
		// This will auto-ingest embedded series
		ingestStudies([study]);
	}
	return res.data as StudyGET;
}

// ===== Search Functions =====

export async function searchInstances(query: any) {
	const res = await api.POST('/instances/search', { body: query });
	const data = res.data as any;
	
	// Ingest studies first (which ingests embedded series)
	if (data.studies) {
		ingestStudies(data.studies);
	}
	
	// Then ingest instances
	if (data.instances) {
		ingestInstances(data.instances);
	}
	
	return data;
}

export async function searchStudies(query: any) {
	const res = await api.POST('/studies/search', { body: query });
	const data = res.data as any;
	
	// Ingest studies (which ingests embedded series)
	if (data.studies) {
		ingestStudies(data.studies);
	}
	
	// StudySearchResponse has instances: InstanceMeta[] (lightweight references)
	// Ingest into separate instanceMetas store
	if (data.instances) {
		ingestInstanceMetas(data.instances);
	}
	
	return data;
}

// ===== Signature Functions =====

export async function getInstancesSignature() {
	const res = await api.GET('/instances/search/signature', {});
	return res.data ?? [];
}

export async function getStudiesSignature() {
	const res = await api.GET('/studies/search/signature', {});
	return res.data ?? [];
}

// ===== Segmentation Creation (specialized) =====

export async function createSegmentation(item: any, np_array?: any) {
	const formData = new FormData();
	formData.append('metadata', JSON.stringify(item));
	
	if (np_array) {
		formData.append('np_array', await np_array.toBlob(true), 'np_array.npy.gz');
	}
	
	const res = await api.POST('/segmentations' as any, {
		body: formData
	} as any);
	
	if (res.data) {
		ingestSegmentations([res.data as any]);
	}
	
	return res.data;
}

export async function createSegmentationFrom(
	image: any,  // AbstractImage type
	feature_id: number,
	data_representation: any,
	data_type: any,
	threshold?: number,
	sparse_axis?: number,
	subtask_id?: number
) {
	const instance = image.instance;
	const scan_indices = image.is3D ? [] : null;
	let shape = {
		depth: image.depth,
		height: image.height,
		width: image.width,
	};
	
	if (sparse_axis === 1) {
		// projection
		shape.depth = image.height;
		shape.height = 1;
		shape.width = image.width;
	}

	const item = {
		image_instance_id: instance.id,
		...shape,
		sparse_axis,
		image_projection_matrix: null,
		scan_indices,
		data_representation,
		data_type,
		threshold,
		reference_segmentation_id: null,
		feature_id: feature_id,
		subtask_id: subtask_id ?? null,
	};

	return createSegmentation(item);
}

// ===== Form Annotations Functions =====

export async function fetchFormAnnotation(id: number) {
	const res = await api.GET('/form-annotations/{annotation_id}' as any, {
		params: { path: { annotation_id: id } } as any
	});
	if (res.data) {
		ingestFormAnnotations([res.data as any]);
	}
	return res.data as any;
}

export async function fetchFormAnnotations(filters?: {
	patient_id?: number;
	study_id?: number;
	image_instance_id?: number;
	form_schema_id?: number;
	sub_task_id?: number;
}) {
	const res = await api.GET('/form-annotations', {
		params: { query: filters ?? {} }
	});
	const data = (res.data ?? []) as any[];
	ingestFormAnnotations(data);
	return data;
}

export async function createFormAnnotation(data: {
	form_schema_id: number;
	patient_id: number;
	study_id?: number;
	image_instance_id: number;
	sub_task_id?: number;
	form_data: any;
	form_annotation_reference_id?: number;
}) {
	const res = await api.POST('/form-annotations', {
		body: data as any
	});
	if (res.data) {
		ingestFormAnnotations([res.data as any]);
	}
	return res.data as any;
}

export async function deleteFormAnnotation(id: number) {
	await api.DELETE('/form-annotations/{annotation_id}' as any, {
		params: { path: { annotation_id: id } } as any
	});
	formAnnotations.delete(id);
}

// ===== Segmentation Functions =====

export async function fetchSegmentation(id: number) {
	const res = await api.GET('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any
	});
	if (res.data) {
		ingestSegmentations([res.data as any]);
	}
	return res.data as any;
}

export async function updateSegmentation(id: number, data: { threshold?: number; reference_segmentation_id?: number | null }) {
	const res = await api.PATCH('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any,
		body: data as any
	});
	if (res.data) {
		ingestSegmentations([res.data as any]);
	}
	return res.data as any;
}

export async function deleteSegmentation(id: number) {
	await api.DELETE('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any
	});
	segmentations.delete(id);
}

// ===== Tag Star/Unstar =====

export async function starTag(tagId: number) {
	try {
		await api.POST('/tags/{tag_id}/star' as any, {
			params: { path: { tag_id: tagId } } as any
		});
	} catch {
		await fetch(`/api/tags/${tagId}/star`, { 
			method: 'POST', 
			credentials: 'include' 
		});
	}
}

export async function unstarTag(tagId: number) {
	try {
		await api.DELETE('/tags/{tag_id}/star' as any, {
			params: { path: { tag_id: tagId } } as any
		});
	} catch {
		await fetch(`/api/tags/${tagId}/star`, { 
			method: 'DELETE', 
			credentials: 'include' 
		});
	}
}

// ===== Task Functions =====

export async function fetchTasks() {
	const res = await api.GET('/task', {});
	const data = (res.data ?? []) as TaskGET[];
	ingestTasks(data);
	return data;
}

export async function fetchTask(id: number) {
	const res = await api.GET('/task/{task_id}' as any, {
		params: { path: { task_id: id } } as any
	});
	if (res.data) {
		ingestTasks([res.data as TaskGET]);
	}
	return res.data as TaskGET;
}

export async function fetchSubTasks(params: {
	task_id: number;
	with_images?: boolean;
	limit?: number;
	page?: number;
	subtask_status?: string;
}) {
	const res = await api.GET('/task/{task_id}/subtasks' as any, {
		params: {
			path: { task_id: params.task_id },
			query: {
				with_images: params.with_images ?? true,
				limit: params.limit ?? 20,
				page: params.page ?? 0,
				subtask_status: params.subtask_status
			}
		} as any
	});
	const data = res.data as any;
	if (data.subtasks) {
		ingestSubTasks(data.subtasks);
	}
	return data;
}

// ===== SubTask Update Functions =====

export async function updateSubTask(
    subtask_id: number,
    patch: { task_state?: any; comments?: string | null }
) {
    const res = await api.PATCH('/subtasks/{subtaskid}' as any, {
        params: { path: { subtaskid: Number(subtask_id) } } as any,
        body: patch as any
    });
    if (res.data) {
        ingestSubTasks([res.data as any]);
    }
    return res.data as any;
}

export async function fetchSubTask(subtask_id: number) {
    const res = await api.GET('/subtasks/{subtaskid}' as any, {
        params: { path: { subtaskid: Number(subtask_id) } } as any
    });
    if (res.data) {
        ingestSubTasks([res.data as any]);
    }
    return res.data as any;
}

