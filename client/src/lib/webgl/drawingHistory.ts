import { writable, type Readable, derived } from "svelte/store";

export class DrawingHistory {
    undoStack: string[] = [];
    redoStack: string[] = [];

    private readonly maxSize: number;
    private readonly trigger = writable(0);
    initialized = false;

    constructor(maxSize: number = 10) {
        this.undoStack = [];
        this.redoStack = [];
        this.trigger.update(n => n + 1);
        this.maxSize = maxSize;
    }

    initialize(drawing: string): void {
        this.initialized = true;
        this.undoStack = [drawing];
        this.redoStack = [];
        this.trigger.update(n => n + 1);
    }

    checkpoint(drawing: string): void {
        this.undoStack.push(drawing);
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

    undo(): string | undefined {
        if (this.undoStack.length > 1) {
            this.redoStack.push(this.undoStack.pop()!);
            this.trigger.update(n => n + 1);
            return this.undoStack[this.undoStack.length - 1];
        }
    }

    redo(): string | undefined {
        if (this.redoStack.length > 0) {
            this.undoStack.push(this.redoStack.pop()!);
            this.trigger.update(n => n + 1);
            return this.undoStack[this.undoStack.length - 1];
        }

    }
}

export class UndoRedo {
    private history: DrawingHistory[];

    constructor(
        readonly depth: number,
        public maxUndo: number = 10
    ) {
        
        this.history = Array.from({ length: depth }).map(() => new DrawingHistory(maxUndo));
    }

    isInitialized(scanNr: number): boolean {
        return this.history[scanNr].initialized;
    }

    initialize(scanNr: number, drawing: string): void {
        this.history[scanNr].initialize(drawing);
    }

    checkpoint(scanNr: number, drawing: string): void {
        this.history[scanNr].checkpoint(drawing);
    }

    canUndo(scanNr: number): Readable<boolean> {
        return this.history[scanNr].canUndo;
    }

    canRedo(scanNr: number): Readable<boolean> {
        return this.history[scanNr].canRedo;
    }
    
    undo(scanNr: number): string | undefined {
        return this.history[scanNr].undo();
    }

    redo(scanNr: number): string | undefined {
        return this.history[scanNr].redo();
    }

}