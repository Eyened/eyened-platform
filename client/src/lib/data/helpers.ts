import type {
    FeatureGET,
    FeaturePATCH,
    FeaturePUT,
    FormAnnotationGET,
    ImageGET,
    SegmentationGET,
    StudyGET,
    SubTaskWithImagesGET,
    TagGET,
    TagMeta,
    TagType,
    TaskGET,
    TaskPATCH,
    TaskPUT,
} from "../../types/openapi_types";
import { ApiError, api, fetchApi } from "../api/client";
import { apiInvoke, apiInvokeAllowEmpty } from "./api";
import { decodeNpy, NPYArray } from "../utils/npy_loader";
import {
    features,
    featuresByName,
    formAnnotations,
    ingestSubTasks,
    ingestTasks,
    instances,
    segmentations,
    studies,
    tags,
    tasks,
} from "./stores.svelte";

// ===== Tag Helpers =====

export async function tagInstance(
    instance: ImageGET,
    tagId: number,
    comment?: string,
) {
    const { data } = await apiInvoke(() =>
        api.POST("/instances/{instance_id}/tags", {
            params: { path: { instance_id: instance.id } },
            body: { tag_id: tagId, comment },
        }),
    );

    // Update store with new tag
    if (instances.has(instance.id) && data) {
        instances.set(instance.id, {
            ...instances.get(instance.id)!,
            tags: [...instances.get(instance.id)!.tags, data],
        });
    }
}

export async function updateTagInstance(
    instanceId: string,
    tagId: number,
    comment?: string,
) {
    const res = await apiInvoke(() =>
        api.PATCH("/instances/{instance_id}/tags/{tag_id}", {
            params: { path: { instance_id: instanceId, tag_id: tagId } },
            body: { comment },
        }),
    );
    const inst = instances.get(instanceId);
    if (inst && res.data) {
        const tm: TagMeta = res.data;
        instances.set(instanceId, {
            ...inst,
            tags: inst.tags.map((t) => (t.id === tagId ? tm : t)),
        });
    }
}

export async function untagInstance(instance: ImageGET, tagId: number) {
    await apiInvoke(() =>
        api.DELETE("/instances/{instance_id}/tags/{tag_id}", {
            params: {
                path: { instance_id: instance.id, tag_id: tagId },
            },
        }),
    );
    if (instances.has(instance.id)) {
        const inst = instances.get(instance.id)!;
        instances.set(instance.id, {
            ...inst,
            tags: inst.tags.filter((t) => t.id !== tagId),
        });
    }
}

export async function tagStudy(
    study: StudyGET,
    tagId: number,
    comment?: string,
) {
    const { data } = await apiInvoke(() =>
        api.POST("/studies/{study_id}/tags", {
            params: { path: { study_id: Number(study.id) } },
            body: { tag_id: tagId, comment },
        }),
    );
    // Update store

    if (data) {
        studies.set(study.id, {
            ...study,
            tags: [...study.tags, data],
        });
    }
}

export async function updateTagStudy(
    studyId: number,
    tagId: number,
    comment?: string,
) {
    const res = await apiInvoke(() =>
        api.PATCH("/studies/{study_id}/tags/{tag_id}", {
            params: {
                path: { study_id: Number(studyId), tag_id: tagId },
            },
            body: { comment },
        }),
    );
    const s = studies.get(studyId);
    if (s && res.data) {
        const tm: TagMeta = res.data;
        studies.set(studyId, {
            ...s,
            tags: s.tags.map((t) => (t.id === tagId ? tm : t)),
        });
    }
}

export async function tagFormAnnotation(
    formAnnotation: FormAnnotationGET,
    tagId: number,
    comment?: string,
) {
    const { data } = await apiInvoke(() =>
        api.POST("/form-annotations/{annotation_id}/tags", {
            params: {
                path: { annotation_id: Number(formAnnotation.id) },
            },
            body: { tag_id: tagId, comment },
        }),
    );
    // Update store
    if (data) {
        formAnnotations.set(formAnnotation.id, {
            ...formAnnotation,
            tags: [...(formAnnotation.tags ?? []), data],
        });
    }
}

export async function updateTagFormAnnotation(
    annotationId: number,
    tagId: number,
    comment?: string,
) {
    const res = await apiInvoke(() =>
        api.PATCH("/form-annotations/{annotation_id}/tags/{tag_id}", {
            params: {
                path: {
                    annotation_id: Number(annotationId),
                    tag_id: tagId,
                },
            },
            body: { comment },
        }),
    );
    const fa = formAnnotations.get(annotationId);
    if (fa && res.data) {
        const tm: TagMeta = res.data;
        formAnnotations.set(annotationId, {
            ...fa,
            tags: (fa.tags ?? []).map((t) => (t.id === tagId ? tm : t)),
        });
    }
}

