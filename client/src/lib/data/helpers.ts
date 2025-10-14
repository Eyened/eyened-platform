import type { FeaturePATCH, InstanceGET, SegmentationGET, StudyGET, TaskGET, TaskPATCH, TaskPUT } from '../../types/openapi_types';
import { ingestTasks, instances, segmentations, studies, tasks } from './stores.svelte';


// ===== Tag Helpers =====

export async function tagInstance(instance: InstanceGET, tagId: number) {
	const { api } = await import('../api/client');
	const { data } = await api.POST('/instances/{instance_id}/tags' as any, {
		params: { path: { instance_id: instance.id } } as any,
		body: { tag_id: tagId } as any
	});
    console.log('tagInstance', instance.id, tagId, data);
    console.log({
        ...instance,
        tags: [...instance.tags, data as any]
    })
	// Update store with new tag
	instances.set(instance.id, {
		...instance,
		tags: [...instance.tags, data as any]
	});
}

export async function untagInstance(instance: InstanceGET, tagId: number) {
	const { api } = await import('../api/client');
	await api.DELETE('/instances/{instance_id}/tags/{tag_id}' as any, {
		params: { path: { instance_id: Number(instance.id), tag_id: tagId } } as any
	});
	// Update store - remove tag
	instances.set(instance.id, {
		...instance,
		tags: instance.tags.filter(t => t.id !== tagId)
	});
}

export async function tagStudy(study: StudyGET, tagId: number) {
	const { api } = await import('../api/client');
	const { data } = await api.POST('/studies/{study_id}/tags' as any, {
		params: { path: { study_id: Number(study.id) } } as any,
		body: { tag_id: tagId } as any
	});
	// Update store
    console.log('tagStudy', study.id, tagId, data);
    console.log({
		...study,
		tags: [...study.tags, data as any]
	})
	studies.set(study.id, {
		...study,
		tags: [...study.tags, data as any]
	});
}

export async function untagStudy(study: StudyGET, tagId: number) {
	const { api } = await import('../api/client');
	await api.DELETE('/studies/{study_id}/tags/{tag_id}' as any, {
		params: { path: { study_id: Number(study.id), tag_id: tagId } } as any
	});
	// Update store
	studies.set(study.id, {
		...study,
		tags: study.tags.filter(t => t.id !== tagId)
	});
}

export async function tagSegmentation(seg: SegmentationGET, tagId: number) {
	const { api } = await import('../api/client');
	const { data } = await api.POST('/segmentations/{segmentation_id}/tags' as any, {
		params: { path: { segmentation_id: Number(seg.id) } } as any,
		body: { tag_id: tagId } as any
	});
	// Update store
	segmentations.set(seg.id, {
		...seg,
		tags: [...seg.tags, data as any]
	});
}

export async function untagSegmentation(seg: SegmentationGET, tagId: number) {
	const { api } = await import('../api/client');
	await api.DELETE('/segmentations/{segmentation_id}/tags/{tag_id}' as any, {
		params: { path: { segmentation_id: Number(seg.id), tag_id: tagId } } as any
	});
	// Update store
	segmentations.set(seg.id, {
		...seg,
		tags: seg.tags.filter(t => t.id !== tagId)
	});
}

// ===== Segmentation Data Helpers =====

export async function getSegmentationData(segmentationId: number, params?: { axis?: number; scan_nr?: number; sparse_axis?: number }) {
	const { api } = await import('../api/client');
	const { decodeNpy } = await import('../utils/npy_loader');
	
	// Match original logic:
	// - axis only sent if sparse_axis != null AND scan_nr != undefined
	// - scan_nr can be sent alone
	const query: any = {};
	const sparseAxis = params?.sparse_axis ?? params?.axis;
	if (sparseAxis != null && params?.scan_nr != null) {
		query.axis = sparseAxis;
	}
	if (params?.scan_nr != null) {
		query.scan_nr = params.scan_nr;
	}
	
	const res = await api.GET('/segmentations/{segmentation_id}/data', {
		params: {
			path: { segmentation_id: segmentationId },
			query
		},
		parseAs: "arrayBuffer"
	});
	return decodeNpy(res.data!);
}

