<script lang="ts">
    import SchemaForm from "./SchemaForm.svelte";
    import { type JSONSchema } from "./schemaType";
    import MainIcon from "$lib/viewer-window/icons/MainIcon.svelte";
    import { Trash } from "$lib/viewer-window/icons/icons";
    import { SchemaValidator } from "./schemaValidator.svelte";

    // creates a globally unique id for grouping the radio input field (only needed if enum)
    // can use $props.id() in svelte 5.20
    const fieldID = [...Array(10)]
        .map(() => Math.random().toString(36)[2])
        .join("");

    let collapsed = $state(false);

    interface Props {
        schema: JSONSchema;
        value: any;
        onchange: (value: any) => void;
        max_radio_options?: number;
        vertical?: boolean;
        canEdit?: boolean;
        collapse?: boolean;
        requiredAbsent?: boolean;
    }
    let {
        schema,
        value,
        onchange,
        max_radio_options = 8,
        vertical = $bindable(true),
        collapse = $bindable(true),
        canEdit = true,
        requiredAbsent = false,
    }: Props = $props();

    const title = schema.title || "?";
    const schemaValidator = new SchemaValidator(schema, value);

    function update() {
        onchange(schemaValidator.value);
    }

    // local variable used to bind input fields to
    // takes care of type conversion and setting undefined values
    const val = {
        get value() {
            return schemaValidator.value;
        },
        set value(val: any) {
            if (val !== undefined) {
                if (schema.type == "integer") {
                    val = parseInt(val);
                } else if (schema.type == "number") {
                    val = parseFloat(val);
                }
            }
            schemaValidator.setValue(val);
            update();
        },
    };

    function clear(e: MouseEvent) {
        e.preventDefault();
        val.value = undefined;
    }

    function keyUpdate(key: string, value: any) {
        schemaValidator.setProperty(key, value);
        update();
    }

    function addArrayValue() {
        schemaValidator.addArrayValue();
        update();
    }
    function setArray(i: number, v: any) {
        schemaValidator.setArrayValue(i, v);
        update();
    }
    function removeArrayValue(i: number) {
        schemaValidator.removeArrayValue(i);
        update();
    }

    let errorKeys = $derived.by(() => {
        return schemaValidator.errors
            .filter((error) => error.path.startsWith("."))
            .map((error) => error.path.slice(1));
    });

    let inputVisible = $derived.by(() => {
        if (!canEdit) return false;
        if (collapse) {
            if (val.value === undefined) {
                return true;
            }
            return false;
        }
        return true;
    });

    // hide if the key is required absent, and no value has been set
    let hidden = $derived.by(() => {
        if (requiredAbsent) {
            if (val.value === undefined) {
                return true;
            }
        }
        return false;
    });
</script>

