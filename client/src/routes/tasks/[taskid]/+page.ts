export const ssr = false;
export const prerender = false;

/** @type {import('./$types').PageLoad} */
export async function load({ params }) {
    // Not all digits: the page shows the load error without a request (v1 sent NaN).
    return {
        taskid: /^\d+$/.test(params.taskid) ? Number(params.taskid) : null,
    };
}
