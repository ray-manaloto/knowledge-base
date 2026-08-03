# Research: How peer tools distribute bulky pre-built derived data

Scope: mechanism-level facts, with citations, on how 10 tools/ecosystems ship
large DERIVED artifacts (vuln DBs, model weights, grammars, plugin data) to end
users — as input to a decision about how this repo (knowledge-base) might
distribute `graphify-out/graph.json` (382 MB, currently gitignored/rebuilt) to
consumers.

Status: COMPLETE — all 10 items researched, written incrementally, one section per tool.

---

## 1. Trivy (aquasecurity/trivy) — vulnerability DB

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | `trivy-db` (CVE/vuln metadata as a bbolt DB) and `trivy-java-db` (Java artifact index), each packaged as a **tar.gz containing `metadata.json` + `trivy.db`**, pushed as an OCI artifact (not a runnable container image). |
| 2 | Transport/registry | **OCI registries via ORAS**, three mirrors: `ghcr.io/aquasecurity/trivy-db` (primary), `aquasec/trivy-db` (Docker Hub), `public.ecr.aws/aquasecurity/trivy-db` (AWS ECR public) — same layout for `trivy-java-db`. Configurable via `--db-repository` with automatic fallback across mirrors (documented as a rate-limit/outage mitigation). |
| 3 | Versioning + integrity | Tag = **DB schema number**, currently **`2`** (`ghcr.io/aquasecurity/trivy-db:2`); schema v1 deprecated Feb 2023. Publish uses the ORAS CLI: `oras push --artifact-type application/vnd.aquasec.trivy.config.v1+json …`, so it is a real OCI artifact-type, not a container-image media type — `docker pull` cannot retrieve it. Rebuilt roughly **every 6 hours** upstream; `metadata.json` embeds a default 24h staleness TTL client-side. Could not verify a documented checksum/signature scheme specific to the DB artifact itself (the March 2026 supply-chain compromise advisory, GHSA-69fq-xp46-6x23, shows Trivy's integrity story leans on Sigstore signing of *releases* and digest-pinned images, not on a DB-specific checksum file — this is inference from that advisory, not a direct doc statement, so flagged as **not fully verified**). |
| 4 | Install-time vs lazy | **Lazy / automatic**: Trivy checks for a DB update **before every scan** by default and downloads if the cached copy is stale, with no separate install step. `--skip-db-update` opts out; `--download-db-only` pre-fetches without scanning. |
| 5 | Size | Docs did not state an exact number. Secondary source (oneuptime.com blog) describes it as "several hundred MB" decompressed; **could not verify a precise figure from a primary source** — flagged as unverified. |
| 6 | Partial/tiered download | No content-partial mode found (no "light" vs "full" DB tiers in current docs) — the whole DB/java-db artifact is fetched atomically each time. The only granularity control is *which registry/mirror* (`--db-repository`) and *whether* to fetch at all (`--skip-db-update`), not a subset of the DB. |

Sources: [trivy.dev DB config docs](https://trivy.dev/latest/docs/configuration/db/), [github.com/aquasecurity/trivy-db](https://github.com/aquasecurity/trivy-db), [GHSA-69fq-xp46-6x23 supply-chain advisory](https://github.com/advisories/GHSA-69fq-xp46-6x23), [oneuptime.com blog (secondary, size claim unverified against primary)](https://oneuptime.com/blog/post/2026-01-28-trivy-db-updates/view).

---

## 2. Grype / Anchore — vulnerability DB

Notably **not** OCI-registry-based (unlike Trivy) — it is a plain HTTPS file-archive distribution, and it has **two live schema generations with different discovery-file formats** in production simultaneously.

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | A DB archive (SQLite-backed) compressed as **`tar.zst`** (zstd), built by `grype-db package`. |
| 2 | Transport/registry | **Plain HTTPS object storage**, not OCI/ORAS — hosted on **Cloudflare R2** (S3-compatible) at `https://grype.anchore.io/databases/`. Discoverable via a **discovery/index file**, not a container registry manifest: schema **v5** (legacy) uses `databases/listing.json` = `{"available": {"1": [...], "2": [...], "5": [...]}}` (URLs grouped by schema major, newest first); schema **v6** (current) uses `databases/v6/latest.json` = `{"url":…, "built":…, "checksum":…, "schemaVersion":6}`, i.e. a single-pointer "latest" file rather than a full listing. The download base URL is itself configurable client-side (`package.base-url`), so a self-hosted air-gapped mirror is a supported first-class case (Harness docs describe hand-adding an entry with `built`/`version`/`url`/`checksum` to a local `listing.json`). |
| 3 | Versioning + integrity | DB **schema version** (v5/v6; v1–v4 retired) is the versioning axis, independent of the grype binary's own version. v6's `latest.json` carries an explicit **`checksum`** field grype validates post-download; v5's older `listing.json` format's integrity story is comparatively less clear from docs (could not verify a per-entry checksum field for v5 specifically — flagged unverified). Grype also enforces **DB freshness**, refusing to scan with a DB older than **5 days** by default (configurable). |
| 4 | Install-time vs lazy | **Lazy/automatic**: "When Grype is launched, it checks for an existing vulnerability database, and looks for an updated one online. If available, Grype will automatically download the new database" — no separate install step. `grype db update` (explicit) and `grype db check` (check-only, no download) are also available. |
| 5 | Size | Not stated in any primary doc page fetched — **could not verify** an approximate MB figure. |
| 6 | Partial/tiered download | No partial-download mechanism found; each schema version's archive is fetched as one atomic unit. The only "tiering" is *which schema major* (v5 vs v6) a given grype binary requests, not a size/content tier within one DB. |

Sources: [oss.anchore.com/docs/architecture/grype-db](https://oss.anchore.com/docs/architecture/grype-db/), [oss.anchore.com/docs/guides/vulnerability/database](https://oss.anchore.com/docs/guides/vulnerability/database/), [github.com/anchore/grype-db](https://github.com/anchore/grype-db), [Harness air-gapped Grype setup docs](https://developer.harness.io/docs/security-testing-orchestration/sto-techref-category/grype/grype-setup-in-airgapped/).

---

## 3. Ollama — model distribution

**Verified directly against the live registry**: fetched `https://registry.ollama.ai/v2/library/llama3.2/manifests/1b` and got back a real **Docker Distribution Manifest V2** JSON document (not a paraphrase) — see raw JSON below. This is the strongest-verified section of this report.

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
  "config": {
    "mediaType": "application/vnd.docker.container.image.v1+json",
    "digest": "sha256:4f659a1e86d7f5a33c389f7991e7224b7ee6ad0358b53437d54c02d2e1b1118d",
    "size": 485
  },
  "layers": [
    { "mediaType": "application/vnd.ollama.image.model",    "digest": "sha256:74701a8c…", "size": 1321082688 },
    { "mediaType": "application/vnd.ollama.image.template", "digest": "sha256:966de95c…", "size": 1429 },
    { "mediaType": "application/vnd.ollama.image.license",  "digest": "sha256:fcc5a6be…", "size": 7711 },
    { "mediaType": "application/vnd.ollama.image.license",  "digest": "sha256:a70ff7e5…", "size": 6016 }
  ]
}
```

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | A **model image**: a multi-layer OCI-style artifact whose layers each have an Ollama-custom `mediaType` — `application/vnd.ollama.image.model` (the actual GGUF weights blob, ~1.3GB in this example), `.template` (prompt template), `.license`, `.system`, `.params`, etc. — analogous to a container image's layer list but for model files instead of filesystem diffs. |
| 2 | Transport/registry | **`registry.ollama.ai` is a real Docker/OCI Distribution-API v2 registry** — `GET /v2/library/<model>/manifests/<tag>` returns `schemaVersion: 2`, `mediaType: application/vnd.docker.distribution.manifest.v2+json` (confirmed live, not inferred). Blobs are fetched from the registry's blob endpoint by digest, same as any Docker registry. |
| 3 | Versioning + integrity | Tag = model name + parameter-size/quantization variant (e.g. `llama3.2:1b`). **Content-addressed integrity**: every layer is identified and fetched by its **SHA-256 digest**; after a pull, Ollama recomputes each blob's SHA-256 and compares to the manifest digest before it is considered valid (per DeepWiki's description of the client code — not independently re-verified against source in this pass, so treat as secondary-sourced but internally consistent with standard OCI-client behavior). |
| 4 | Install-time vs lazy | **Lazy**, per-model, on `ollama pull <model>` or the first `ollama run <model>` if not cached — nothing is fetched at `ollama` install time itself. |
| 5 | Size | Varies enormously by model/quantization — the confirmed example layer above is **~1.3 GB** for `llama3.2:1b`'s weight blob; larger models run into tens of GB. No single "typical size" — it is per-model. |
| 6 | Partial/tiered download | **Resumable, parallelized chunked downloads** (per DeepWiki, describing the client): partial downloads are tracked as `{name}-partial-*` files under the blob cache and resumed by byte range across up to **16 concurrent parts** (`numDownloadParts`) if interrupted. This is resumability of *one* artifact's transfer, not a content-subset/tiered download — **quantization variants (`q4_0` vs `q8_0` etc.) are separate tags/manifests, not a partial-fetch of one underlying model**, so "choosing a smaller download" means choosing a different tag, not a partial pull. Cache layout: `manifests/` + `blobs/` under `~/.ollama/models` (macOS), `/usr/share/ollama/.ollama/models` (Linux), `C:\Users\%username%\.ollama\models` (Windows) — all overridable via `OLLAMA_MODELS` env var (confirmed from ollama/ollama `docs/faq.mdx` via `gh api`, a primary source). |

Sources: [registry.ollama.ai live manifest fetch](https://registry.ollama.ai/v2/library/llama3.2/manifests/1b) (primary, verified), [ollama/ollama docs/faq.mdx via GitHub API](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) (primary), [DeepWiki: Storage and Blob Transfer](https://deepwiki.com/ollama/ollama/2.4-storage-and-blob-transfer) (secondary — AI-generated wiki over the repo, used only for client-behavior description not independently re-verified against source in this pass).

---

## 4. Hugging Face Hub / `huggingface_hub` — model/dataset distribution

The richest mechanism of the ten researched: file-level content-addressing (blobs/snapshots), PLUS an additional chunk-level content-addressing layer (Xet) underneath that.

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | Arbitrary repo files (weights — `.safetensors`/`.bin`/`.gguf`/`.onnx`/etc., configs, tokenizers) inside a **git-backed repo** per model/dataset/space. |
| 2 | Transport | `hf_hub_download()` (single file) and `snapshot_download()` (whole repo at a revision, **downloaded concurrently**) — both are the primitives; the `hf download` CLI and `hf://` URIs wrap them. Newer transport is **`hf_xet`** (Rust `xet-core` bindings, auto-installed since `huggingface_hub` 0.32.0): breaks files into **~64 KB immutable chunks**, groups chunks into remote blocks ("xorbs"), and on download queries a **content-addressable service (CAS)** with the file's LFS SHA-256 to get reconstruction metadata (chunk ranges) + presigned URLs, then fetches only the needed xorb ranges — i.e. **cross-file, cross-revision chunk-level dedup**, not just whole-file dedup. `hf_transfer` (the older LFS-era accelerator) is deprecated in favor of `hf_xet`. |
| 3 | Versioning + integrity | **Revision-pinned**: `revision=` accepts a branch, tag, PR ref (`refs/pr/3`), or a **full-length commit SHA** (a 7-char short hash is explicitly rejected — "must be the full-length hash"). `HfApi.resolve_revision()` resolves `main`→commit-hash **once** and returns a `ResolvedRevision` so every file in a multi-call download provably comes from the same commit (avoids a moving-target repo landing files from two different commits). Integrity: `hf cache verify <repo>` validates cached files against Hub checksums; Xet reconstruction is itself hash-keyed (CAS lookup by LFS SHA-256). |
| 4 | Install-time vs lazy | **Lazy, per-call.** Nothing is pre-fetched at `pip install huggingface_hub` time; every download happens on an explicit `hf_hub_download`/`snapshot_download`/`hf download` call (or implicitly the first time a downstream library like `transformers` needs a file), and results are cached so a second call for the same commit costs at most one HTTP call (resolving the ref) or zero if pinned to a resolved SHA. |
| 5 | Size | No fixed size — this is a general per-repo download mechanism; the docs' own worked `--dry-run` example against `gpt2` totals **5.6 GB across 26 files** when unfiltered (illustrative, not a claim about typical model size). |
| 6 | Partial/tiered download | **Yes, explicitly first-class**: `allow_patterns` / `ignore_patterns` (glob/`fnmatch`, e.g. `allow_patterns="*.safetensors"` to skip legacy `.bin`/`.h5`/`.msgpack` weight formats) on `snapshot_download()`, and `--include`/`--dry-run` on the CLI (dry-run prints exactly which files/bytes would download, per-file, before committing). Below the file level, Xet's chunk-level CAS dedup means even a *full* download only fetches chunks not already present in the local `chunk_cache` (10 GB soft cap) from any other cached repo/revision — a second form of "partial" download that operates below `allow_patterns`'s file granularity. |

**Cache layout** (`~/.cache/huggingface/hub`, overridable via `HF_HOME`/`HF_HUB_CACHE`): per-repo dir `models--<org>--<name>/` containing `blobs/` (content, filename = hash), `snapshots/<commit-sha>/` (symlinks into `blobs/`, so identical files across revisions are stored once), `refs/<branch>` (pointer files holding the resolved commit sha), and `trees/<commit-sha>.json` (a cached file-manifest so a repeat download of an already-resolved commit costs a single HTTP call). Windows without symlink support falls back to copying files directly into `snapshots/` (`HF_HUB_DISABLE_SYMLINKS=1`). A separate `xet/` cache directory holds the chunk-level `chunk_cache`/`shard_cache`/`staging`.

Sources: [huggingface_hub docs — Download files from the Hub](https://huggingface.co/docs/huggingface_hub/en/guides/download) (primary), [huggingface_hub docs — Understand caching](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache) (primary).

---

## 5. spaCy trained pipelines (`spacy download`)

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | A **standard pip-installable Python package** (wheel + sdist) — the model *is* a package, not a side-loaded data blob; e.g. `en_core_web_sm-3.8.0-py3-none-any.whl`. |
| 2 | Transport/registry | **GitHub Releases**, confirmed live via `gh api`: `github.com/explosion/spacy-models/releases`, one release tag per `<model_name>-<version>` (e.g. tag `en_core_web_lg-3.8.0`) carrying both a `.whl` and a `.tar.gz` asset. `spacy download <name>` is documented as "a convenient, interactive wrapper" over `pip install` that resolves the right release URL and compatibility check — **`pip install <url-or-path-to-wheel>` works directly** too (docs state this explicitly), and a release URL can be dropped straight into `requirements.txt`. Not PyPI-hosted as a discoverable package (these are not `pip install spacy-en-core-web-sm`-from-index; they're `pip install`-from-URL). |
| 3 | Versioning + integrity | **`compatibility.json`** at `github.com/explosion/spacy-models/master/compatibility.json` (fetched live) is keyed `{"spacy": {"<spacy-minor-version>": {"<model-name>": ["<compatible-model-versions>"]}}}`, e.g. `"3.8": {"en_core_web_sm": ["3.8.0"], ...}` — `spacy download`/`spacy validate` read this table to pick the model version matching the installed spaCy version. Integrity is whatever pip/wheel provides (no separate spaCy-specific checksum layer found in the fetched docs). |
| 4 | Install-time vs lazy | **Explicit, on-demand**: never auto-fetched — a user must run `spacy download <model>` (or `pip install`) as its own step; nothing downloads at `pip install spacy` time. |
| 5 | Size | **Measured directly from GitHub Releases (`gh api`), spaCy 3.8.0 English models**: `en_core_web_sm` wheel = **12 MB**, `en_core_web_lg` = **382 MB**, `en_core_web_trf` (transformer-based) = **436 MB**. Non-English example: `zh_core_web_sm` = 48.5 MB, `zh_core_web_trf` = 415 MB. So "small" (rule-based/small-vector) vs "lg"/"trf" (dense vectors / transformer weights) differ by roughly **30–40×**. |
| 6 | Partial/tiered download | **Tiering exists at the package-selection level, not within one package**: spaCy ships each language in `sm`/`md`/`lg`/`trf` (and now `hftrf`) variants as *separate, independently downloadable packages* — the user picks the tier by choosing which package name to install; there is no partial/streamed fetch of a single package. |

Sources: [spacy.io/usage/models](https://spacy.io/usage/models) (primary), [github.com/explosion/spacy-models releases via `gh api`](https://github.com/explosion/spacy-models/releases) (primary, live-measured sizes), [compatibility.json via raw.githubusercontent.com](https://raw.githubusercontent.com/explosion/spacy-models/master/compatibility.json) (primary, live-fetched).

---

## 6. NLTK (`nltk.download()`)

**Verified directly**: fetched the live `index.xml` and it contains a **per-package checksum** — a genuinely stronger integrity story than several of the other tools researched, and worth calling out to the caller explicitly.

```xml
<package id="abc" name="Australian Broadcasting Commission 2006" ... unzip="1"
  unzipped_size="4054966" size="1487851"
  checksum="ffb36b67ff24cbf7daaf171c897eb904"
  sha256_checksum="129bb6001beb828049a90a59b7dd3c2f0594a47012e48fc5177dfae38e658565"
  subdir="corpora"
  url="https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/abc.zip" />
```

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | Per-package **zip archives** (corpora, tokenizer models, taggers, grammars, etc.), each independently addressable — NLTK's data is explicitly modeled as N small packages, not one bundle. |
| 2 | Transport/registry | A dedicated **data index**: `index.xml` at `nltk_data`'s `gh-pages` branch (fetched live at `raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml`) lists every package with a direct download `url` — the packages themselves are also just files in that same GitHub repo/gh-pages site (`.../packages/<subdir>/<id>.zip`), i.e. **GitHub Pages serving static files**, not a registry/API. `nltk.org/nltk_data/` is the human-browsable mirror of the same list. |
| 3 | Versioning + integrity | **No repo-wide version number** — each `<package>` entry stands alone with its own `size`/`unzipped_size`. **Real integrity checking**: each entry carries both a legacy `checksum` (MD5) and a `sha256_checksum`, so `nltk.download()` can verify a fetched zip against a manifest-declared hash — this is the strongest integrity mechanism of any tool in this survey with an explicitly confirmed field, verified directly from the primary index rather than inferred. |
| 4 | Install-time vs lazy | **Neither automatic** — NLTK does **not** auto-download on first use. Its own install docs are explicit: "After installing the NLTK package, please do install the necessary datasets/models for specific functions to work," via `nltk.download('popular')` or `python -m nltk.downloader popular`. (Could not confirm from docs fetched whether a missing-data lookup raises `LookupError` specifically — that detail is widely known from the library's runtime behavior but was not independently re-verified against a primary doc in this pass, so flagged unverified-here.) |
| 5 | Size | Fully per-package and highly variable — the `abc` corpus example above is **~1.4 MB compressed / ~3.9 MB unzipped**; NLTK explicitly offers an `"all"` collection (everything) versus named sub-collections like `"book"` or `"popular"` precisely because the full corpus set is much larger than any single package (no single "total" figure obtained in this pass). |
| 6 | Partial/tiered download | **Yes, fine-grained and native to the design**: `nltk.download('<package_id>')` for one package, `nltk.download('<collection>')` for a named bundle (e.g. `"book"`, `"popular"`), or `nltk.download('all')` for everything — the index's per-package `size`/`unzipped_size` fields are exactly what a client uses to plan/report a partial fetch. This is the most granular download story of any tool in this report. |

Local layout: `~/nltk_data` (or another searched path) with **type-based subdirectories** (`corpora/`, `taggers/`, `tokenizers/`, `chunkers/`, `grammars/`, `models/`, `sentiment/`, `stemmers/`, `misc/`, `help/`) — each package unzips into the subdir named by its `subdir` index attribute (e.g. Brown Corpus → `nltk_data/corpora/brown`).

Sources: [nltk.org/data.html](https://www.nltk.org/data.html) (primary), [nltk.org/install.html](https://www.nltk.org/install.html) (primary), [raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml](https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml) (primary, live-fetched).

---

## 7. tldr-pages — `tldr.zip` / per-language archives

**Verified directly** by pulling the live `v2.3` release via `gh api repos/tldr-pages/tldr/releases/latest` and downloading its checksum file — real numbers, not paraphrase.

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | `index.json` (a manifest of every page), `tldr.zip` (all languages combined), **39 separate per-language zips** `tldr-pages.<lang>.zip` (`ar`,`bg`,`bn`,`bs`,`ca`,`cs`,`da`,`de`,`el`,`en`,`es`,`fa`,`fi`,`fr`,`hi`,`id`,`it`,`ja`,`ko`,`lo`,`ml`,`nb`,`ne`,`nl`,`no`,`pl`,`pt_BR`,`pt_PT`,`ro`,`ru`,`sh`,`sr`,`sv`,`ta`,`th`,`tr`,`uk`,`uz`,`zh`,`zh_TW`), plus PDF "book" renders per language, and a `tldr.sha256sums` checksum manifest. |
| 2 | Transport/registry | **GitHub Releases**, plain asset downloads — `github.com/tldr-pages/tldr/releases/download/v2.3/<asset>`. No registry/API layer; a release tag (`v2.3`) is the version. |
| 3 | Versioning + integrity | Version = the **GitHub release tag** (`v2.3` at research time). **Real per-file SHA-256 integrity checking**: `tldr.sha256sums` (fetched live, 3.6 KB) is a standard `sha256sum`-format manifest with one line per artifact, e.g. `0e8b6ef9…  index.json`, `1758c3bd…  tldr-pages.ar.zip` — a client (or a human) can `sha256sum -c` the whole release. |
| 4 | Install-time vs lazy | Not applicable in the "package install" sense — tldr clients fetch these archives **on first use / on explicit cache-refresh** (client-dependent; the c/Rust client `tlrc` and others cache locally and re-check periodically), not bundled into the client's own install artifact. Exact per-client behavior (auto vs explicit) was not independently verified against each client's docs in this pass. |
| 5 | Size (live-measured) | `index.json` = **1.89 MB**; `tldr.zip` (**all** languages) = **20.1 MB**; `tldr-pages.en.zip` (English only) = **3.29 MB** (largest single-language archive is `tldr-pages.ko.zip` at 3.33 MB, likely due to encoding, followed by `de` at 364 KB — `en`/`ko` are outliers vs. most languages sitting in the 90 KB–700 KB range); `tldr.sha256sums` = 3.6 KB. |
| 6 | Partial/tiered download | **Yes — the per-language zip split is exactly this.** A client only needs to fetch `tldr-pages.<user-locale>.zip` (tens to low-hundreds of KB, `en` being the largest non-outlier at 3.29 MB) instead of the 20 MB all-language `tldr.zip`. This is coarse (whole-language granularity) rather than fine-grained (per-command), but it is a genuine, shipped tiering mechanism. |

Sources: [github.com/tldr-pages/tldr](https://github.com/tldr-pages/tldr) (primary), live release data via `gh api repos/tldr-pages/tldr/releases/latest` (primary, verified 2026-08-02, tag `v2.3`), live-fetched `tldr.sha256sums` (primary).

---

## 8. tree-sitter grammars — nvim-treesitter and the official CLI

Two different, independently-verified answers depending on which layer you mean: the **official** tooling compiles locally; a **community** package ships real prebuilt WASM binaries via plain npm.

| # | Question | Answer |
|---|---|---|
| Compiled-or-prebuilt (official) | **nvim-treesitter (2026, current `main`) compiles from source locally — it does NOT fetch prebuilt binaries.** Docs require a C compiler on PATH, `tree-sitter-cli` **0.26.1+**, plus `tar`/`curl` to fetch each parser's **source** archive. Parser source + pinned commit (`revision`) comes from that language's own `tree-sitter-<lang>` GitHub repo, per an internal `parser.lua` compatibility table ("this plugin is only guaranteed to work with specific versions of language parsers"); `:TSInstall` fetches source + compiles to a native `.so`, `:TSUpdate` re-syncs every installed parser to the pinned revisions after a plugin upgrade. |
| Compiled-or-prebuilt (official CLI, WASM) | The official `tree-sitter build --wasm` **also compiles locally** — it invokes the **WASI SDK** (`TREE_SITTER_WASI_SDK_PATH`, or auto-downloaded to a cache dir on first use if unset) to produce the `.wasm`; there is no official prebuilt-WASM registry/CDN. |
| Is there a prebuilt WASM distribution anywhere? | **Yes, but third-party/community, not official.** `tree-sitter-wasms` (npm, maintainer "Gregor", MIT/Unlicense) ships **prebuilt `.wasm` files for ~39 parsers directly inside the npm tarball** — confirmed live via `curl https://registry.npmjs.org/tree-sitter-wasms/latest`: `fileCount: 39`, **`unpackedSize: 51,769,841` bytes (~51.8 MB)**. So the binaries are bundled in the package itself (fetched at `npm install` time, no separate lazy download), not fetched from a CDN on demand. Forks exist for narrower language sets (e.g. `@repomix/tree-sitter-wasms`), and raw files are also individually browsable at `unpkg.com/browse/tree-sitter-wasms@latest/out/`. |
| Versioning/integrity | Official parsers: version = the pinned git **`revision`** (commit hash) per language in `parser.lua`, with an optional `branch` override — no separate checksum layer beyond git's own commit-hash integrity. `tree-sitter-wasms`: versioned as a normal semver npm package (`0.1.13` at check time), integrity via npm's standard **`integrity` (sha512) + signature** fields in registry metadata (confirmed in the fetched JSON) — npm's normal package-integrity mechanism, not anything tree-sitter-specific. |
| Install-time vs lazy | **nvim-treesitter: lazy, per-language, on explicit `:TSInstall <lang>`** (or configured `ensure_installed`), never all-at-once. **`tree-sitter-wasms`: install-time** — the whole ~51.8 MB bundle of all included languages' `.wasm` files arrives in one `npm install`, with no documented per-language partial-install mode found. |
| Size | `tree-sitter-wasms` unpacked = **~51.8 MB for ~39 languages** (measured live) → roughly **1–2 MB per language** on average, though grammars vary considerably in complexity. Individual `tree-sitter-<lang>` native compile artifacts (`.so`) were not measured in this pass. |
| Partial/tiered download | nvim-treesitter: yes, install exactly the languages you configure (`ensure_installed = {...}`), each a separate fetch+compile. `tree-sitter-wasms`: no partial mode — one npm package, all included languages, one download. |

Sources: [github.com/nvim-treesitter/nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter) (primary), [tree-sitter.github.io/tree-sitter/cli/build.html](https://tree-sitter.github.io/tree-sitter/cli/build.html) (primary), [registry.npmjs.org/tree-sitter-wasms/latest](https://registry.npmjs.org/tree-sitter-wasms/latest) (primary, live-fetched), [npmjs.com/package/tree-sitter-wasms](https://www.npmjs.com/package/tree-sitter-wasms) (attempted, blocked 403 — substituted the raw registry API fetch above).

---

## 9. Claude Code plugins / plugin marketplaces

Fetched `code.claude.com/docs/en/plugin-marketplaces` and `.../plugins-reference` directly (primary, current docs) — no size limit or size guidance number is stated anywhere in either page; the mechanism instead pushes large/derived data out of the "plugin bundle" entirely and into a separate persistent-data directory or a sparse-clone path.

| # | Question | Answer |
|---|---|---|
| 1 | Artifact | A plugin is a directory of components (`skills/`, `agents/`, `hooks/`, `mcpServers`, `lspServers`) plus a `.claude-plugin/plugin.json` manifest, catalogued by a marketplace's `.claude-plugin/marketplace.json`. **A plugin's own repo is not necessarily where large data lives** — see rule 4 below. |
| 2 | Transport | **Multiple source types, git-based by default but not exclusively**: `github` (owner/repo, `ref`/`sha`), `url` (any git remote), **`git-subdir`** (a subdirectory of a monorepo, fetched via a **sparse, partial git clone** — docs state explicitly: "minimizing bandwidth for large monorepos"), `npm` (installed via `npm install` from any registry), and a bare relative path for same-repo plugins. Marketplace *itself* is also fetchable via a plain URL to a `marketplace.json` file, but that mode does NOT download anything else — relative-path plugin sources fail under it, because "only that file is downloaded" (confirmed doc quote). |
| 3 | Versioning + integrity | Version resolves from, in order: `plugin.json`'s `version` field → the marketplace entry's `version` field → **the git commit SHA** of the source (so an unversioned git-based plugin is implicitly versioned by commit — every new commit counts as a new version). `github`/`url`/`git-subdir` sources support pinning both a `ref` (branch/tag) and a `sha` (exact 40-char commit); when both are set, `sha` is authoritative and Claude Code "fetches and checks out the pinned commit directly," which — per the docs — still resolves even if the named branch/tag is later deleted upstream (on hosts that support fetch-by-SHA; not AWS CodeCommit). No content-hash/checksum-of-artifact mechanism beyond git's own commit-hash integrity was found; `npm` sources presumably ride on npm's own package integrity (not stated in this doc). |
| 4 | Install-time vs lazy, and where big data actually goes | **Install-time for the plugin package itself** — `/plugin install` clones/downloads to `~/.claude/plugins/cache` immediately. For genuinely bulky DERIVED data (the closest analogue to this repo's `graph.json`), the docs describe **`${CLAUDE_PLUGIN_DATA}`** → `~/.claude/plugins/data/{id}/`, a directory explicitly intended for "installed dependencies such as `node_modules` or Python virtual environments, generated code, and caches" — created **lazily, on first reference**, and **persists across plugin updates** (unlike the versioned plugin-cache directory, which is treated as disposable/replaceable each update). This is the documented pattern for a plugin that needs to materialize large data after install rather than ship it in the git payload: install a small plugin, then build/download the bulky artifact into `${CLAUDE_PLUGIN_DATA}` on first use. |
| 5 | Size | **No number given anywhere in either doc.** The only proxy for "this could get large" is operational: a **120-second git-operation timeout** (`CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS`, overridable) on clone/pull, and the `/plugin` interface "shows the directory size and prompts before deleting" for `${CLAUDE_PLUGIN_DATA}` — i.e. size is surfaced to the user at deletion time, not gated at install time. |
| 6 | Partial/tiered download | **`git-subdir` is exactly this**: a sparse/partial clone of one path within a larger repo, explicitly justified in the docs as a bandwidth-minimization feature for monorepos — the closest peer-tool analogue in this whole survey to "clone only the piece you need out of a much bigger tracked tree." `claude plugin marketplace add ... --sparse <paths...>` additionally lets a **marketplace-level** add restrict checkout to specific directories. There is no partial-fetch mechanism for a *single* plugin's own bundled files once the plugin source is chosen — the whole plugin directory is copied to cache atomically. |

Sources: [code.claude.com/docs/en/plugin-marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) (primary), [code.claude.com/docs/en/plugins-reference](https://code.claude.com/docs/en/plugins-reference) (primary).

---

## 10. Precise platform limits — GitHub and PyPI

All numbers below are quoted directly from the current primary docs (fetched live).

| Limit | Exact figure | Source |
|---|---|---|
| Plain `git push` — hard block per file | **GitHub blocks files larger than 100 MiB.** | [GitHub docs — About large files on GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) |
| Plain `git push` — warning threshold | **"If you attempt to add or update a file that is larger than 50 MiB, you will receive a warning from Git."** | same as above |
| Repository size guidance (soft, non-enforced) | "We recommend repositories remain small, ideally **less than 1 GB**, and **less than 5 GB** is strongly recommended." | same as above |
| GitHub Release — max size per asset file | **Each file included in a release must be under 2 GiB.** | [GitHub docs — About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) |
| GitHub Release — total release size / asset count | **No limit on total release size or bandwidth**; up to **1,000 assets per release** (asset-count cap per the same fetch). | same as above |
| Git LFS — free tier (GitHub Free/Pro) | **10 GiB storage + 10 GiB bandwidth/month** included. | [GitHub docs — About storage and bandwidth usage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-storage-and-bandwidth-usage) |
| Git LFS — Team/Enterprise Cloud | **250 GiB storage + 250 GiB bandwidth/month** included. | same as above |
| PyPI — default per-file size limit | **100.0 MiB by default**; "individual projects may differ" (increase requestable). | [pypi.org/help/](https://pypi.org/help/) |
| PyPI — default per-project total size limit | **10.0 GiB by default**; "individual projects may differ" (increase requestable, after pruning old releases). | [pypi.org/help/](https://pypi.org/help/) |

**Note for this repo's own decision context**: `graphify-out/graph.json` is **382 MB** (per this repo's own `CLAUDE.md`). That is under GitHub's hard 100 MiB-per-file *push* block only if... it is not — 382 MB exceeds the 100 MiB hard block by ~3.8×, exceeds the 50 MiB warning threshold by ~7.6×, and comfortably fits a single GitHub Release asset (2 GiB cap) or Git LFS (10 GiB free-tier storage). It also exceeds PyPI's 100 MiB default per-file limit if ever considered for that channel. This directly explains why the repo's own invariants keep it gitignored and route distribution through `kb-serve` MCP or a pushed graph DB rather than a git blob.

---

## GitHub repos touched

- [aquasecurity/trivy](https://github.com/aquasecurity/trivy) — read supply-chain advisory GHSA-69fq-xp46-6x23 re: integrity/signing story.
- [aquasecurity/trivy-db](https://github.com/aquasecurity/trivy-db) — read README for DB build/publish/ORAS mechanism and schema versioning.
- [anchore/grype-db](https://github.com/anchore/grype-db) — read README for listing.json/latest.json distribution format.
- [anchore/grype](https://github.com/anchore/grype) — read repo overview (limited detail found; superseded by oss.anchore.com docs).
- [ollama/ollama](https://github.com/ollama/ollama) — read `docs/faq.mdx` (via GitHub API) for model storage locations and `OLLAMA_MODELS` env var.
- [explosion/spacy-models](https://github.com/explosion/spacy-models) — live `gh api` release/asset queries for wheel sizes, and fetched `compatibility.json` from raw.githubusercontent.com.
- [nltk/nltk_data](https://github.com/nltk/nltk_data) — live-fetched `index.xml` (gh-pages branch) for per-package checksum/size manifest format.
- [tldr-pages/tldr](https://github.com/tldr-pages/tldr) — live `gh api` release query for asset list/sizes, and fetched `tldr.sha256sums` checksum manifest.
- [nvim-treesitter/nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter) — read README for parser install/compile mechanism.
- [Gregoor/tree-sitter-wasms](https://github.com/Gregoor/tree-sitter-wasms) — identified as the community prebuilt-WASM npm package; queried its npm registry metadata (not the GitHub repo content directly).
- [huggingface/huggingface_hub](https://github.com/huggingface/huggingface_hub) — implicit source of the fetched huggingface.co/docs/huggingface_hub guide pages (docs are generated from this repo; not directly browsed).

## Non-GitHub primary sources touched

- trivy.dev (Trivy official docs site)
- oss.anchore.com (Anchore/Grype official docs site)
- registry.ollama.ai (live OCI Distribution API v2 manifest fetch)
- huggingface.co/docs/huggingface_hub (official docs)
- spacy.io/usage/models (official docs)
- nltk.org/data.html, nltk.org/install.html (official docs)
- tree-sitter.github.io/tree-sitter/cli/build.html (official docs)
- registry.npmjs.org (live npm registry API)
- code.claude.com/docs (official Claude Code docs)
- docs.github.com (official GitHub docs — file/release/LFS limits)
- pypi.org/help/ (official PyPI help docs)

