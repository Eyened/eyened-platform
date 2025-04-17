import { CLAHE } from './CLAHE';

// Tell TypeScript this is a worker context
const ctx: Worker = self as any;

// Create CLAHE instance with default parameters
let claheProcessor = new CLAHE();

// Handle incoming messages
ctx.addEventListener('message', (event: MessageEvent) => {
    const { buffer, width, height, tileSize, clipLimit } = event.data;

    // Create a new CLAHE instance if parameters are provided
    if (tileSize !== undefined && clipLimit !== undefined) {
        claheProcessor = new CLAHE(tileSize, clipLimit);
    }

    // Process the image data
    const result = claheProcessor.applyClahe(new Uint8ClampedArray(buffer), width, height);

    // Send the result back to the main thread
    ctx.postMessage({ result: result.buffer }, [result.buffer]);
});

// Notify that the worker is ready
ctx.postMessage({ status: 'ready' });
