import type { FeatureGET, FeaturePATCH, FeaturePUT, FormAnnotationGET, ImageGET, SegmentationGET, StudyGET, SubTaskWithImagesGET, TagType, TaskGET, TaskPATCH, TaskPUT } from '../../types/openapi_types';
import { api, fetchApi } from '../api/client';
import { decodeNpy, NPYArray } from '../utils/npy_loader';
import { features, featuresByName, formAnnotations, ingestSubTasks, ingestTasks, instances, segmentations, studies, tags, tasks } from './stores.svelte';


// ===== Tag Helpers =====

export async function tagInstance(instance: ImageGET, tagId: number, comment?: string) {
    const { data } = await api.POST('/instances/{instance_id}/tags' as any, {
        params: { path: { instance_id: instance.id } } as any,
        body: { tag_id: tagId, comment } as any
    });

    // Update store with new tag
    if (instances.has(instance.id)) {
        instances.set(instance.id, {
            ...instances.get(instance.id)!,
            tags: [...instances.get(instance.id)!.tags, data as any]
        });
    }
}

export async function updateTagInstance(instanceId: string, tagId: number, comment?: string) {
    const res = await api.PATCH('/instances/{instance_id}/tags/{tag_id}' as any, {
        params: { path: { instance_id: instanceId, tag_id: tagId } } as any,
        body: { comment } as any
    });
    const inst = instances.get(instanceId);
    if (inst && res.data) {
        const tm = res.data as any;
        instances.set(instanceId, { ...inst, tags: inst.tags.map(t => t.id === tagId ? tm : t) });
    }
}

export async function untagInstance(instance: ImageGET, tagId: number) {
    await api.DELETE('/instances/{instance_id}/tags/{tag_id}' as any, {
        params: { path: { instance_id: instance.id, tag_id: tagId } } as any
    });
    if (instances.has(instance.id)) {
        const inst = instances.get(instance.id)!;
        instances.set(instance.id, {
            ...inst,
            tags: inst.tags.filter(t => t.id !== tagId)
        });
    }
}

export async function tagStudy(study: StudyGET, tagId: number, comment?: string) {
    const { data } = await api.POST('/studies/{study_id}/tags' as any, {
        params: { path: { study_id: Number(study.id) } } as any,
        body: { tag_id: tagId, comment } as any
    });
    // Update store

    studies.set(study.id, {
        ...study,
        tags: [...study.tags, data as any]
    });
}

export async function updateTagStudy(studyId: number, tagId: number, comment?: string) {
    const res = await api.PATCH('/studies/{study_id}/tags/{tag_id}' as any, {
        params: { path: { study_id: Number(studyId), tag_id: tagId } } as any,
        body: { comment } as any
    });
    const s = studies.get(studyId);
    if (s && res.data) {
        const tm = res.data as any;
        studies.set(studyId, { ...s, tags: s.tags.map(t => t.id === tagId ? tm : t) });
    }
}

export async function tagFormAnnotation(formAnnotation: FormAnnotationGET, tagId: number, comment?: string) {
    const { data } = await api.POST('/form-annotations/{form_annotation_id}/tags' as any, {
        params: { path: { form_annotation_id: Number(formAnnotation.id) } } as any,
        body: { tag_id: tagId, comment } as any
    });
    // Update store
    formAnnotations.set(formAnnotation.id, {
        ...formAnnotation,
        tags: [...(formAnnotation.tags ?? []), data as any]
    });
}

export async function updateTagFormAnnotation(annotationId: number, tagId: number, comment?: string) {
    const res = await api.PATCH('/form-annotations/{form_annotation_id}/tags/{tag_id}' as any, {
        params: { path: { form_annotation_id: Number(annotationId), tag_id: tagId } } as any,
        body: { comment } as any
    });
    const fa = formAnnotations.get(annotationId);
    if (fa && res.data) {
        const tm = res.data as any;
        formAnnotations.set(annotationId, { ...fa, tags: (fa.tags ?? []).map(t => t.id === tagId ? tm : t) });
    }
}

export async function untagFormAnnotation(formAnnotation: FormAnnotationGET, tagId: number) {
    await api.DELETE('/form-annotations/{form_annotation_id}/tags/{tag_id}' as any, {
        params: { path: { form_annotation_id: Number(formAnnotation.id), tag_id: tagId } } as any
    });
    // Update store
    formAnnotations.set(formAnnotation.id, {
        ...formAnnotation,
        tags: (formAnnotation.tags ?? []).filter(t => t.id !== tagId)
    });
}



export async function untagStudy(study: StudyGET, tagId: number) {
    await api.DELETE('/studies/{study_id}/tags/{tag_id}' as any, {
        params: { path: { study_id: Number(study.id), tag_id: tagId } } as any
    });
    // Update store
    studies.set(study.id, {
        ...study,
        tags: study.tags.filter(t => t.id !== tagId)
    });
}

