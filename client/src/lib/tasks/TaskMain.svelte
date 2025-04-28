<script lang="ts">
	import { globalContext } from '$lib/main';
	import type { TaskContext } from '$lib/types';
	import ViewerWindowLoader from '$lib/viewer-window/ViewerWindowLoader.svelte';
	import { setContext } from 'svelte';

	const taskContext: TaskContext = $props();
	setContext('taskContext', taskContext);

	const { updateConfig } = $globalContext;
	updateConfig(taskContext.taskConfig);

	const instanceIDs = taskContext.subTask.instanceIds;
</script>

<ViewerWindowLoader instanceIDs={$instanceIDs} />
