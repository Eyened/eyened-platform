<script lang="ts">
	import { getContext } from 'svelte';
	import { host } from '$lib/config';
	import type { GlobalContext } from './data-loading/globalContext.svelte';
	import { data } from '$lib/datamodel/model';

	const { creators } = data;

	let password = $state('');
	let newPassword1 = $state('');
	let newPassword2 = $state('');
	let passwordsMatch = $derived(newPassword1 == newPassword2);

	const { userManager } = getContext<GlobalContext>('globalContext');
	const creator = creators.get(userManager.CreatorID!);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		const resp = await fetch(`${host}/api/auth/change-password`, {
			method: 'POST',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				old_password: password,
				new_password: newPassword1
			})
		});

		if (resp.ok) {
			alert('Password changed');
		} else {
			if (resp.status == 401) {
				alert('Incorrect username or password');
			} else {
				alert('Unknown error');
			}
		}
	}
	let collapsed = $state(true);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<h3 onclick={() => (collapsed = !collapsed)}>Change password</h3>
<div class="container" class:collapsed>
	<form onsubmit={handleSubmit}>
		<div>
			<label for="username">Username:</label>
			<input
				type="text"
				id="username"
				placeholder="Enter your username"
				value={creator?.name}
				disabled
			/>
		</div>
		<div>
			<label for="password">Current Password:</label>
			<input
				type="password"
				id="password"
				placeholder="Enter your password"
				bind:value={password}
			/>
		</div>
		<div>
			<label for="new_password_1">New Password:</label>
			<input
				type="password"
				id="new_password_1"
				placeholder="Enter your new password"
				bind:value={newPassword1}
				class:invalid={!passwordsMatch}
			/>
		</div>
		<div>
			<label for="new_password_2">Repeat New Password:</label>
			<input
				type="password"
				id="new_password_2"
				placeholder="Enter your new password"
				bind:value={newPassword2}
				class:invalid={!passwordsMatch}
			/>
		</div>
		<div>
			<button type="submit" disabled={newPassword1 == '' || !passwordsMatch}>
				Change password
			</button>
		</div>
	</form>
</div>

<style>
	h3 {
		cursor: pointer;
	}
	h3:hover {
		text-decoration: underline;
	}
	.container {
		padding: 3em;
		background-color: #e8e8e8;
		border-radius: 10px;
		overflow: hidden;
	}
	form {
		display: flex;
		flex-direction: column;
	}
	div.collapsed {
		display: none;
	}

	form > div {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	div {
		margin-bottom: 1em;
	}

	label {
		flex: 1;
		margin-right: 0.5em;
	}

	input {
		flex: 2;
		padding: 8px;
		border: 1px solid #ccc;
		border-radius: 4px;
	}
	input[type='password'].invalid {
		border-color: red;
		background-color: d0ffff;
	}

	button {
		padding: 10px;
		border: none;
		border-radius: 4px;
		background-color: #007bff;
		color: white;
		cursor: pointer;
	}

	button:hover {
		background-color: #0056b3;
	}

	button:disabled,
	button:disabled:hover {
		background-color: gray;
		cursor: default;
	}
</style>
