import { SvelteMap } from 'svelte/reactivity';
import type {
	InstanceGET,
	InstanceMeta,
	StudyGET,
	TagGET,
	FeatureGET,
	FormSchemaGET,
	SegmentationGET,
	ModelSegmentationGET,
	FormAnnotationGET,
	TaskGET,
	SubTaskGET,
	SubTaskWithImagesGET
} from '../../types/openapi_types';

// Simple stores - just maps of plain data by ID
export const instances = new SvelteMap<number, InstanceGET>();
export const instanceMetas = new SvelteMap<number, InstanceMeta>();  // Lightweight references
export const studies = new SvelteMap<number, StudyGET>();
export const tags = new SvelteMap<number, TagGET>();
export const features = new SvelteMap<number, FeatureGET>();
export const formSchemas = new SvelteMap<number, FormSchemaGET>();
export const segmentations = new SvelteMap<number, SegmentationGET>();
export const modelSegmentations = new SvelteMap<number, ModelSegmentationGET>();
export const formAnnotations = new SvelteMap<number, FormAnnotationGET>();
export const tasks = new SvelteMap<number, TaskGET>();
export const subtasks = new SvelteMap<number, SubTaskGET | SubTaskWithImagesGET>();

// Secondary indexes for common lookups
export const formSchemasByName = new SvelteMap<string, FormSchemaGET>();
export const featuresByName = new SvelteMap<string, FeatureGET>();
export const tagsByName = new SvelteMap<string, TagGET>();

// Ingest functions handle embedded data extraction
export function ingestStudies(studiesData: StudyGET[]) {
	for (const study of studiesData) {
		studies.set(study.id, study);
	}
}

export function ingestInstances(instancesData: InstanceGET[]) {
	for (const inst of instancesData) {
		// Only ingest full InstanceGET objects (from /instances/search or /instances/{id})
		// If you have InstanceMeta, use ingestInstanceMetas() instead
		if (!('sop_instance_uid' in inst) || !('rows' in inst)) {
			console.error('ingestInstances() expects InstanceGET, got InstanceMeta. Use ingestInstanceMetas() instead:', inst);
			continue;
		}
		instances.set(inst.id, inst);
	}
}

export function ingestInstanceMetas(metasData: InstanceMeta[]) {
	for (const meta of metasData) {
		instanceMetas.set(meta.id, meta);
	}
}

export function ingestTags(tagsData: TagGET[]) {
	for (const tag of tagsData) {
		tags.set(tag.id, tag);
		tagsByName.set(tag.name, tag);
	}
}

export function ingestFeatures(featuresData: FeatureGET[]) {
	for (const feature of featuresData) {
		features.set(feature.id, feature);
		featuresByName.set(feature.name, feature);
	}
}

export function ingestFormSchemas(schemasData: FormSchemaGET[]) {
	for (const schema of schemasData) {
		formSchemas.set(schema.id, schema);
		if (schema.name) {
			formSchemasByName.set(schema.name, schema);
		}
	}
}

export function ingestSegmentations(segsData: SegmentationGET[]) {
	for (const seg of segsData) {
		segmentations.set(seg.id, seg);
	}
}

export function ingestModelSegmentations(segsData: ModelSegmentationGET[]) {
	for (const seg of segsData) {
		modelSegmentations.set(seg.id, seg);
	}
}

export function ingestFormAnnotations(annotationsData: FormAnnotationGET[]) {
	for (const annotation of annotationsData) {
		formAnnotations.set(annotation.id, annotation);
	}
}

export function ingestTasks(tasksData: TaskGET[]) {
	for (const task of tasksData) {
		tasks.set(task.id, task);
	}
}

export function ingestSubTasks(subtasksData: (SubTaskGET | SubTaskWithImagesGET)[]) {
	for (const subtask of subtasksData) {
		subtasks.set(subtask.id, subtask);
	}
}

// Clear functions for cleanup
export function clearInstances() {
	instances.clear();
}

export function clearStudies() {
	studies.clear();
}

export function clearTasks() {
	tasks.clear();
}

export function clearSubTasks() {
	subtasks.clear();
}
