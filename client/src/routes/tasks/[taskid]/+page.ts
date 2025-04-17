export const ssr = false;
export const prerender = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params, url }) {
	return {
		taskid: parseInt(params.taskid)
	}
}
