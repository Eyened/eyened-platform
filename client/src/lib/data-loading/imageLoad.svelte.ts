import type { ImageLoadProgress, ImageLoadState } from "./loadProgress";

/** In-flight or settled image load: spinner {@link message} plus {@link promise}. */
export class ImageLoad<T = unknown> implements ImageLoadState {
    message = $state("Downloading…");
    readonly promise: Promise<T>;

    constructor(
        start: (progress: ImageLoadProgress) => Promise<T>,
        extras: Omit<ImageLoadProgress, "loading"> = {},
    ) {
        this.promise = start({ loading: this, ...extras });
    }
}
