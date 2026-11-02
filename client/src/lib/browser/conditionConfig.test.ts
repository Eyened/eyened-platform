import { describe, expect, it } from "vitest";
import type { BuilderRow } from "$lib/components/ui/condition-builder/types.js";
import type {
    SearchCondition,
    SignatureField,
} from "../../types/openapi_types";
import { conditionsToRows, rowsToConditions } from "./conditionConfig";

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

const SIGNATURE: SignatureField[] = [
    field("Laterality", ["L", "R"], { nullable: true }),
    field("Patient Identifier", "string", { multi: true }),
    field("Study Round", "int", { nullable: true }),
    field("Study Date", "date"),
    field("Score", "float", { type: "attribute", model: "Grader" }),
];

const row = (
    property: string,
    operator?: string,
    value?: string | string[],
): BuilderRow => ({ id: 1, property, operator, value });

const condition = (
    variable: string,
    operator: SearchCondition["operator"],
    value: SearchCondition["value"],
) => ({ type: "default", variable, operator, value }) as SearchCondition;

describe("rowsToConditions", () => {
    it.each([
        [
            "a list as IN",
            row("Laterality", "oneOf", ["L"]),
            condition("Laterality", "IN", ["L"]),
        ],
        [
            "is empty as IS NULL",
            row("Laterality", "isEmpty"),
            condition("Laterality", "IS NULL", null),
        ],
        [
            "trimmed text as ==",
            row("Patient Identifier", "is", " P1 "),
            condition("Patient Identifier", "==", "P1"),
        ],
        [
            "comma-separated text as IN",
            row("Patient Identifier", "oneOf", "P1, P2,"),
            condition("Patient Identifier", "IN", ["P1", "P2"]),
        ],
        [
            "a number above as >",
            row("Study Round", "greater", "2"),
            condition("Study Round", ">", 2),
        ],
        [
            "a number below as <",
            row("Study Round", "lower", "2"),
            condition("Study Round", "<", 2),
        ],
        [
            "a date before as <",
            row("Study Date", "before", "2024-05-01"),
            condition("Study Date", "<", "2024-05-01"),
        ],
        [
            "a date after as >",
            row("Study Date", "after", "2024-05-01"),
            condition("Study Date", ">", "2024-05-01"),
        ],
        [
            "an attribute with its model",
            row("Grader__none__Score", "is", "0.5"),
            {
                type: "attribute",
                model: "Grader",
                variable: "Score",
                operator: "==",
                value: 0.5,
            } as SearchCondition,
        ],
    ])("maps %s", (_name, input, expected) => {
        expect(rowsToConditions([input], SIGNATURE)).toEqual([expected]);
    });

    it("leaves out incomplete rows", () => {
        const incomplete: BuilderRow[] = [
            { id: 1 },
            row("Laterality"),
            row("Laterality", "oneOf", []),
            row("Patient Identifier", "is", "  "),
            row("Study Round", "greater", ""),
            row("Study Date", "is", "2024-02-30"),
            row("Unknown", "is", "x"),
        ];
        expect(rowsToConditions(incomplete, SIGNATURE)).toEqual([]);
    });
});

describe("conditionsToRows", () => {
    it("round-trips conditions through builder rows", () => {
        const conditions = [
            condition("Laterality", "IN", ["L", "R"]),
            condition("Laterality", "IS NULL", null),
            condition("Patient Identifier", "IN", ["P1", "P2"]),
            condition("Study Round", ">", 2),
            condition("Study Date", "==", "2024-05-01"),
            {
                type: "attribute",
                model: "Grader",
                variable: "Score",
                operator: "<",
                value: 0.5,
            } as SearchCondition,
        ];
        expect(
            rowsToConditions(
                conditionsToRows(conditions, SIGNATURE),
                SIGNATURE,
            ),
        ).toEqual(conditions);
    });
});