export async function updateSegmentationData(segmentationId: number, data: ArrayBuffer, params?: { axis?: number; scan_nr?: number; sparse_axis?: number }) {
	const { apiUrl } = await import('../config');
	
	// Match original logic:
	// - axis only sent if sparse_axis != null AND scan_nr != undefined
	// - scan_nr can be sent alone
	const urlParams = new URLSearchParams();
	const sparseAxis = params?.sparse_axis ?? params?.axis;
	if (sparseAxis != null && params?.scan_nr != null) {
		urlParams.append('axis', sparseAxis.toString());
	}
	if (params?.scan_nr != null) {
		urlParams.append('scan_nr', params.scan_nr.toString());
	}
	
	const queryString = urlParams.toString();
	const url = `${apiUrl}/segmentations/${segmentationId}/data${queryString ? '?' + queryString : ''}`;
	
	return fetch(url, {
		method: 'PUT',
		credentials: 'include',
		headers: { 'Content-Type': 'application/octet-stream' },
		body: data
	});
}

export async function getModelSegmentationData(modelSegmentationId: number, params?: { axis?: number; scan_nr?: number; sparse_axis?: number }) {
	const { api } = await import('../api/client');
	const { decodeNpy } = await import('../utils/npy_loader');
	
	// Match original logic:
	// - axis only sent if sparse_axis != null AND scan_nr != undefined
	// - scan_nr can be sent alone
	const query: any = {};
	const sparseAxis = params?.sparse_axis ?? params?.axis;
	if (sparseAxis != null && params?.scan_nr != null) {
		query.axis = sparseAxis;
	}
	if (params?.scan_nr != null) {
		query.scan_nr = params.scan_nr;
	}
	
	const res = await api.GET('/model-segmentations/{model_segmentation_id}/data', {
		params: {
			path: { model_segmentation_id: modelSegmentationId },
			query
		},
		parseAs: "arrayBuffer"
	});
	return decodeNpy(res.data!);
}

// ===== Form Annotation Value Helpers =====

export async function getFormAnnotationValue(annotationId: number) {
	const { api } = await import('../api/client');
	const res = await api.GET('/form-annotations/{form_annotation_id}/value', {
		params: { path: { form_annotation_id: annotationId } }
	});
	return res.data as unknown;
}

export async function setFormAnnotationValue(annotationId: number, form_data: unknown) {
	const { api } = await import('../api/client');
	const { formAnnotations } = await import('./stores.svelte');
	
	// Save to server first (server is source of truth)
	await api.PUT('/form-annotations/{form_annotation_id}/value', {
		params: { path: { form_annotation_id: annotationId } },
		body: form_data as any
	});
	
	// Then update local store so other components see the change
	const existing = formAnnotations.get(annotationId);
	if (existing) {
		formAnnotations.set(annotationId, {
			...existing,
			form_data: form_data as any
		});
	} else {
        console.error(`Form annotation ${annotationId} not found`);
    }
}

// ===== Feature Helpers =====

export async function updateFeature(featureId: number, patch: FeaturePATCH) {
	const { api } = await import('../api/client');
	const { features, featuresByName } = await import('./stores.svelte');
	
	const res = await api.PATCH('/features/{feature_id}' as any, {
		params: { path: { feature_id: featureId } } as any,
		body: patch
	});
	
	if (res.data) {
		const updatedFeature = res.data as any;
		features.set(updatedFeature.id, updatedFeature);
		featuresByName.set(updatedFeature.name, updatedFeature);
	}
	
	return res.data as any;
}

export async function deleteFeature(featureId: number) {
	const { api } = await import('../api/client');
	const { features, featuresByName } = await import('./stores.svelte');
	
	// Get the feature name before deleting
	const feature = features.get(featureId);
	
	await api.DELETE('/features/{feature_id}' as any, {
		params: { path: { feature_id: featureId } } as any
	});
	
	// Remove from both stores
	features.delete(featureId);
	if (feature) {
		featuresByName.delete(feature.name);
	}
}

