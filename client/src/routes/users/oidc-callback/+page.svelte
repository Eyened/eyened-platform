<script lang="ts">
    import { page } from '$app/state';
    // TODO: move authClient to lib?
    import { authClient } from '../../../auth';

    async function handleCallback() {
        let code = $derived(page.url.searchParams.get('code'));
        let state = $derived(page.url.searchParams.get('state'));
        $inspect(code, state);

        let resp = await authClient.OIDCAuthenticate(code, state);
    }

    handleCallback();
</script>

<h1>OIDC callback page (no content)</h1>
