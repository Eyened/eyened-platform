export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params }) {
    const ImageInstanceID = parseInt(params.ImageInstanceID);
    return { ImageInstanceID };
}