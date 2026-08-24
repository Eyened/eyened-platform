export class ClaheWorkerAPI {
    private worker: Worker | null = null;
    private ready: boolean = false;
    private readyPromise: Promise<void>;
    private processingQueue: Promise<any> = Promise.resolve();
    private isBrowser: boolean = typeof window !== 'undefined' && typeof Worker !== 'undefined';

    constructor() {
        // Set up the ready promise
        if (this.isBrowser) {
            // Create the worker only in browser environment
            this.worker = new Worker(new URL('./clahe-worker.ts', import.meta.url), { type: 'module' });
            
            this.readyPromise = new Promise<void>((resolve) => {
                this.worker?.addEventListener('message', (event: MessageEvent) => {
                    if (event.data.status === 'ready') {
                        this.ready = true;
                        resolve();
                    }
                });
            });

            this.worker?.addEventListener('error', (error) => {
                console.error('CLAHE Worker error:', error);
            });
        } else {
            // In server environment, just mark as ready immediately
            this.ready = true;
            this.readyPromise = Promise.resolve();
        }
    }

    /**
     * Wait for the worker to be ready
     */
    public async waitForReady(): Promise<void> {
        return this.readyPromise;
    }

    /**
     * Process image data with CLAHE
     * @param data The image data
     * @param width The image width
     * @param height The image height
     * @param options Optional parameters
     * @returns Processed image data
     */
    public async processClahe(
        data: Uint8ClampedArray,
        width: number,
        height: number,
        options?: { tileSize?: number, clipLimit?: number }
    ): Promise<Uint8ClampedArray> {
        // Wait for worker to be ready
        if (!this.ready) {
            await this.waitForReady();
        }

        // If not in browser, return the original data
        if (!this.isBrowser || !this.worker) {
            console.warn('CLAHE processing not available in server environment');
            return data;
        }

        // Queue this operation to prevent concurrent processing
        return this.processingQueue = this.processingQueue.then(() => {
            return new Promise<Uint8ClampedArray>((resolve, reject) => {
                // Set up one-time message handler for this request
                const messageHandler = (event: MessageEvent) => {
                    if (event.data.result) {
                        this.worker?.removeEventListener('message', messageHandler);
                        resolve(new Uint8ClampedArray(event.data.result));
                    }
                };

                this.worker?.addEventListener('message', messageHandler);

                // Create a copy of the data to avoid detaching the original buffer
                const dataCopy = new Uint8ClampedArray(data);

                // Send the data to the worker - transfer the copy's buffer
                this.worker?.postMessage({
                    buffer: dataCopy.buffer,
                    width,
                    height,
                    ...options
                }, [dataCopy.buffer]);
            });
        });
    }

    /**
     * Terminate the worker
     */
    public terminate(): void {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
        }
    }
}

// Export a singleton instance for convenience
export const claheWorker = new ClaheWorkerAPI();