export async function tagSegmentation(seg: SegmentationGET, tagId: number, comment?: string) {
    const { data } = await api.POST('/segmentations/{segmentation_id}/tags' as any, {
        params: { path: { segmentation_id: Number(seg.id) } } as any,
        body: { tag_id: tagId, comment } as any
    });
    // Update store
    segmentations.set(seg.id, {
        ...seg,
        tags: [...seg.tags, data as any]
    });
}

export async function untagSegmentation(seg: SegmentationGET, tagId: number) {
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

export async function getSegmentationData(segmentationId: number, params?: { scan_nr?: number; sparse_axis?: number }): Promise<NPYArray | null> {
    const query: any = {};

    query.axis = params?.sparse_axis;
    query.scan_nr = params?.scan_nr;
    const res = await api.GET('/segmentations/{segmentation_id}/data', {
        params: {
            path: { segmentation_id: segmentationId },
            query
        },
        parseAs: "arrayBuffer"
    });
    if (res.response.status == 204) {
        return null;
    }
    return decodeNpy(res.data!);
}

export async function updateSegmentationData(segmentationId: number, data: ArrayBuffer, params?: { scan_nr?: number; sparse_axis?: number }) {
    const urlParams = new URLSearchParams();
    const sparseAxis = params?.sparse_axis;
    if (sparseAxis != null) {
        urlParams.append('axis', sparseAxis.toString());
    }
    if (params?.scan_nr != null) {
        urlParams.append('scan_nr', params.scan_nr.toString());
    }

    return fetchApi(`/segmentations/${segmentationId}/data`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: data,
        query: urlParams
    });
}

export async function getModelSegmentationData(modelSegmentationId: number, params?: { axis?: number; scan_nr?: number; sparse_axis?: number }): Promise<NPYArray | null> {
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
    if (res.response.status == 204) {
        return null;
    }
    return decodeNpy(res.data!);
}

// ===== Form Annotation Value Helpers =====

export async function getFormAnnotationValue(annotationId: number) {
    const res = await api.GET('/form-annotations/{form_annotation_id}/value', {
        params: { path: { form_annotation_id: annotationId } }
    });
    return res.data as unknown;
}

export async function setFormAnnotationValue(annotationId: number, form_data: unknown) {
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

/** Create a new feature on the server and update local feature stores. */
export async function createFeature(data: FeaturePUT): Promise<FeatureGET | null> {
    const res = await api.POST('/features' as any, { body: data });
    if (res.data) {
        const feature = res.data as FeatureGET;
        features.set(feature.id, feature);
        featuresByName.set(feature.name, feature);
        return feature;
    }
    return null;
}

export async function updateFeature(featureId: number, patch: FeaturePATCH) {
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
    tagType: TagType,
    description?: string
) {
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
    await api.DELETE('/tags/{tag_id}' as any, {
        params: { path: { tag_id: tagId } } as any
    });

    // Remove from store
    tags.delete(tagId);
}

// ===== Task CRUD Helpers =====

export async function createTask(data: TaskPUT) {
    const res = await api.POST('/task', { body: data });
    if (res.data) {
        ingestTasks([res.data as TaskGET]);
    }
    return res.data as TaskGET;
}

export async function updateTask(id: number, patch: TaskPATCH) {
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
    await api.DELETE('/task/{task_id}' as any, {
        params: { path: { task_id: id } } as any
    });
    tasks.delete(id);
}

// ===== SubTask Helpers =====

export async function addSubTaskImage(subtaskId: number, instanceId: string) {
    const res = await api.POST('/subtasks/{subtaskid}/images' as any, {
        params: {
            path: {
                subtaskid: subtaskId
            }
        } as any,
        body: { instance_id: instanceId } as any
    });

    if (res.data) {
        ingestSubTasks([res.data as any]);
    }
    return res.data;
}

export async function removeSubTaskImage(subtaskId: number, instanceId: string) {
    const res = await api.DELETE('/subtasks/{subtaskid}/images/{instance_id}' as any, {
        params: {
            path: {
                subtaskid: subtaskId,
                instance_id: instanceId
            }
        } as any
    });

    if (res.data) {
        ingestSubTasks([res.data as any]);
    }
    return res.data;
}

export async function updateSubTaskComments(subtaskId: number, comments: string) {
    const res = await api.PATCH('/subtasks/{subtaskid}' as any, {
        params: {
            path: {
                subtaskid: subtaskId
            }
        } as any,
        body: { comments } as any
    });

    if (res.data) {
        ingestSubTasks([res.data as SubTaskWithImagesGET]);
    }
    return res.data;
}

export function getInstanceBySOPInstanceUID(SOPInstanceUid: string): ImageGET | undefined {
    return instances.find(inst => inst.sop_instance_uid === SOPInstanceUid);
}
export function getInstanceByDataSourceId(sourceId: string): ImageGET | undefined {
    return instances.find(inst => inst.data_source_id === sourceId);
}