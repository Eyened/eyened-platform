<script lang="ts">
	import type { GlobalContext } from '$lib/data/globalContext.svelte';
	import { getContext } from 'svelte';
	import ChangePasswordForm from './ChangePasswordForm.svelte';

	const globalContext = getContext<GlobalContext>("globalContext");
	const { userManager, user: creator } = globalContext;
	function logout() {
		globalContext.popupComponent = null;
        userManager.logout();		
	}
</script>

<div id="main">
	<div>
		<span>User:</span>
		<span>{creator.username}</span>
	</div>
	<div>
		<ChangePasswordForm />
	</div>
	<div>
		<button onclick={logout}>Logout</button>
	</div>
</div>

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
