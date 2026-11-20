export type ImageLoadState = {
    message: string;
};

export type ImageLoadProgress = {
    loading?: ImageLoadState;
};

export function setLoadMessage(
    progress: ImageLoadProgress | undefined,
    message: string,
): void {
    if (progress?.loading) {
        progress.loading.message = message;
    }
}
