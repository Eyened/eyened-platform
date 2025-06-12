import StringDialogue from './StringDialogue.svelte';
import type { Component } from 'svelte';
import { readonly, writable, type Readable } from 'svelte/store';

export interface Dialogue {
    component: Component;
    props: any;
    resolve: (result: any) => void;
    reject: () => void;
}

export class DialogueManager {
    private _dialogue = writable<Dialogue | undefined>(undefined);
    public dialogue: Readable<Dialogue | undefined> = readonly(this._dialogue);

    constructor() { }

    show<T, P>(component: Component, props: P, onResolve?: (result: T) => void, onReject?: () => void) {

        const reject = () => {
            onReject?.();
            this.hide();
        };
        const resolve = (result: T) => {
            onResolve?.(result);
            this.hide();
        };
        this._dialogue.set({
            component,
            props,
            resolve,
            reject,
        });
    }
    showQuery<T, P>(
        query: string,
        approve: string = 'Yes',
        decline: string = 'Cancel',
        onResolve?: (result: T) => void
    ) {
        this.show(StringDialogue, { query, approve, decline }, onResolve);
    }
    hide() {
        this._dialogue.set(undefined);
    }
}

// Create a singleton instance
export const dialogueManager = new DialogueManager(); 