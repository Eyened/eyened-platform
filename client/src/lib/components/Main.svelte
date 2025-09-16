<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { authEnabled } from '$lib/config';
// import { popup } from '$lib/stores';
	import { getContext } from 'svelte';
	import type { GlobalContext } from '../data/globalContext.svelte';
	import UserMenu from './UserMenu.svelte';

	let { children }: { children: any } = $props();

	const {userManager} = getContext<GlobalContext>('globalContext');;
	console.log('authEnabled', authEnabled)

	// let creator: Creator | undefined

	if(authEnabled && !userManager.loggedIn) {
		// redirect to login page if user not logged
		console.log('User not logged in. Redirecting..')
		goto(`/users/login?redirect=${encodeURIComponent(page.url.pathname + page.url.search)}`);
	}
</script>

{#if !authEnabled || (authEnabled && userManager.loggedIn)}
	{@render children?.()}
{/if}

<!-- {#if $popup}
	<div class="popup">
		<div>
			<span>{$popup}</span>
			<button onclick={() => popup.set(undefined)}>Close</button>
		</div>
	</div>
{/if} -->

<UserMenu />

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		font-family: Verdana, sans-serif;
		background-color: white;
		display: flex;
		flex-direction: column;
	}
	div {
		display: flex;
	}
	div.popup {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(255, 255, 255, 0.9);
		backdrop-filter: blur(5px);

		height: 100vh;
		width: 100vw;

		display: flex;
		z-index: 100;
	}
	div.popup div {
		align-items: center;
		flex-direction: column;
		display: flex;
	}
</style>