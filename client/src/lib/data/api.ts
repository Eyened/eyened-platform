import type { components } from "../../types/openapi";
import type {
    FeatureGET,
    FormAnnotationGET,
    FormAnnotationPUT,
    FormSchemaGET,
    ImageGET,
    PatientDetailGET,
    SearchQuery,
    SearchResponse,
    SegmentationDataRepresentation,
    SegmentationDataType,
    SegmentationGET,
    SegmentationPATCH,
    SegmentationPOST,
    SignatureField,
    StudyGET,
    StudySearchQuery,
    StudySearchResponse,
    SubTaskGET,
    SubTaskState,
    SubTasksResponse,
    SubTasksWithImagesResponse,
    SubTaskWithImagesGET,
    TagGET,
    TaskGET,
} from "../../types/openapi_types";

type SubTaskPATCH = components["schemas"]["SubTaskPATCH"];
type SegmentationCreateMetadata = Omit<SegmentationPOST, "$defs">;
import {
    ApiError,
    api,
    fetchApi,
    isUnauthorizedStatus,
    withAuthRetry,
} from "../api/client";
import type { AbstractImage } from "../webgl/abstractImage";
import type { NPYArray } from "../utils/npy_loader";
import {
    formAnnotations,
    ingestFeatures,
    ingestFormAnnotations,
    ingestFormSchemas,
    ingestInstances,
    ingestModelSegmentations,
    ingestPatients,
    ingestSegmentations,
    ingestStudies,
    ingestSubTasks,
    ingestTags,
    ingestTasks,
    segmentations,
} from "./stores.svelte";

// ===== Helper Functions =====

/**
 * Helper function to handle API responses and throw errors if present
 * @param res - The API response from openapi-fetch
 * @param operation - The operation name for error messages (e.g., "fetch tags")
 * @returns The data from the response
 */
function handleResponse<T>(
    res: { data?: T; error?: unknown; response: Response },
    operation: string,
): T {
    if (res.error || isUnauthorizedStatus(res.response.status)) {
        // Auth errors may surface as status only (fetch retried once at HTTP layer).
        // withAuthRetry on callers can refresh and run the operation again.
        throw new ApiError(
            res.response.status,
            `Failed to ${operation}: ${res.response.status}`,
        );
    }
    return res.data as T;
}

export type ApiCallResult<T = unknown> = {
    data?: T;
    error?: unknown;
    response: Response;
};

/**
 * openapi-fetch call with HTTP-level and app-level auth retry.
 */
export async function apiInvoke<T = unknown>(
    call: () => Promise<ApiCallResult<T>>,
    operation = "request",
): Promise<ApiCallResult<T>> {
    return withAuthRetry(async () => {
        const res = await call();
        if (res.error || isUnauthorizedStatus(res.response.status)) {
            throw new ApiError(
                res.response.status,
                `Failed to ${operation}: ${res.response.status}`,
            );
        }
        return res;
    });
}

/** Like apiInvoke but does not treat openapi `error` as failure (e.g. 204 No Content). */
export async function apiInvokeAllowEmpty<T = unknown>(
    call: () => Promise<ApiCallResult<T>>,
): Promise<ApiCallResult<T>> {
    return withAuthRetry(async () => {
        const res = await call();
        if (isUnauthorizedStatus(res.response.status)) {
            throw new ApiError(
                res.response.status,
                `Request failed: ${res.response.status}`,
            );
        }
        return res;
    });
}

async function invokeGet<T>(
    call: () => Promise<ApiCallResult<T>>,
    operation: string,
): Promise<T> {
    return withAuthRetry(async () => {
        const res = await call();
        return handleResponse<T>(res, operation);
    });
}

async function invokePost<T>(
    call: () => Promise<ApiCallResult<T>>,
    operation: string,
): Promise<T> {
    return withAuthRetry(async () => {
        const res = await call();
        return handleResponse<T>(res, operation);
    });
}

