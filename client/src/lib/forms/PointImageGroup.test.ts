import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointImageGroup from "./PointImageGroup.svelte";

const group = {
    publicId: "img-abc",
    rows: [
        { publicId: "img-abc", index: 0, pt: { x: 1, y: 2 } },
        { publicId: "img-abc", index: 1, pt: { x: 3, y: 4, note: "n" } },
    ],
};

describe("PointImageGroup", () => {
    it("renders by-image chips and expands an editor", async () => {
        const onToggleExpand = vi.fn();
        const onRemovePoint = vi.fn();
        const onCollapse = vi.fn();

        render(PointImageGroup, {
            props: {
                group,
                addressing: "byImage",
                cardinality: "list",
                expandedKey: "img-abc:1",
                canEdit: true,
                hasExtras: true,
                enumExtras: [],
                stringExtraKeys: ["note"],
                formatCoord: (pt) => `[${pt.x},${pt.y}]`,
                extraPreview: (pt) =>
                    typeof pt.note === "string" ? ` ${pt.note}` : "",
                rowKey: (row) => `${row.publicId}:${row.index}`,
                indexApplicable: () => false,
                onToggleExpand,
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemovePoint,
                onCollapse,
            },
        });

        expect(screen.getByText("img-abc")).toBeInTheDocument();
        expect(screen.getByText("2 pts")).toBeInTheDocument();
        expect(screen.getByText("[1,2]")).toBeInTheDocument();
        expect(screen.getByText("n")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Done" }),
        ).toBeInTheDocument();

        await fireEvent.click(screen.getByText("[1,2]"));
        expect(onToggleExpand).toHaveBeenCalled();

        await fireEvent.click(
            screen.getByRole("button", { name: "Remove point" }),
        );
        expect(onRemovePoint).toHaveBeenCalledWith("img-abc", 1);

        await fireEvent.click(screen.getByRole("button", { name: "Done" }));
        expect(onCollapse).toHaveBeenCalled();
    });

    it("omits the public id for bare addressing", () => {
        render(PointImageGroup, {
            props: {
                group: {
                    publicId: "img-abc",
                    rows: [
                        { publicId: "img-abc", index: 0, pt: { x: 8, y: 9 } },
                    ],
                },
                addressing: "bare",
                cardinality: "single",
                expandedKey: null,
                canEdit: false,
                hasExtras: false,
                enumExtras: [],
                stringExtraKeys: [],
                formatCoord: (pt) => `[${pt.x},${pt.y}]`,
                extraPreview: () => "",
                rowKey: (row) => `${row.publicId}:${row.index}`,
                indexApplicable: () => false,
                onToggleExpand: vi.fn(),
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemovePoint: vi.fn(),
                onCollapse: vi.fn(),
            },
        });

        expect(screen.queryByText("img-abc")).not.toBeInTheDocument();
        expect(screen.queryByText(/pts/)).not.toBeInTheDocument();
        expect(screen.getByText("[8,9]")).toBeInTheDocument();
    });
});
