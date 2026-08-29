<script lang="ts">
  import {
    ArrowLeft,
    ArrowRight,
    Check,
    FileSpreadsheet,
    Files,
    FlaskConical,
    Info,
    ShieldCheck,
    Sparkles,
    UploadCloud,
    X,
    Zap,
  } from "lucide-svelte";
  import { formatBytes } from "../lib/demo";
  import type { Budget, NewRunInput } from "../lib/types";

  export let onback: () => void;
  export let onlaunch: (input: NewRunInput) => void | Promise<void>;

  let files: File[] = [];
  let title = "";
  let metadata = "";
  let budget: Budget = "standard";
  let dragging = false;
  let launching = false;
  let launchError = "";
  let fileInput: HTMLInputElement;

  const supportedExtensions = ["csv", "tsv", "parquet", "xlsx", "xls"];

  function addFiles(incoming: File[]) {
    const accepted = incoming.filter((file) => supportedExtensions.includes(file.name.split(".").pop()?.toLowerCase() ?? ""));
    const known = new Set(files.map((file) => `${file.name}:${file.size}`));
    files = [...files, ...accepted.filter((file) => !known.has(`${file.name}:${file.size}`))];
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragging = false;
    addFiles(Array.from(event.dataTransfer?.files ?? []));
  }

  function handleInput(event: Event) {
    addFiles(Array.from((event.currentTarget as HTMLInputElement).files ?? []));
  }

  function removeFile(index: number) {
    files = files.filter((_, position) => position !== index);
  }

  async function launch() {
    if (!files.length) return;
    launching = true;
    launchError = "";
    try {
      await onlaunch({ files, title, metadata, budget });
    } catch (error) {
      launchError = error instanceof Error ? error.message : "The discovery could not be launched.";
    } finally {
      launching = false;
    }
  }
</script>

<section class="page new-page">
  <header class="new-page-header">
    <button type="button" class="back-button" onclick={onback}><ArrowLeft size={17} /> Overview</button>
    <div class="eyebrow"><span class="eyebrow-dot"></span> NEW DISCOVERY</div>
    <h1>What should we investigate?</h1>
    <p>Upload a dataset and enough context to help Urithiru form useful, falsifiable hypotheses.</p>
  </header>

  <form class="discovery-form" onsubmit={(event) => { event.preventDefault(); launch(); }}>
    <section class="form-section">
      <div class="form-section-number">01</div>
      <div class="form-section-body">
        <div class="form-heading">
          <div><h2>Dataset</h2><p>One dataset can include multiple related files.</p></div>
          <span class="required-label">Required</span>
        </div>

        <button
          type="button"
          class:dragging
          class:has-files={files.length > 0}
          class="upload-dropzone"
          onclick={() => fileInput.click()}
          ondragover={(event) => { event.preventDefault(); dragging = true; }}
          ondragleave={() => dragging = false}
          ondrop={handleDrop}
        >
          <input
            bind:this={fileInput}
            type="file"
            multiple
            accept=".csv,.tsv,.parquet,.xlsx,.xls"
            onchange={handleInput}
          />
          <span class="upload-icon"><UploadCloud size={25} strokeWidth={1.6} /></span>
          <strong>Drop your dataset here</strong>
          <span>or <u>choose files</u> from your computer</span>
          <small>CSV, TSV, Parquet, or Excel · up to 100 MB</small>
        </button>

        {#if files.length}
          <div class="uploaded-files">
            {#each files as file, index}
              <div class="uploaded-file">
                <span class="file-type-icon"><FileSpreadsheet size={18} strokeWidth={1.8} /></span>
                <span class="file-copy"><strong>{file.name}</strong><small>{formatBytes(file.size)} · Ready to upload</small></span>
                <span class="file-ready"><Check size={13} strokeWidth={2.4} /> Ready</span>
                <button type="button" aria-label={`Remove ${file.name}`} onclick={() => removeFile(index)}><X size={16} /></button>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </section>

    <section class="form-section">
      <div class="form-section-number">02</div>
      <div class="form-section-body">
        <div class="form-heading">
          <div><h2>Research context</h2><p>Help the agents interpret columns and avoid invalid assumptions.</p></div>
          <span class="optional-label">Recommended</span>
        </div>

        <label class="field-label" for="run-title">Discovery name <span>Optional</span></label>
        <input id="run-title" class="text-field" bind:value={title} placeholder="e.g. Urban particulate signatures" maxlength="80" />

        <label class="field-label metadata-label" for="metadata">About this dataset <span>Optional</span></label>
        <textarea
          id="metadata"
          class="text-area"
          bind:value={metadata}
          placeholder="Describe what was measured, the population or system, units, collection period, known caveats, and any questions you care about…"
          rows="6"
        ></textarea>
        <div class="field-hint"><Info size={13} /> Metadata guides exploration but does not prescribe the conclusion.</div>
      </div>
    </section>

    <section class="form-section">
      <div class="form-section-number">03</div>
      <div class="form-section-body">
        <div class="form-heading">
          <div><h2>Discovery budget</h2><p>Choose how widely the MCTS engine should explore.</p></div>
        </div>

        <div class="budget-grid">
          <label class:checked={budget === "fast"} class="budget-option">
            <input type="radio" bind:group={budget} value="fast" />
            <span class="budget-radio"><span></span></span>
            <span class="budget-icon fast"><Zap size={18} strokeWidth={1.8} /></span>
            <span class="budget-copy"><strong>Fast</strong><small>3 tested hypotheses</small></span>
            <span class="budget-time">~8 min</span>
          </label>
          <label class:checked={budget === "standard"} class="budget-option recommended">
            <span class="recommended-tag">Recommended</span>
            <input type="radio" bind:group={budget} value="standard" />
            <span class="budget-radio"><span></span></span>
            <span class="budget-icon standard"><FlaskConical size={18} strokeWidth={1.8} /></span>
            <span class="budget-copy"><strong>Standard</strong><small>6 tested hypotheses</small></span>
            <span class="budget-time">~20 min</span>
          </label>
          <label class:checked={budget === "deep"} class="budget-option">
            <input type="radio" bind:group={budget} value="deep" />
            <span class="budget-radio"><span></span></span>
            <span class="budget-icon deep"><Files size={18} strokeWidth={1.8} /></span>
            <span class="budget-copy"><strong>Deep</strong><small>12 tested hypotheses</small></span>
            <span class="budget-time">~45 min</span>
          </label>
        </div>

        <div class="isolation-note">
          <ShieldCheck size={18} strokeWidth={1.7} />
          <div><strong>Isolated experiment execution</strong><span>Every hypothesis runs in a fresh, ephemeral sandbox with scoped access to this dataset.</span></div>
        </div>
      </div>
    </section>

    {#if launchError}<div class="launch-error" role="alert">{launchError}</div>{/if}
    <div class="launch-bar">
      <div>
        <Sparkles size={17} />
        <span><strong>Ready when you are.</strong> You can close this page after launch.</span>
      </div>
      <button class="primary-button launch-button" type="submit" disabled={!files.length || launching}>
        {launching ? "Launching discovery…" : "Run autonomous discovery"} {#if !launching}<ArrowRight size={17} />{/if}
      </button>
    </div>
  </form>
</section>
