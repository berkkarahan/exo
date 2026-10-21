<script lang="ts">
  interface HuggingFaceModel {
    id: string;
    author: string;
    downloads: number;
    likes: number;
    last_modified: string;
    tags: string[];
    has_gguf?: boolean;
  }

  interface GgufFile {
    filename: string;
    size_bytes: number;
    quantization: string;
    is_split: boolean;
  }

  type HuggingFaceResultItemProps = {
    model: HuggingFaceModel;
    isAdded: boolean;
    isAdding: boolean;
    onAdd: () => void;
    onAddFile?: (filename: string) => void;
    onSelect: () => void;
    downloadedOnNodes?: string[];
  };

  let {
    model,
    isAdded,
    isAdding,
    onAdd,
    onAddFile,
    onSelect,
    downloadedOnNodes = [],
  }: HuggingFaceResultItemProps = $props();

  let showFiles = $state(false);
  let files = $state<GgufFile[]>([]);
  let loadingFiles = $state(false);
  let filesError = $state<string | null>(null);
  let addingFile = $state<string | null>(null);

  function formatNumber(num: number | undefined): string {
    if (num == null) return "0";
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`;
    } else if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  }

  function formatBytes(bytes: number): string {
    if (!bytes) return "";
    if (bytes >= 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  }

  async function toggleFiles() {
    showFiles = !showFiles;
    if (showFiles && files.length === 0 && !loadingFiles) {
      loadingFiles = true;
      filesError = null;
      try {
        const response = await fetch(
          `/models/huggingface/files?model_id=${encodeURIComponent(model.id)}`
        );
        if (response.ok) {
          files = await response.json();
        } else {
          filesError = "Failed to list GGUF files";
        }
      } catch (err) {
        filesError = err instanceof Error ? err.message : "Error fetching files";
      } finally {
        loadingFiles = false;
      }
    }
  }

  const modelName = $derived(model.id);
  const isGgufModel = $derived(
    model.has_gguf ||
    model.tags?.includes("gguf") ||
    model.id.toLowerCase().includes("gguf")
  );
</script>

<div class="border-b border-white/5 last:border-b-0">
  <div
    class="flex items-center justify-between gap-3 px-3 py-2.5 hover:bg-white/5 transition-colors"
  >
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="text-sm font-mono text-white truncate" title={model.id}
          >{modelName}</span
        >
        {#if downloadedOnNodes.length > 0}
          <span
            class="flex-shrink-0"
            title={`Downloaded on ${downloadedOnNodes.join(", ")}`}
          >
            <svg
              class="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                class="text-white/40"
                d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"
              />
              <path class="text-green-400" d="m9 13 2 2 4-4" />
            </svg>
          </span>
        {/if}
        {#if isGgufModel}
          <span
            class="px-1.5 py-0.5 text-[10px] font-mono bg-yellow-500/20 text-yellow-400 rounded"
            >GGUF</span
          >
        {/if}
        {#if isAdded}
          <span
            class="px-1.5 py-0.5 text-[10px] font-mono bg-green-500/20 text-green-400 rounded"
            >Added</span
          >
        {/if}
      </div>
      <div class="flex items-center gap-3 mt-0.5 text-xs text-white/40">
        <span class="truncate">{model.author}</span>
        <span
          class="flex items-center gap-1 shrink-0"
          title="Downloads in the last 30 days"
        >
          <svg
            class="w-3 h-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          {formatNumber(model.downloads)}
        </span>
        <span
          class="flex items-center gap-1 shrink-0"
          title="Community likes on Hugging Face"
        >
          <svg
            class="w-3 h-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
            />
          </svg>
          {formatNumber(model.likes)}
        </span>
      </div>
    </div>

    <div class="flex items-center gap-2 shrink-0">
      {#if !isAdded}
        <button
          type="button"
          onclick={toggleFiles}
          title="View GGUF files in this repo"
          class="px-2 py-1.5 text-xs font-mono text-white/50 hover:text-white/80 hover:bg-white/5 border border-white/10 rounded transition-colors cursor-pointer"
        >
          {showFiles ? "Hide Files" : "Files"}
        </button>
      {/if}
      {#if isAdded}
        <button
          type="button"
          onclick={onSelect}
          class="px-3 py-1.5 text-xs font-mono tracking-wider uppercase bg-wEXO-yellow/10 text-wEXO-yellow border border-wEXO-yellow/30 hover:bg-wEXO-yellow/20 transition-colors rounded cursor-pointer"
        >
          Select
        </button>
      {:else}
        <button
          type="button"
          onclick={onAdd}
          disabled={isAdding}
          class="px-3 py-1.5 text-xs font-mono tracking-wider uppercase bg-orange-500/10 text-orange-400 border border-orange-400/30 hover:bg-orange-500/20 transition-colors rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if isAdding}
            <span class="flex items-center gap-1.5">
              <span
                class="w-3 h-3 border-2 border-orange-400 border-t-transparent rounded-full animate-spin"
              ></span>
              Adding...
            </span>
          {:else}
            + Add
          {/if}
        </button>
      {/if}
    </div>
  </div>

  {#if showFiles}
    <div class="bg-black/30 border-t border-white/5 px-4 py-2.5 text-xs font-mono">
      {#if loadingFiles}
        <div class="flex items-center gap-2 text-white/40 py-2">
          <span
            class="w-3 h-3 border-2 border-orange-400 border-t-transparent rounded-full animate-spin"
          ></span>
          Scanning repository for GGUF files...
        </div>
      {:else if filesError}
        <p class="text-red-400/80 py-1">{filesError}</p>
      {:else if files.length === 0}
        <p class="text-white/40 py-1">No GGUF files found in this repository.</p>
      {:else}
        <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
          {#each files as f}
            <div
              class="flex items-center justify-between gap-2 py-1 border-b border-white/5 last:border-b-0"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="truncate text-white/80" title={f.filename}>{f.filename}</span>
                {#if f.quantization}
                  <span class="px-1.5 py-0.5 bg-white/10 text-white/70 rounded text-[10px]"
                    >{f.quantization}</span
                  >
                {/if}
                {#if f.is_split}
                  <span
                    class="px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded text-[10px]"
                    >split</span
                  >
                {/if}
                <span class="text-white/40 text-[11px]">{formatBytes(f.size_bytes)}</span>
              </div>
              {#if onAddFile}
                <button
                  type="button"
                  disabled={addingFile === f.filename || isAdding}
                  onclick={async () => {
                    addingFile = f.filename;
                    try {
                      await onAddFile?.(f.filename);
                    } finally {
                      addingFile = null;
                    }
                  }}
                  class="px-2 py-0.5 text-[11px] font-mono uppercase bg-orange-500/10 text-orange-400 border border-orange-400/30 hover:bg-orange-500/20 transition-colors rounded cursor-pointer disabled:opacity-50"
                >
                  {addingFile === f.filename ? "Adding..." : "+ Download"}
                </button>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
