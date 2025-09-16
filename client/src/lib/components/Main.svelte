<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { authEnabled } from '$lib/config';
	import { getContext } from 'svelte';
	import type { GlobalContext } from '../data/globalContext.svelte';
	import UserMenu from './UserMenu.svelte';
	import * as Tooltip from './ui/tooltip';

	let { children }: { children: any } = $props();

	const {userManager} = getContext<GlobalContext>('globalContext');;


	if(authEnabled && !userManager.loggedIn) {
		// redirect to login page if user not logged
		console.log('User not logged in. Redirecting..')
		goto(`/users/login?redirect=${encodeURIComponent(page.url.pathname + page.url.search)}`);
	}
</script>

<Tooltip.Provider>
{#if !authEnabled || (authEnabled && userManager.loggedIn)}
	{@render children?.()}
{/if}

<UserMenu />
</Tooltip.Provider>

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		font-family: Verdana, sans-serif;
		background-color: white;
		display: flex;
		flex-direction: column;
	}
</style>