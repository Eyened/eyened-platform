<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import * as NavigationMenu from '$lib/components/ui/navigation-menu';
	import { getContext } from 'svelte';
	import type { GlobalContext } from '../data/globalContext.svelte';

	const globalContext = getContext<GlobalContext>('globalContext');

	interface Props {
		maxWidth?: string;
	}

	let { maxWidth }: Props = $props();
</script>

<nav class="topnav dark bg-neutral-900 text-white">
	<div class="container class={`${maxWidth ? 'max-w-['+maxWidth+']' : 'max-w-none'}`}">
		<NavigationMenu.Root class="left ">
			<NavigationMenu.List class="flex items-center gap-1">
				<NavigationMenu.Item>
					<NavigationMenu.Link
						href="/"
						class="px-3 py-2 rounded-md text-sm font-medium hover:bg-muted"
					>
						Browser
					</NavigationMenu.Link>
				</NavigationMenu.Item>
				<NavigationMenu.Item>
					<NavigationMenu.Link
						href="/tasks"
						class="px-3 py-2 rounded-md text-sm font-medium hover:bg-muted"
					>
						Tasks
					</NavigationMenu.Link>
				</NavigationMenu.Item>
			</NavigationMenu.List>
		</NavigationMenu.Root>

		<div class="right">
			<Button
				variant="ghost"
				class="h-9"
				onclick={() => (globalContext.showUserMenu = true)}
			>
				{globalContext.userManager.user?.username}
			</Button>
		</div>
	</div>
</nav>

<style>
	:root {
		--topmenu-height: 56px;
	}
	.topnav {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: var(--topmenu-height);
		background-color: black;
		border-bottom: 5px solid #565656;
		z-index: 50;
	}
	.topnav .container {
		width: 100%;
		height: 100%;
		margin: 0 auto;
		padding: 0 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		max-width: none;
	}
</style>