// ===== Tag Creation/Deletion Helpers =====

export async function createTag(
	name: string, 
	tagType: 'Study' | 'ImageInstance' | 'FormAnnotation', 
	description?: string
) {
	const { api } = await import('../api/client');
	const { tags } = await import('./stores.svelte');
	
	const res = await api.POST('/tags' as any, {
		body: {
			name,
			description: description ?? "",
			tag_type: tagType,
		}
	});
	
	// Ingest the newly created tag
	if (res.data) {
		const newTag = res.data as any;
		tags.set(newTag.id, newTag);
		return newTag;
	}
	
	return null;
}

export async function deleteTag(tagId: number) {
	const { api } = await import('../api/client');
	const { tags } = await import('./stores.svelte');
	
	await api.DELETE('/tags/{tag_id}' as any, {
		params: { path: { tag_id: tagId } } as any
	});
	
	// Remove from store
	tags.delete(tagId);
}

// ===== Task CRUD Helpers =====

export async function createTask(data: TaskPUT) {
	const { api } = await import('../api/client');
	const res = await api.POST('/task', { body: data });
	if (res.data) {
		ingestTasks([res.data as TaskGET]);
	}
	return res.data as TaskGET;
}

export async function updateTask(id: number, patch: TaskPATCH) {
	const { api } = await import('../api/client');
	const res = await api.PATCH('/task/{task_id}' as any, {
		params: { path: { task_id: id } } as any,
		body: patch
	});
	if (res.data) {
		ingestTasks([res.data as TaskGET]);
	}
	return res.data as TaskGET;
}

export async function deleteTask(id: number) {
	const { api } = await import('../api/client');
	await api.DELETE('/task/{task_id}' as any, {
		params: { path: { task_id: id } } as any
	});
	tasks.delete(id);
}

// ===== SubTask Helpers =====

export async function addSubTaskImage(taskId: number, subtaskIndex: number, instanceId: number) {
	const { api } = await import('../api/client');
	const { ingestSubTasks } = await import('./stores.svelte');
	
	const res = await api.POST('/task/{task_id}/subtask/{subtask_index}/images/{instance_id}' as any, {
		params: {
			path: {
				task_id: taskId,
				subtask_index: subtaskIndex,
				instance_id: instanceId
			}
		} as any
	});
	
	if (res.data) {
		ingestSubTasks([res.data as any]);
	}
	return res.data;
}

export async function removeSubTaskImage(taskId: number, subtaskIndex: number, instanceId: number) {
	const { api } = await import('../api/client');
	const { ingestSubTasks } = await import('./stores.svelte');
	
	const res = await api.DELETE('/task/{task_id}/subtask/{subtask_index}/images/{instance_id}' as any, {
		params: {
			path: {
				task_id: taskId,
				subtask_index: subtaskIndex,
				instance_id: instanceId
			}
		} as any
	});
	
	if (res.data) {
		ingestSubTasks([res.data as any]);
	}
	return res.data;
}

export async function updateSubTaskComments(taskId: number, subtaskIndex: number, comments: string) {
	const { api } = await import('../api/client');
	const { ingestSubTasks } = await import('./stores.svelte');
	
	const res = await api.PATCH('/task/{task_id}/subtask/{subtask_index}' as any, {
		params: {
			path: {
				task_id: taskId,
				subtask_index: subtaskIndex
			}
		} as any,
		body: { comments } as any
	});
	
	if (res.data) {
		ingestSubTasks([res.data as any]);
	}
	return res.data;
}

export function getInstanceBySOPInstanceUID(SOPInstanceUid: string): InstanceGET | undefined {
	return instances.find(inst => inst.sop_instance_uid === SOPInstanceUid);
}
export function getInstanceByDataSetIdentifier(datasetIdentifier: string): InstanceGET | undefined {
	return instances.find(inst => inst.dataset_identifier === datasetIdentifier);
}