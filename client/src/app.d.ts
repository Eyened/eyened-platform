/// <reference types="@testing-library/jest-dom/vitest" />
// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
// and what to do when importing types
declare namespace App {
    // interface Error {}
    // interface Locals {}
    // interface PageData {}
    // interface Platform {}
}

interface Window {
    /** Set by the viewer page; the form window's hand-back calls it after a page load. */
    adoptFormWindow?: (win: Window) => void;
}
