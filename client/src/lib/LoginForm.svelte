<script lang="ts">
	import { apiUrl } from '$lib/config'
	import type { TokenData } from './usermanager'

	interface LoginFormProps {
		onLogin: (tokenData: TokenData) => void;
	}
	const { onLogin }: LoginFormProps = $props();

	let username = $state('');
	let password = $state('');

	async function handleLogin(e: Event) {
		e.preventDefault();
		if (!username || !password) {
			return alert('Please enter both username and password');
		}
		const resp = await fetch(`${apiUrl}/auth/login-password`, {
			method: 'POST',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ username, password })
		});

		if (resp.ok) {
			const response = await resp.json();
			console.log('Login successful', response);
			onLogin(response);
		} else {
			if (resp.status == 401) {
				alert('Bad username and/or password');
			} else {
				alert('Unknown error');
			}
		}
	}
</script>

<div class="container">
	<form onsubmit={handleLogin}>
		<div>
			<label for="username">Username:</label>
			<input type="text" id="username" placeholder="Enter your username" bind:value={username} />
		</div>
		<div>
			<label for="password">Password:</label>
			<input
				type="password"
				id="password"
				placeholder="Enter your password"
				bind:value={password}
			/>
		</div>
		<div>
			<button type="submit">Login</button>
		</div>
	</form>
</div>

<style>
	.container {
		margin: 0;
		position: absolute;
		top: 50%;
		left: 50%;
		-ms-transform: translate(-50%, -50%);
		transform: translate(-50%, -50%);

		padding: 3em;
		background-color: #e8e8e8;
		border-radius: 10px;
	}
	form {
		display: flex;
		flex-direction: column;
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
</style>
