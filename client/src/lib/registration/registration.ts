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
}

export class Registration {


    private pointer: Pointer = { image_id: '', position: { x: 0, y: 0, index: 0 } };
    private cache = new Map<string, Position | undefined>();

    private readonly mappings = new Mapper<mappingFunction>();
    private readonly registrationItems = new Mapper<RegistrationItem>();
    private shortestPaths: { [node: string]: { [node: string]: string[] } } = allPairsShortestPaths(this.mappings);

    constructor() { }

    // set the pointer position for the given image
    setPosition(source: string, position: Position) {
        this.pointer = { image_id: source, position };
        this.cache.clear();
        this.cache.set(source, position);
    }

    getPosition(image_id: string): Position | undefined {
        if (this.cache.has(image_id)) {
            return this.cache.get(image_id);
        }
        const source = this.pointer.image_id;
        const target = image_id;
        let path = this.shortestPaths[source]?.[target];
        if (!path) {
            return;
        }
        let current = source;
        let currentPosition: Position | undefined = this.pointer.position;
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
        this.cache.set(image_id, currentPosition);
        return currentPosition;
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
        this.shortestPaths = allPairsShortestPaths(this.mappings);
    }

    getLinkedImgIds(source: string): Set<string> {
        return new Set(Object.keys(this.shortestPaths[source] ?? {}));
    }

    mapPosition(source: string, target: string, position: Position): Position | undefined {
        if (source == target) {
            return position;
        }
        return this.mappings.get(source, target)?.(position);
    }


    getRegistrationItem(source: string, target: string): RegistrationItem | undefined {
        return this.registrationItems.get(source, target);
    }
}


function allPairsShortestPaths(graph: Mapper<mappingFunction>): { [node: string]: { [node: string]: string[] } } {

    const distances: { [node: string]: { [node: string]: number } } = {};
    const predecessors: { [node: string]: { [node: string]: string } } = {};

    const nodeSet = new Set<string>();
    for (const [k, v] of graph.sourceEntries()) {
        nodeSet.add(k);
        for (const k of v.keys())
            nodeSet.add(k);
    }
    const keys: string[] = [...nodeSet];

    // Initialize the distances to Infinity for all pairs of nodes
    for (const node1 of keys) {
        distances[node1] = {};
        predecessors[node1] = {};
        for (const node2 of keys) {
            distances[node1][node2] = Infinity;
        }
        distances[node1][node1] = 0;
    }

    // Set the distances for the edges in the graph
    for (const [node1, neighbors] of graph.sourceEntries()) {
        for (const node2 of neighbors.keys()) {
            distances[node1][node2] = 1;
            predecessors[node1][node2] = node1;
        }
    }

    // Compute the shortest path between every pair of nodes
    for (const k of keys) {
        for (const i of keys) {
            for (const j of keys) {
                if (distances[i][j] > distances[i][k] + distances[k][j]) {
                    distances[i][j] = distances[i][k] + distances[k][j];
                    predecessors[i][j] = predecessors[k][j];
                }
            }
        }
    }

    function getPath(start: string, end: string) {
        const path = [end];
        let current = end;
        while (current !== start) {
            current = predecessors[start][current];
            if (!current) {
                return null;
            }
            path.unshift(current);
        }
        return path;
    }

    // Construct the shortest path between every pair of nodes
    const paths: { [node: string]: { [node: string]: string[] } } = {};
    for (const node1 of keys) {
        paths[node1] = {};
        for (const node2 of keys) {
            const path = getPath(node1, node2);
            if (path) {
                paths[node1][node2] = path;
            }
        }
    }

    return paths;
}
