---
name: artifact-download
description: Plan, resume, and verify large immutable model or dataset downloads. Use for Hugging Face snapshots, very large weights, transfer tuning, disk preflight, or download receipts.
---

# Artifact download

Use the project transfer boundary; it delegates bytes to a locked upstream SDK.

1. Query Graphify for the source, immutable revision, and prior transfer receipts.
2. Plan without payload transfer:

   ```text
   mise run kb-artifact-download -- --source OWNER/REPO --revision COMMIT_SHA --destination PATH --include PATTERN
   ```

3. Check the selected files, byte total, free disk, provider versions, and revision match in the receipt.
4. Add `--apply` only when the user has authorized the download. Reuse the same destination so Hugging Face can retain completed files and its local resume metadata.
5. Finish only when `.artifact-download.json` says `complete`. A `failed` or missing receipt is not success.

Profiles:

- Default `balanced` lets Xet adapt its concurrency.
- Add `--profile high-performance` only on a machine with at least 64 GB RAM when saturating CPU, disk, and network is acceptable.
- Add `--range-gets N` only for a measured comparison; it overrides one Xet concurrency control.
- Add `--verify-sha256` when the provider exposes file hashes and the extra full-disk read is justified.

The implemented provider is `hf-xet`. A stable HTTP URL plus checksum may later use aria2, and a verified object-store mirror may later use rclone, but neither is an interchangeable accelerator for Xet-backed Hugging Face repositories.
