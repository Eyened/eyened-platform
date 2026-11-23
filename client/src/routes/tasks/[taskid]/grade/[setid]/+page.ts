import { redirect } from "@sveltejs/kit";

export const ssr = false;
export const prerender = false;

/** Old links count sets from 0; the set route counts from 1. The query string comes along. */
/** @type {import('./$types').PageLoad} */
export function load({ params, url }) {
    redirect(
        307,
        `/tasks/${params.taskid}/set/${Number(params.setid) + 1}${url.search}`,
    );
}