export async function untagFormAnnotation(
    formAnnotation: FormAnnotationGET,
    tagId: number,
) {
    await apiInvoke(() =>
        api.DELETE("/form-annotations/{annotation_id}/tags/{tag_id}", {
            params: {
                path: {
                    annotation_id: Number(formAnnotation.id),
                    tag_id: tagId,
                },
            },
        }),
    );
    // Update store
    formAnnotations.set(formAnnotation.id, {
        ...formAnnotation,
        tags: (formAnnotation.tags ?? []).filter((t) => t.id !== tagId),
    });
}

export async function untagStudy(study: StudyGET, tagId: number) {
    await apiInvoke(() =>
        api.DELETE("/studies/{study_id}/tags/{tag_id}", {
            params: {
                path: { study_id: Number(study.id), tag_id: tagId },
            },
        }),
    );
    // Update store
    studies.set(study.id, {
        ...study,
        tags: study.tags.filter((t) => t.id !== tagId),
    });
}

export async function tagSegmentation(
    seg: SegmentationGET,
    tagId: number,
    comment?: string,
) {
    const { data } = await apiInvoke(() =>
        api.POST("/segmentations/{segmentation_id}/tags", {
            params: { path: { segmentation_id: Number(seg.id) } },
            body: { tag_id: tagId, comment },
        }),
    );
    // Update store
    if (data) {
        segmentations.set(seg.id, {
            ...seg,
            tags: [...seg.tags, data],
        });
    }
}

export async function untagSegmentation(seg: SegmentationGET, tagId: number) {
    await apiInvoke(() =>
        api.DELETE("/segmentations/{segmentation_id}/tags/{tag_id}", {
            params: {
                path: { segmentation_id: Number(seg.id), tag_id: tagId },
            },
        }),
    );
    // Update store
    segmentations.set(seg.id, {
        ...seg,
        tags: seg.tags.filter((t) => t.id !== tagId),
    });
}

// ===== Segmentation Data Helpers =====

export async function getSegmentationData(
    segmentationId: number,
    params?: { scan_nr?: number; sparse_axis?: number },
): Promise<NPYArray | null> {
    const query: {
        axis?: number | null;
        scan_nr?: number | null;
    } = {};

    query.axis = params?.sparse_axis;
    query.scan_nr = params?.scan_nr;
    const res = await apiInvokeAllowEmpty(() =>
        api.GET("/segmentations/{segmentation_id}/data", {
            params: {
                path: { segmentation_id: segmentationId },
                query,
            },
            parseAs: "arrayBuffer",
        }),
    );
    if (res.response.status == 204) {
        return null;
    }
    return decodeNpy(res.data!);
}

export async function updateSegmentationData(
    segmentationId: number,
    data: ArrayBuffer,
    params?: { scan_nr?: number; sparse_axis?: number; keepalive?: boolean },
) {
    const urlParams = new URLSearchParams();
    const sparseAxis = params?.sparse_axis;
    if (sparseAxis != null) {
        urlParams.append("axis", sparseAxis.toString());
    }
    if (params?.scan_nr != null) {
        urlParams.append("scan_nr", params.scan_nr.toString());
    }

    const keepalive = params?.keepalive ?? false;
    return fetchApi(`/segmentations/${segmentationId}/data`, {
        method: "PUT",
        headers: { "Content-Type": "application/octet-stream" },
        body: data,
        query: urlParams,
        keepalive,
        // Avoid async token refresh during page unload; cookies still sent.
        skipAuthRetry: keepalive,
    });
}

export async function getModelSegmentationData(
    modelSegmentationId: number,
    params?: { axis?: number; scan_nr?: number; sparse_axis?: number },
): Promise<NPYArray | null> {
    // Match original logic:
    // - axis only sent if sparse_axis != null AND scan_nr != undefined
    // - scan_nr can be sent alone
    const query: {
        axis?: number | null;
        scan_nr?: number | null;
    } = {};
    const sparseAxis = params?.sparse_axis ?? params?.axis;
    if (sparseAxis != null && params?.scan_nr != null) {
        query.axis = sparseAxis;
    }
    if (params?.scan_nr != null) {
        query.scan_nr = params.scan_nr;
    }

    const res = await apiInvokeAllowEmpty(() =>
        api.GET("/model-segmentations/{model_segmentation_id}/data", {
            params: {
                path: { model_segmentation_id: modelSegmentationId },
                query,
            },
            parseAs: "arrayBuffer",
        }),
    );
    if (res.response.status == 204) {
        return null;
    }
    return decodeNpy(res.data!);
}

// ===== Form Annotation Value Helpers =====

export async function getFormAnnotationValue(annotationId: number) {
    const res = await apiInvoke(() =>
        api.GET("/form-annotations/{form_annotation_id}/value", {
            params: { path: { form_annotation_id: annotationId } },
        }),
    );
    return res.data as unknown;
}

