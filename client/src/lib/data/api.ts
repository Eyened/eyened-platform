import { api } from '../api/client';
import type { TagGET, FeatureGET, FormSchemaGET, InstanceGET, StudyGET, TaskGET, SubTaskWithImagesGET, SubTaskGET } from '../../types/openapi_types';
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

// ===== Helper Functions =====

/**
 * Helper function to handle API responses and throw errors if present
 * @param res - The API response from openapi-fetch
 * @param operation - The operation name for error messages (e.g., "fetch tags")
 * @returns The data from the response
 */
function handleResponse<T>(res: { data?: T; error?: any; response: Response }, operation: string): T {
	if (res.error) {
		// If authentication error, redirect is already handled by fetchWithAuthRetry
		// But we should still throw to prevent processing invalid data
		throw new Error(`Failed to ${operation}: ${res.response.status}`);
	}
	return res.data as T;
}

/**
 * Extract operation name from API path for error messages
 */
function getOperationName(path: string, method: string): string {
	// Remove leading slash and convert to readable format
	const cleanPath = path.replace(/^\//, '').replace(/\//g, ' ');
	// Convert method to verb
	const verb = method === 'GET' ? 'fetch' : method === 'POST' ? 'create' : method === 'PATCH' ? 'update' : method === 'DELETE' ? 'delete' : method.toLowerCase();
	return `${verb} ${cleanPath}`;
}

/**
 * Wrapped API GET method that automatically handles errors
 */
async function apiGet<T = any>(path: string, options?: any): Promise<T> {
	const res = await api.GET(path as any, options);
	return handleResponse<T>(res, getOperationName(path, 'GET'));
}

/**
 * Wrapped API POST method that automatically handles errors
 */
async function apiPost<T = any>(path: string, options?: any): Promise<T> {
	const res = await api.POST(path as any, options);
	return handleResponse<T>(res, getOperationName(path, 'POST'));
}

/**
 * Wrapped API PATCH method that automatically handles errors
 */
async function apiPatch<T = any>(path: string, options?: any): Promise<T> {
	const res = await api.PATCH(path as any, options);
	return handleResponse<T>(res, getOperationName(path, 'PATCH'));
}

/**
 * Wrapped API DELETE method that automatically handles errors
 */
async function apiDelete(path: string, options?: any): Promise<void> {
	const res = await api.DELETE(path as any, options);
	handleResponse(res, getOperationName(path, 'DELETE'));
}

// ===== Fetch Functions =====

export async function fetchTags(): Promise<TagGET[]> {
	const data = (await apiGet<TagGET[]>('/tags', {}) ?? []) as TagGET[];
	ingestTags(data);
	return data;
}

export async function fetchFeatures(params?: { with_counts?: boolean }): Promise<FeatureGET[]> {
	const data = (await apiGet<FeatureGET[]>('/features', { 
		params: { query: params ?? {} } as any 
	}) ?? []) as FeatureGET[];
	ingestFeatures(data);
	return data;
}

export async function fetchFormSchemas(): Promise<FormSchemaGET[]> {
	const data = (await apiGet<FormSchemaGET[]>('/form-schemas', {}) ?? []) as FormSchemaGET[];
	ingestFormSchemas(data);
	return data;
}

export async function fetchInstance(
	id: number, 
	options?: {
		with_segmentations?: boolean;
		with_form_annotations?: boolean;
		with_model_segmentations?: boolean;
		with_tag_metadata?: boolean;
	}
): Promise<InstanceGET> {
	const instance = await apiGet<InstanceGET>('/instances/{instance_id}' as any, {
		params: { 
			path: { instance_id: id },
			query: { 
				with_tag_metadata: true,
				...options
			}
		} as any
	}) as any;
	
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
	
	return instance;
}

export async function fetchStudy(id: number): Promise<StudyGET> {
	const study = await apiGet<StudyGET>('/studies/{study_id}' as any, {
		params: { path: { study_id: id } } as any
	});
	// This will auto-ingest embedded series
	ingestStudies([study]);
	return study;
}

// ===== Search Functions =====

export async function searchInstances(query: any): Promise<any> {
	const data = await apiPost<any>('/instances/search', { body: query });
	
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

export async function searchStudies(query: any): Promise<any> {
	const data = await apiPost<any>('/studies/search', { body: query });
	
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

export async function getInstancesSignature(): Promise<any[]> {
	return await apiGet<any[]>('/instances/search/signature', {}) ?? [];
}

export async function getStudiesSignature(): Promise<any[]> {
	return await apiGet<any[]>('/studies/search/signature', {}) ?? [];
}

// ===== Segmentation Creation (specialized) =====

export async function createSegmentation(item: any, np_array?: any): Promise<any> {
	const formData = new FormData();
	formData.append('metadata', JSON.stringify(item));
	
	if (np_array) {
		formData.append('np_array', await np_array.toBlob(true), 'np_array.npy.gz');
	}
	
	const data = await apiPost<any>('/segmentations' as any, {
		body: formData
	} as any);
	
	ingestSegmentations([data]);
	
	return data;
}

export async function createSegmentationFrom(
	image: any,  // AbstractImage type
	feature_id: number,
	data_representation: any,
	data_type: any,
	threshold?: number,
	sparse_axis?: number,
	subtask_id?: number
): Promise<any> {
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

export async function fetchFormAnnotation(id: number): Promise<any> {
	const data = await apiGet<any>('/form-annotations/{annotation_id}' as any, {
		params: { path: { annotation_id: id } } as any
	});
	ingestFormAnnotations([data]);
	return data;
}

export async function fetchFormAnnotations(filters?: {
	patient_id?: number;
	study_id?: number;
	image_instance_id?: number;
	form_schema_id?: number;
	sub_task_id?: number;
}): Promise<any[]> {
	const data = (await apiGet<any[]>('/form-annotations', {
		params: { query: filters ?? {} }
	}) ?? []) as any[];
	ingestFormAnnotations(data);
	return data;
}

export async function createFormAnnotation(data: {
	form_schema_id: number;
	patient_id: number;
	study_id?: number;
	image_instance_id: number;
	laterality?: 'L' | 'R';
	sub_task_id?: number;
	form_data: any;
	form_annotation_reference_id?: number;
}): Promise<any> {
	const result = await apiPost<any>('/form-annotations', {
		body: data as any
	});
	ingestFormAnnotations([result]);
	return result;
}

export async function deleteFormAnnotation(id: number): Promise<void> {
	await apiDelete('/form-annotations/{annotation_id}' as any, {
		params: { path: { annotation_id: id } } as any
	});
	formAnnotations.delete(id);
}

// ===== Segmentation Functions =====

export async function fetchSegmentation(id: number): Promise<any> {
	const data = await apiGet<any>('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any
	});
	ingestSegmentations([data]);
	return data;
}

export async function updateSegmentation(
	id: number, 
	data: { threshold?: number; reference_segmentation_id?: number | null }
): Promise<any> {
	const result = await apiPatch<any>('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any,
		body: data as any
	});
	ingestSegmentations([result]);
	return result;
}

export async function deleteSegmentation(id: number): Promise<void> {
	await apiDelete('/segmentations/{segmentation_id}' as any, {
		params: { path: { segmentation_id: id } } as any
	});
	segmentations.delete(id);
}

// ===== Tag Star/Unstar =====

export async function starTag(tagId: number): Promise<void> {
	await apiPost('/tags/{tag_id}/star' as any, {
		params: { path: { tag_id: tagId } } as any
	});
}

export async function unstarTag(tagId: number): Promise<void> {
	await apiDelete('/tags/{tag_id}/star' as any, {
		params: { path: { tag_id: tagId } } as any
	});
}

// ===== Task Functions =====

export async function fetchTasks(): Promise<TaskGET[]> {
	const data = (await apiGet<TaskGET[]>('/task', {}) ?? []) as TaskGET[];
	ingestTasks(data);
	return data;
}

export async function fetchTask(id: number): Promise<TaskGET> {
	const task = await apiGet<TaskGET>('/task/{task_id}' as any, {
		params: { path: { task_id: id } } as any
	});
	ingestTasks([task]);
	return task;
}

export async function fetchSubTasks(params: {
	task_id: number;
	with_images?: boolean;
	limit?: number;
	page?: number;
	subtask_status?: string;
}): Promise<any> {
	const data = await apiGet<any>('/task/{task_id}/subtasks' as any, {
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
	if (data.subtasks) {
		ingestSubTasks(data.subtasks);
	}
	return data;
}

// ===== SubTask Update Functions =====

export async function updateSubTask(
    subtask_id: number,
    patch: { task_state?: any; comments?: string | null }
): Promise<any> {
    const data = await apiPatch<any>('/subtasks/{subtaskid}' as any, {
        params: { path: { subtaskid: Number(subtask_id) } } as any,
        body: patch as any
    });
    ingestSubTasks([data]);
    return data;
}

export async function fetchSubTask(subtask_id: number): Promise<any> {
    const data = await apiGet<any>('/subtasks/{subtaskid}' as any, {
        params: { path: { subtaskid: Number(subtask_id) } } as any
    });
    ingestSubTasks([data]);
    return data;
}

export async function fetchSubTaskByIndex(
    task_id: number,
    subtask_index: number,
    options?: {
        with_images?: boolean;
        with_next?: boolean;
    }
): Promise<SubTaskWithImagesGET | SubTaskGET> {
    const data = await apiGet<SubTaskWithImagesGET | SubTaskGET>('/task/{task_id}/subtask/{subtask_index}' as any, {
        params: {
            path: {
                task_id: Number(task_id),
                subtask_index: Number(subtask_index)
            },
            query: {
                with_images: options?.with_images ?? false,
                with_next: options?.with_next ?? false
            }
        } as any
    });
    ingestSubTasks([data]);
    return data;
}

