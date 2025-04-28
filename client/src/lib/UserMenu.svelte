<script lang="ts">
	import { globalContext } from './main';
	import ChangePasswordForm from './ChangePasswordForm.svelte';

	const { userManager, creator } = $globalContext;
	function logout() {
		userManager.logout();
		$globalContext.popupComponent = null;
	}
</script>

<div id="main">
	<div>
		<span>User:</span>
		<span>{creator.name}</span>
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
