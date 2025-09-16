<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import * as Dialog from '$lib/components/ui/dialog';
	import { getContext } from 'svelte';
	import type { GlobalContext } from '../data/globalContext.svelte';
	import Settings from './Settings.svelte';

	const globalContext = getContext<GlobalContext>('globalContext');
	const { userManager } = globalContext;

	function logout() {
		userManager.logout();
		globalContext.showUserMenu = false;
	}
</script>

<Dialog.Root
	open={globalContext.showUserMenu}
	onOpenChange={(open) => (globalContext.showUserMenu = open)}
>
	<Dialog.Content class="min-w-[80vw] min-h-[85vh] align-top">
		<Dialog.Header class="relative">
			<Button variant="destructive" onclick={logout} class="absolute top-0 right-10">Log out</Button>
			<Settings/>
		</Dialog.Header>
	</Dialog.Content>
</Dialog.Root>


<style>
	div#main {
		display: flex;
		padding: 3em;
		flex-direction: column;
	}
	span {
		flex: 1;
	}
	button {
		flex: 1;
	}
</style>