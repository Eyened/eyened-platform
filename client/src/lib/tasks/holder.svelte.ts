import { ApiError } from "$lib/api/client";
import { fetchSubTaskByIndex, updateSubTask } from "$lib/data/api";
import { subtasks } from "$lib/data/stores.svelte";
import type { SaveTracker } from "$lib/saving/saveTracker.svelte";
import { tick } from "svelte";
import { flushWithin } from "./setNavigation.svelte";

export type HolderAction = "claim" | "giveBack";

export interface SetHolderDeps {
    subTaskId: number;
    taskId: number;
    /** The set's 0-based index, for the refetch after a lost Claim. */
    index: number;
    userId: number;
    tracker: SaveTracker;
    /** Where focus goes once a lost Claim has taken the control away. */
    focusAfterRace: () => void;
}

/** Who holds the set, and Claim / Give back, read from the store so every reply updates it in place. */
export class SetHolder {
    busy = $state(false);
    failed: HolderAction | null = $state(null);
    /** The last Claim lost to someone else's; the notice says so and is announced. */
    raceLost = $state(false);

    constructor(private readonly deps: SetHolderDeps) {}

    private get set() {
        return subtasks.get(this.deps.subTaskId);
    }

    private get holderId(): number | null {
        return this.set?.creator_id ?? null;
    }

    /** The server's answer to "may I change status and comments". */
    get canEdit(): boolean {
        return this.set?.can_edit_status_and_comments === true;
    }

    get text(): string {
        if (this.holderId === null) return "Unclaimed";
        if (this.holderId === this.deps.userId) return "Yours";
        return `Held by ${this.set?.creator?.name ?? ""}`;
    }

    /** Claim on an unclaimed set, Give back on mine; none on someone else's or when I may not change the set. */
    get action(): HolderAction | null {
        if (!this.canEdit) return null;
        if (this.holderId === null) return "claim";
        return this.holderId === this.deps.userId ? "giveBack" : null;
    }

    /** Shown only while the failed action is still the one on offer. */
    get failText(): string {
        if (this.failed !== this.action) return "";
        if (this.failed === "claim") return "Couldn't claim. Try again.";
        if (this.failed === "giveBack") return "Couldn't give back. Try again.";
        return "";
    }

    /** The canvas notice while someone else holds the set. */
    get notice(): { title: string; subtitle: string; alert: boolean } | null {
        if (this.holderId === null || this.holderId === this.deps.userId)
            return null;
        const name = this.set?.creator?.name ?? "";
        return {
            title: this.raceLost
                ? `${name} claimed this set first`
                : `${name} holds this set`,
            subtitle: "What you save here is saved as yours, inside this set.",
            alert: this.raceLost,
        };
    }

    async run(): Promise<void> {
        const action = this.action;
        if (!action || this.busy) return;
        this.busy = true;
        this.failed = null;
        try {
            // A save still running would claim the set again behind the tag; its failure shows as usual.
            if (
                action === "giveBack" &&
                !(await flushWithin(this.deps.tracker, 5000))
            )
                return;
            await updateSubTask(this.deps.subTaskId, {
                claim: action === "claim",
            });
        } catch (e) {
            if (
                action === "claim" &&
                e instanceof ApiError &&
                e.code === "subtask_already_claimed"
            )
                await this.showWinner();
            else this.failed = action;
        } finally {
            this.busy = false;
        }
    }

    /** Refetch, so the tag, the lock and the next open set follow whoever won. */
    private async showWinner(): Promise<void> {
        try {
            await fetchSubTaskByIndex(this.deps.taskId, this.deps.index);
        } catch {
            this.failed = "claim";
            return;
        }
        this.raceLost = true;
        await tick();
        this.deps.focusAfterRace();
    }
}
