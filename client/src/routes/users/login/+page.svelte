<script lang="ts">
    import { goto, invalidateAll } from "$app/navigation";
    import { page } from "$app/state";
    import LoginForm from "$lib/LoginForm.svelte";
    import { UserManager, type TokenData } from "$lib/usermanager";

    interface Props {
        data: {
            userManager: UserManager;
        };
    }
    let { data }: Props = $props();
    const { userManager } = data;

    async function handleLogin(tokenData: TokenData) {
        userManager.setTokenData(tokenData);
        let redirectUrl = page.url.searchParams.get("redirect");
        if (redirectUrl == null) {
            redirectUrl = "/";
        } else {
            redirectUrl = decodeURIComponent(redirectUrl);
        }
        await invalidateAll();
        await goto(redirectUrl, { replaceState: true, invalidateAll: true });
    }
</script>

<LoginForm onLogin={handleLogin} />
