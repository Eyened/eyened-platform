import { browser } from "$app/environment";
import { goto } from "$app/navigation";

import {
    getInstancesSignature,
    getStudiesSignature,
    searchInstances,
    searchStudies,
} from "$lib/data/api";
import { instances, studies } from "$lib/data/stores.svelte";
import type {
    ImageGET,
    SearchCondition as SearchConditionT,
    SearchQuery,
    SignatureField as SignatureFieldT,
    StudyGET,
    StudySearchCondition,
    StudySearchQuery,
} from "../../types/openapi_types";
import type { BuilderRow } from "$lib/components/ui/condition-builder/types.js";
import {
    acceptsRow,
    conditionsToRows,
    isIsoDate,
    labelFor,
    rowsToConditions,
} from "./conditionConfig";

export type QueryMode = "studies" | "instances";
export type DisplayMode = "instance" | "study";

export type Condition = SearchConditionT;
export type SignatureField = SignatureFieldT;
export type InstancesSortBy = SearchQuery["order_by"];
export type StudiesSortBy = StudySearchQuery["order_by"];
export type SortDirection = "ASC" | "DESC";
export type SortBy = InstancesSortBy | StudiesSortBy;

/** The search form's one notification; the latest replaces the previous. */
export type SearchNotification = {
    kind: "error" | "warning";
    title: string;
    subtitle: string;
};

/** One value per Basic field; each filled field is its own condition (AND). */
export type BasicFields = {
    patientIdentifier: string;
    studyDate: string;
    projectName: string;
};

/** The columns both modes sort by. */
export const SORT_COLUMNS: SortBy[] = [
    "Study Date",
    "Patient Birthdate",
    "Date Inserted",
];

const EMPTY_BASIC: BasicFields = {
    patientIdentifier: "",
    studyDate: "",
    projectName: "",
};

type SearchResult = {
    result_ids?: (string | number)[];
    count?: number | null;
    studies?: { id: number }[];
};

function basicConditions(basic: BasicFields): Condition[] {
    const conditions: Condition[] = [];
    const id = basic.patientIdentifier.trim();
    if (id)
        conditions.push({
            type: "default",
            variable: "Patient Identifier",
            operator: "==",
            value: id,
        });
    if (isIsoDate(basic.studyDate))
        conditions.push({
            type: "default",
            variable: "Study Date",
            operator: "==",
            value: basic.studyDate,
        });
    if (basic.projectName)
        conditions.push({
            type: "default",
            variable: "Project Name",
            operator: "IN",
            value: [basic.projectName],
        });
    return conditions;
}

// A condition fills a quick field only if it fits it exactly; the first fit wins, the rest become rows.
function splitConditions(conditions: Condition[]): {
    basic: BasicFields;
    rest: Condition[];
} {
    const basic = { ...EMPTY_BASIC };
    const rest: Condition[] = [];
    for (const c of conditions) {
        const text = typeof c.value === "string" ? c.value : "";
        if (
            !basic.patientIdentifier &&
            c.variable === "Patient Identifier" &&
            c.operator === "==" &&
            text.trim()
        )
            basic.patientIdentifier = text;
        else if (
            !basic.studyDate &&
            c.variable === "Study Date" &&
            c.operator === "==" &&
            isIsoDate(text)
        )
            basic.studyDate = text;
        else if (
            !basic.projectName &&
            c.variable === "Project Name" &&
            c.operator === "IN" &&
            Array.isArray(c.value) &&
            c.value.length === 1
        )
            basic.projectName = String(c.value[0]);
        else rest.push(c);
    }
    return { basic, rest };
}

export class BrowserContext {
    // Default smallest per current mode
    getDefaultLimit(): number {
        return this.queryMode === "instances" && this.displayMode === "instance"
            ? 100
            : 10;
    }

    limitOptionsStudies = [10, 20, 30, 40, 50];
    limitOptionsInstances = [100, 200, 500, 1000];

    selectedIds: string[] = $state([]);
    queryMode: QueryMode = $state("studies");
    displayMode: DisplayMode = $state("study");
    loading: boolean = $state(false);

    // When false, searches/pagination will not push state to the URL.
    // Used when the browser is embedded as a widget (e.g. overlays).
    urlSync: boolean = $state(true);

    page: number = $state(0);
    limit: number = $state(10);
    count: number = $state(0);
    sortBy: SortBy = $state("Study Date");
    sortDirection: SortDirection = $state("ASC");

    // NEW: ordered arrays for rendering
    orderedInstanceIds: string[] = $state([]);
    orderedStudyIds: number[] = $state([]);

