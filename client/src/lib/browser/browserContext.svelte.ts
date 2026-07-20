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
    AttributeCondition,
    DefaultCondition,
    ImageGET,
    SearchCondition as SearchConditionT,
    SearchQuery,
    SearchResponse,
    SignatureField as SignatureFieldT,
    StudyGET,
    StudySearchCondition,
    StudySearchQuery,
    StudySearchResponse,
} from "../../types/openapi_types";

export type QueryMode = "studies" | "instances";
export type DisplayMode = "instance" | "study";
export type FilterMode = "basic" | "advanced";

export type Condition = SearchConditionT;
export type SignatureField = SignatureFieldT;
export type InstancesSortBy = SearchQuery["order_by"];
export type StudiesSortBy = StudySearchQuery["order_by"];
export type SortDirection = "ASC" | "DESC";

type BrowserSearchResponse = SearchResponse | StudySearchResponse;

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
    filterMode: FilterMode = $state("basic");

    // When false, searches/pagination will not push state to the URL.
    // Used when the browser is embedded as a widget (e.g. overlays).
    urlSync: boolean = $state(true);

    page: number = $state(0);
    limit: number = $state(10);
    count: number = $state(0);
    sortBy: InstancesSortBy | StudiesSortBy = $state("Study Date");
    sortDirection: SortDirection = $state("ASC");

    resultIds: Set<number> = $state(new Set());

    // NEW: ordered arrays for rendering
    orderedInstanceIds: string[] = $state([]);
    orderedStudyIds: number[] = $state([]);

    // renamed
    advancedConditions: Condition[] = $state([]);

    // new
    basicCondition: Condition | null = $state(null);

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

    toggleFilterMode() {
        this.filterMode = this.filterMode === "basic" ? "advanced" : "basic";
    }

    // Helper to get allowed values (returns [] if type marker)
    getValueOptions(fieldName: string): string[] {
        const f = this.activeSignature.find((s) => s.name === fieldName);
        return Array.isArray(f?.values) ? (f!.values as string[]) : [];
    }

    // Get signature field by variable name (handles attribute encoding)
    private getFieldSignature(fieldValue: string): SignatureField | undefined {
        if (fieldValue.includes("__")) {
            const parts = fieldValue.split("__");
            if (parts.length === 3) {
                const [model, feature, name] = parts;
                return this.activeSignature.find(
                    (s) =>
                        s.name === name &&
                        s.model === model &&
                        (feature === "none"
                            ? !s.feature
                            : s.feature === feature),
                );
            }
        }
        return this.activeSignature.find((s) => s.name === fieldValue);
    }

    // Get operator options for a field based on its signature
    private getOperatorOptions(fieldName: string): Condition["operator"][] {
        const sig = this.getFieldSignature(fieldName);
        if (!sig) return [];

        const ops: Condition["operator"][] = [];

        if (Array.isArray(sig.values)) {
            ops.push("IN");
        } else {
            switch (sig.values) {
                case "string":
                    ops.push("==");
                    // Free-text fields flagged as multi (e.g. Patient Identifier)
                    // additionally support matching several values at once.
                    if (sig.multi) ops.push("IN");
                    break;
                case "int":
                case "float":
                case "date":
                    ops.push(">", "<", "==");
                    break;
                default:
                    ops.push("==");
            }
        }

        if (sig.nullable) {
            ops.push("IS NULL" as Condition["operator"]);
        }

        return ops;
    }

    // Get default operator for a field
    private getDefaultOperator(fieldName: string): Condition["operator"] {
        const sig = this.getFieldSignature(fieldName);
        if (!sig) return "==";
        return Array.isArray(sig.values) ? "IN" : "==";
    }

    // Coerce value based on field type
    private coerceValue(
        value: unknown,
        fieldType: string | string[],
    ): Condition["value"] {
        if (Array.isArray(fieldType)) {
            if (Array.isArray(value)) {
                return value.map(String);
            }
            if (value == null || value === "") {
                return [];
            }
            return [String(value)];
        }

        switch (fieldType) {
            case "int":
                return typeof value === "string"
                    ? parseInt(value, 10) || 0
                    : (value as number);
            case "float":
                return typeof value === "string"
                    ? parseFloat(value) || 0
                    : (value as number);
            case "date":
            case "string":
            default:
                return value as Condition["value"];
        }
    }

    // Normalize a single condition against current signature
    private normalizeCondition(condition: Condition): Condition | null {
        const sig = this.getFieldSignature(condition.variable);
        if (!sig) return null; // Drop unknown fields

        const allowedOps = this.getOperatorOptions(condition.variable);
        const operator = allowedOps.includes(condition.operator)
            ? condition.operator
            : this.getDefaultOperator(condition.variable);

        let value = condition.value;
        if (operator !== "IS NULL") {
            value = this.coerceValue(condition.value, sig.values);
            // IN always operates on a list of values, even for free-text fields
            // whose signature type is a scalar (e.g. Patient Identifier).
            if (operator === "IN" && !Array.isArray(value)) {
                value = value == null || value === "" ? [] : [String(value)];
            }
        }

        if (condition.type === "attribute") {
            const normalized: AttributeCondition = {
                type: "attribute",
                model: condition.model || "",
                variable: condition.variable,
                operator,
                value,
                feature: condition.feature ?? undefined,
            };
            return normalized;
        }

        const normalized: DefaultCondition = {
            type: "default",
            variable: condition.variable as DefaultCondition["variable"],
            operator,
            value,
        };
        return normalized;
    }

    // Normalize conditions array against current signature (public for use in components)
    normalizeConditions(conditions: Condition[]): Condition[] {
        return conditions
            .map((c) => this.normalizeCondition(c))
            .filter((c): c is Condition => c !== null);
    }

    // Set advanced conditions with normalization
    setAdvancedConditions(conditions: Condition[]) {
        this.advancedConditions = this.normalizeConditions(conditions);
    }

    /** Active filter conditions for the current filter mode. */
    getActiveConditions(): Condition[] {
        return this.filterMode === "advanced"
            ? this.advancedConditions
            : this.basicCondition
              ? [this.basicCondition]
              : [];
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
        this.loading = true;
        try {
            await this.loadSignatureFields();
        } finally {
            this.loading = false;
        }
    }

    // Refresh signatures (e.g., after creating/modifying tags)
    async refreshSignatures() {
        return this.loadSignatureFields();
    }

    // Reset state when queryMode changes
    async resetForQueryModeChange(queryMode: QueryMode) {
        const currentConditions = this.getActiveConditions();

        this.page = 0;
        this.limit = this.getDefaultLimit();
        this.count = 0;

        this.sortBy = "Study Date";
        this.sortDirection = "ASC";

        this.resultIds = new Set();
        this.orderedInstanceIds = [];
        this.orderedStudyIds = [];
        this.selectedIds = [];

        if (queryMode == "instances") {
            this.displayMode = "instance";
            this.limit = this.limitOptionsInstances[0];
        } else {
            this.displayMode = "study";
            this.limit = this.limitOptionsStudies[0];
        }

        // Auto-search with previous conditions if we had any
        if (currentConditions.length > 0) {
            await this.runSearch({ conditions: currentConditions });
        }
    }

    /** Run search using the current filter conditions (pagination, Search button, etc.). */
    async search() {
        return this.runSearch();
    }

    // Seed state for an embedded/widget usage (no URL involved).
    // Normalizes the conditions against the loaded signature and stores them
    // in the active filter slot so a subsequent search() picks them up.
    applyInitialConditions(
        conds: Condition[],
        opts: {
            queryMode?: QueryMode;
            displayMode?: DisplayMode;
            filterMode?: FilterMode;
        } = {},
    ) {
        if (opts.queryMode) this.queryMode = opts.queryMode;
        if (opts.displayMode) this.displayMode = opts.displayMode;
        this.filterMode = opts.filterMode ?? "advanced";

        const normalized = this.normalizeConditions(conds ?? []);
        if (this.filterMode === "advanced") {
            this.advancedConditions = normalized;
        } else {
            this.basicCondition = normalized[0] ?? null;
        }
    }

    // Method to load conditions from external source (like URL)
    loadConditions(conds: Condition[]) {
        // Preserve legacy callers; default these into advanced
        // Normalize conditions when loading from external source
        this.advancedConditions = this.normalizeConditions(conds ?? []);
        // If it looks like a single basic condition, also set basic
        this.basicCondition =
            conds?.length === 1 ? conds[0] : this.basicCondition;
    }

    toggleInstance(instance: ImageGET) {
        const i = this.selectedIds.indexOf(instance.id);
        if (i !== -1) {
            this.selectedIds.splice(i, 1);
        } else {
            this.selectedIds.push(instance.id);
        }
    }

    /** Search with explicit conditions (e.g. URL restore, overlay patient search). */
    async fetch(query: Condition[], updateUrl: boolean = true) {
        return this.runSearch({ conditions: query, updateUrl });
    }

    private async runSearch(
        options: {
            conditions?: Condition[];
            updateUrl?: boolean;
        } = {},
    ) {
        const query = this.normalizeConditions(
            options.conditions ?? this.getActiveConditions(),
        );
        if (!query.length) {
            return;
        }

        this.advancedConditions = query;

        if (options.updateUrl !== false) {
            this.updateURL(query);
        }

        this.loading = true;
        // When embedded as a widget (no URL sync), the selection represents the
        // set the user is building up across multiple searches, so keep it.
        if (this.urlSync) {
            this.selectedIds = [];
        }

        try {
            const res = await this.executeSearch(query);
            this.processSearchResults(res);
            return res;
        } finally {
            this.loading = false;
        }
    }

    private updateURL(query: Condition[]) {
        if (!this.urlSync) return;
        const params = new URLSearchParams();
        params.set("page", this.page.toString());
        params.set("limit", this.limit.toString());
        params.set("conditions", encodeConditions(query));
        params.set("order_by", String(this.sortBy));
        params.set("order", this.sortDirection);
        params.set("queryMode", this.queryMode);
        params.set("displayMode", this.displayMode);
        params.set("filterMode", this.filterMode);
        // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
        goto(`?${params.toString()}`);
    }

    private buildSearchBody(query: Condition[]) {
        return {
            conditions: query,
            limit: this.limit,
            page: this.page,
            order_by: this.sortBy,
            order: this.sortDirection ?? "ASC",
            include_count: true,
        };
    }

    private executeSearch(query: Condition[]) {
        const body = this.buildSearchBody(query);
        return this.queryMode === "instances"
            ? searchInstances(body as SearchQuery)
            : searchStudies({
                  ...body,
                  conditions: query as unknown as StudySearchCondition[],
              } as StudySearchQuery);
    }

    private processSearchResults(res: BrowserSearchResponse) {
        // searchInstances/searchStudies already ingest; track current result set
        this.resultIds = new Set(res.result_ids as unknown as number[]);
        this.count = res.count ?? 0;

        // Set ordered IDs based on query mode
        let studyIds: number[];
        if (this.queryMode === "instances") {
            this.orderedInstanceIds = (res.result_ids ?? []).map(String);
            studyIds = (res.studies ?? []).map((s) => s.id);
        } else {
            studyIds = (res.result_ids ?? []) as number[];
            this.orderedInstanceIds = [];
        }

        // Sort studies by date
        const get_date = (studyId: number) => {
            const study = studies.get(studyId);
            return study ? new Date(study.date).getTime() : 0;
        };
        this.orderedStudyIds = studyIds.sort(
            (a: number, b: number) => get_date(b) - get_date(a),
        );
    }

    openTab(imageIds: string[]) {
        const suffix_string = `?instances=${imageIds.join(",")}`;
        const url = `${window.location.origin}/view${suffix_string}`;
        window.open(url, "_blank")?.focus();
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
            const encodedVariable = encodeURIComponent(condition.variable);
            const encodedOperator = encodeURIComponent(condition.operator);
            const encodedValue = encodeURIComponent(
                serializeValue(condition.value ?? null),
            );
            const encodedType = encodeURIComponent(condition.type);
            const encodedModel = encodeURIComponent(
                condition.type === "attribute" ? (condition.model ?? "") : "",
            );
            const encodedFeature = encodeURIComponent(
                condition.type === "attribute"
                    ? (condition.feature ?? "")
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
        const type: Condition["type"] = t
            ? (decodeURIComponent(t) as Condition["type"])
            : "default";
        const model = m ? decodeURIComponent(m) : undefined;
        const feature = f ? decodeURIComponent(f) : undefined; // Decode feature
        if (type === "attribute") {
            const decoded: AttributeCondition = {
                type: "attribute",
                variable,
                operator,
                value,
                model,
                feature: feature || undefined, // Include feature, convert empty string to undefined
            };
            return decoded;
        }
        const decoded: DefaultCondition = {
            type: "default",
            variable: variable as DefaultCondition["variable"],
            operator,
            value,
        };
        return decoded;
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
