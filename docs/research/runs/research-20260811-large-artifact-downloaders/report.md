# Large artifact downloaders on macOS

**Date:** 2026-08-11

**Scope:** repeatable downloads of 100 GB-2 TB model/source artifacts on macOS,
with Hugging Face Xet as the immediate case

## Decision

Adopt the provider's native transfer engine behind one manifest-driven Python
interface. For Hugging Face, the default must remain
`huggingface_hub.snapshot_download` with `hf-xet`, pinned at versions containing
the poor-network hang fix. Do not build a segmented HTTP downloader and do not
put aria2 in front of Hugging Face Xet URLs. Xet's client already resolves the
content-addressed reconstruction plan, obtains expiring range URLs, downloads
ranges concurrently, and reconstructs the files.

The plug-and-play boundary should be:

```text
mise task -> kb_setup artifact-download -> provider adapter -> provider client
                                      \-> common receipt and verifier
```

Recommended providers, in order:

1. **`huggingface-xet`** for Hugging Face repositories. Use an immutable commit,
   `allow_patterns`, a persistent `local_dir`, and a current pinned client.
2. **`modelscope`** only when the model owner or a trusted publisher hosts the
   exact required artifact there and its byte manifest can be matched. It is a
   separate registry, not a transparent Hugging Face accelerator.
3. **`rclone`** for an organization-controlled S3/R2/B2/NAS mirror. This is the
   strongest path for repeat downloads after a verified first acquisition.
4. **`aria2`** for ordinary static HTTP(S) URLs with stable Range support and an
   authoritative SHA-256. It is not an HF-Xet backend.
5. **Git LFS** as a compatibility/recovery path, not the normal model installer.
   It carries authoritative SHA-256 pointers and resumable HTTP, but adds Git
   metadata and commonly retains both the LFS object and a working-tree copy.

For the current GLM canary, keep Hugging Face Xet. The exact Colibri-converted
repository exists on Hugging Face at the pinned commit, while a bounded
ModelScope API probe returned 404 for that repository. ModelScope has an
official `ZhipuAI/GLM-5.2`, but that is not the same grouped-int4 Colibri
container and cannot substitute for it.

## Why the current transfer can still be improved

The canary already does three important things correctly: it pins the full
revision, filters the snapshot, and enables `HF_XET_HIGH_PERFORMANCE=1`. The
remaining gains are mostly operational rather than a new transport:

