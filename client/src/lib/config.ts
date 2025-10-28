export const apiUrl = import.meta.env.VITE_API_URL;
export const fsHost = import.meta.env.VITE_FILESERVER_URL;
export const thumbnailHost = import.meta.env.VITE_THUMBNAIL_SERVER_URL;
export const authEnabled = !(import.meta.env.VITE_PUBLIC_AUTH_DISABLED=='1');