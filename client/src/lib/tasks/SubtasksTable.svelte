<script lang="ts">
  import { BrowserContext } from "$lib/browser/browserContext.svelte";
  import PaginatedResults from "$lib/components/PaginatedResults.svelte";
  import * as Table from "$lib/components/ui/table";
  import type { SubTasksRepo } from "$lib/data/repos.svelte";
  import SubTaskRow from "$lib/tasks/SubTaskRow.svelte";
  import { setContext } from "svelte";
  import type { SubTaskGET, SubTaskWithImagesGET } from "../../types/openapi_types";

  type SubTaskAny = SubTaskGET | SubTaskWithImagesGET;
  let { rows, repo, taskId }: { rows: SubTaskAny[]; repo: SubTasksRepo; taskId: number } = $props();

  const browserContext = new BrowserContext();
  browserContext.thumbnailSize = 4;
  setContext("browserContext", browserContext);

  let currentPage = $state(0);
  const perPage = 100;

  const count = $derived(rows.length);
  const start = $derived(currentPage * perPage);
  const end = $derived(Math.min(start + perPage, count));
  const paginatedRows = $derived(rows.slice(start, end));

  // Clamp page if rows change and current page is now out of range
  $effect(() => {
    if (currentPage > 0 && start >= count) {
      currentPage = Math.max(0, Math.ceil(count / perPage) - 1);
    }
  });

  function onPageChange(p: number) {
    currentPage = p;
  }
</script>

<PaginatedResults {count} {perPage} page={currentPage} {onPageChange}>
  <div class="rounded-md border">
    <Table.Root>
      <Table.Header>
        <Table.Row>
          <Table.Head>ID</Table.Head>
          <Table.Head>Status</Table.Head>
          <Table.Head>View</Table.Head>
          <Table.Head>Images</Table.Head>
          <Table.Head>Comments</Table.Head>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {#each paginatedRows as row, index (row.id)}
          <SubTaskRow obj={repo.object(row.id)} taskId={taskId} index={index} start={start} />
        {:else}
          <Table.Row>
            <Table.Cell colspan="5" class="h-24 text-center">No results.</Table.Cell>
          </Table.Row>
        {/each}
      </Table.Body>
    </Table.Root>
  </div>
</PaginatedResults>