- Pin both `huggingface_hub` and `hf-xet`. On 2026-08-11 the current releases
  were `huggingface_hub` 1.27.0 and `hf-xet` 1.6.0. `hf-xet` 1.5.2 fixed an
  HTTP retry bug that could appear to hang on poor networks, and
  `huggingface_hub` 1.27.0 raised its minimum Xet version to 1.5.2. A floating
  `uv run --with huggingface-hub` can silently land on a known-bad transfer
  implementation. [hf-xet 1.5.2 release](https://github.com/huggingface/xet-core/releases/tag/v1.5.2),
  [huggingface_hub 1.27.0 release](https://github.com/huggingface/huggingface_hub/releases/tag/v1.27.0)
- Make the Xet resource profile explicit. Public HF documentation says high
  performance mode tries to saturate network, CPU, and disk. In Xet 1.6.0 it
  also raises adaptive download concurrency and reconstruction buffers; it is
  an intentionally whole-machine profile, not a harmless boolean. Keep it for
  a dedicated download run, but provide a balanced profile for interactive use.
  [HF environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables),
  [Xet 1.6.0 high-performance configuration](https://github.com/huggingface/xet-core/blob/v1.6.0/xet_runtime/src/config/xet_config.rs#L148-L177)
- Keep `HF_XET_RECONSTRUCT_WRITE_SEQUENTIALLY` unset on the internal Mac SSD.
  HF documents it as an HDD optimization; Xet's normal direct-addressed
  parallel writes target SSD/NVMe.
- Keep the Xet chunk cache disabled for a one-off new snapshot. Its documented
  default is zero, and HF says disabling it is usually faster for new data.
  Enable a large cache only when repeated revisions are expected to share
  chunks. [HF Xet cache documentation](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache#chunk-based-caching-xet)
- Expose `snapshot_download(max_workers=...)`. It controls concurrent **files**
  and defaults to eight. Xet separately controls ranges within each file; these
  are different concurrency layers. The public
  `HF_XET_NUM_CONCURRENT_RANGE_GETS` defaults to 16, but the current Xet engine
  also has adaptive concurrency. Do not multiply both blindly.
  [snapshot_download source and API](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/_snapshot_download.py),
  [HF Xet environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables#hf_xet_num_concurrent_range_gets)
- Preserve the destination's `.cache/huggingface` metadata. With `local_dir`,
  `snapshot_download` bypasses the ordinary Hub blob cache and stores small
  metadata inside the destination, avoiding a deliberate second model copy.
  Removing that metadata does not remove the model, but makes later recovery
  and freshness checks slower. [HF download guide](https://huggingface.co/docs/huggingface_hub/en/guides/download#download-file-s-to-a-local-folder)

## Transport comparison

| Method | Parallelism | Resume boundary | Integrity/provenance | Disk behavior | Verdict |
|---|---|---|---|---|---|
| HF `snapshot_download` + `hf-xet` | Files plus Xet CAS ranges; high-performance or adaptive tuning | Completed files are reused; interrupted Xet files can restart from zero | Immutable Hub commit; Xet reconstruction keyed by LFS SHA-256; add common post-verification | `local_dir` avoids the main blob-cache copy; Xet chunk cache is off by default | **Default for HF** |
| `hf download` CLI | Same helpers as Python | Same as Python | Same | Same | Useful manual surface; library is better for structured receipts |
| Direct HTTP + custom ranges | Only what we build | Can resume byte ranges if server honors them | Must separately acquire/check size and SHA-256 | One target plus partials | **Do not build**; HF regular HTTP has a current >50 GB problem and Xet needs reconstruction metadata |
| aria2 1.37.0 | Multiple sources, splits, per-host connections | `.aria2` control file and HTTP Range | Supports explicit `--checksum`; no registry/revision semantics | Target, control file, optional preallocation | Adopt only for stable ordinary URLs |
| rclone 1.75.0 | File transfers plus multi-thread streams | Backend-dependent; robust retries/partials | Strong when the object backend exposes hashes; HTTP remote has limited metadata | One destination plus partials | Preferred for our own object-store mirror, not raw HF |
| Git LFS 3.7.1 | Default eight objects; resumable HTTP Range | Object-level resume | Pointer includes SHA-256 and byte size | `.git/lfs/objects` plus working tree can approach 2x | Compatibility/recovery only |
| ModelScope Hub 0.2.0 | File workers plus parallel ranges, capped range workers | HTTP Range for a file and retained part files | Registry SHA-256 verified after merge; immutable revision must be supplied | Cache or direct local directory; parallel merge needs part headroom | Good only for exact ModelScope-hosted artifact |
| Public/community HF mirror | Unknown | Unknown | Endpoint redirects and metadata can differ | Unknown | Reject by default |

### Hugging Face Xet

`huggingface_hub` has used `hf-xet` automatically since 0.32.0. The old
`HF_HUB_ENABLE_HF_TRANSFER` path is deprecated because Hub storage is now Xet.
`snapshot_download` lists one immutable tree, filters it, and downloads files
concurrently. Pinning a full commit avoids resolving `main` and prevents files
from different revisions being mixed.

Xet's major limitation for very large single files remains resume granularity.
Two current upstream issues document interrupted or cancelled Xet files
restarting at zero; completed files in a snapshot remain reusable. For a
many-shard model, the loss is normally the files active at interruption, not
the whole repository. For a single 50-100 GB GGUF, the gap is material. Do not
claim byte-resume until an explicit control proves it in the pinned versions.
[huggingface_hub #4196](https://github.com/huggingface/huggingface_hub/issues/4196),
[huggingface_hub #4632](https://github.com/huggingface/huggingface_hub/issues/4632)

The non-Xet HTTP path is not a safe universal fallback. An open first-party
issue reproduces the regular method rejecting a roughly 59 GB file and directs
users to Xet. The issue also notes that Xet is currently the intended supported
path for such large files. [huggingface_hub #3868](https://github.com/huggingface/huggingface_hub/issues/3868)

### aria2 and direct HTTP ranges

aria2 is a mature implementation of the thing we should not reimplement: split
HTTP transfers, multiple connections, continuation, preallocation controls,
and supplied checksum validation. Its manual documents `--split`,
`--max-connection-per-server`, `--min-split-size`, `--continue`, and
`--checksum`. [aria2 manual](https://aria2.github.io/manual/en/html/aria2c.html)

It is an excellent adapter when a manifest contains stable URLs and hashes,
such as a release asset or owner-operated object store. It is a poor adapter
for HF Xet because it cannot obtain/interpret Xet reconstruction terms, and
transfer action URLs may expire. The Git LFS batch specification explicitly
allows a download action to carry headers and an expiry time, demonstrating
why persisting a resolved CDN URL is not a durable artifact manifest.
[Git LFS Batch API](https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md)

### rclone

rclone belongs at the mirror layer. For S3-compatible storage it can use the
provider's native multipart/range behavior, hashes, retries, and credentials.
Its HTTP remote is read-only and can attach headers, but lacks the registry
semantics and rich hashes needed to establish an HF snapshot. Its generic
multi-thread flags require the backend to provide size and range support.
[rclone HTTP backend](https://rclone.org/http/),
[rclone global transfer options](https://rclone.org/docs/#multi-thread-streams-n)

The high-value future optimization is therefore: acquire once with HF Xet,
fully verify, then optionally copy the immutable receipt plus files to a
private organization-controlled object prefix and use rclone for subsequent
hosts. That trades public-Hub WAN variability for a storage bill and a mirror
governance obligation; it should be opt-in, not automatic.

### Git LFS

Git LFS pointers provide a strong provenance primitive: the required `oid` is
currently SHA-256 and `size` is bytes. The client defaults to eight concurrent
transfers, supports resumable HTTP downloads using Range headers, and supports
path include/exclude filters. [Git LFS pointer specification](https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md),
[Git LFS transfer configuration](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-config.adoc),
[git lfs fetch](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-fetch.adoc)

For hundreds of gigabytes it is still inferior to `snapshot_download`: clone
metadata is unnecessary, smudge is inefficient, and the local LFS object store
plus checkout can consume close to two payload copies. If used, clone with
smudge disabled, fetch only the exact commit and include paths, then check out;
preflight for the larger disk requirement.

### ModelScope and mirrors

The current official ModelScope Hub client is technically attractive: its
source implements HTTP Range resume, per-part retry, parallel parts, atomic
merge, SHA-256 verification, file locks, and concurrent files. It defaults to
four snapshot workers, and parallel range workers are capped at 16.
[ModelScope Hub README](https://github.com/modelscope/modelscope_hub/blob/aa8dbf11ef4373faa83a9bc5d73f7dff6478b08b/README.md),
[download implementation](https://github.com/modelscope/modelscope_hub/blob/aa8dbf11ef4373faa83a9bc5d73f7dff6478b08b/src/modelscope_hub/_download.py)

That does not make it a generic HF mirror. A backend is eligible only if all of
these are true:

1. the exact format is published there by the owner or an explicitly trusted
   distributor;
2. an immutable revision is available;
3. every selected file's path, byte size, and SHA-256 matches an approved
   manifest, or the alternate artifact has been separately qualified;
4. its model license and registry terms allow the intended download and any
   later redistribution.

Do not set `HF_ENDPOINT` to an arbitrary mirror. A current open issue shows a
mirror's 308 redirect causing missing commit metadata and misleading
`LocalEntryNotFoundError`, including a query-dropping redirect bug. The safe
workaround is the official endpoint. [huggingface_hub #4637](https://github.com/huggingface/huggingface_hub/issues/4637)

## Proposed manifest and library contract

The tracked input should be declarative TOML. It must identify content, not a
temporary URL:

```toml
schema = 1
id = "glm52-colibri-g64"
provider = "huggingface-xet"
repo_id = "mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp"
revision = "fd9b461ac7cae4b921470d0db12230c6505bd03c"
allow = ["*.safetensors", "config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json"]
license = "mit"

[requirements]
min_free_bytes_after_plan = 20_000_000_000

[verification]
mode = "sha256"
require_complete_tree = true
```

The planner resolves the immutable repository tree and emits a receipt with:

- provider and API endpoint;
- requested and resolved revision;
- selected file path, size, and upstream SHA-256 where available;
- total selected bytes, already-complete bytes, and required new bytes;
- destination filesystem capacity and conservative temporary headroom;
- pinned downloader versions and resource profile;
- model-card license, gated/private status, and source URL;
- start/end time, actual byte counts, final hashes, and result state.

Use a small provider protocol rather than one giant conditional:

```python
class ArtifactProvider(Protocol):
    def plan(self, request: Request) -> Plan: ...
    def fetch(self, plan: Plan, destination: Path, profile: Profile) -> Receipt: ...
```

Common code owns capacity checks, path containment, receipts, redaction,
verification, and exit states. Provider adapters own only native API calls.
The initial implementation needs only `HuggingFaceXetProvider`; add another
adapter when a real manifest requires it. This is adopt-before-build while
keeping the internal implementation replaceable.

## Mise task surface

Recommended task:

```text
mise run kb-artifact-download -- <manifest> <destination> \
  [--backend auto|huggingface-xet|modelscope|aria2|rclone|git-lfs] \
  [--profile balanced|throughput] [--apply] [--verify sha256|size]
```

Behavior:

- default is a dry plan; `--apply` authorizes the large write;
- `auto` means the manifest's native provider, never an unreviewed public
  mirror;
- `balanced` leaves Xet adaptive defaults in place and bounds file workers;
- `throughput` enables `HF_XET_HIGH_PERFORMANCE=1`, warns that it intentionally
  consumes machine resources, and remains the recommended dedicated-download
  profile;
- a rerun uses the same persistent destination and exact revision;
- the task never deletes incomplete data automatically;
- tokens come from the provider's supported environment/keychain path, are
  never placed in the manifest or command line, and are redacted from logs;
- success means selected-tree completeness plus verification, not merely a zero
  downloader exit code.

For the existing canary, replace its direct download call with this library
entry point or call the same provider object. Do not make one mise task invoke
another task through shell text; both tasks should call the shared Python
library.

## Verification and supply-chain rules

1. Require a full immutable revision. Reject `main` for an applied transfer.
2. Record the repository tree before download. Dry-run output is part of the
   capacity and review gate.
3. Treat file size as a progress/capacity check, not integrity.
4. Verify every LFS/Xet weight against the upstream LFS SHA-256. Full hashing
   costs one sequential local read but is appropriate after a 100 GB-2 TB
   acquisition. Small Git files without an upstream SHA-256 remain bound to
   the immutable repository tree; record their local SHA-256 in the receipt.
5. Parse container metadata after hashing: safetensors header/index references,
   expected shard count, and required configuration/tokenizer files.
6. Never turn a missing hash, unreachable metadata API, incomplete tree, or
   unverifiable mirror into green. Report `NOT_RUN`/`UNVERIFIED` distinctly.
7. Keep model license and access restrictions in the plan. Gated HF models
   require a user access grant and token; a mirror must never be used to bypass
   the gate. [HF gated-model documentation](https://huggingface.co/docs/hub/en/models-gated)
8. Mirroring is a separate publish/copy authorization. A successful download
   does not authorize redistribution. Preserve model cards, notices, and any
   custom license alongside mirrored bytes.

## Failure handling

- On network error, retain all destination and metadata bytes and instruct the
  user to rerun the same manifest. Never `force_download` automatically.
- If a download appears stalled, first confirm pinned `hf-xet >=1.5.2`, then
  capture `RUST_LOG=info` to a file and use Xet's macOS diagnostic wrapper.
  `hf-xet` provides a first-party macOS diagnostic script.
  [xet-core diagnostics](https://github.com/huggingface/xet-core#issues-diagnostics--debugging)
- Distinguish transfer progress from reconstruction progress. A progress bar
  can look still while Xet is reconstructing; current clients have improved
  aggregate reporting, but elapsed network/disk counters are stronger evidence.
- Do not enable `HF_HUB_DISABLE_XET` as a generic retry for files over 50 GB.
- If a single-file Xet restart is repeatedly unaffordable, stop and choose an
  owner-supported Git LFS/ModelScope/object-store source with Range resume;
  do not scrape a temporary CAS URL.
- Capacity failure is preflight, not a mid-transfer cleanup. Account for target
  bytes, incomplete parts/reconstruction, verification working space, and the
  configured cache. Never empty shared caches as part of the downloader.

## Bounded probes and evidence boundary

No throughput benchmark was run. A small-file benchmark would not predict a
400 GB reconstruction and any competing transfer could perturb the active GLM
download. Only bounded metadata/API reads were performed:

- Hugging Face returned the exact target repository at
  `fd9b461ac7cae4b921470d0db12230c6505bd03c`, public, ungated, MIT, with 149
  repository entries on 2026-08-11.
- ModelScope returned 404 for the exact `mastouri` repository and 200 for its
  different official `ZhipuAI/GLM-5.2` repository.
- Current release APIs were checked for `huggingface_hub` 1.27.0, `hf-xet`
  1.6.0, ModelScope Hub 0.2.0, rclone 1.75.0, Git LFS 3.7.1, and aria2 1.37.0.

These probes establish availability and client behavior, not comparative
throughput. After the active transfer finishes, benchmark the provider boundary
with a disposable 1-5 GB multi-shard public fixture, an isolated cache, and a
fixed network window. Compare balanced versus throughput profiles over at least
three fresh-cache runs and one interrupted-resume control. Record WAN bytes,
payload bytes, wall time, mean/peak throughput, CPU, peak RSS, disk writes,
temporary peak disk, and verified SHA-256. A repeat-cache run is a separate
deduplication experiment and must not be mixed with cold throughput.

## Primary sources

- Hugging Face: [download guide](https://huggingface.co/docs/huggingface_hub/en/guides/download),
  [cache guide](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache),
  [environment variables](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables),
  [`snapshot_download` implementation](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/_snapshot_download.py),
  and [Xet core](https://github.com/huggingface/xet-core).
- ModelScope: [Hub SDK](https://github.com/modelscope/modelscope_hub) and
  [download implementation](https://github.com/modelscope/modelscope_hub/blob/aa8dbf11ef4373faa83a9bc5d73f7dff6478b08b/src/modelscope_hub/_download.py).
- aria2: [official manual](https://aria2.github.io/manual/en/html/aria2c.html).
- rclone: [official documentation](https://rclone.org/docs/) and
  [HTTP backend](https://rclone.org/http/).
- Git LFS: [specification](https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md),
  [Batch API](https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md),
  and [configuration](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-config.adoc).
