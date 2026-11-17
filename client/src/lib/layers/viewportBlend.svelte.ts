import { composeGlslPath } from "$lib/registration/composeGlslPath";
import { glslPathBetween } from "$lib/registration/glslPathBetween";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { affineFromFormData } from "$lib/viewer-window/panelRegistration/directAffine";
import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import {
    BlendRenderer,
    type BlendLayer,
    type BlendLayerStyle,
} from "$lib/webgl/blendRenderer";
import type { ImageRenderer } from "$lib/webgl/imageRenderer";
import {
    imageName,
    type ImageName,
    type TitleSuffix,
} from "$lib/workspace/imageMeta";
import { registeredImageSize } from "./blendStyles";
import { eyeKey, pairCount } from "./pointsets";
import { defaultTicks, nextStop, seriesLayerWeights } from "./seriesBlend";

export type BlendMode = "off" | "overlay" | "checker" | "flicker" | "series";

/** Pairs an affine alignment needs. */
export const MIN_PAIRS = 3;
const FLICKER_MS = 1000;
const IDENTITY = composeGlslPath([]);

export type SeriesItem = { image: AbstractImage; mapping: string };

/** What a viewport's blend reads from its window. */
export type BlendWindow = Pick<
    ViewerWindowContext,
    | "pointsets"
    | "blendStyles"
    | "images"
    | "registration"
    | "topViewers"
    | "twins"
>;

function reducedMotion(): boolean {
    return (
        typeof matchMedia === "function" &&
        matchMedia("(prefers-reduced-motion: reduce)").matches
    );
}

const dateOf = (image: AbstractImage) => image.instance.study.date ?? "";

/** One viewport's blend, kept while it is mounted: the mode, its other image or series, and the renderer it swaps in. */
export class ViewportBlend {
    mode: BlendMode = $state("off");
    /** Checkerboard square size in this image's pixels. */
    tile = $state(64);
    playing = $state(false);
    /** Flicker is showing the other image. */
    showOther = $state(false);
    /** The blend shader failed to compile; the next mode change clears it. */
    error = $state(false);
    private withId: string | null = $state(null);
    private ticks: string[] | null = $state(null);
    private position: number | null = $state(null);
    private timer: ReturnType<typeof setInterval> | undefined;
    private renderer: BlendRenderer | null = null;
    private base: ImageRenderer | null = null;

    constructor(
        private readonly image: AbstractImage,
        private readonly win: BlendWindow,
        private readonly catalogue: () => readonly string[],
        /** Images one shader can sample: the device's texture units. */
        readonly cap: number,
        /** `layout.hide` has Registration: no Overlay drop zone. */
        private readonly hidden: boolean,
    ) {}

    // Deriveds that read constructor parameters use `.by`: a plain `$derived(expr)` initializer runs before them (TS2729).

    /** The eye's current registration; pair modes blend with its images. */
    registration = $derived.by(() =>
        this.win.pointsets.current(eyeKey(this.image.instance)),
    );

    /** The registration's other loaded 2D images, in strip order. */
    candidates = $derived.by((): AbstractImage[] => {
        const data = this.registration?.form_data;
        if (!data || typeof data !== "object") return [];
        return this.catalogue().flatMap((id) => {
            const image = this.win.images.get(id);
            return image?.is2D &&
                image.image_id !== this.image.image_id &&
                image.instance.id in data
                ? [image]
                : [];
        });
    });

    /** "With": the picked image while the registration has it, else its first. */
    other = $derived(
        this.candidates.find((image) => image.image_id === this.withId) ??
            this.candidates[0] ??
            null,
    );

    /** The other image has the pairs an alignment needs. */
    aligned = $derived(
        this.other !== null && this.pairs(this.other) >= MIN_PAIRS,
    );

    /** Loaded 2D images of this eye with a registration path from this one, oldest first; this image included. */
    seriesItems = $derived.by((): SeriesItem[] => {
        void this.win.registration.revision;
        const eye = eyeKey(this.image.instance);
        const items: SeriesItem[] = [];
        for (const image of this.win.images.values()) {
            if (!image.is2D || eyeKey(image.instance) !== eye) continue;
            const mapping = glslPathBetween(
                this.win.registration,
                this.image.image_id,
                image.image_id,
                (id) => registeredImageSize(this.win, id),
            );
            if (mapping) items.push({ image, mapping });
        }
        return items.sort((a, b) =>
            dateOf(a.image).localeCompare(dateOf(b.image)),
        );
    });

