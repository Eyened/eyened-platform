<script lang="ts">
	import { GlobalContext } from '$lib/data-loading/globalContext.svelte';
	import type { TaskContext } from '$lib/types';
	import ViewerWindowLoader from '$lib/viewer-window/ViewerWindowLoader.svelte';
	import { getContext, setContext } from 'svelte';

	const taskContext: TaskContext = $props();
	setContext('taskContext', taskContext);

	const globalContext = getContext<GlobalContext>('globalContext');
	globalContext.updateConfig(taskContext.taskConfig);

	const instanceIDs = taskContext.subTask.instanceIds;
</script>

<ViewerWindowLoader instanceIDs={$instanceIDs} />
