import { formSchemas } from "$lib/data/stores.svelte";
import { copyStyles, windowFeatures } from "$lib/newWindow";
import type { FormEntityScope } from "$lib/viewer-window/panelForm/formEntityScope";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { ImageMeta } from "$lib/workspace/imageMeta";
import { mount, unmount } from "svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import FormWindowContent from "./FormWindowContent.svelte";
import { formWindowHandback } from "./formWindowHandback";
import { schemaName } from "./formTargets";
import { pointArming } from "./pointArming.svelte";

const NAME = "eyened-form";

/** "‹schema› #id": the window's title and the viewport chip's name. */
function formLabel(form: FormAnnotationGET): string {
    const schema = formSchemas.get(form.form_schema_id);
    return `${schema ? schemaName(schema) : "Form"} #${form.id}`;
}

/** What the window shows. */
export type WindowView =
    | { kind: "opening" }
    | {
          kind: "form";
          form: FormAnnotationGET;
          canEdit: boolean;
          viewerContext?: ViewerContext;
      }
    | {
          kind: "grade";
          schemaName: string;
          meta: ImageMeta;
          scope: FormEntityScope;
          failed: boolean;
          ongrade: () => void;
      }
    /** A row's Grade whose create failed; Grading has the notice and the retry. */
    | { kind: "failed" }
    | { kind: "nothing" }
    | { kind: "closed" };

export interface ShowOptions {
    canEdit: boolean;
    viewerContext?: ViewerContext;
    /** The strip images of the form's target; their viewports get the chip. */
    imageIds: string[];
    /** Where it was opened, for the closed state's words after a page load. */
    from: "viewer" | "browse";
    /** The opening component's getAllContexts(), so the form sees the task, the workspace and the user. */
    contexts: Map<unknown, unknown>;
    /** Raise the window and take keyboard focus; false when it only follows the set. Default true. */
    focus?: boolean;
}

/** What the window showed before a page load, kept on its own document. */
export interface WindowMemory {
    schemaId: number | null;
    formId: number | null;
}

/** The one form window, named so every click and page load finds the same one. */
class FormWindow {
    /** The form the window shows; rows and viewport chips read it. */
    formId: number | null = $state(null);
    imageIds: readonly string[] = $state.raw([]);
    /** "‹schema› #id", for the viewport chip. */
    label = $state("");
    /** The place whose open was blocked; its notice shows there. */
    blocked: string | null = $state(null);
    private blockedControl: HTMLElement | null = null;
    private win: Window | null = null;
    private listening: AbortController | null = null;
    private app: Record<string, unknown> | null = null;

    /** Call inside the click, before any await: finds or opens the window and shows "Opening…". Null when blocked. */
    begin(source: string): Window | null {
        const win = window.open("", NAME, `popup,${windowFeatures()}`);
        if (!win) {
            this.blocked = source;
            this.blockedControl =
                document.activeElement instanceof HTMLElement
                    ? document.activeElement
                    : null;
            return null;
        }
        this.blocked = null;
        this.adopt(win);
        this.showView(win, { kind: "opening" }, new Map());
        return win;
    }

    /** The blocked notice's close button: focus goes back to the control that was clicked. */
    dismissBlocked(): void {
        this.blocked = null;
        this.blockedControl?.focus();
        this.blockedControl = null;
    }