    /** Ticked image ids: the grader's picks, else this image's modality nearest by date. */
    ticked = $derived.by(
        () =>
            this.ticks ??
            defaultTicks(
                this.seriesItems.map(({ image }) => ({
                    id: image.image_id,
                    date: dateOf(image),
                    modality: image.instance.modality ?? "",
                })),
                this.image.image_id,
                this.cap,
            ),
    );

    /** The ticked images, oldest first. */
    shown = $derived(
        this.seriesItems.filter(({ image }) =>
            this.ticked.includes(image.image_id),
        ),
    );

    /** The slider, as an index into `shown`; it starts on this image. */
    seriesPosition = $derived.by(
        () =>
            this.position ??
            Math.max(
                0,
                this.shown.findIndex(
                    ({ image }) => image.image_id === this.image.image_id,
                ),
            ),
    );

    /** The image the slider is nearest to. */
    showing = $derived(
        this.shown[Math.round(this.seriesPosition)]?.image ?? null,
    );

    /** Added to the viewport title while blending. */
    titleSuffix = $derived.by((): TitleSuffix | null => {
        if (this.mode === "series")
            return this.showing && this.shown.length > 1
                ? this.suffix(" · series · showing", this.showing)
                : null;
        if (this.mode === "off" || !this.registration || !this.other)
            return null;
        return this.suffix(
            this.mode === "flicker" ? " · flicker with" : " · blended with",
            this.other,
        );
    });

    /** One line over the viewport when a pair mode cannot draw the other image. */
    viewportLine = $derived.by((): string | null => {
        if (this.mode === "off" || this.mode === "series") return null;
        if (!this.registration)
            return "Make a registration current in Pointsets.";
        if (!this.other) return null;
        const missing = MIN_PAIRS - this.pairs(this.other);
        return missing > 0
            ? `Place ${missing} more pair${missing === 1 ? "" : "s"} to line up the images`
            : null;
    });

    pairs(image: AbstractImage): number {
        return pairCount(
            this.registration?.form_data,
            this.image.instance.id,
            image.instance.id,
        );
    }

    /** How Layers names an image here: its name line with the twin number, over its device line. */
    nameOf(image: AbstractImage): ImageName {
        return imageName(
            image.instance,
            this.win.twins.get(image.image_id) ?? "",
        );
    }

    /** True when another image's name line reads the same as this image's, so only its device tells them apart. */
    sameName(image: AbstractImage): boolean {
        return (
            image !== this.image &&
            this.nameOf(image).name === this.nameOf(this.image).name
        );
    }

    private suffix(lead: string, image: AbstractImage): TitleSuffix {
        const { name, device } = imageName(image.instance, "");
        const shown =
            this.sameName(image) && device ? `${name} · ${device}` : name;
        return {
            rest: `${lead} ${shown}`,
            twin: this.win.twins.get(image.image_id) ?? "",
        };
    }

    setMode(mode: BlendMode): void {
        this.stopTimer();
        this.playing = false;
        this.error = false;
        this.mode = mode;
        if (mode !== "flicker") return;
        this.showOther = false;
        if (!reducedMotion()) this.play();
    }

    setWith(imageId: string): void {
        this.withId = imageId;
    }

    /** A strip tile dropped on "Overlay". */
    overlayWith(imageId: string): void {
        this.withId = imageId;
        this.setMode("overlay");
    }

    /** Whether a dragged tile offers "Overlay" here: it has pairs with this image in the current registration. */
    canOverlay(imageId: string): boolean {
        if (this.hidden) return false;
        const image = this.candidates.find((c) => c.image_id === imageId);
        return image !== undefined && this.pairs(image) > 0;
    }

    play(): void {
        this.stopTimer();
        this.playing = true;
        this.timer = setInterval(() => {
            this.showOther = !this.showOther;
        }, FLICKER_MS);
    }

    pause(): void {
        this.stopTimer();
        this.playing = false;
    }

