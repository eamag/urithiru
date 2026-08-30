<script lang="ts">
  import type { LaunchInput, StageMinutes } from "../lib/types";

  let { onback, onlaunch }: { onback: () => void; onlaunch: (input: LaunchInput) => Promise<void> } = $props();
  let data = $state<File[]>([]);
  let metadataFiles = $state<File[]>([]);
  let title = $state("");
  let metadata = $state("");
  let steps = $state(3);
  let seed = $state(42);
  let limits = $state(false);
  let minutes = $state<StageMinutes>({});
  let dragging = $state(false);
  let launching = $state(false);
  let error = $state("");
  let dataInput: HTMLInputElement;
  let metadataInput: HTMLInputElement;

  const allowed = new Set(["csv", "tsv", "parquet", "xlsx", "xls"]);
  const STAGES: { key: keyof StageMinutes; label: string }[] = [
    { key: "proposal", label: "Proposal" },
    { key: "search", label: "Literature" },
    { key: "code", label: "Experiment" },
    { key: "external", label: "External" },
  ];
  let bytes = $derived([...data, ...metadataFiles].reduce((total, file) => total + file.size, 0));

  function formatBytes(value: number): string {
    if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KiB`;
    return `${(value / 1024 / 1024).toFixed(2)} MiB`;
  }

  function addData(files: File[]) {
    const known = new Set(data.map((file) => `${file.name}:${file.size}`));
    data = [...data, ...files.filter((file) => allowed.has(file.name.split(".").at(-1)?.toLowerCase() ?? "") && !known.has(`${file.name}:${file.size}`))];
  }

  function addMetadata(files: File[]) {
    const known = new Set(metadataFiles.map((file) => `${file.name}:${file.size}`));
    metadataFiles = [...metadataFiles, ...files.filter((file) => !known.has(`${file.name}:${file.size}`))];
  }

  async function submit() {
    if (!data.length || bytes > 100 * 1024 * 1024) return;
    launching = true;
    error = "";
    try {
      await onlaunch({ data, metadataFiles, title, metadata, steps, seed, minutes });
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      launching = false;
    }
  }
</script>

<section class="launch-page">
  <header>
    <button type="button" class="back" onclick={onback}>← All runs</button>
    <p class="eyebrow">NEW DISCOVERY</p>
    <h1>Launch a real run</h1>
    <p class="intro">Upload related tables and context. The operator stages them, starts the configured runtime, and keeps publishing progress here.</p>
  </header>

  <form onsubmit={(event) => { event.preventDefault(); void submit(); }}>
    <section class="form-section">
      <div class="number">01</div>
      <div>
        <div class="section-heading"><span><h2>Data files</h2><p>CSV, TSV, Parquet, XLSX, or XLS. Related tables stay separate.</p></span><b>required</b></div>
        <button
          class:dragging
          class="dropzone"
          type="button"
          onclick={() => dataInput.click()}
          ondragover={(event) => { event.preventDefault(); dragging = true; }}
          ondragleave={() => dragging = false}
          ondrop={(event) => { event.preventDefault(); dragging = false; addData(Array.from(event.dataTransfer?.files ?? [])); }}
        >
          <input bind:this={dataInput} type="file" multiple accept=".csv,.tsv,.parquet,.xlsx,.xls" onchange={(event) => addData(Array.from(event.currentTarget.files ?? []))} />
          <span class="plus">+</span><strong>Choose files or drop them here</strong><small>Complete upload limit: 100 MiB</small>
        </button>
        {#if data.length}
          <ul class="files">
            {#each data as file, index}
              <li><span><b>{file.name}</b><small>{formatBytes(file.size)}</small></span><button type="button" aria-label={`Remove ${file.name}`} onclick={() => data = data.filter((_, position) => position !== index)}>×</button></li>
            {/each}
          </ul>
          <p class:error={bytes > 100 * 1024 * 1024} class="total">{data.length} data file{data.length === 1 ? "" : "s"} · {formatBytes(bytes)} total</p>
        {/if}
      </div>
    </section>

    <section class="form-section">
      <div class="number">02</div>
      <div>
        <div class="section-heading"><span><h2>Context</h2><p>Describe table grain, units, population, caveats, and valid claim strength.</p></span><b class="optional">recommended</b></div>
        <label>Discovery name <input bind:value={title} placeholder="NHANES 2021-2023 cardiometabolic signals" maxlength="100" /></label>
        <label>Notes <textarea bind:value={metadata} rows="6" placeholder="What do these files measure? Which joins are valid? What must not be interpreted causally?"></textarea></label>
        <button type="button" class="metadata-button" onclick={() => metadataInput.click()}>Attach dictionaries or metadata files</button>
        <input class="hidden" bind:this={metadataInput} type="file" multiple accept=".txt,.md,.json,.csv" onchange={(event) => addMetadata(Array.from(event.currentTarget.files ?? []))} />
        {#if metadataFiles.length}<p class="metadata-list">{metadataFiles.map((file) => file.name).join(" · ")}</p>{/if}
      </div>
    </section>

    <section class="form-section">
      <div class="number">03</div>
      <div>
        <div class="section-heading"><span><h2>Search budget</h2><p>One step evaluates one hypothesis. Search and experiment run in parallel.</p></span></div>
        <div class="budget">
          <label>Hypotheses to evaluate
            <input bind:value={steps} type="number" min="1" max="12" step="1" />
            <small>1 to 12, evaluated in parallel batches.</small>
          </label>
          <label>Seed
            <input bind:value={seed} type="number" min="0" step="1" />
            <small>Seeds selection and every model call.</small>
          </label>
        </div>

        <button type="button" class="disclosure" onclick={() => (limits = !limits)}>
          {limits ? "Hide" : "Set"} stage time limits
        </button>
        {#if limits}
          <div class="minutes">
            {#each STAGES as stage}
              <label>{stage.label}
                <input bind:value={minutes[stage.key]} type="number" min="1" max="60" step="1" placeholder="profile" />
              </label>
            {/each}
          </div>
          <p class="operator-note">
            Minutes per stage, overriding the profile for this run only. Literature and experiment
            run at the same time, so a step costs proposal + max(literature, experiment) + external.
            Leave a field empty to keep the profile's value.
          </p>
        {/if}
        <p class="operator-note">Runs use the operator configuration on this machine. You can close the page after launch.</p>
      </div>
    </section>

    {#if error}<p class="launch-error" role="alert">{error}</p>{/if}
    <footer>
      <span>{data.length ? `${data.length} data file${data.length === 1 ? "" : "s"} ready` : "Choose data to continue"}</span>
      <button class="submit" type="submit" disabled={!data.length || launching || bytes > 100 * 1024 * 1024}>{launching ? "Uploading and launching…" : "Launch discovery →"}</button>
    </footer>
  </form>
</section>

<style>
  .launch-page { max-width: 900px; margin: 0 auto; padding: 44px 36px 100px; }
  header { margin-bottom: 38px; }
  .back { border: 0; padding: 0; color: var(--dim); background: transparent; cursor: pointer; }
  .eyebrow { margin: 34px 0 8px; color: var(--violet); font: 10px var(--mono); letter-spacing: .13em; }
  h1 { margin: 0; font-size: 30px; font-weight: 520; letter-spacing: -.03em; }
  .intro { max-width: 620px; margin: 10px 0 0; color: var(--dim); line-height: 1.65; }
  form { border-top: 1px solid var(--line); }
  .form-section { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 18px; padding: 30px 0; border-bottom: 1px solid var(--line); }
  .number { color: var(--faint); font: 11px var(--mono); }
  .section-heading { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
  .section-heading h2 { margin: 0; font-size: 16px; font-weight: 520; }
  .section-heading p { margin: 4px 0 0; color: var(--dim); font-size: 12px; }
  .section-heading > b { align-self: start; color: var(--violet); font: 9px var(--mono); text-transform: uppercase; }
  .section-heading > b.optional { color: var(--faint); }
  .dropzone { width: 100%; min-height: 132px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; border: 1px dashed var(--edge); border-radius: 7px; color: var(--dim); background: var(--panel); cursor: pointer; }
  .dropzone.dragging, .dropzone:hover { border-color: var(--violet); background: var(--accent-bg); }
  .dropzone input, .hidden { display: none; }
  .dropzone strong { color: var(--text); font-size: 13px; font-weight: 500; }
  .dropzone small { color: var(--faint); }
  .plus { color: var(--violet); font: 27px/1 var(--mono); }
  .files { list-style: none; margin: 10px 0 0; padding: 0; border-top: 1px solid var(--line); }
  .files li { min-height: 48px; display: flex; justify-content: space-between; align-items: center; padding: 7px 4px; border-bottom: 1px solid var(--line); }
  .files b { display: block; font: 11px var(--mono); }
  .files small { display: block; margin-top: 2px; color: var(--faint); font-size: 10px; }
  .files button { border: 0; color: var(--faint); background: transparent; font-size: 18px; cursor: pointer; }
  .total, .metadata-list { margin: 9px 0 0; color: var(--faint); font: 10px var(--mono); }
  .total.error { color: var(--red); }
  label { display: grid; gap: 6px; margin-top: 14px; color: var(--dim); font-size: 11px; }
  input, textarea { width: 100%; border: 1px solid var(--line); border-radius: 5px; padding: 9px 10px; color: var(--text); background: var(--bg); font: inherit; outline: 0; }
  input:focus, textarea:focus { border-color: var(--accent-line); }
  textarea { resize: vertical; line-height: 1.55; }
  .metadata-button { margin-top: 10px; border: 0; padding: 0; color: var(--violet); background: transparent; cursor: pointer; font: 11px var(--mono); }
  .budget { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
  .budget input, .minutes input { font-family: var(--mono); }
  .budget small, .minutes small { color: var(--faint); font-size: 10px; }
  .disclosure { margin-top: 16px; border: 0; padding: 0; color: var(--violet); background: transparent; cursor: pointer; font: 11px var(--mono); }
  .minutes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }
  .operator-note { margin: 16px 0 0; color: var(--faint); font-size: 11px; }
  .launch-error { padding: 10px 12px; border: 1px solid var(--danger-line); border-radius: 5px; color: var(--danger-text); background: var(--danger-bg); }
  footer { min-height: 76px; display: flex; justify-content: space-between; align-items: center; gap: 20px; }
  footer span { color: var(--dim); font-size: 11px; }
  .submit { min-width: 220px; height: 40px; border: 1px solid var(--accent-edge); border-radius: 5px; color: var(--accent-text); background: var(--accent-fill); cursor: pointer; }
  .submit:disabled { opacity: .4; cursor: default; }
  @media (max-width: 620px) { .launch-page { padding: 28px 20px 80px; } .form-section { grid-template-columns: 1fr; } .number { display: none; } .budget, .minutes { grid-template-columns: 1fr; } footer { align-items: stretch; flex-direction: column; padding-top: 18px; } .submit { width: 100%; } }
</style>
