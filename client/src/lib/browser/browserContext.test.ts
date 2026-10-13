import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
    SearchCondition,
    SignatureField,
    StudyGET,
} from "../../types/openapi_types";

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$app/environment", () => ({ browser: true }));
vi.mock("$lib/data/api", async (importOriginal) => ({
    ...(await importOriginal<typeof import("$lib/data/api")>()),
    getInstancesSignature: vi.fn(),
    getStudiesSignature: vi.fn(),
    searchInstances: vi.fn(),
    searchStudies: vi.fn(),
}));

const api = await import("$lib/data/api");
const { studies } = await import("$lib/data/stores.svelte");
const { BrowserContext, encodeConditions } = await import(
    "./browserContext.svelte"
);

const field = (
    name: string,
    values: SignatureField["values"],
    extra: Partial<SignatureField> = {},
): SignatureField => ({
    name,
    values,
    type: "default",
    nullable: false,
    multi: false,
    ...extra,
});
const COMMON = [
    field("Patient Identifier", "string", { multi: true }),
    field("Study Date", "date"),
    field("Project Name", ["Alpha", "Beta"]),
];
const STUDIES = [...COMMON, field("Study Round", "int", { nullable: true })];
const INSTANCES = [
    ...COMMON,
    field("Laterality", ["L", "R"], { nullable: true }),
];

const condition = (
    variable: string,
    operator: SearchCondition["operator"],
    value: SearchCondition["value"],
) => ({ type: "default", variable, operator, value }) as SearchCondition;

const response = (ids: number[]) => ({
    result_ids: ids,
    count: ids.length,
    studies: [],
    instances: [],
});

async function makeContext() {
    vi.mocked(api.getStudiesSignature).mockResolvedValue(STUDIES);
    vi.mocked(api.getInstancesSignature).mockResolvedValue(INSTANCES);
    const ctx = new BrowserContext();
    ctx.urlSync = false;
    await ctx.loadSignatures();
    return ctx;
}

beforeEach(() => {
    goto.mockReset();
    vi.mocked(api.searchStudies).mockReset();
    vi.mocked(api.searchInstances).mockReset();
});

describe("BrowserContext", () => {
    it("keeps the server's study order", async () => {
        studies.set(1, { id: 1, date: "2020-01-01" } as StudyGET);
        studies.set(2, { id: 2, date: "2024-01-01" } as StudyGET);
        vi.mocked(api.searchStudies).mockResolvedValue(response([1, 2]));
        const ctx = await makeContext();
        ctx.basic.patientIdentifier = "P1";

        await ctx.submitSearch();

        expect(ctx.orderedStudyIds).toEqual([1, 2]);
    });

    it("keeps the selection, the sort and the rows images accept when switching to images", async () => {
        const ctx = await makeContext();
        ctx.filterMode = "advanced";
        ctx.advancedRows = [
            {
                id: 1,
                property: "Patient Identifier",
                operator: "is",
                value: "P1",
            },
            { id: 2, property: "Study Round", operator: "greater", value: "2" },
        ];
        ctx.selectedIds = ["7"];
        ctx.sortBy = "Date Inserted";
        ctx.sortDirection = "DESC";

        await ctx.resetForQueryModeChange("instances");

        expect(ctx.selectedIds).toEqual(["7"]);
        expect([ctx.sortBy, ctx.sortDirection]).toEqual([
            "Date Inserted",
            "DESC",
        ]);
        expect(ctx.advancedRows.map((r) => r.id)).toEqual([1]);
        expect(ctx.notification).toEqual({
            kind: "warning",
            title: "Conditions removed",
            subtitle: "Images can't use Study Round.",
        });
    });

    it("clears the results and reports a failed search", async () => {
        vi.mocked(api.searchStudies)
            .mockResolvedValueOnce(response([1, 2]))
            .mockRejectedValueOnce(new Error("Bad gateway"));
        const ctx = await makeContext();
        ctx.basic.patientIdentifier = "P1";

        await ctx.submitSearch();
        await ctx.submitSearch();

        expect(ctx.orderedStudyIds).toEqual([]);
        expect(ctx.count).toBe(0);
        expect(ctx.notification).toEqual({
            kind: "error",
            title: "Search failed",
            subtitle: "Try searching again.",
        });
    });

    it("applies sort and page size at once, on page 1, but only after a first search", async () => {
        vi.mocked(api.searchStudies).mockResolvedValue(response([1]));
        const ctx = await makeContext();
        ctx.basic.patientIdentifier = "P1";

        await ctx.setSort("Patient Birthdate", "DESC");
        expect(api.searchStudies).not.toHaveBeenCalled();

        await ctx.submitSearch();
        await ctx.setPage(3);
        await ctx.setPageSize(50);

        expect(vi.mocked(api.searchStudies).mock.lastCall?.[0]).toMatchObject({
            page: 0,
            limit: 50,
            order_by: "Patient Birthdate",
            order: "DESC",
        });
    });

    it("searches the Basic fields as AND conditions and leaves Advanced alone", async () => {
        vi.mocked(api.searchStudies).mockResolvedValue(response([]));
        const ctx = await makeContext();
        const rows = [{ id: 1, property: "Study Round", operator: "isEmpty" }];
        ctx.advancedRows = rows;
        ctx.basic = {
            patientIdentifier: "P1",
            studyDate: "2024-05-01",
            projectName: "Alpha",
        };

        await ctx.submitSearch();

        expect(
            vi.mocked(api.searchStudies).mock.lastCall?.[0].conditions,
        ).toEqual([
            condition("Patient Identifier", "==", "P1"),
            condition("Study Date", "==", "2024-05-01"),
            condition("Project Name", "IN", ["Alpha"]),
        ]);
        expect(ctx.advancedRows).toEqual(rows);
    });

    it("restores Basic fields and Advanced rows from the URL", async () => {
        const ctx = await makeContext();

        const basic = new URLSearchParams({
            filterMode: "basic",
            conditions: encodeConditions([
                condition("Patient Identifier", "==", "P1"),
            ]),
        });
        expect(ctx.restoreFromParams(basic)).toBe(true);
        expect(ctx.basic.patientIdentifier).toBe("P1");

        const advanced = new URLSearchParams({
            filterMode: "advanced",
            page: "2",
            conditions: encodeConditions([condition("Study Round", ">", 2)]),
        });
        expect(ctx.restoreFromParams(advanced)).toBe(true);
        expect(ctx.filterMode).toBe("advanced");
        expect(ctx.page).toBe(2);
        expect(ctx.advancedRows).toEqual([
            { id: 1, property: "Study Round", operator: "greater", value: "2" },
        ]);
    });

    it("applies only the latest of overlapping searches", async () => {
        let resolveFirst: (value: unknown) => void = () => {};
        vi.mocked(api.searchStudies)
            .mockReturnValueOnce(
                new Promise((resolve) => (resolveFirst = resolve)),
            )
            .mockResolvedValueOnce(response([2]));
        const ctx = await makeContext();
        ctx.basic.patientIdentifier = "P1";

        const first = ctx.submitSearch();
        await ctx.submitSearch();
        expect(ctx.loading).toBe(false);

        resolveFirst(response([1]));
        await first;
        expect(ctx.orderedStudyIds).toEqual([2]);
    });
});
