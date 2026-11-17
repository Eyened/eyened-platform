export type ImageLoadState = {
    message: string;
};

export type ImageLoadProgress = {
    loading?: ImageLoadState;
    /** OCTA: angio_flow attached after structural was already shown. */
    onFlowReady?: (imageId: string) => void;
};

export function setLoadMessage(
    progress: ImageLoadProgress | undefined,
    message: string,
): void {
    if (progress?.loading) {
        progress.loading.message = message;
    }
}
