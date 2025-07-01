import { writable, type Readable, derived } from "svelte/store";
import type { DrawingArray } from "./segmentation";

export interface Serializer<T> {
    serialize: (drawing: DrawingArray) => T;
    deserialize: (serialized: T) => Promise<DrawingArray>;
}

export class DrawingHistory<T> {
    undoStack: T[] = [];
    redoStack: T[] = [];

    private readonly maxSize: number;
    private readonly trigger = writable(0);

    constructor(private readonly serializer: Serializer<T>, maxSize: number = 10) {
        this.undoStack = [];
        this.redoStack = [];
        this.trigger.update(n => n + 1);
        this.maxSize = maxSize;
    }

    checkpoint(drawing: DrawingArray): void {
        this.undoStack.push(this.serializer.serialize(drawing));
        if (this.undoStack.length > this.maxSize) {
            this.undoStack.shift();
        }
        this.redoStack.length = 0;
        this.trigger.update(n => n + 1);
    }

    get canUndo(): Readable<boolean> {
        return derived(this.trigger, () => this.undoStack.length > 1);
    }

    get canRedo(): Readable<boolean> {
        return derived(this.trigger, () => this.redoStack.length > 0);
    }

    async undo(): Promise<DrawingArray | undefined> {
        if (this.undoStack.length > 1) {
            this.redoStack.push(this.undoStack.pop()!);
            this.trigger.update(n => n + 1);
            return this.serializer.deserialize(this.undoStack[this.undoStack.length - 1]);
        }
    }

    async redo(): Promise<DrawingArray | undefined> {
        if (this.redoStack.length > 0) {
            this.undoStack.push(this.redoStack.pop()!);
            this.trigger.update(n => n + 1);
            return this.serializer.deserialize(this.undoStack[this.undoStack.length - 1]);
        }

    }
}
