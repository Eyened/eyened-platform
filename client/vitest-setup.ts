import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/svelte";

// jsdom has no WebGL; texture.ts reads GLenum constants at module load.
if (typeof WebGL2RenderingContext === "undefined") {
    globalThis.WebGL2RenderingContext = {
        RED_INTEGER: 0x8d94,
        NEAREST: 0x2600,
        RED: 0x1903,
        UNSIGNED_BYTE: 0x1401,
        LINEAR: 0x2601,
        RG: 0x8227,
        FLOAT: 0x1406,
        R8: 0x8229,
        R8UI: 0x8232,
        UNSIGNED_SHORT: 0x1403,
        R16UI: 0x8234,
        UNSIGNED_INT: 0x1405,
        R32UI: 0x8236,
        R32F: 0x822e,
        RG32F: 0x8230,
        RGBA: 0x1908,
        RGBA8: 0x8058,
    } as unknown as typeof WebGL2RenderingContext;
}

// Unmount any component rendered by a test so DOM state never leaks between tests.
afterEach(() => {
    cleanup();
});