async function invokePatch<T>(
    call: () => Promise<ApiCallResult<T>>,
    operation: string,
): Promise<T> {
    return withAuthRetry(async () => {
        const res = await call();
        return handleResponse<T>(res, operation);
    });
}

async function invokeDelete(
    call: () => Promise<ApiCallResult<unknown>>,
    operation: string,
): Promise<void> {
    return withAuthRetry(async () => {
        const res = await call();
        handleResponse(res, operation);
    });
}

// ===== Fetch Functions =====

export async function fetchTags(): Promise<TagGET[]> {
    const data =
        (await invokeGet(() => api.GET("/tags", {}), "fetch tags")) ?? [];
    ingestTags(data);
    return data;
}

export async function fetchFeatures(params?: {
    with_counts?: boolean;
}): Promise<FeatureGET[]> {
    const data =
        (await invokeGet(
            () =>
                api.GET("/features", {
                    params: { query: params ?? {} },
                }),
            "fetch features",
        )) ?? [];
    ingestFeatures(data);
    return data;
}

export async function fetchFormSchemas(): Promise<FormSchemaGET[]> {
    const data =
        (await invokeGet(() => api.GET("/form-schemas", {}), "fetch form-schemas")) ??
        [];
    ingestFormSchemas(data);
    return data;
}

export async function fetchInstance(
    id: string,
    options: {
        with_segmentations?: boolean;
        with_form_annotations?: boolean;
        with_model_segmentations?: boolean;
        with_tag_metadata?: boolean;
    } = {
        with_segmentations: true,
        with_form_annotations: true,
        with_model_segmentations: true,
        with_tag_metadata: true,
    },
): Promise<ImageGET> {
    const instance = await invokeGet(
        () =>
            api.GET("/images/{image_id}", {
                params: {
                    path: { image_id: id },
                    query: {
                        with_tag_metadata: true,
                        ...options,
                    },
                },
            }),
        "fetch images image_id",
    );

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
    const response = await fetchApi(`/studies/${id}`, { method: "GET" });
    if (!response.ok) {
        throw new ApiError(
            response.status,
            `Failed to fetch studies study_id: ${response.status}`,
        );
    }
    const study = (await response.json()) as StudyGET;
    // This will auto-ingest embedded series
    ingestStudies([study]);
    return study;
}

export async function fetchPatient(
    id: number,
    options: { include_attributes?: boolean } = { include_attributes: true },
): Promise<PatientDetailGET> {
    const patient = await invokeGet(
        () =>
            api.GET("/patients/{patient_id}", {
                params: {
                    path: { patient_id: id },
                    query: {
                        include_attributes: options.include_attributes ?? true,
                    },
                },
            }),
        "fetch patients patient_id",
    );
    ingestPatients([patient]);
    return patient;
}

// ===== Search Functions =====