    /** Takes the window for this page: the hand-back goes in when missing, the styles and the closing listener once per page. */
    adopt(win: Window): WindowMemory {
        const root = win.document.documentElement;
        if (!root.dataset.eyenedForm) {
            root.dataset.eyenedForm = "1";
            const script = win.document.createElement("script");
            script.textContent = `(${formWindowHandback.toString()})(window);`;
            win.document.head.append(script);
        }
        if (this.win !== win) {
            this.win = win;
            root.lang = document.documentElement.lang;
            win.document.head
                .querySelectorAll("[data-eyened-style]")
                .forEach((node) => node.remove());
            copyStyles(win.document);
            // This page's listener leaves the pop-up when this page does.
            this.listening?.abort();
            const listening = new AbortController();
            this.listening = listening;
            win.addEventListener("pagehide", () => this.gone(win), {
                signal: listening.signal,
            });
            window.addEventListener("pagehide", () => listening.abort(), {
                once: true,
            });
        }
        // Nothing is open until a form is shown again.
        this.clear();
        pointArming.disarm();
        const id = (value: string | undefined) =>
            value ? Number(value) : null;
        return {
            schemaId: id(root.dataset.schemaId),
            formId: id(root.dataset.formId),
        };
    }

    /** Shows the form in the window from begin() or adopt(); a window the grader closed meanwhile is left alone. */
    showForm(win: Window, form: FormAnnotationGET, opts: ShowOptions): void {
        if (win.closed || win !== this.win) return;
        const root = win.document.documentElement;
        root.dataset.from = opts.from;
        root.dataset.schemaId = String(form.form_schema_id);
        root.dataset.formId = String(form.id);
        this.showView(
            win,
            {
                kind: "form",
                form,
                canEdit: opts.canEdit,
                viewerContext: opts.viewerContext,
            },
            opts.contexts,
        );
        this.formId = form.id;
        this.imageIds = opts.imageIds;
        this.label = formLabel(form);
        if (opts.focus !== false) win.focus();
    }

    /** Replaces what the window shows; focus, if it was in the window, goes to the new view's heading. */
    showView(
        win: Window,
        view: WindowView,
        contexts: Map<unknown, unknown>,
    ): void {
        if (win.closed || win !== this.win) return;
        if (this.app) void unmount(this.app);
        const doc = win.document;
        const focused = doc.hasFocus();
        doc.title = view.kind === "form" ? formLabel(view.form) : "Form window";
        // A fresh host, so a gone page's delegated listeners are not on the element this page mounts into.
        const host = doc.createElement("div");
        // Made with the opener's document: bits-ui checks portal targets with the opener's Element.
        // ASSUMPTION: Chrome keeps a moved node's opener prototype, so this still passes that check in the popup.
        const portalTo = document.createElement("div");
        doc.body.replaceChildren(host, portalTo);
        this.app = mount(FormWindowContent, {
            target: host,
            props: { view, portalTo },
            context: contexts,
        });
        doc.documentElement.dataset.mounted = "1";
        if (focused) doc.querySelector<HTMLElement>("h1")?.focus();
    }

    /** A saved form, from a click. The form already in the window only comes to the front. */
    open(
        form: FormAnnotationGET,
        opts: ShowOptions & { source: string },
    ): void {
        if (this.formId === form.id && this.win && !this.win.closed) {
            this.focusWindow();
            return;
        }
        const win = this.begin(opts.source);
        if (win) this.showForm(win, form, opts);
    }

    focusWindow(): void {
        this.win?.focus();
    }

    close(win: Window): void {
        win.close();
        this.gone(win);
    }

    /** After a delete: the window closes if it shows that form. */
    closeFor(formId: number): void {
        if (this.win && this.formId === formId) this.close(this.win);
    }

    /** Before this page loads another set: the words the hand-back shows meanwhile. */
    leaving(text: string): void {
        if (this.win && !this.win.closed)
            this.win.document.documentElement.dataset.loading = text;
    }

    /** The viewer left without a page load: the window says so, and nothing stays open. */
    release(): void {
        if (this.win && !this.win.closed)
            this.showView(this.win, { kind: "closed" }, new Map());
        this.clear();
        pointArming.disarm();
    }

    private gone(win: Window): void {
        if (win !== this.win) return;
        if (this.app) void unmount(this.app);
        this.app = null;
        this.win = null;
        this.clear();
        pointArming.disarm();
    }

    private clear(): void {
        this.formId = null;
        this.imageIds = [];
        this.label = "";
    }
}

export const formWindow = new FormWindow();
