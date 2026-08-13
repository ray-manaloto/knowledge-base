# Native pause semantics for the Colibri GLM-5.2 download

Date: 2026-08-12

## Question and scope

Does the exact transfer stack used by the Colibri canary —
`huggingface-hub==1.27.0`, `hf-xet==1.6.0`, and
`snapshot_download()` — expose a native pause/resume operation? If not, what
mechanism can pause the live transfer without converting pause into
cancellation plus a later restart?

This review used the installed wheels and the corresponding upstream tags:

- `huggingface_hub` v1.27.0 resolves to commit
  `a7d85da5de06e8b85e94999e7cf985f6e0f9991b`.
- `xet-core` v1.6.0 resolves to commit
  `de71453d952bd8b806edaa997c72313051a49050`.

## Verdict

**Neither `snapshot_download()` nor the public `hf-xet` 1.6.0 download API has
a pause/resume operation.** The native Xet controls are cancellation controls:
`XetFileDownload.cancel()`, `XetFileDownloadGroup.abort()`, and
`XetSession.sigint_abort()`. A subsequent `snapshot_download()` invocation can
reuse completed Hub files and locally cached Xet chunks, but that is
**cancel/restart with cache-backed recovery**, not resumption of the same live
task.

For this macOS-hosted tmux workflow, the available true in-process suspension
primitive is the operating system's **`SIGSTOP` / `SIGCONT` pair**, applied to
the exact receipt-identified Python/Xet process. `SIGSTOP` stops execution and
cannot be caught or ignored; `SIGCONT` continues a stopped process. The same
Python process, Xet session, Rust runtime, task handles, open files, and memory
remain alive across this suspension. Python documents both Unix signals and
`os.kill()` for signaling an exact process
([signal reference](https://docs.python.org/3/library/signal.html#signal.SIGSTOP),
[process signaling](https://docs.python.org/3/library/os.html#os.kill)).

This is OS-native suspension, not a Hugging Face/Xet feature. It survives a
ChatGPT Desktop restart because tmux owns the process, but not logout, reboot,
process death, or tmux-server termination.

## Evidence

### `snapshot_download()` has no control handle

The v1.27.0 signature returns only a completed snapshot path (or dry-run file
metadata). Its parameters include repository selection, cache/local directory,
patterns, and worker count; it exposes neither a task handle nor `pause`,
`resume`, `cancel`, or signal callbacks. It dispatches per-file downloads and
waits for them to finish
([v1.27.0 source](https://github.com/huggingface/huggingface_hub/blob/a7d85da5de06e8b85e94999e7cf985f6e0f9991b/src/huggingface_hub/_snapshot_download.py)).

The official download guide says `snapshot_download()` uses
`hf_hub_download()` internally and that downloaded files are cached. For a
`local_dir`, `.cache/huggingface/` metadata prevents re-downloading unchanged
files on a later invocation
([official guide](https://huggingface.co/docs/huggingface_hub/en/guides/download#download-an-entire-repository),
[local-folder behavior](https://huggingface.co/docs/huggingface_hub/en/guides/download#download-files-to-a-local-folder)).
That explains recovery after cancellation; it does not provide live task
suspension.

`resume_download` is not a hidden control. In v1.27.0 the validator removes it,
warns that it is deprecated and ignored, and states that downloads resume
whenever possible
([v1.27.0 validator](https://github.com/huggingface/huggingface_hub/blob/a7d85da5de06e8b85e94999e7cf985f6e0f9991b/src/huggingface_hub/utils/_validators.py)).
Here, "resume" means retry/re-entry using persistent artifacts, not pausing a
running call.

### `hf-xet` exposes abort/cancel, not pause/resume

The exact v1.6.0 Python bindings expose these relevant controls:

- `XetFileDownload.cancel()` cancels one download.
- `XetFileDownloadGroup.abort()` cancels all active downloads in a group.
- `XetSession.sigint_abort()` cancels all operations and destroys the session
  runtime; its documentation requires discarding the session before further
  transfers.
- Status values are `Running`, `Finalizing`, `Completed`, and `UserCancelled`.
  There is no `Paused` state.

The binding implementations contain no pause or resume method on
`XetSession`, `XetFileDownloadGroup`, or `XetFileDownload`
([session binding](https://github.com/huggingface/xet-core/blob/de71453d952bd8b806edaa997c72313051a49050/hf_xet/src/py_xet_session.rs),
[group binding](https://github.com/huggingface/xet-core/blob/de71453d952bd8b806edaa997c72313051a49050/hf_xet/src/py_file_download_group.rs),
[task binding](https://github.com/huggingface/xet-core/blob/de71453d952bd8b806edaa997c72313051a49050/hf_xet/src/py_file_download_handle.rs)).

`huggingface_hub`'s Xet path creates a global session, a file-download group,
and a background file task. On `KeyboardInterrupt`, it calls
`abort_xet_session()`, whose implementation performs `sigint_abort()` and
clears the session so that a later call creates a new one
([download integration](https://github.com/huggingface/huggingface_hub/blob/a7d85da5de06e8b85e94999e7cf985f6e0f9991b/src/huggingface_hub/file_download.py),
[session holder](https://github.com/huggingface/huggingface_hub/blob/a7d85da5de06e8b85e94999e7cf985f6e0f9991b/src/huggingface_hub/utils/_xet.py)).
Therefore Ctrl-C is conclusively an abort boundary.

### What persists after abort/restart

Xet reconstructs each file from content-addressed chunks and checks its local
chunk cache before transferring missing chunks. The official `hf-xet` package
description identifies chunk-based deduplication and a local disk cache as core
features
([v1.6.0 package source](https://github.com/huggingface/xet-core/tree/de71453d952bd8b806edaa997c72313051a49050/hf_xet)).
The Hub cache separately stores downloaded blobs and commit snapshots, and both
`snapshot_download()` and `hf_hub_download()` consult it
([official cache guide](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache)).

Consequently, cancellation is recoverable, but the granularity is artifact- and
chunk-cache reuse. The original task and runtime are gone, and partially
reconstructed output may require more work on the next invocation.

## Implementation recommendation for the Colibri task

Implement `pause` and `resume` as controlled process signaling around the
already detached tmux job:

1. Record and validate the Python PID plus its foreground process-group and tmux
   pane identity. Never discover it with a broad name match.
2. `pause` sends `SIGSTOP` to that exact Python/Xet PID, verifies it is stopped,
   and records `paused`, timestamp, pane, PID, and process-group identity.
3. `resume` revalidates that the recorded group still belongs to the same tmux
   pane, sends `SIGCONT`, verifies running state and renewed byte/progress
   movement, and updates the receipt.
4. Make both operations idempotent: pausing a stopped valid group and resuming a
   running valid group should report current state without launching duplicates.
5. If the process group is absent, `resume` must explicitly fall back to a new
   cache-backed invocation and label that outcome `restarted`, not `resumed`.

The live control arm refined the initial recommendation: stopping the complete
foreground group in the retained tmux pane was immediately undone on this
macOS job-control topology, while stopping the exact Python PID reliably held
the transfer. All Xet transfer concurrency is threads plus the Rust runtime
inside that process; the `mise` and `uv` ancestors remain idle. PGID and pane
identity remain validation evidence, not the signal target.

## Caveats and verification controls

- Suspension retains sockets but does not freeze remote servers or token
  expiry. After a long pause, `SIGCONT` may surface an expired connection or
  token and exercise the stack's retry/refresh logic. If the live task exits,
  recovery becomes cache-backed restart.
- `SIGSTOP` cannot run application cleanup or update a receipt. The controller
  must write the paused receipt only after independently observing stopped
  process state.
- A control test should pause during measurable byte transfer, prove bytes and
  CPU stop changing, resume, and prove the same Python PID/process group moves
  bytes again. A mutation that signals a wrapper PID or an unvalidated PID
  should fail this test.
- A second control should terminate the stopped group and prove `resume`
  reports `restarted` while reusing the same model revision and work directory.

## Conclusion

There is no library-native pause/resume facility in the pinned stack. Preserve
the distinction in the CLI and receipt model:

- `pause` / `resume`: `SIGSTOP` / `SIGCONT`, same live process and task.
- `stop` / `restart`: Xet abort or process termination, then a new
  `snapshot_download()` call that reuses durable caches.
