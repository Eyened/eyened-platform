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

// ReactiveMap extends SvelteMap with array-like iteration methods
class ReactiveMap<K, V> extends SvelteMap<K, V> {
	// Returns array of filtered values
	filter(predicate: (value: V, key: K, map: this) => boolean): V[] {
		const result: V[] = [];
		for (const [key, value] of this.entries()) {
			if (predicate(value, key, this)) {
				result.push(value);
			}
		}
		return result;
	}

	// Returns array of mapped values
	map<U>(callback: (value: V, key: K, map: this) => U): U[] {
		const result: U[] = [];
		for (const [key, value] of this.entries()) {
			result.push(callback(value, key, this));
		}
		return result;
	}

	// Returns first matching value or undefined
	find(predicate: (value: V, key: K, map: this) => boolean): V | undefined {
		for (const [key, value] of this.entries()) {
			if (predicate(value, key, this)) {
				return value;
			}
		}
		return undefined;
	}

	// Returns true if any value matches
	some(predicate: (value: V, key: K, map: this) => boolean): boolean {
		for (const [key, value] of this.entries()) {
			if (predicate(value, key, this)) {
				return true;
			}
		}
		return false;
	}

	// Returns true if all values match
	every(predicate: (value: V, key: K, map: this) => boolean): boolean {
		for (const [key, value] of this.entries()) {
			if (!predicate(value, key, this)) {
				return false;
			}
		}
		return true;
	}

	// Reduce over values
	reduce<U>(callback: (acc: U, value: V, key: K, map: this) => U, initial: U): U {
		let acc = initial;
		for (const [key, value] of this.entries()) {
			acc = callback(acc, value, key, this);
		}
		return acc;
	}

	// Execute function for each value
	forEach(callback: (value: V, key: K, map: this) => void): void {
		for (const [key, value] of this.entries()) {
			callback(value, key, this);
		}
	}
}

// Simple stores - just maps of plain data by ID
export const instances = new ReactiveMap<number, InstanceGET>();
export const instanceMetas = new ReactiveMap<number, InstanceMeta>();  // Lightweight references
export const studies = new ReactiveMap<number, StudyGET>();
export const tags = new ReactiveMap<number, TagGET>();
export const features = new ReactiveMap<number, FeatureGET>();
export const formSchemas = new ReactiveMap<number, FormSchemaGET>();
export const segmentations = new ReactiveMap<number, SegmentationGET>();
export const modelSegmentations = new ReactiveMap<number, ModelSegmentationGET>();
export const formAnnotations = new ReactiveMap<number, FormAnnotationGET>();
export const tasks = new ReactiveMap<number, TaskGET>();
export const subtasks = new ReactiveMap<number, SubTaskGET | SubTaskWithImagesGET>();

// Secondary indexes for common lookups
export const formSchemasByName = new ReactiveMap<string, FormSchemaGET>();
export const featuresByName = new ReactiveMap<string, FeatureGET>();
export const tagsByName = new ReactiveMap<string, TagGET>();

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
