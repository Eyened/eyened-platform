import { browser } from "$app/environment";
import { goto } from "$app/navigation";
import { page } from "$app/state";
import type { ComponentDef } from "$lib/data-loading/globalContext.svelte";
import { loadSearchParams } from "$lib/datamodel/api";
import type { Instance } from "$lib/datamodel/instance";
import { clearData } from "$lib/datamodel/model";

export class BrowserContext {

    selection: number[] = $state([]);
    popup: ComponentDef | null = $state(null);
    loading: boolean = $state(false);
    constructor(selection: number[]) {
        this.selection = selection;
    }

    toggleInstance(instance: Instance) {
        if (this.selection.includes(instance.id)) {
            this.selection.splice(this.selection.indexOf(instance.id), 1);
        } else {
            this.selection.push(instance.id);
        }
    }

    async loadDataFromServer() {
        if (!browser) {
            return;
        }
        this.loading = true;
        // removes existing entities from the model
        clearData();
        
        await loadSearchParams(page.url.searchParams);
        this.loading = false;
    }
}

export async function toggleParam(variable: string, value: string) {
    if (!browser) return;

    const params = page.url.searchParams;
    const values = params.getAll(variable);
    if (values.includes(value)) {
        values.splice(values.indexOf(value), 1);
    } else {
        values.push(value);
    }
    params.delete(variable);
    values.forEach(v => params.append(variable, v));
    await goto(`?${params.toString()}`);
}

export async function removeParam(variable: string, value: string) {
    if (!browser) return;

    const params = page.url.searchParams;
    const values = params.getAll(variable);
    const index = values.indexOf(value);
    if (index >= 0) {
        values.splice(index, 1);
        params.delete(variable);
        values.forEach(v => params.append(variable, v));
        await goto(`?${params.toString()}`);
    }
}