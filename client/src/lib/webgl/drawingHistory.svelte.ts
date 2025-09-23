import type { DrawingArray } from "./mask.svelte";

export interface Serializer<T> {
    serialize: (drawing: DrawingArray) => T;
    deserialize: (serialized: T) => Promise<DrawingArray>;
}

export class DrawingHistory<T> {
    undoStack: T[] = $state([]);
    redoStack: T[] = $state([]);
    canUndo: boolean = $derived.by(() => this.undoStack.length > 1);
    canRedo: boolean = $derived.by(() => this.redoStack.length > 0);


    constructor(private readonly serializer: Serializer<T>,
        public maxSize: number = 10) {
    }

    checkpoint(drawing: DrawingArray): void {
        this.undoStack.push(this.serializer.serialize(drawing));
        if (this.undoStack.length > this.maxSize) {
            this.undoStack.shift();
        }
        this.redoStack.length = 0;
    }

    async undo(): Promise<DrawingArray | undefined> {
        if (this.undoStack.length > 1) {
            this.redoStack.push(this.undoStack.pop()!);
            return this.serializer.deserialize(this.undoStack[this.undoStack.length - 1]);
        }
    }

    async redo(): Promise<DrawingArray | undefined> {
        if (this.redoStack.length > 0) {
            this.undoStack.push(this.redoStack.pop()!);
            return this.serializer.deserialize(this.undoStack[this.undoStack.length - 1]);
        }
    }

    clear() {
        this.undoStack.length = 0;
        this.redoStack.length = 0;
    }
}
