import type { ComponentDef } from "$lib/data-loading/globalContext.svelte";
import type { Instance } from "$lib/datamodel/instance";
import type { ItemCollection } from "$lib/datamodel/itemList";

export class BrowserContext {

    selection: number[] = $state([]);
    popup: ComponentDef | null = $state(null);

    constructor(public readonly instances: ItemCollection<Instance>, selection: number[]) {
        this.selection = selection;
    }

    toggleInstance(instance: Instance) {
        if (this.selection.includes(instance.id)) {
            this.selection.splice(this.selection.indexOf(instance.id), 1);
        } else {
            this.selection.push(instance.id);
        }
    }
}