    /** Condition builder rows: the only source of the Advanced conditions. */
    advancedRows: BuilderRow[] = $state([]);
    basic: BasicFields = $state({ ...EMPTY_BASIC });
    notification: SearchNotification | null = $state(null);
    /** A search ran since the page opened, or since the Studies/Images switch cleared the results. */
    hasSearched: boolean = $state(false);
    /** The last search failed: no results and no count. */
    failed: boolean = $state(false);
    signaturesLoaded: boolean = $state(false);

    // Only the latest search's response is applied (B12).
    private searchSeq = 0;

    // Signature state for dynamic filters
    instancesSignature: SignatureField[] = $state([]);
    studiesSignature: SignatureField[] = $state([]);

    thumbnailSize: string = $state("8em");

    // Derived: depends on queryMode + signatures
    activeSignature: SignatureField[] = $derived(
        this.queryMode === "instances"
            ? this.instancesSignature
            : this.studiesSignature,
    );

    limitOptions: number[] = $derived(
        this.queryMode === "instances" && this.displayMode === "instance"
            ? this.limitOptionsInstances
            : this.limitOptionsStudies,
    );

    /** The quick fields' and the builder's complete conditions, ANDed; incomplete rows are left out. */
    activeConditions: Condition[] = $derived([
        ...basicConditions(this.basic),
        ...rowsToConditions(this.advancedRows, this.activeSignature),
    ]);

    /** Search needs the search fields and at least one complete condition (B9). */
    canSearch: boolean = $derived(
        this.signaturesLoaded && this.activeConditions.length > 0,
    );

    private getInstance(id: string): ImageGET | undefined {
        return instances.get(id);
    }

    selectedInstances = $derived(
        this.selectedIds
            .map((id) => this.getInstance(id))
            .filter((x): x is ImageGET => x !== undefined),
    );

    // Derived: ordered instances for rendering
    orderedInstances = $derived(
        this.orderedInstanceIds
            .map((id) => this.getInstance(id))
            .filter((x): x is ImageGET => x !== undefined),
    );

    // Derived: ordered studies for rendering
    orderedStudies = $derived(
        this.orderedStudyIds
            .map((id) => studies.get(id))
            .filter((x): x is StudyGET => x !== undefined),
    );

    // Helper to get allowed values (returns [] if type marker)
    getValueOptions(fieldName: string): string[] {
        const f = this.activeSignature.find((s) => s.name === fieldName);
        return Array.isArray(f?.values) ? (f!.values as string[]) : [];
    }

    private async loadSignatureFields() {
        const [instances, studies] = await Promise.all([
            getInstancesSignature(),
            getStudiesSignature(),
        ]);
        this.instancesSignature = instances as SignatureField[];
        this.studiesSignature = studies as SignatureField[];
    }

    async loadSignatures() {
        try {
            await this.loadSignatureFields();
            this.signaturesLoaded = true;
        } catch {
            this.notification = {
                kind: "error",
                title: "Could not load search fields",
                subtitle: "Reload the page to try again.",
            };
        }
    }

    /** Restore state from the URL; true when the filters have conditions. */
    restoreFromParams(params: URLSearchParams): boolean {
        const qm = params.get("queryMode");
        if (qm === "instances" || qm === "studies") this.queryMode = qm;
        const dm = params.get("displayMode");
        if (dm === "instance" || dm === "study") this.displayMode = dm;
        const sortBy = SORT_COLUMNS.find((c) => c === params.get("order_by"));
        if (sortBy) this.sortBy = sortBy;
        const order = params.get("order");
        if (order === "ASC" || order === "DESC") this.sortDirection = order;
        const limit = Number(params.get("limit"));
        this.limit = this.limitOptions.includes(limit)
            ? limit
            : this.getDefaultLimit();
        const page = params.get("page") ?? "";
        this.page = /^\d+$/.test(page) ? Number(page) : 0;

        // No conditions param (the header's Browser link): keep the form.
        if (params.has("conditions"))
            this.setFilters(decodeConditions(params.get("conditions") ?? ""));
        return this.activeConditions.length > 0;
    }

