// src/hooks.server.js
import { host } from '$lib/config';

/** @type {import('@sveltejs/kit').HandleFetch} */
export async function handleFetch({ event, request, fetch }) {
	return fetch(request);
}
