<script lang="ts">
    import Main from "$lib/components/Main.svelte";
    import { fetchApi } from "$lib/api/client";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";
    import { ArrowLeft, Circle, LoaderCircle, CheckCircle2, ArrowRight } from "@lucide/svelte";

    type CVIResponse = {
        id: string | number;
        id_column: string;
        record: Record<string, any>;
        added_by_display_name?: string | null;
        pdf_url?: string | null;
    };

    type CVIPdfIndexItem = {
        id: string | number;
        form_ID?: string | number | null;
        pdf_file: string;
        pdf_url: string;
        status?: string | null;
    };

    type CVIPdfStatus = "Not Started" | "Busy" | "Ready";

    const globalContext = getContext<GlobalContext>("globalContext");

    const fieldOrder = [
        "data_access_group",
        "added_by",
        "data_added",
        "form_ID",
        "folder_number",
        "nhs_number",
        "patient_name",
        "visual_status",
        "patient_postcode",
        "dob",
        "gender",
        "form_version",
        "patient_town",
        "patient_date",
        "signatory_is",
        "registration_date",
        "hospital_name",
        "hospital_name_other",
        "social_service_department",
        "social_service_department_extracted",
        "red1",
        "red2",
        "led1",
        "led2",
        "main_diagnosis",
        "main_cause_from",
        "q1",
        "q2",
        "q3",
        "q4",
        "q5",
        "q6",
        "q7",
        "patient_is",
        "ethnicity",
        "recieved_by",
    ];

    const labels: Record<string, string> = {
        added_by: "Added By",
        data_added: "Date Added",
        form_ID: "Form ID",
        folder_number: "Folder Number",
        nhs_number: "NHS Number",
        patient_name: "Patient Name",
        visual_status: "Visual Status",
        patient_postcode: "Patient Postcode",
        dob: "Date of Birth",
        gender: "Gender",
        form_version: "Form Version",
        patient_town: "Patient Town",
        patient_date: "Patient Date",
        signatory_is: "Signatory Is",
        registration_date: "Registration Date",
        hospital_name: "Hospital Name",
        hospital_name_other: "Hospital Name Other",
        social_service_department: "Social Service Department",
        social_service_department_extracted: "Social Service Department Extracted",
        red1: "Right Eye Diagnosis 1",
        red2: "Right Eye Diagnosis 2",
        led1: "Left Eye Diagnosis 1",
        led2: "Left Eye Diagnosis 2",
        main_diagnosis: "Main Diagnosis",
        main_cause_from: "Main Cause From",
        q1: "Does the patient live alone?",
        q2: "Does someone support you with your care?",
        q3: "Poor physical mobility?",
        q4: "Hearing impairment?",
        q5: "Learning disability?",
        q6: "Diagnosis of dementia?",
        q7: "Known to specialist visual impairment education service?",
        patient_is: "Patient Is",
        ethnicity: "Ethnicity",
        data_access_group: "Data Access Group",
        recieved_by: "Recieved By",
    };

    const intFields = new Set(["added_by", "form_ID", "folder_number", "form_version"]);
    const dateFields = new Set(["dob", "patient_date", "registration_date"]);
    const readonlyFields = new Set(["added_by", "form_ID", "folder_number"]);

    const patientIsOptions = [
        "Retired",
        "Employed",
        "Unemployed",
        "Child",
        "Student",
        "Not_Recorded (ocr)",
        "Conflict please check",
        "Not Recorded",
    ];

    const ethnicityOptions = [
        "White_British",
        "White_Irish",
        "White_Other",
        "Asian_or_Asian_British_Indian",
        "Asian_or_Asian_British_Pakistani",
        "Asian_or_Asian_British_Bangladeshi",
        "Asian_or_Asian_British_Other_Asian",
        "Other_Ethnic_Groups_Chinese",
        "Any_Other_Ethnic_Group",
        "Mixed_White_and_Black_Caribbean",
        "Mixed_White_and_Black_African",
        "Mixed_White_and_Asian",
        "Other_Mixed",
        "Black_or_Black_British_Carribean",
        "Black_or_Black_British_African",
        "Black_or_Black_British_Other",
        "Unentered",
        "Unknown",
        "White_Scottish",
        "White_Welsh",
        "Gypsy_Traveller",
        "White_English",
        "White_Northen_Irish",
    ];

    const qOptions = ["Yes", "No", "Unrecorded", "Dont's know"];
    const visualStatusOptions = ["Unknown", "Blind", "Partial Sight", "Not Eligible", "Not Recorded"];
    const mainCauseFromOptions = ["", "from_form", "decided_by_us", "unspecified"];
    const dataAccessGroupOptions = ["No_assignment", "2025/26", "2026/27", "2027/28", "2028/29", "2029/30"];
    const signatoryIsOptions = ["", "Patient", "Representative", "Guardian"];

    let loading = $state(true);
    let saving = $state(false);
    let message = $state("");
    let error = $state("");

    let idColumn = $state("id");
    let recordId = $state<string | number | null>(null);
    let currentRecord = $state<Record<string, any>>({});
    let form = $state<Record<string, string>>({});
    let addedByDisplayName = $state("");
    let pdfUrl = $state<string | null>(null);
    let workflowStatus = $state("");
    let pdfIndexItems = $state<CVIPdfIndexItem[]>([]);
    let pdfIndexLoading = $state(false);
    let formIdSearch = $state("");
    let leftPanelWidth = $state(52);
    let cviPageEl: HTMLDivElement | null = null;
    let isDraggingDivider = $state(false);
    let dragStartX = 0;
    let dragStartLeftWidth = 52;
    let openDropdownKey = $state<string | null>(null);
    let dropdownFilters = $state<Record<string, string>>({});
    let lookupOptions = $state<Record<string, string[]>>({
        visual_status: visualStatusOptions,
        patient_is: patientIsOptions,
        ethnicity: ethnicityOptions,
        q1: qOptions,
        q2: qOptions,
        q3: qOptions,
        q4: qOptions,
        q5: qOptions,
        q6: qOptions,
        q7: qOptions,
        red1: [],
        red2: [],
        led1: [],
        led2: [],
        main_diagnosis: [],
        main_cause_from: mainCauseFromOptions,
        data_access_group: dataAccessGroupOptions,
        hospital_name: [],
        social_service_department: [],
    });

    function optionsForKey(key: string): string[] {
        return lookupOptions[key] ?? [];
    }

    function listIdForKey(key: string): string {
        return `${key}-options`;
    }

    function openDropdown(key: string) {
        // Opening should show the full list first; typing will apply filtering.
        dropdownFilters[key] = "";
        openDropdownKey = key;
    }

    function closeDropdown(key: string) {
        if (openDropdownKey !== key) return;
        setTimeout(() => {
            if (openDropdownKey === key) {
                openDropdownKey = null;
            }
        }, 120);
    }

    function filteredOptionsForKey(key: string): string[] {
        const options = optionsForKey(key);
        const query = (dropdownFilters[key] ?? "").trim().toLowerCase();
        if (!query) return options;
        return options.filter((option) => option.toLowerCase().includes(query));
    }

    function handleDropdownInput(key: string, value: string) {
        form[key] = value;
        dropdownFilters[key] = value;
        openDropdownKey = key;
    }

    function pickDropdownOption(key: string, value: string) {
        form[key] = value;
        dropdownFilters[key] = "";
        openDropdownKey = null;
    }

    async function loadLookupOptions() {
        try {
            const [diagnosisRes, hospitalRes, socialRes] = await Promise.all([
                fetch("/diagnosis.json"),
                fetch("/hospital.json"),
                fetch("/social_service_department.json"),
            ]);

            const diagnosisJson = diagnosisRes.ok ? await diagnosisRes.json() : {};
            const hospitalJson = hospitalRes.ok ? await hospitalRes.json() : {};
            const socialJson = socialRes.ok ? await socialRes.json() : {};

            const diagnosisValues = Array.isArray(diagnosisJson?.["Right Eye Diagnosis"]) ? diagnosisJson["Right Eye Diagnosis"] : [];
            const hospitalValues = Array.isArray(hospitalJson?.hospital_name_) ? hospitalJson.hospital_name_ : [];
            const socialValues = Array.isArray(socialJson?.["Social Service Department"]) ? socialJson["Social Service Department"] : [];

            lookupOptions = {
                ...lookupOptions,
                red1: diagnosisValues,
                red2: diagnosisValues,
                led1: diagnosisValues,
                led2: diagnosisValues,
                main_diagnosis: diagnosisValues,
                hospital_name: hospitalValues,
                social_service_department: socialValues,
            };
        } catch {
            // Keep manual fallback lists if static files are unavailable.
        }
    }

    function todayIso(): string {
        return new Date().toISOString().slice(0, 10);
    }

    function normalizeForInput(key: string, value: any): string {
        if (value == null) return "";
        if (key === "folder_number") {
            const numeric = String(value).replace(/\D/g, "");
            if (!numeric) return "";
            return numeric.padStart(4, "0");
        }
        if (dateFields.has(key)) {
            const raw = String(value);
            return raw.length >= 10 ? raw.slice(0, 10) : raw;
        }
        return String(value);
    }

    function getPdfNameFromPath(pathValue: string | null | undefined): string {
        if (!pathValue) return "";
        const cleaned = String(pathValue).replace(/\\/g, "/").trim();
        if (!cleaned) return "";
        const fileName = cleaned.split("/").pop() ?? cleaned;
        return decodeURIComponent(fileName);
    }

    function currentPdfName(): string {
        return getPdfNameFromPath(currentRecord.pdf_file);
    }

    function pdfLabel(item: CVIPdfIndexItem): string {
        const name = getPdfNameFromPath(item.pdf_file);
        if (item.form_ID == null || item.form_ID === "") {
            return name;
        }
        return `${item.form_ID} - ${name}`;
    }

    function normalizeCviStatus(value: string | null | undefined): CVIPdfStatus {
        const normalized = String(value ?? "").trim().toLowerCase();
        if (!normalized) return "Not Started";
        if (["ready", "completed", "finished"].includes(normalized)) return "Ready";
        if (["busy", "working", "in progress", "in_progress", "processing"].includes(normalized)) return "Busy";
        return "Not Started";
    }

    function statusIconFor(status: CVIPdfStatus) {
        switch (status) {
            case "Ready":
                return CheckCircle2;
            case "Busy":
                return LoaderCircle;
            default:
                return Circle;
        }
    }

    function loadIntoForm(response: CVIResponse) {
        idColumn = response.id_column;
        recordId = response.id;
        currentRecord = response.record ?? {};
        addedByDisplayName = response.added_by_display_name ?? "";
        pdfUrl = response.pdf_url ?? null;
        workflowStatus = String(currentRecord.status ?? "").trim();

        const nextForm: Record<string, string> = {};
        for (const key of fieldOrder) {
            nextForm[key] = normalizeForInput(key, currentRecord[key]);
        }
        nextForm.added_by = addedByDisplayName;
        nextForm.data_added = todayIso();
        form = nextForm;
    }

    async function fetchFirst() {
        loading = true;
        error = "";
        try {
            const res = await fetchApi("/cvi/record/first");
            if (!res.ok) {
                throw new Error(`Failed to load first CVI row (${res.status})`);
            }
            const payload = (await res.json()) as CVIResponse;
            loadIntoForm(payload);
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to load CVI row";
        } finally {
            loading = false;
        }
    }

    async function loadPdfIndex() {
        pdfIndexLoading = true;
        try {
            const res = await fetchApi("/cvi/records/pdf-index");
            if (!res.ok) {
                throw new Error(`Failed to load PDF list (${res.status})`);
            }
            const payload = (await res.json()) as CVIPdfIndexItem[];
            pdfIndexItems = Array.isArray(payload) ? payload : [];
        } catch {
            // Keep page functional even if the index endpoint is unavailable.
            pdfIndexItems = [];
        } finally {
            pdfIndexLoading = false;
        }
    }

    async function jumpToRecord(targetId: string | number) {
        loading = true;
        error = "";
        message = "";
        try {
            const res = await fetchApi(`/cvi/record/${targetId}`);
            if (!res.ok) {
                throw new Error(`Failed to load row (${res.status})`);
            }
            const payload = (await res.json()) as CVIResponse;
            loadIntoForm(payload);
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to open CVI row";
        } finally {
            loading = false;
        }
    }

    async function searchByFormId() {
        const query = formIdSearch.trim();
        if (!query) {
            message = "Enter a Form ID.";
            return;
        }

        loading = true;
        error = "";
        message = "";
        try {
            const res = await fetchApi(`/cvi/record/by-form-id/${encodeURIComponent(query)}`);
            if (!res.ok) {
                if (res.status === 404) {
                    message = `Form ID ${query} not found.`;
                    return;
                }
                throw new Error(`Failed to search Form ID (${res.status})`);
            }
            const payload = (await res.json()) as CVIResponse;
            loadIntoForm(payload);
            message = `Opened Form ID ${query}`;
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to search by Form ID";
        } finally {
            loading = false;
        }
    }

    function buildPatchPayload(
        forceAssignAddedByForNext = false,
        onlyKeys?: Set<string>,
    ): Record<string, any> {
        const patch: Record<string, any> = {};
        const currentUser = globalContext.userManager.user;

        for (const key of fieldOrder) {
            if (onlyKeys && !onlyKeys.has(key)) {
                continue;
            }
            if (key === "added_by") {
                continue;
            }
            if (key === "form_ID" || key === "folder_number") {
                continue;
            }
            if (key === "data_added") {
                continue;
            }
            const raw = (form[key] ?? "").trim();
            const original = currentRecord[key];
            const originalInputValue = normalizeForInput(key, original).trim();

            // Avoid patching unchanged values that only differ in serialization
            // (for example DATETIME vs YYYY-MM-DD input format).
            if (raw === originalInputValue) {
                continue;
            }

            if (intFields.has(key)) {
                if (raw === "") {
                    if (original !== null) {
                        patch[key] = null;
                    }
                } else {
                    const n = Number(raw);
                    if (!Number.isFinite(n)) {
                        continue;
                    }
                    const nextValue = Math.trunc(n);
                    const currentValue = original == null ? null : Number(original);
                    if (currentValue !== nextValue) {
                        patch[key] = nextValue;
                    }
                }
            } else {
                patch[key] = raw === "" ? null : raw;
            }

            if ((original ?? null) === (patch[key] ?? null)) {
                delete patch[key];
            }
        }

        if (forceAssignAddedByForNext) {
            const current = (currentRecord.added_by ?? "").toString().trim();
            if (!current && currentUser.id > 0) {
                patch.added_by = currentUser.id;
            }
        }

        return patch;
    }

    async function save(forceAssignAddedByForNext = false, onlyKeys?: Set<string>): Promise<boolean> {
        if (recordId == null) return false;

        error = "";
        message = "";

        const values = buildPatchPayload(forceAssignAddedByForNext, onlyKeys);
        if (Object.keys(values).length === 0) {
            return true;
        }

        saving = true;
        try {
            const res = await fetchApi(`/cvi/record/${recordId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ values }),
            });
            if (!res.ok) {
                throw new Error(`Save failed (${res.status})`);
            }
            const payload = (await res.json()) as CVIResponse;
            loadIntoForm(payload);
            message = "Saved";
            return true;
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to save";
            return false;
        } finally {
            saving = false;
        }
    }

    async function nextRecord() {
        if (recordId == null) return;

        loading = true;
        error = "";
        message = "";
        try {
            const res = await fetchApi(`/cvi/record/${recordId}/next`);
            if (!res.ok) {
                throw new Error(`Failed to load next row (${res.status})`);
            }
            const payload = (await res.json()) as { next: CVIResponse | null };
            if (!payload.next) {
                message = "No next record.";
                return;
            }
            loadIntoForm(payload.next);
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to load next row";
        } finally {
            loading = false;
        }
    }

    async function previousRecord() {
        if (recordId == null) return;

        loading = true;
        error = "";
        message = "";
        try {
            const res = await fetchApi(`/cvi/record/${recordId}/previous`);
            if (!res.ok) {
                throw new Error(`Failed to load previous row (${res.status})`);
            }
            const payload = (await res.json()) as { previous: CVIResponse | null };
            if (!payload.previous) {
                message = "No previous record.";
                return;
            }
            loadIntoForm(payload.previous);
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to load previous row";
        } finally {
            loading = false;
        }
    }

    function isWorkflowStatusSelected(status: string): boolean {
        return workflowStatus.trim().toLowerCase() === status.trim().toLowerCase();
    }

    function startResize(event: PointerEvent) {
        isDraggingDivider = true;
        dragStartX = event.clientX;
        dragStartLeftWidth = leftPanelWidth;
        event.preventDefault();

        const handleMove = (moveEvent: PointerEvent) => {
            if (!isDraggingDivider || !cviPageEl) return;
            const bounds = cviPageEl.getBoundingClientRect();
            const delta = moveEvent.clientX - dragStartX;
            const nextPercent = ((dragStartLeftWidth / 100) * bounds.width + delta) / bounds.width * 100;
            leftPanelWidth = Math.min(75, Math.max(30, nextPercent));
        };

        const handleUp = () => {
            isDraggingDivider = false;
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
        };

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp, { once: true });
    }

    function handleDividerKeydown(event: KeyboardEvent) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        leftPanelWidth = Math.max(30, Math.min(75, leftPanelWidth + (event.key === "ArrowLeft" ? -2 : 2)));
    }

    async function setStatus(status: "Not Started" | "Busy" | "Ready") {
        if (status === "Busy" || status === "Ready") {
            const ok = await save(false);
            if (!ok) return;
        }

        error = "";
        message = "";
        saving = true;
        try {
            const res = await fetchApi(`/cvi/record/${recordId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ values: { status } }),
            });
            if (!res.ok) {
                throw new Error(`Save failed (${res.status})`);
            }
            const payload = (await res.json()) as CVIResponse;
            loadIntoForm(payload);
            message = "Saved";
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to save";
        } finally {
            saving = false;
        }
    }

    loadLookupOptions();
    loadPdfIndex();
    fetchFirst();
