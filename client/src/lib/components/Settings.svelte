<script lang="ts">
	import ChangePasswordForm from "$lib/ChangePasswordForm.svelte";
	import * as Tabs from "$lib/components/ui/tabs";
	import type { GlobalContext } from '$lib/data/globalContext.svelte';
	import TagsEditorJoint from "$lib/tags/TagsEditorJoint.svelte";
	import { getContext } from 'svelte';

	const globalContext = getContext<GlobalContext>('globalContext');
	const { userManager } = globalContext;

	function logout() {
		userManager.logout();
		globalContext.showUserMenu = false;
	}
</script>



 
<Tabs.Root value="tags">
  <Tabs.List>
    <Tabs.Trigger value="tags">Tags</Tabs.Trigger>
    <Tabs.Trigger value="password">Password</Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="tags">
    <TagsEditorJoint/>
  </Tabs.Content>
  <Tabs.Content value="password">
    <p>Change your password here.</p>
    <ChangePasswordForm />
  </Tabs.Content>
</Tabs.Root>