export async function searchInstances(
    query: SearchQuery,
): Promise<SearchResponse> {
    const data = await invokePost(
        () => api.POST("/instances/search", { body: query }),
        "create instances search",
    );

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

export async function searchStudies(
    query: StudySearchQuery,
): Promise<StudySearchResponse> {
    const data = await invokePost(
        () => api.POST("/studies/search", { body: query }),
        "create studies search",
    );

    // Ingest studies (which ingests embedded series)
    if (data.studies) {
        ingestStudies(data.studies);
    }

    if (data.instances) {
        ingestInstances(data.instances);
    }

    return data;
}

// ===== Signature Functions =====

export async function getInstancesSignature(): Promise<SignatureField[]> {
    return (
        (await invokeGet(
            () => api.GET("/instances/search/signature", {}),
            "fetch instances search signature",
        )) ?? []
    );
}

export async function getStudiesSignature(): Promise<SignatureField[]> {
    return (
        (await invokeGet(
            () => api.GET("/studies/search/signature", {}),
            "fetch studies search signature",
        )) ?? []
    );
}

// ===== Segmentation Creation (specialized) =====

export async function createSegmentation(
    item: SegmentationPOST,
    np_array?: NPYArray,
): Promise<SegmentationGET> {
    const formData = new FormData();
    formData.append("metadata", JSON.stringify(item));

    if (np_array) {
        formData.append(
            "np_array",
            await np_array.toBlob(true),
            "np_array.npy.gz",
        );
    }

    const response = await fetchApi("/segmentations", {
        method: "POST",
        body: formData,
    });
    if (!response.ok) {
        throw new ApiError(
            response.status,
            `Failed to create segmentations: ${response.status}`,
        );
    }
    const data = (await response.json()) as SegmentationGET;

    ingestSegmentations([data]);

    return data;
}

export type CreateSegmentationShape = {
    depth: number;
    height: number;
    width: number;
};

export type CreateSegmentationOptions = {
    shape?: CreateSegmentationShape;
    image_projection_matrix?: number[][] | null;
};

export async function createSegmentationFrom(
    image: AbstractImage,
    feature_id: number,
    data_representation: SegmentationDataRepresentation,
    data_type: SegmentationDataType,
    threshold?: number,
    sparse_axis?: number,
    subtask_id?: number,
    options?: CreateSegmentationOptions,
): Promise<SegmentationGET> {
    const instance = image.instance;
    const scan_indices = image.is3D ? [] : null;
    let shape: CreateSegmentationShape = options?.shape ?? {
        depth: image.depth,
        height: image.height,
        width: image.width,
    };

    if (!options?.shape && sparse_axis === 1) {
        // projection
        shape = {
            depth: image.height,
            height: 1,
            width: image.width,
        };
    }

    const item: SegmentationCreateMetadata = {
        image_id: instance.id,
        ...shape,
        sparse_axis: sparse_axis ?? null,
        image_projection_matrix: options?.image_projection_matrix ?? null,
        scan_indices,
        data_representation,
        data_type,
        threshold: threshold ?? null,
        reference_segmentation_id: null,
        feature_id,
        subtask_id: subtask_id ?? null,
    };

    return createSegmentation(item as SegmentationPOST);
}

// ===== Form Annotations Functions =====

export async function fetchFormAnnotation(
    id: number,
): Promise<FormAnnotationGET> {
    const data = await invokeGet(
        () =>
            api.GET("/form-annotations/{annotation_id}", {
                params: { path: { annotation_id: id } },
            }),
        "fetch form-annotations annotation_id",
    );
    ingestFormAnnotations([data]);
    return data;
}

export async function fetchFormAnnotations(filters?: {
    patient_id?: number;
    study_id?: number;
    image_id?: string;
    form_schema_id?: number;
    sub_task_id?: number;
}): Promise<FormAnnotationGET[]> {
    const data =
        (await invokeGet(
            () =>
                api.GET("/form-annotations", {
                    params: { query: filters ?? {} },
                }),
            "fetch form-annotations",
        )) ?? [];
    ingestFormAnnotations(data);
    return data;
}

export async function createFormAnnotation(
    data: FormAnnotationPUT,
): Promise<FormAnnotationGET> {
    const result = await invokePost(
        () => api.POST("/form-annotations", { body: data }),
        "create form-annotations",
    );
    ingestFormAnnotations([result]);
    return result;
}

export async function deleteFormAnnotation(id: number): Promise<void> {
    await invokeDelete(
        () =>
            api.DELETE("/form-annotations/{annotation_id}", {
                params: { path: { annotation_id: id } },
            }),
        "delete form-annotations annotation_id",
    );
    formAnnotations.delete(id);
}

// ===== Segmentation Functions =====

export async function fetchSegmentation(
    id: number,
): Promise<SegmentationGET> {
    const data = await invokeGet(
        () =>
            api.GET("/segmentations/{segmentation_id}", {
                params: { path: { segmentation_id: id } },
            }),
        "fetch segmentations segmentation_id",
    );
    ingestSegmentations([data]);
    return data;
}

export async function updateSegmentation(
    id: number,
    data: SegmentationPATCH,
): Promise<SegmentationGET> {
    const result = await invokePatch(
        () =>
            api.PATCH("/segmentations/{segmentation_id}", {
                params: { path: { segmentation_id: id } },
                body: data,
            }),
        "update segmentations segmentation_id",
    );
    ingestSegmentations([result]);
    return result;
}

export async function deleteSegmentation(id: number): Promise<void> {
    await invokeDelete(
        () =>
            api.DELETE("/segmentations/{segmentation_id}", {
                params: { path: { segmentation_id: id } },
            }),
        "delete segmentations segmentation_id",
    );
    segmentations.delete(id);
}

// ===== Tag Star/Unstar =====

export async function starTag(tagId: number): Promise<void> {
    await invokePost(
        () =>
            api.POST("/tags/{tag_id}/star", {
                params: { path: { tag_id: tagId } },
            }),
        "create tags tag_id star",
    );
}

export async function unstarTag(tagId: number): Promise<void> {
    await invokeDelete(
        () =>
            api.DELETE("/tags/{tag_id}/star", {
                params: { path: { tag_id: tagId } },
            }),
        "delete tags tag_id star",
    );
}

// ===== Task Functions =====

export async function fetchTasks(): Promise<TaskGET[]> {
    const data =
        (await invokeGet(() => api.GET("/task", {}), "fetch task")) ?? [];
    ingestTasks(data);
    return data;
}

export async function fetchTask(id: number): Promise<TaskGET> {
    const task = await invokeGet(
        () =>
            api.GET("/task/{task_id}", {
                params: { path: { task_id: id } },
            }),
        "fetch task task_id",
    );
    ingestTasks([task]);
    return task;
}

export async function fetchSubTasks(params: {
    task_id: number;
    with_images?: boolean;
    limit?: number;
    page?: number;
    subtask_status?: SubTaskState;
}): Promise<SubTasksWithImagesResponse | SubTasksResponse> {
    const data = await invokeGet(
        () =>
            api.GET("/task/{task_id}/subtasks", {
                params: {
                    path: { task_id: params.task_id },
                    query: {
                        with_images: params.with_images ?? true,
                        limit: params.limit ?? 20,
                        page: params.page ?? 0,
                        subtask_status: params.subtask_status,
                    },
                },
            }),
        "fetch task task_id subtasks",
    );
    if ("subtasks" in data && data.subtasks) {
        ingestSubTasks(data.subtasks as SubTaskWithImagesGET[]);
    }
    return data;
}

// ===== SubTask Update Functions =====

export async function updateSubTask(
    subtask_id: number,
    patch: SubTaskPATCH,
): Promise<SubTaskGET> {
    const data = await invokePatch(
        () =>
            api.PATCH("/subtasks/{subtaskid}", {
                params: { path: { subtaskid: Number(subtask_id) } },
                body: patch,
            }),
        "update subtasks subtaskid",
    );
    ingestSubTasks([data as SubTaskWithImagesGET]);
    return data;
}

export async function fetchSubTask(
    subtask_id: number,
): Promise<SubTaskWithImagesGET | SubTaskGET> {
    const data = await invokeGet(
        () =>
            api.GET("/subtasks/{subtaskid}", {
                params: { path: { subtaskid: Number(subtask_id) } },
            }),
        "fetch subtasks subtaskid",
    );
    ingestSubTasks([data as SubTaskWithImagesGET]);
    return data;
}

export async function fetchSubTaskByIndex(
    task_id: number,
    subtask_index: number,
    options?: {
        with_images?: boolean;
        with_next?: boolean;
    },
): Promise<SubTaskWithImagesGET | SubTaskGET> {
    const data = await invokeGet(
        () =>
            api.GET("/task/{task_id}/subtask/{subtask_index}", {
                params: {
                    path: {
                        task_id: Number(task_id),
                        subtask_index: Number(subtask_index),
                    },
                    query: {
                        with_images: options?.with_images ?? false,
                        with_next: options?.with_next ?? false,
                    },
                },
            }),
        "fetch task task_id subtask subtask_index",
    );
    ingestSubTasks([data as SubTaskWithImagesGET]);
    return data;
}