{#snippet query(showValue = true)}
    <div class="query">
        {schema.description}:
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        {#if showValue}
            {#if canEdit}
                <span
                    onclick={clear}
                    class="selected"
                    class:hide={schemaValidator.value === undefined}
                >
                    {schemaValidator.value}
                </span>
            {:else}
                <span
                    class="value"
                    class:hide={schemaValidator.value === undefined}
                >
                    {schemaValidator.value}
                </span>
            {/if}
        {/if}
    </div>
{/snippet}

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main" class:hidden>
    <div class="content" class:valid={schemaValidator.isValid}>
        {#if schema.type == "object"}
            <header onclick={() => (collapsed = !collapsed)}>
                {#if collapsed}▶{:else}▼{/if}
                {title}
            </header>
            <div class="object" class:collapsed>
                {#each schemaValidator.keysSorted as key}
                    <div
                        class="key"
                        class:error={errorKeys.includes(key)}
                        class:absent={schemaValidator.requiredAbsent.includes(
                            key,
                        )}
                    >
                        <SchemaForm
                            schema={schema.properties![key]}
                            value={schemaValidator.value?.[key]}
                            onchange={(value) => keyUpdate(key, value)}
                            bind:vertical
                            bind:collapse
                            requiredAbsent={schemaValidator.requiredAbsent.includes(
                                key,
                            )}
                            {canEdit}
                        />
                    </div>
                {/each}
            </div>
        {:else if schema.type == "array" && schema.items !== undefined}
            {@render query(false)}
            <ol class="array">
                {#each schemaValidator.value ?? [] as sub_value, i (i)}
                    <li>
                        <span>{i}</span>
                        <SchemaForm
                            value={sub_value}
                            schema={schema.items}
                            onchange={(v) => setArray(i, v)}
                            bind:vertical
                            bind:collapse
                            {canEdit}
                        />
                        <div class="icon">
                            {#if canEdit}
                                {#snippet icon()}
                                    <Trash size="1.5em" />
                                {/snippet}
                                <MainIcon
                                    onclick={() => removeArrayValue(i)}
                                    theme="light"
                                    {icon}
                                />
                            {/if}
                        </div>
                    </li>
                {/each}
            </ol>
            <div class="input">
                <button onclick={addArrayValue} disabled={!canEdit}>
                    {`Add ${schema.items.title}`}
                </button>
            </div>
        {:else if schema.type == "string" || schema.type == "number" || schema.type == "integer"}
            {#if schema.description}
                {@render query(
                    !(schema.enum && schema.enum.length > max_radio_options),
                )}
            {/if}

            {#if schema.enum}
                {#if schema.enum.length <= max_radio_options}
                    {#if inputVisible}
                        <ol class:vertical>
                            {#each schema.enum as option}
                                <li>
                                    <label>
                                        <input
                                            type="radio"
                                            value={option}
                                            name={fieldID}
                                            bind:group={val.value}
                                        />
                                        <span>{option}</span>
                                    </label>
                                </li>
                            {/each}
                        </ol>
                    {/if}
                {:else}
                    <div class="input">
                        <select bind:value={val.value}>
                            {#each schema.enum as option}
                                <option value={option}>{option}</option>
                            {/each}
                        </select>
                    </div>
                {/if}
            {:else if inputVisible}
                <div class="input">
                    <input
                        type={schemaValidator.inputType}
                        bind:value={val.value}
                        size={schemaValidator.inputType == "text" ? 100 : 4}
                    />
                </div>
            {/if}
        {/if}
    </div>
</div>

<style>
    div.hidden {
        display: none;
    }
    div.query {
        display: flex;
        flex-direction: row;
    }
    div.absent {
        opacity: 0.3;
    }
    div.key {
        display: flex;
        flex-direction: row;
    }
    div.key.error {
        background-color: rgba(255, 0, 0, 0.1);
    }
    span.selected {
        font-weight: bold;
        color: darkolivegreen;
        margin-left: 1em;
        padding: 0.1em;

        border-radius: 2px;
        border: 1px solid lightblue;
        background-color: lavender;
    }
    span.selected:hover {
        cursor: pointer;
        background-color: rgb(247, 247, 255);
    }
    span.selected.hide {
        visibility: hidden;
    }
    span.value {
        margin-left: 1em;
        color: darkolivegreen;
    }
    button {
        margin-left: 1em;
    }
    div.content {
        border-left: 0.2em solid red;
    }
    div.content.valid {
        border-left: 0.2em solid green;
    }
    div {
        display: flex;
        flex-direction: column;
    }
    div.input {
        flex-direction: row;
    }
    div.content {
        padding-left: 0.2em;
        overflow: auto;
    }
    ol {
        padding: 0;
        padding-left: 0.5em;
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 0.1em;
        margin: 0;
    }
    ol.vertical {
        flex-direction: column;
        gap: 0.1em;
    }
    ol.array {
        flex-direction: column;
    }
    li {
        padding-left: 0.2 em;
        display: flex;
        align-items: center;
        flex: 0 0 auto;
    }
    div.object {
        flex-direction: column;
    }
    li {
        display: flex;
        align-items: center;
    }
    div.icon {
        flex: 0;
    }
    div.main {
        flex-direction: column;
        flex: 1;
        padding: 0.1em;
        border-radius: 2px;
        border: 1px solid black;
        margin: 0.2em;

        border-radius: 2px;
        box-shadow: rgba(149, 157, 165, 0.1) 0px 3px 6px;
    }

    div.query {
        font-weight: bold;
    }
    header {
        font-weight: bold;
        padding: 0.2em;
        cursor: pointer;
    }

    div.collapsed {
        display: none;
    }
</style>
