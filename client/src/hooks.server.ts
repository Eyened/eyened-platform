// src/hooks.server.ts
/** @type {import('@sveltejs/kit').HandleFetch} */
export async function handleFetch({ event, request, fetch }) {
	return fetch(request);
}
