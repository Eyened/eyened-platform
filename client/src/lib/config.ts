// Get the base URL from the current window location
const getBaseUrl = () => {
    if (typeof window === 'undefined') return ''; // SSR case
    const { protocol, hostname, port } = window.location;
    return `${protocol}//${hostname}${port ? `:${port}` : ''}`;
};

export const apiUrl = `${getBaseUrl()}/api`;
export const fsHost = `${getBaseUrl()}/api/instances/images`;
export const thumbnailHost = `${getBaseUrl()}/api/instances/thumbnails`;