export async function setFormAnnotationValue(
    annotationId: number,
    form_data: unknown,
) {
    // Save to server first (server is source of truth)
    const response = await fetchApi(`/form-annotations/${annotationId}/value`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form_data),
    });
    if (!response.ok) {
        throw new ApiError(
            response.status,
            `Failed to update form annotation value: ${response.status}`,
        );
    }

    // Then update local store so other components see the change
    const existing = formAnnotations.get(annotationId);
    if (existing) {
        formAnnotations.set(annotationId, {
            ...existing,
            form_data,
        });
    } else {
        console.error(`Form annotation ${annotationId} not found`);
    }
}

// ===== Feature Helpers =====

/** Create a new feature on the server and update local feature stores. */
export async function createFeature(
    data: FeaturePUT,
): Promise<FeatureGET | null> {
    const res = await apiInvoke(() => api.POST("/features", { body: data }));
    if (res.data) {
        const feature = res.data as FeatureGET;
        features.set(feature.id, feature);
        featuresByName.set(feature.name, feature);
        return feature;
    }
    return null;
}

export async function updateFeature(
    featureId: number,
    patch: FeaturePATCH,
): Promise<FeatureGET | undefined> {
    const res = await apiInvoke(() =>
        api.PATCH("/features/{feature_id}", {
            params: { path: { feature_id: featureId } },
            body: patch,
        }),
    );

    if (res.data) {
        const updatedFeature: FeatureGET = res.data;
        features.set(updatedFeature.id, updatedFeature);
        featuresByName.set(updatedFeature.name, updatedFeature);
    }

    return res.data;
}

export async function deleteFeature(featureId: number) {
    // Get the feature name before deleting
    const feature = features.get(featureId);

    await apiInvoke(() =>
        api.DELETE("/features/{feature_id}", {
            params: { path: { feature_id: featureId } },
        }),
    );

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
    description?: string,
) {
    const res = await apiInvoke(() =>
        api.POST("/tags", {
            body: {
                name,
                description: description ?? "",
                tag_type: tagType,
            },
        }),
    );

    // Ingest the newly created tag
    if (res.data) {
        const newTag: TagGET = res.data;
        tags.set(newTag.id, newTag);
        return newTag;
    }

    return null;
}

export async function deleteTag(tagId: number) {
    await apiInvoke(() =>
        api.DELETE("/tags/{tag_id}", {
            params: { path: { tag_id: tagId } },
        }),
    );

    // Remove from store
    tags.delete(tagId);
}

// ===== Task CRUD Helpers =====

export async function createTask(data: TaskPUT) {
    const res = await apiInvoke(() => api.POST("/task", { body: data }));
    if (res.data) {
        ingestTasks([res.data as TaskGET]);
    }
    return res.data as TaskGET;
}

export async function updateTask(id: number, patch: TaskPATCH) {
    const res = await apiInvoke(() =>
        api.PATCH("/task/{task_id}", {
            params: { path: { task_id: id } },
            body: patch,
        }),
    );
    if (res.data) {
        ingestTasks([res.data as TaskGET]);
    }
    return res.data as TaskGET;
}

export async function deleteTask(id: number) {
    await apiInvoke(() =>
        api.DELETE("/task/{task_id}", {
            params: { path: { task_id: id } },
        }),
    );
    tasks.delete(id);
}

// ===== SubTask Helpers =====

export async function addSubTaskImage(subtaskId: number, instanceId: string) {
    const res = await apiInvoke(() =>
        api.POST("/subtasks/{subtaskid}/images", {
            params: {
                path: {
                    subtaskid: subtaskId,
                },
            },
            body: { instance_id: instanceId },
        }),
    );

    if (res.data) {
        ingestSubTasks([res.data]);
    }
    return res.data;
}

export async function removeSubTaskImage(
    subtaskId: number,
    instanceId: string,
) {
    const res = await apiInvoke(() =>
        api.DELETE("/subtasks/{subtaskid}/images/{instance_id}", {
            params: {
                path: {
                    subtaskid: subtaskId,
                    instance_id: instanceId,
                },
            },
        }),
    );

    if (res.data) {
        ingestSubTasks([res.data]);
    }
    return res.data;
}

export async function updateSubTaskComments(
    subtaskId: number,
    comments: string,
) {
    const res = await apiInvoke(() =>
        api.PATCH("/subtasks/{subtaskid}", {
            params: {
                path: {
                    subtaskid: subtaskId,
                },
            },
            body: { comments },
        }),
    );

    if (res.data) {
        ingestSubTasks([res.data as SubTaskWithImagesGET]);
    }
    return res.data;
}

export function getInstanceBySOPInstanceUID(
    SOPInstanceUid: string,
): ImageGET | undefined {
    return instances.find((inst) => inst.sop_instance_uid === SOPInstanceUid);
}