    /** Studies/Images: keeps the selection, the sort and the conditions the new mode accepts (B2, B13). */
    async resetForQueryModeChange(queryMode: QueryMode) {
        const searchAgain = this.hasSearched;
        const from = this.activeSignature;
        this.queryMode = queryMode;
        this.displayMode = queryMode === "instances" ? "instance" : "study";
        this.page = 0;
        this.limit = this.getDefaultLimit();
        this.clearResults();
        this.failed = false;
        this.hasSearched = false;

        const removed = this.advancedRows.filter(
            (r) => !acceptsRow(r, this.activeSignature),
        );
        if (removed.length > 0) {
            this.advancedRows = this.advancedRows.filter(
                (r) => !removed.includes(r),
            );
            const labels = removed
                .map((r) => labelFor(r.property ?? "", from))
                .filter((l, i, all) => all.indexOf(l) === i);
            this.notification = {
                kind: "warning",
                title: "Conditions removed",
                subtitle: `${queryMode === "instances" ? "Images" : "Studies"} can't use ${labels.join(", ")}.`,
            };
        }
        if (searchAgain && this.activeConditions.length > 0)
            await this.runSearch();
    }

    /** Empties both filter groups, the notification and the results (B9); the selection stays. */
    clearFilters() {
        this.basic = { ...EMPTY_BASIC };
        this.advancedRows = [];
        this.notification = null;
        this.searchSeq++; // drop a search still in flight
        this.loading = false;
        this.failed = false;
        this.hasSearched = false;
        this.clearResults();
        this.updateURL([]);
    }

    /** Search the current page (pagination, URL restore, a widget's seed). */
    async search() {
        return this.runSearch();
    }

    /** The Search button and Enter: always page 1 (B11). */
    async submitSearch() {
        this.page = 0;
        return this.runSearch();
    }

    // Sort, page and page size apply at once, but only once a search has run (B5).
    async setPage(page: number) {
        this.page = page;
        if (this.hasSearched) await this.runSearch();
    }

    async setPageSize(limit: number) {
        this.limit = limit;
        this.page = 0;
        if (this.hasSearched) await this.runSearch();
    }

    async setSort(by: SortBy, direction: SortDirection) {
        this.sortBy = by;
        this.sortDirection = direction;
        this.page = 0;
        if (this.hasSearched) await this.runSearch();
    }

    // Seed state for an embedded/widget usage (no URL involved).
    applyInitialConditions(
        conds: Condition[],
        opts: { queryMode?: QueryMode; displayMode?: DisplayMode } = {},
    ) {
        if (opts.queryMode) this.queryMode = opts.queryMode;
        if (opts.displayMode) this.displayMode = opts.displayMode;
        this.setFilters(conds);
    }

    private setFilters(conditions: Condition[]) {
        const { basic, rest } = splitConditions(conditions);
        this.basic = basic;
        this.advancedRows = conditionsToRows(rest, this.activeSignature);
    }

    // Refresh signatures (e.g., after creating/modifying tags)
    async refreshSignatures() {
        return this.loadSignatureFields();
    }

    toggleInstance(instance: ImageGET) {
        const i = this.selectedIds.indexOf(instance.id);
        if (i !== -1) {
            this.selectedIds.splice(i, 1);
        } else {
            this.selectedIds.push(instance.id);
        }
    }

    openTab(imageIds: string[]) {
        const suffix_string = `?instances=${imageIds.join(",")}`;
        const url = `${window.location.origin}/view${suffix_string}`;
        window.open(url, "_blank")?.focus();
    }

    private async runSearch() {
        const query = this.activeConditions;
        if (query.length === 0) return;
        const seq = ++this.searchSeq;
        this.updateURL(query);
        this.loading = true;
        this.hasSearched = true;
        // On the landing page a search clears the selection (v1; PR 5 changes this). A widget keeps it.
        if (this.urlSync) this.selectedIds = [];
        try {
            const res: SearchResult = await this.executeSearch(query);
            if (seq !== this.searchSeq) return;
            this.failed = false;
            if (this.notification?.kind === "error") this.notification = null;
            this.processSearchResults(res);
        } catch {
            if (seq !== this.searchSeq) return;
            this.failed = true;
            this.clearResults();
            this.notification = {
                kind: "error",
                title: "Search failed",
                subtitle: "Try searching again.",
            };
        } finally {
            if (seq === this.searchSeq) this.loading = false;
        }
    }

    private clearResults() {
        this.count = 0;
        this.orderedInstanceIds = [];
        this.orderedStudyIds = [];
    }

    private updateURL(query: Condition[]) {
        if (!this.urlSync) return;
        const params = new URLSearchParams([
            ["page", String(this.page)],
            ["limit", String(this.limit)],
            ["conditions", encodeConditions(query)],
            ["order_by", String(this.sortBy)],
            ["order", this.sortDirection],
            ["queryMode", this.queryMode],
            ["displayMode", this.displayMode],
        ]);
        // Replace, not push: Back leaves the page instead of changing only the URL (B6).
        // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
        goto(`?${params}`, {
            replaceState: true,
            keepFocus: true,
            noScroll: true,
        });
    }

