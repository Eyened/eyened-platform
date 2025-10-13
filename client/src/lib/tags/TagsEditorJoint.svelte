<script lang="ts">
	import * as Tabs from "$lib/components/ui/tabs";
	import TagsEditor from "./TagsEditor.svelte";
</script>

<Tabs.Root value="image">
	<Tabs.List>
		<Tabs.Trigger value="image">Image Tags</Tabs.Trigger>
		<Tabs.Trigger value="study">Study Tags</Tabs.Trigger>
		<Tabs.Trigger value="annotation">Annotation Tags</Tabs.Trigger>
	</Tabs.List>
	<Tabs.Content value="image">
		<div class="tageditor-container">
			<h2 class="text-l font-bold">Image Tags</h2>
			<TagsEditor tagType="ImageInstance" />
		</div>
	</Tabs.Content>
	<Tabs.Content value="study">
		<div class="tageditor-container">
			<h2 class="text-l font-bold">Study Tags</h2>
			<TagsEditor tagType="Study" />
		</div>
	</Tabs.Content>
	<Tabs.Content value="annotation">
		<div class="tageditor-container">
			<h2 class="text-l font-bold">Annotation Tags</h2>
			<TagsEditor tagType="Annotation" />
		</div>
	</Tabs.Content>
</Tabs.Root>