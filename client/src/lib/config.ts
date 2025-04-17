import * as env from '$env/static/public';

export const authTokenDuration = parseInt(env.PUBLIC_AUTH_TOKEN_DURATION)
export const apiUrl = env.PUBLIC_API_URL;
export const fsHost = env.PUBLIC_FILESERVER_URL;
export const thumbnailHost = env.PUBLIC_THUMBNAIL_SERVER_URL;