</script>

<svelte:head>
    <title>CVI</title>
</svelte:head>

<Main>
    {#snippet children()}
        <div class="cvi-page" bind:this={cviPageEl} style={`--left-panel-width: ${leftPanelWidth}%`}>
            <div class="left-panel">
                {#if loading}
                    <p>Loading...</p>
                {:else if error}
                    <p class="error">{error}</p>
                {:else}
                    <div class="status-row">
                        <p class="status-label">{workflowStatus || "-"}</p>
                    </div>
                    <div class="form-grid">
                        {#each fieldOrder as key}
                            <label class="field" for={key}>
                                <span>{labels[key] ?? key}</span>
                                {#if key === "added_by"}
                                    <input id={key} type="text" bind:value={form[key]} disabled />
                                {:else if key === "data_added"}
                                    <input id={key} type="date" bind:value={form[key]} disabled />
                                {:else if key === "gender"}
                                    <select id={key} bind:value={form[key]}>
                                        <option value="">-</option>
                                        <option value="Unknown">Unknown</option>
                                        <option value="Male">Male</option>
                                        <option value="Female">Female</option>
                                    </select>
                                {:else if key === "data_access_group"}
                                    <select id={key} bind:value={form[key]}>
                                        {#each dataAccessGroupOptions as option}
                                            <option value={option}>{option}</option>
                                        {/each}
                                    </select>
                                {:else if key === "signatory_is"}
                                    <select id={key} bind:value={form[key]}>
                                        {#each signatoryIsOptions as option}
                                            <option value={option}>{option || "-"}</option>
                                        {/each}
                                    </select>
                                {:else if dateFields.has(key)}
                                    <input id={key} type="date" bind:value={form[key]} disabled={readonlyFields.has(key)} />
                                {:else if key === "potential_duplicate_warning"}
                                    <textarea id={key} rows="2" bind:value={form[key]} disabled={readonlyFields.has(key)} />
                                {:else}
                                    {#if optionsForKey(key).length > 0}
                                        <div class="searchable-dropdown" onfocusin={() => openDropdown(key)} onfocusout={() => closeDropdown(key)}>
                                            <input
                                                id={key}
                                                type="text"
                                                bind:value={form[key]}
                                                disabled={readonlyFields.has(key)}
                                                onclick={() => openDropdown(key)}
                                                oninput={(event) => handleDropdownInput(key, event.currentTarget.value)}
                                                autocomplete="off"
                                            />
                                            {#if openDropdownKey === key && !readonlyFields.has(key)}
                                                <div class="dropdown-menu" role="listbox">
                                                    {#each filteredOptionsForKey(key) as option}
                                                        <button
                                                            type="button"
                                                            class="dropdown-option"
                                                            onmousedown={(event) => {
                                                                event.preventDefault();
                                                                pickDropdownOption(key, option);
                                                            }}
                                                        >
                                                            {option || "(empty)"}
                                                        </button>
                                                    {:else}
                                                        <div class="dropdown-empty">No matches</div>
                                                    {/each}
                                                </div>
                                            {/if}
                                        </div>
                                    {:else}
                                        <input
                                            id={key}
                                            type="text"
                                            bind:value={form[key]}
                                            disabled={readonlyFields.has(key)}
                                        />
                                    {/if}
                                {/if}
                            </label>
                        {/each}
                    </div>
                    <div class="footer-actions">
                        <button class="action-btn" onclick={previousRecord} disabled={saving || loading}>
                            <ArrowLeft size={16} />
                            Back
                        </button>
                        <button class="action-btn" class:active={isWorkflowStatusSelected("Not Started")} onclick={() => setStatus("Not Started")} disabled={saving || loading}>
                            <Circle size={16} />
                            Not Started
                        </button>
                        <button class="action-btn" class:active={isWorkflowStatusSelected("Busy")} onclick={() => setStatus("Busy")} disabled={saving || loading}>
                            <LoaderCircle size={16} />
                            Busy
                        </button>
                        <button class="action-btn" class:active={isWorkflowStatusSelected("Ready")} onclick={() => setStatus("Ready")} disabled={saving || loading}>
                            <CheckCircle2 size={16} />
                            Ready
                        </button>
                        <button class="action-btn" onclick={nextRecord} disabled={saving || loading}>
                            <ArrowRight size={16} />
                            Next
                        </button>
                        <div class="form-id-search">
                            <label for="form-id-search">Form ID</label>
                            <input
                                id="form-id-search"
                                type="text"
                                bind:value={formIdSearch}
                                placeholder="Find form"
                                onkeydown={(event) => {
                                    if (event.key === "Enter") {
                                        searchByFormId();
                                    }
                                }}
                            />
                            <button class="action-btn" type="button" onclick={searchByFormId} disabled={saving || loading}>
                                Search
                            </button>
                        </div>
                    </div>
                {/if}
            </div>

            <div class="divider" aria-label="Resize CVI panels" title="Drag to resize panels" role="separator" tabindex="0" onpointerdown={startResize} onkeydown={handleDividerKeydown}></div>
            <div class="right-panel">
                <div class="pdf-top">
                    <div class="pdf-title-line">
                        <span class="pdf-title-label">Current PDF</span>
                        <strong class="pdf-title-name">{currentPdfName() || "-"}</strong>
                    </div>
                    <div class="pdf-jump-list" aria-label="PDF jump list">
                        {#if pdfIndexLoading}
                            <span class="pdf-jump-loading">Loading PDF list...</span>
                        {:else if pdfIndexItems.length === 0}
                            <span class="pdf-jump-loading">No PDF names available.</span>
                        {:else}
                            {#each pdfIndexItems as item}
                                {@const status = normalizeCviStatus(item.status)}
                                <button
                                    type="button"
                                    class="pdf-jump-btn"
                                    class:active={String(item.id) === String(recordId)}
                                    onclick={() => jumpToRecord(item.id)}
                                >
                                    <span class="pdf-jump-label">{pdfLabel(item)}</span>
                                    <span class="pdf-status" class:ready={status === "Ready"} class:busy={status === "Busy"} class:not-started={status === "Not Started"}>
                                        <svelte:component this={statusIconFor(status)} size={14} />
                                        <span>{status}</span>
                                    </span>
                                </button>
                            {/each}
                        {/if}
                    </div>
                </div>
                {#if pdfUrl}
                    <iframe src={pdfUrl + "?v=" + recordId} title="CVI PDF" class="pdf-view"></iframe>
                    <p class="pdf-fallback">
                        If the PDF does not render inline,
                        <a href={pdfUrl} target="_blank" rel="noreferrer">open it in a new tab</a>.
                    </p>
                {:else}
                    <p>No PDF file linked for this record.</p>
                {/if}
            </div>
        </div>
    {/snippet}
</Main>

<style>
    .cvi-page {
        display: grid;
        grid-template-columns: minmax(320px, var(--left-panel-width)) 10px minmax(360px, 1fr);
        gap: 0;
        padding: 16px;
        min-height: calc(100vh - 56px);
        box-sizing: border-box;
        align-items: stretch;
    }

    .left-panel,
    .right-panel {
        border: 1px solid #d9d9d9;
        border-radius: 8px;
        background: #fff;
        padding: 12px;
    }

    .left-panel {
        display: grid;
        grid-template-rows: minmax(0, 1fr) auto;
        min-height: 0;
    }

    .right-panel {
        min-width: 0;
    }

    .divider {
        position: relative;
        width: 10px;
        cursor: col-resize;
        user-select: none;
        background: transparent;
    }

    .divider::before {
        content: "";
        position: absolute;
        left: 50%;
        top: 0;
        bottom: 0;
        width: 2px;
        transform: translateX(-50%);
        background: #d9d9d9;
    }

    .form-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        min-height: 0;
        max-height: calc(100vh - 225px);
        overflow-y: auto;
        padding-right: 6px;
    }

    .field {
        display: grid;
        gap: 4px;
    }

    .field span {
        font-size: 12px;
        color: #333;
    }

    .searchable-dropdown {
        position: relative;
        width: 100%;
    }

    .searchable-dropdown input {
        width: 100%;
        box-sizing: border-box;
    }

    .dropdown-menu {
        position: absolute;
        z-index: 30;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        width: 100%;
        box-sizing: border-box;
        max-height: 220px;
        overflow-y: auto;
        border: 1px solid #cfcfcf;
        border-radius: 6px;
        background: #fff;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    }

    .dropdown-option {
        width: 100%;
        box-sizing: border-box;
        text-align: left;
        border: 0;
        background: #fff;
        padding: 8px;
        font-size: 13px;
        cursor: pointer;
    }

    .dropdown-option:hover {
        background: #f3f4f6;
    }

    .dropdown-empty {
        padding: 8px;
        font-size: 12px;
        color: #666;
    }

    input,
    select,
    textarea {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #cfcfcf;
        border-radius: 6px;
        padding: 8px;
        font-size: 13px;
    }

    .status-row {
        display: flex;
        align-items: center;
        height: 18px;
        min-height: 18px;
        max-height: 18px;
        margin: 0 0 4px;
        padding: 0;
        box-sizing: border-box;
    }

    .footer-actions {
        margin-top: 8px;
        padding-top: 6px;
        display: flex;
        flex-wrap: nowrap;
        gap: 6px;
        justify-content: flex-start;
        align-items: center;
        align-content: flex-start;
        height: 56px;
        min-height: 56px;
        max-height: 56px;
        flex: 0 0 auto;
        overflow-x: auto;
        border-top: 1px solid #efefef;
    }

    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid #c8c8c8;
        background: #fff;
        color: #111;
        border-radius: 6px;
        padding: 5px 8px;
        cursor: pointer;
        font-size: 11px;
        line-height: 1;
    }

    .action-btn.active {
        background: #111;
        color: #fff;
        border-color: #111;
    }

    .status-label {
        margin: 0;
        padding: 0;
        font-size: 11px;
        font-weight: 600;
        color: #111;
        line-height: 1;
        height: 18px;
        min-height: 18px;
        max-height: 18px;
        display: flex;
        align-items: center;
    }

    .action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .error {
        color: #b42318;
    }

    .message {
        color: #0f766e;
    }

    .right-panel {
        display: grid;
        grid-template-rows: auto 1fr auto;
        gap: 8px;
    }

    .pdf-top {
        display: grid;
        gap: 6px;
        border: 1px solid #ececec;
        border-radius: 6px;
        padding: 8px;
        background: #fafafa;
    }

    .pdf-title-line {
        display: flex;
        gap: 8px;
        align-items: baseline;
        flex-wrap: wrap;
    }

    .pdf-title-label {
        font-size: 11px;
        text-transform: uppercase;
        color: #555;
        letter-spacing: 0.02em;
    }

    .pdf-title-name {
        font-size: 13px;
        color: #111;
        word-break: break-word;
    }

    .pdf-jump-list {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        padding-bottom: 2px;
    }

    .pdf-jump-loading {
        font-size: 12px;
        color: #666;
    }

    .pdf-jump-btn {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
        width: 100%;
        text-align: left;
        border: 1px solid #d3d3d3;
        background: #fff;
        color: #222;
        border-radius: 10px;
        font-size: 11px;
        padding: 7px 10px;
        white-space: nowrap;
        cursor: pointer;
    }

    .pdf-jump-label {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .pdf-status {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.2rem 0.5rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        border: 1px solid transparent;
    }

    .pdf-status.ready {
        color: #166534;
        background: #dcfce7;
        border-color: #86efac;
    }

    .pdf-status.busy {
        color: #92400e;
        background: #fef3c7;
        border-color: #fcd34d;
    }

    .pdf-status.not-started {
        color: #374151;
        background: #f3f4f6;
        border-color: #d1d5db;
    }

    .pdf-jump-btn.active {
        border-color: #111;
        background: #111;
        color: #fff;
    }

    .form-id-search {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-left: auto;
        padding-left: 6px;
        border-left: 1px solid #ececec;
    }

    .form-id-search label {
        font-size: 11px;
        color: #444;
        white-space: nowrap;
    }

    .form-id-search input {
        width: 120px;
        padding: 5px 7px;
        font-size: 11px;
    }

    .pdf-view {
        width: 100%;
        height: calc(100vh - 130px);
        border: 1px solid #ddd;
        border-radius: 6px;
    }

    .pdf-fallback {
        margin: 2px 0 0;
        font-size: 12px;
        color: #555;
    }

    @media (max-width: 1100px) {
        .cvi-page {
            grid-template-columns: 1fr;
        }

        .divider {
            display: none;
        }

        .footer-actions {
            flex-wrap: wrap;
            overflow-x: visible;
            height: auto;
            min-height: 56px;
            max-height: none;
        }

        .form-id-search {
            margin-left: 0;
            border-left: 0;
            padding-left: 0;
        }

        .pdf-view {
            height: 65vh;
        }
    }
</style>
