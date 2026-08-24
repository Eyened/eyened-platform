<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { getContext } from 'svelte';
	import type { GlobalContext } from '../data/globalContext.svelte';
	import Settings from './Settings.svelte';
	import { Button } from './ui/button';

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
	<Dialog.Content class="flex h-[85vh] min-w-[80vw]">
		<Button variant="destructive" onclick={logout} size="sm" class="absolute top-2 right-12">Log out</Button>
		<Settings/>
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