    /** Flips the paused flicker to the other image. */
    swap(): void {
        if (!this.playing) this.showOther = !this.showOther;
    }

    /** This image stays ticked; ticking past the cap does nothing. The slider goes back to this image. */
    toggleTick(imageId: string): void {
        if (imageId === this.image.image_id) return;
        const ticked = this.ticked;
        if (ticked.includes(imageId))
            this.ticks = ticked.filter((id) => id !== imageId);
        else if (ticked.length < this.cap) this.ticks = [...ticked, imageId];
        this.position = null;
    }

    /** Null returns the slider to this image. */
    setPosition(position: number | null): void {
        this.position = position;
    }

    /** Previous / Next image, and Page Up / Down on the slider. */
    step(direction: 1 | -1): void {
        this.position = nextStop(
            this.seriesPosition,
            direction,
            this.shown.length,
        );
    }

    /** The layers to draw; null draws the plain image. Layer 0 takes the viewport's render mode and W/L. */
    layers(
        viewerContext: Pick<ViewerContext, "renderMode" | "windowLevel">,
    ): BlendLayer[] | null {
        const styles = this.win.blendStyles;
        const id = this.image.image_id;
        const own = (role: "this" | "series"): BlendLayerStyle => ({
            ...styles.get(id, role),
            renderMode: viewerContext.renderMode,
            windowLevel: viewerContext.windowLevel,
        });
        if (this.mode === "off") return null;
        if (this.mode === "series") {
            const shown = this.shown;
            if (shown.length < 2) return null;
            const weights = seriesLayerWeights(
                shown.map(({ image }) => image.image_id),
                id,
                this.seriesPosition,
            );
            const others = shown.filter(({ image }) => image.image_id !== id);
            return [
                {
                    image: this.image,
                    mapping: IDENTITY,
                    style: own("series"),
                    weight: weights[0]!,
                },
                ...others.map(({ image, mapping }, i) => ({
                    image,
                    mapping,
                    style: styles.get(image.image_id, "series"),
                    weight: weights[i + 1]!,
                })),
            ];
        }
        const other = this.other;
        if (!this.registration || !other) return null;
        // Only this registration's own points align the pair; another registration's path is never borrowed.
        const affine = affineFromFormData(
            this.registration.form_data,
            id,
            other.image_id,
        );
        let first = own("this");
        let second = styles.get(other.image_id, "other");
        let weights = [1, 1];
        if (this.mode === "flicker") {
            first = { ...first, tint: 0, opacity: 1 };
            second = { ...second, tint: 0, opacity: 1 };
            weights = affine && this.showOther ? [0, 1] : [1, 0];
        }
        return [
            {
                image: this.image,
                mapping: IDENTITY,
                style: first,
                weight: weights[0]!,
            },
            {
                image: other,
                mapping: { affine },
                style: second,
                weight: weights[1]!,
            },
        ];
    }

    /** Swaps the viewport's renderer for a BlendRenderer while there is something to blend, and back. */
    apply(viewerContext: ViewerContext): void {
        const layers = this.layers(viewerContext);
        if (!layers) {
            this.restore(viewerContext);
            return;
        }
        if (!this.renderer) {
            this.base = viewerContext.imageRenderer;
            this.renderer = new BlendRenderer();
            viewerContext.imageRenderer = this.renderer;
        }
        try {
            this.renderer.setLayers(layers);
            this.renderer.setComposite(
                this.mode === "checker" ? "checkerboard" : "overlay",
                this.tile,
            );
        } catch (error) {
            console.error("Blend shader failed", error);
            this.restore(viewerContext);
            // Runs inside the apply effect: the effect re-runs once, finds no layers and stops.
            this.setMode("off");
            this.error = true;
        }
    }

    dispose(viewerContext: ViewerContext): void {
        this.stopTimer();
        this.restore(viewerContext);
    }

    private restore(viewerContext: ViewerContext): void {
        if (!this.renderer) return;
        viewerContext.imageRenderer = this.base!;
        this.renderer.dispose();
        this.renderer = null;
        this.base = null;
    }

    private stopTimer(): void {
        clearInterval(this.timer);
        this.timer = undefined;
    }
}
