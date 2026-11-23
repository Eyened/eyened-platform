import { createFormAnnotation } from "$lib/data";
import { formAnnotations, formSchemas } from "$lib/data/stores.svelte";
import { buildFormAnnotationCreatePayload } from "$lib/viewer-window/panelForm/formEntityScope";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { followSet } from "./followSet";
import { formWindow } from "./formWindow.svelte";
import {
    schemaName,
    targetOf,
    type FormTarget,
    type OpenImage,
} from "./formTargets";
import { viewerFor } from "./formViewer";

/** A page load handed the window to this viewer page: in a task it follows the set; on /view it shows the same form again. */
export function adoptFormWindow(
    win: Window,
    deps: {
        workspace: Workspace;
        images: readonly OpenImage[];
        userId: number;
        /** The set; undefined on /view. */
        subTaskId?: number;
        canEdit: (form: FormAnnotationGET) => boolean;
        contexts: Map<unknown, unknown>;
    },
): void {
    const { workspace, images, contexts, subTaskId } = deps;
    const memory = formWindow.adopt(win);
    const show = (form: FormAnnotationGET, target: FormTarget | null) =>
        formWindow.showForm(win, form, {
            canEdit: deps.canEdit(form),
            viewerContext: target ? viewerFor(workspace, target) : undefined,
            imageIds: target?.imageIds ?? [],
            from: "viewer",
            contexts,
            // Arriving after a page load must not take the keyboard from the viewer.
            focus: false,
        });
    const closed = () => formWindow.showView(win, { kind: "closed" }, contexts);

    if (subTaskId === undefined) {
        const form =
            memory.formId === null
                ? undefined
                : formAnnotations.get(memory.formId);
        const schema = form && formSchemas.get(form.form_schema_id);
        if (form && schema) show(form, targetOf(form, schema, images));
        else closed();
        return;
    }
    const schema =
        memory.schemaId === null ? undefined : formSchemas.get(memory.schemaId);
    if (!schema) return closed();
    const arrival = followSet({
        schema,
        images,
        selectedImageId: workspace.slots[workspace.selected]?.imageId ?? null,
        forms: formAnnotations.values(),
        userId: deps.userId,
        subTaskId,
    });
    if (arrival.kind === "form") return show(arrival.form, arrival.target);
    if (arrival.kind === "nothing")
        return formWindow.showView(win, { kind: "nothing" }, contexts);
    const { target, image } = arrival;
    // Grade is pressed inside the window, so it needs no window.open; arriving never creates a form.
    const ask = (failed: boolean) =>
        formWindow.showView(
            win,
            {
                kind: "grade",
                schemaName: schemaName(schema),
                meta: image.instance,
                scope: target.scope,
                failed,
                ongrade: () => void grade(),
            },
            contexts,
        );
    // An arrow, not a function declaration, so `schema` stays narrowed inside it.
    const grade = async () => {
        formWindow.showView(win, { kind: "opening" }, contexts);
        try {
            const form = await createFormAnnotation(
                buildFormAnnotationCreatePayload({
                    formSchemaId: schema.id,
                    scope: target.scope,
                    ctx: target.ctx,
                    subTaskId,
                }),
            );
            show(form, target);
        } catch {
            ask(true);
        }
    };
    ask(false);
}
