<script lang="ts">
	import ChangePasswordForm from "$lib/ChangePasswordForm.svelte";
	import FeaturesEditor from "$lib/components/FeaturesEditor.svelte";
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



 <div class="h-full w-full">
  <Tabs.Root value="tags" class="h-full w-full">
    <Tabs.List class="flex-none">
      <Tabs.Trigger value="tags">Tags</Tabs.Trigger>
      <Tabs.Trigger value="features">Features</Tabs.Trigger>
      <Tabs.Trigger value="password">Password</Tabs.Trigger>
    </Tabs.List>
    <Tabs.Content value="tags" class="flex-1 overflow-y-auto">
      <TagsEditorJoint/>
    </Tabs.Content>
    <Tabs.Content value="features" class="flex-1 overflow-y-auto">
      <FeaturesEditor/>
    </Tabs.Content>
    <Tabs.Content value="password" class="flex-1 overflow-y-auto">
      <p>Change your password here.</p>
      <ChangePasswordForm />
    </Tabs.Content>
  </Tabs.Root>
</div>