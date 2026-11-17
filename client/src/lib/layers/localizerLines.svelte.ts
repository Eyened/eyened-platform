import type { PhotoLocator } from "$lib/registration/photoLocators";
import { readLocalizer, writeLocalizer } from "$lib/workspace/workspacePrefs";
import type { LocalizerMode } from "$lib/workspace/workspaceRules";

/** One viewport's localizer lines: the mode for every OCT its image localizes, kept while it is mounted. */
export class LocalizerLines {
    mode: LocalizerMode = $state(readLocalizer());
    /** The mode O turns back on; not saved. */
    private lastOn: Exclude<LocalizerMode, "off"> =
        this.mode === "off" ? "current" : this.mode;

    /** The B-scan positions of loaded OCTs on this image; none hides the section. */
    constructor(readonly locators: () => PhotoLocator[]) {}

    set(mode: LocalizerMode): void {
        if (mode !== "off") this.lastOn = mode;
        this.mode = mode;
        writeLocalizer(mode);
    }

    /** O: Off and the last other mode; nothing on an image without lines. */
    toggle(): void {
        if (!this.locators().length) return;
        this.set(this.mode === "off" ? this.lastOn : "off");
    }
}
