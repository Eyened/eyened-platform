import { browser } from '$app/environment';
import * as env from '$env/static/public';

export const authTokenDuration = parseInt(env.PUBLIC_AUTH_TOKEN_DURATION)
export const fsHost = env.PUBLIC_FILESERVER_HOSTNAME;
export const thumbnailHost = env.PUBLIC_THUMBNAIL_SERVER_HOSTNAME;
export const host = browser ? window.location.origin : undefined;