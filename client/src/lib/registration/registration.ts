import type { Position } from "$lib/types";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { photoLocatorsToRegistrationItems, type PhotoLocator } from "./photoLocators";
import { OCTToProj, ProjToOCT } from "./projectionRegistration";
import type { mappingFunction, RegistrationItem } from "./registrationItem";

export type Pointer = {
    image_id: string,
    position: Position
};

class Mapper<T> {
    private readonly mappings = new Map<string, Map<string, T>>();

    set(source: string, target: string, val: T) {
        if (!this.mappings.has(source)) {
            this.mappings.set(source, new Map());
        }
        this.mappings.get(source)!.set(target, val);
    }

    get(source: string, target: string): T | undefined {
        return this.mappings.get(source)?.get(target);
    }

    sourceEntries(): Iterable<[string, Map<string, T>]> {
        return this.mappings.entries();
    }

    targets(source: string): Iterable<string> {
        return this.mappings.get(source)?.keys() ?? [];
    }
}

export class Registration {


    private pointer: Pointer = { image_id: '', position: { x: 0, y: 0, index: 0 } };
    private cache = new Map<string, Position | undefined>();
    private loadedImageIds = new Set<string>();

    private readonly mappings = new Mapper<mappingFunction>();
    private readonly registrationItems = new Mapper<RegistrationItem>();
    private shortestPaths: { [node: string]: { [node: string]: string[] } } = allPairsShortestPaths(this.mappings, this.loadedImageIds);

    // Debounce state for coalescing path recomputation across multiple imports
    private pathsDirty = false;
    private recomputeScheduled = false;

    constructor() { }

    // set the pointer position for the given image
    setPosition(source: string, position: Position) {
        this.pointer = { image_id: source, position };
        this.cache.clear();
        this.cache.set(source, position);
    }

    private mapPositionAlongPath(source: string, target: string, startPosition: Position): Position | undefined {
        const path = this.shortestPaths[source]?.[target];
        if (!path) {
            return;
        }
        let current = source;
        let currentPosition: Position | undefined = startPosition;
        for (let i = 1; i < path.length; i++) {
            const next = path[i];
            const func = this.mappings.get(current, next);
            if (!func) {
                console.log('no mapping found', current, next);
                return;
            }
            currentPosition = func(currentPosition);
            if (!currentPosition) {
                return;
            }
            current = next;
        }
        return currentPosition;
    }

    getPosition(image_id: string): Position | undefined {
        
        if (this.cache.has(image_id)) {
            return this.cache.get(image_id);
        }
        
        const source = this.pointer.image_id;
        const target = image_id;
        const currentPosition = this.mapPositionAlongPath(source, target, this.pointer.position);
        if (currentPosition !== undefined) {
            this.cache.set(image_id, currentPosition);
        }
        return currentPosition;
    }

    private scheduleRecompute() {
        if (this.recomputeScheduled) return;
        this.recomputeScheduled = true;
        queueMicrotask(() => {
            this.recomputeScheduled = false;
            if (!this.pathsDirty) return;
            this.pathsDirty = false;

            console.log('recomputing shortest paths', this.mappings, this.loadedImageIds);
            const start = performance.now();
            this.shortestPaths = allPairsShortestPaths(this.mappings, this.loadedImageIds);
            const duration = performance.now() - start;
            console.log(`allPairsShortestPaths computation took ${duration.toFixed(2)} ms`);
        });
    }

    // Expose an explicit synchronous recomputation when needed by callers
    public recomputePathsNow() {
        this.pathsDirty = false;
        this.recomputeScheduled = false;
        this.shortestPaths = allPairsShortestPaths(this.mappings, this.loadedImageIds);
    }

    public setLoadedImageIds(ids: Iterable<string>) {
        this.loadedImageIds = new Set(ids);
        this.pathsDirty = true;
        this.scheduleRecompute();
    }

    async addImage(image: AbstractImage, photoLocators: PhotoLocator[]) {
        const items = photoLocatorsToRegistrationItems(photoLocators);
        if (image.is3D) {
            items.push(new OCTToProj(image.instance));
            items.push(new ProjToOCT(image.instance));
        }
        this.importRegistrationItems(items);
    }


    importRegistrationItems(items: Iterable<RegistrationItem>, addInverse = true) {
        for (const item of items) {
            this.registrationItems.set(item.source, item.target, item);
            this.mappings.set(item.source, item.target, p => item.mapping(p));
            if (addInverse) {
                const inverse = item.inverse;
                this.registrationItems.set(item.target, item.source, inverse);
                this.mappings.set(item.target, item.source, p => inverse.mapping(p));
            }
        }
        this.pathsDirty = true;
        this.scheduleRecompute();
    }

    getLinkedImgIds(source: string): Set<string> {
        return new Set(Object.keys(this.shortestPaths[source] ?? {}));
    }

    mapPosition(source: string, target: string, position: Position): Position | undefined {
        if (source == target) {
            return position;
        }
        return this.mapPositionAlongPath(source, target, position);
    }


    getRegistrationItem(source: string, target: string): RegistrationItem | undefined {
        return this.registrationItems.get(source, target);
    }
}


function allPairsShortestPaths(
    graph: Mapper<mappingFunction>,
    allowedNodes?: ReadonlySet<string>
): { [node: string]: { [node: string]: string[] } } {
    const allNodes = new Set<string>();
    for (const [source, neighbors] of graph.sourceEntries()) {
        allNodes.add(source);
        for (const target of neighbors.keys()) {
            allNodes.add(target);
        }
    }
    const keys = [...allNodes];
    const endpoints = allowedNodes ? keys.filter((node) => allowedNodes.has(node)) : keys;

    const paths: { [node: string]: { [node: string]: string[] } } = {};

    function reconstructPath(source: string, target: string, prev: Map<string, string | null>): string[] | null {
        if (!prev.has(target)) {
            return null;
        }
        const path: string[] = [];
        let current: string | null = target;
        while (current !== null) {
            path.push(current);
            if (current === source) {
                break;
            }
            current = prev.get(current) ?? null;
        }
        if (path[path.length - 1] !== source) {
            return null;
        }
        path.reverse();
        return path;
    }

    for (const source of endpoints) {
        const prev = new Map<string, string | null>();
        const queue: string[] = [source];
        prev.set(source, null);

        // BFS shortest paths in unweighted directed graph
        for (let i = 0; i < queue.length; i++) {
            const current = queue[i];
            for (const next of graph.targets(current)) {
                if (prev.has(next)) {
                    continue;
                }
                prev.set(next, current);
                queue.push(next);
            }
        }

        paths[source] = {};
        for (const target of endpoints) {
            const path = reconstructPath(source, target, prev);
            if (path) {
                paths[source][target] = path;
            }
        }
    }

    return paths;
}
