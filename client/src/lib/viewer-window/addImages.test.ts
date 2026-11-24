import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "$lib/api/client";
import { subtasks } from "$lib/data/stores.svelte";
import type { SubTaskWithImagesGET } from "../../types/openapi_types";

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$lib/data/helpers", () => ({
    addSubTaskImage: vi.fn(),
    removeSubTaskImage: vi.fn(),
}));
const { addSubTaskImage, removeSubTaskImage } = await import(
    "$lib/data/helpers"
);
const { addImages } = await import("./addImages");

const SET = 31;
/** What the server holds; each reply replaces the store's list, as ingestSubTasks does. */
const linked = () =>
    (subtasks.get(SET)?.images ?? []).map((image) => String(image.id));
function serverHas(ids: string[]) {
    subtasks.set(SET, {
        id: SET,
        images: ids.map((id) => ({ id })),
    } as unknown as SubTaskWithImagesGET);
}

let inFlight = 0;
let mostInFlight = 0;
const order: string[] = [];
async function request(change: string, next: () => string[]) {
    inFlight += 1;
    mostInFlight = Math.max(mostInFlight, inFlight);
    await Promise.resolve();
    order.push(change);
    serverHas(next());
    inFlight -= 1;
}

beforeEach(() => {
    order.length = 0;
    mostInFlight = 0;
    goto.mockReset();
    vi.mocked(removeSubTaskImage)
        .mockReset()
        .mockImplementation((_set, id) =>
            request(`-${id}`, () => linked().filter((x) => x !== id)),
        );
    vi.mocked(addSubTaskImage)
        .mockReset()
        .mockImplementation((_set, id) =>
            request(`+${id}`, () => [...linked(), id]),
        );
});

const inTask = (setInstanceIDs = vi.fn()) => ({
    subTaskId: SET,
    setInstanceIDs,
    rewriteUrl: false,
});

describe("addImages", () => {
    it("removes, then adds, one request at a time, then shows the images", async () => {
        serverHas(["a", "b"]);
        const target = inTask();
        await addImages(["b", "c", "d"], target);
        expect(order).toEqual(["-a", "+c", "+d"]);
        expect(mostInFlight).toBe(1);
        expect(target.setInstanceIDs).toHaveBeenCalledWith(["b", "c", "d"]);
        expect(goto).not.toHaveBeenCalled();
    });

    it("a failed add rejects without showing the images; a retry sends only what didn't save", async () => {
        serverHas(["a"]);
        let failC = true;
        vi.mocked(addSubTaskImage).mockImplementation((_set, id) => {
            if (id === "c" && failC)
                return Promise.reject(new Error("Network down"));
            return request(`+${id}`, () => [...linked(), id]);
        });
        const target = inTask();
        await expect(addImages(["b", "c"], target)).rejects.toThrow(
            /^Earlier changes were saved; the rest were not applied\. Try again\.$/,
        );
        expect(target.setInstanceIDs).not.toHaveBeenCalled();

        failC = false;
        order.length = 0;
        await addImages(["b", "c"], target);
        expect(order).toEqual(["+c"]);
        expect(target.setInstanceIDs).toHaveBeenCalledWith(["b", "c"]);
    });

    it("an image outside the task's projects says which projects", async () => {
        serverHas([]);
        vi.mocked(addSubTaskImage).mockRejectedValue(
            new ApiError(409, "conflict", {
                code: "image_outside_task_declaration",
                message:
                    "Image 88213 is in a project this task does not declare.",
                image_projects: [7],
                declared_projects: [3, 5],
            }),
        );
        await expect(addImages(["x"], inTask())).rejects.toThrow(
            /^Image project 7; task declares 3, 5\. Earlier changes were saved; the rest were not applied\.$/,
        );
    });

    it("on /view saves nothing and writes instances= in the address", async () => {
        const setInstanceIDs = vi.fn();
        await addImages(["a", "b"], {
            subTaskId: null,
            setInstanceIDs,
            rewriteUrl: true,
        });
        expect(addSubTaskImage).not.toHaveBeenCalled();
        expect(setInstanceIDs).toHaveBeenCalledWith(["a", "b"]);
        expect(goto).toHaveBeenCalledWith("?instances=a,b");
    });
});
