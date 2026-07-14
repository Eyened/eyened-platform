import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/svelte";

// Unmount any component rendered by a test so DOM state never leaks between tests.
afterEach(() => {
    cleanup();
});