    private executeSearch(query: Condition[]) {
        const body = {
            conditions: query,
            limit: this.limit,
            page: this.page,
            order_by: this.sortBy,
            order: this.sortDirection,
            include_count: true,
        };
        return this.queryMode === "instances"
            ? searchInstances(body as SearchQuery)
            : searchStudies({
                  ...body,
                  conditions: query as unknown as StudySearchCondition[],
              } as StudySearchQuery);
    }

    // searchInstances/searchStudies ingest into the stores; keep the ids in the server's order,
    // which is order_by's (server/routes/search.py), not the date (B1).
    private processSearchResults(res: SearchResult) {
        this.count = res.count ?? 0;
        const ids = res.result_ids ?? [];
        if (this.queryMode === "instances") {
            this.orderedInstanceIds = ids.map(String);
            this.orderedStudyIds = (res.studies ?? []).map((s) => s.id);
        } else {
            this.orderedInstanceIds = [];
            this.orderedStudyIds = ids.map(Number);
        }
    }
}

// Encoding helpers for URL round-trip
function serializeValue(value: string | number | string[] | null): string {
    // JSON string; do NOT pre-encode elements; callers will URI-encode once
    return JSON.stringify(value);
}

function deserializeValue(encoded: string): string | number | string[] | null {
    // First-level decode of the whole JSON payload
    const raw = decodeURIComponent(encoded);
    return JSON.parse(raw);
}

export function encodeConditions(conditions: Condition[]): string {
    return conditions
        .map((condition) => {
            const encodedVariable = encodeURIComponent(
                (condition as any).variable,
            );
            const encodedOperator = encodeURIComponent(
                (condition as any).operator,
            );
            const encodedValue = encodeURIComponent(
                serializeValue((condition as any).value ?? null),
            );
            const encodedType = encodeURIComponent(
                (condition as any).type ?? "default",
            );
            const encodedModel = encodeURIComponent(
                (condition as any).type === "attribute"
                    ? ((condition as any).model ?? "")
                    : "",
            );
            const encodedFeature = encodeURIComponent(
                (condition as any).type === "attribute"
                    ? ((condition as any).feature ?? "")
                    : "",
            );
            return `${encodedVariable}:${encodedOperator}:${encodedValue}:${encodedType}:${encodedModel}:${encodedFeature}`;
        })
        .join(";");
}

export function decodeConditions(urlString: string): Condition[] {
    if (urlString === "") return [];
    return urlString.split(";").map((conditionString) => {
        const parts = conditionString.split(":");
        const [v, o, val, t, m, f] = parts; // Add 'f' for feature
        const variable = decodeURIComponent(v);
        const operator = decodeURIComponent(o) as Condition["operator"];
        const value = deserializeValue(val);
        const type = t ? (decodeURIComponent(t) as any) : "default";
        const model = m ? decodeURIComponent(m) : undefined;
        const feature = f ? decodeURIComponent(f) : undefined; // Decode feature
        if (type === "attribute") {
            return {
                type: "attribute",
                variable,
                operator: operator as any,
                value,
                model,
                feature: feature || undefined, // Include feature, convert empty string to undefined
            } as any;
        }
        return {
            type: "default",
            variable: variable as any,
            operator: operator as any,
            value,
        } as any;
    });
}

// URL param helpers for component compatibility
export function getSearchParams(): URLSearchParams {
    const src = browser ? window.location.search : "";
    return new URLSearchParams(src);
}

export async function setParam(key: string, value: string | null) {
    const params = getSearchParams();
    params.delete(key);
    if (value !== null && value !== "") params.set(key, value);
    // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
    await goto(`?${params.toString()}`);
}

export async function removeParam(key: string, value?: string) {
    const params = getSearchParams();
    if (value === undefined) {
        params.delete(key);
    } else {
        const values = params.getAll(key).filter((v) => v !== value);
        params.delete(key);
        values.forEach((v) => params.append(key, v));
    }
    // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
    await goto(`?${params.toString()}`);
}

export async function toggleParam(key: string, value: string) {
    const params = getSearchParams();
    const values = new Set(params.getAll(key));
    if (values.has(value)) {
        values.delete(value);
    } else {
        values.add(value);
    }
    params.delete(key);
    Array.from(values).forEach((v) => params.append(key, v));
    // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
    await goto(`?${params.toString()}`);
}
