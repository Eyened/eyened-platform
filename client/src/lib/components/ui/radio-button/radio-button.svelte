<script lang="ts">
    import { cn } from "$lib/utils.js";

    // Carbon radio button over a native input: 20 px circle, 8 px dot, 8 px to the label. Radios sharing a name are one tab stop.
    const uid = $props.id();
    let {
        labelText,
        hideLabel = false,
        name,
        value,
        checked,
        onchange,
        describedBy,
        primaryFocus = false,
        class: className,
    }: {
        labelText: string;
        hideLabel?: boolean;
        name: string;
        value: string;
        checked: boolean;
        onchange: () => void;
        /** Id of text that describes this radio, such as a "Current" tag. */
        describedBy?: string;
        /** ui/modal focuses this radio when it opens. */
        primaryFocus?: boolean;
        class?: string;
    } = $props();
</script>

<span class={cn("inline-flex items-start gap-2", className)}>
    <input
        id={uid}
        type="radio"
        data-slot="radio-button"
        data-modal-primary-focus={primaryFocus || undefined}
        aria-describedby={describedBy}
        {name}
        {value}
        {checked}
        onchange={() => onchange()}
        onkeydown={(e) => {
            // Carbon radios select with Space and arrows; Enter must not submit a surrounding form.
            if (e.key === "Enter") e.preventDefault();
        }}
        class="grid size-5 shrink-0 cursor-pointer appearance-none place-content-center rounded-full border border-icon-primary bg-transparent before:size-2 before:scale-0 before:rounded-full before:bg-icon-primary before:content-[''] checked:before:scale-100 disabled:cursor-not-allowed disabled:border-icon-disabled disabled:before:bg-icon-disabled"
    />
    <label
        for={uid}
        class={cn(
            "cursor-pointer pt-0.5 text-body-compact-01 text-text-primary",
            hideLabel && "sr-only",
        )}>{labelText}</label
    >
</span>
