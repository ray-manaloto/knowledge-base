# Signer isolation for the graphify live receipt: research report

Research subagent, 2026-10-03. Read-only: nothing in the repo, settings, accounts, keychain, GitHub or system was changed, and no secret value was printed.

**Inputs read:**

- `.agent/kb/reports/agents/zero-human-merge-research-final.md`
- `.github/workflows/graphify-live-receipt.yml`
- `.github/graphify/allowed-signers`, with the key body elided
- `python/src/kb_setup/live_receipt.py:280-318`
- `git show 4b31be8d:python/src/kb_setup/live_receipt_produce.py`, lines 1-30 and 670-720

## 0. The question, restated

A receipt can lie in two ways, and they need different fixes.

- **T1, a forged receipt.** The agent signs a receipt without running the cases. Isolating the key closes this. Today the signing key is an ordinary file that the agent's user can read, so the signature proves nothing (prior report, fact 3).
- **T2, a lying run.** The cases really run, but the code under test is the PR's own code, and that code controls the outputs.
  - The verifier checks only the signature, the PR/head binding and the `uv.lock`/manifest hashes (`live_receipt.py:200-207, :227-241`). Everything else is self-reported (`:148-171, :259-266`).
  - Isolating the key does nothing against T2. Only sandboxing plus base-owned assertions can narrow it, and none of the options removes it.

Every proposal below is rated against both T1 and T2.

## 1. Local facts (read-only probes)

| command | rc | result |
|---|---|---|
| `sw_vers` | 0 | macOS **27.0.1** (26A434) |
| `uname -m` | 0 | arm64 |
| `ssh -V` | 0 | **OpenSSH_10.3p1**, LibreSSL 3.3.6 (Apple's `/usr/bin/ssh-keygen`) |
| `id` | 0 | uid 501 `rmanaloto`. **Member of group 80 `admin`** |
| `dscl . -read /Groups/admin GroupMembership` | 0 | `root rmanaloto` |
| `sudo -n true` | **1** | "a password is required". There is no NOPASSWD rule |
| `/bin/ls -l /etc/pam.d/sudo_local` | 1 | file absent, so Touch ID for sudo is not configured |
| `/bin/ls -led /Users/rmanaloto` | 0 | `drwxr-x---+ rmanaloto staff`, ACL `group:everyone deny delete` |
| `/usr/bin/stat` on `/Users/Stephanie` | 0 | `drwxr-x--- Stephanie staff`. **The macOS default home is group-`staff`, r-x** |
| `/usr/bin/stat` on `/opt/homebrew` and `/opt/homebrew/bin` | 0 | **`rmanaloto admin`**, and `bin` is group-writable |
| `/usr/bin/stat` on `/Applications` | 0 | `drwxrwxr-x root admin` |
| `csrutil status` | 0 | SIP enabled |
| `fdesetup status` | 0 | FileVault on |
| `ls -la /etc/sudoers.d` | 0 | one root-only 0440 file (contents not read) |
| `command -v …` | 0 | present: `sandbox-exec`, `docker`/`colima` (mise shims), `orb`/`orbctl`. **Absent: Apple `container`, `podman`** |
| `ls -l /usr/lib/ssh-keychain.dylib` | 0 | present (387,728 bytes) |

**What these imply for any local signer:**

1. **The agent user is an admin.** It cannot `sudo` without the password, but it can still do the following:
   - write `/Applications` (admin group);
   - pop a GUI authorization dialog (`osascript … with administrator privileges`) that a human might approve by reflex;
   - read most of any other user's home, because macOS creates homes as 0750 group `staff`. The signer user's home must be `chmod 700`.
2. **`/opt/homebrew` is owned by the agent user.** A signer daemon that runs any Homebrew binary (git, python, uv, gh, openssh) can be trojaned by the agent. The same holds for anything under `~rmanaloto/.local/share/mise`.
   - The signer must use only root-owned system binaries (`/usr/bin/ssh-keygen`, `/usr/bin/git`) or tools installed inside its own 0700 home.
   - **This is the single most common way a "separate user" signer silently fails.**
3. **`sudo` needs a password,** so the agent cannot install or alter a LaunchDaemon in `/Library/LaunchDaemons` without the human. That is good, and it must stay true: never add a NOPASSWD rule or `pam_tid` "for convenience".

## 2. Primary-source facts used below

**OpenSSH (local man page, 10.3p1):**

- `ssh-keygen -Y sign -f` "may refer to either a private key, or a public key with the private half available via ssh-agent(1)".
- Supported FIDO types are `ecdsa-sk` and `ed25519-sk`. Generation options include `no-touch-required`, `verify-required` and `resident`.
- "FIDO authenticators generally require the user to explicitly authorise operations by touching or tapping them."
- `SSH_SK_PROVIDER` overrides the built-in USB HID middleware.

**Allowed-signers file:**

- The only options are `cert-authority`, `namespaces=`, `valid-after=` and `valid-before=`. Upstream `sshsig.c` (`sshsigopt_parse`) parses exactly these four and has no user-presence check.
- **So `-Y verify` accepts a no-touch `-sk` signature exactly like a touched one. The allowlist cannot demand touch.**
- This is my reading of the man page and the source; I did not arm it with a real sk key.

**The verifier is key-type agnostic.** `live_receipt.py:294-318` runs `ssh-keygen -Y verify -f allowed-signers -I SIGNER -n NAMESPACE`, so any key type placed in `.github/graphify/allowed-signers` verifies. Today that file holds one `ssh-ed25519` key with `namespaces="graphify-live@ray-manaloto.github"`.

**The unmerged producer** (4b31be8d, around lines 676-694):

- It requires `private_key.is_file()` and mode `& 0o077 == 0`, then runs `ssh-keygen -Y sign -f <private key>`.
- A FIDO/Secure Enclave key-handle file passes those checks.
- An agent-only key (Secretive) would need a small producer change to accept a `.pub` path plus `SSH_AUTH_SOCK`.

**macOS Secure Enclave SSH keys:**

- Since macOS 26 ("Tahoe"), `/usr/lib/ssh-keychain.dylib` implements the SecurityKeyProvider interface backed by the Secure Enclave.
- Key creation: `sc_auth create-ctk-identity -l ssh -k p-256-ne -t {bio|pin|none}`.
- Export of handle and public key: `ssh-keygen -w /usr/lib/ssh-keychain.dylib -K -N ""` produces `id_ecdsa_sk_rk`.
- Use: `SSH_SK_PROVIDER=/usr/lib/ssh-keychain.dylib`.
- Sources: gist arianvp/5f59f1783e3eaf1a2d4cd8e952bb4acf, ewpratten.com/blog/ssh-secure-enclave, notes.billmill.org (2025-11).
- These are community write-ups, not Apple docs. Apple has not documented this in a page I could reach. **UNVERIFIED on this host.** That `-Y sign` works through the provider is inferred, because git SSH signing uses `ssh-keygen -Y sign`; not armed.
- `-t none` means no Touch ID, so it is zero-human. But then any process running as that user can sign.

**Secretive** (README):

- Secure Enclave keys are non-exportable.
- Keys can require Touch ID or Apple Watch, and the app "notifies you whenever your keys are accessed".
- It supports YubiKey smart cards.
- The README does not document an option for no authentication, the key types, or the socket path; those live in its FAQ. **UNVERIFIED here.**

**launchd.plist(5)** (local man page):

- `UserName`/`GroupName` are "only applicable for services that are loaded into the privileged system domain". So a LaunchDaemon in `/Library/LaunchDaemons` needs root to install.
- `Sockets` supports `SockPathName`, `SockPathOwner`, `SockPathGroup` and `SockPathMode`.
- `QueueDirectories` keeps the job alive while a directory is non-empty.
- `WatchPaths` is "highly discouraged … race-prone".

**sandbox-exec(1)** (local man page): "The sandbox-exec command is DEPRECATED". It is still present on 27.0.1 and still works. Claude Code's and Codex's macOS sandboxes are built on the same Seatbelt mechanism (general knowledge, not re-verified here).

**Apple `container`** (README): "a Mac with Apple silicon", "supported on macOS 26", and each container runs as a lightweight VM. The README does not document network egress controls (UNVERIFIED). It is not installed here.

**GitHub** (docs fetched 2026-10-03):

- `pull_request` runs the merge ref's workflow file, and **secrets ARE passed for same-repo PRs**.
  - So under `pull_request` the PR can edit the workflow and exfiltrate secrets or skip the cases.
  - Fork PRs get no secrets.
- `pull_request_target` runs the base workflow with secrets: "Running untrusted code on the `pull_request_target` trigger may lead to security vulnerabilities … cache poisoning and granting unintended access to write privileges or secrets."
- Secure use: "Self-hosted runners should almost never be used for public repositories on GitHub, because any user can open pull requests against the repository and compromise the environment". They "can be persistently compromised by untrusted code in a workflow".
- Environments: "a job cannot access environment secrets until one of the required reviewers approves it".
  - There is an option to "prevent self-reviews".
  - Admins can bypass by default, but this is configurable.
  - For PUBLIC repos on the Free plan, required reviewers and wait timers are available. Custom deployment protection rules are Pro/Team/Enterprise only (as the docs page states).
- Artifact attestations: `actions/attest@v4` (the docs now name this, not `attest-build-provenance`) needs `id-token: write`, `attestations: write` and `contents: read`. It works on any file via `subject-path`, and you verify with `gh attestation verify <file> -R owner/repo`.
  - Attestations "establish where and how your software was built". That is provenance, not correctness.
  - The plan and visibility matrix was not on that page (UNVERIFIED here; public repos are generally supported).
- Claude Code in Actions:
  - `CLAUDE_CODE_OAUTH_TOKEN` comes from `claude setup-token` and is subscription-billed.
  - Alternatively, OIDC workload identity federation to a Claude Console service account. That is API-billed, so `do-not.md` #4 territory.
- Codex auth: "Use API key authentication for programmatic Codex CLI workflows, such as CI/CD jobs." The ChatGPT login can be carried over by copying `~/.codex/auth.json` ("Treat ~/.codex/auth.json like a password"), which the docs reserve for trusted environments.

## 3. Proposals

### P-A: separate macOS user plus a LaunchDaemon holding a 0600 key (the honest minimum for T1)

**Mechanism:**

- Create a standard (non-admin) user `_kbsigner`, or a hidden role account with a home.
- Install a root-owned plist at `/Library/LaunchDaemons/…kbsigner.plist` with `UserName=_kbsigner`.
- Its program is root-owned or `_kbsigner`-owned, and **never** comes from `/opt/homebrew` or the owner's mise.
- It holds an `ed25519` key at `~_kbsigner/.ssh/receipt_ed25519`. The home is mode 700 and the key is 0600.
- It also holds its own GitHub credential (P7-style): a fine-grained token or App key that can write only `graphify-live-evidence`, protected by a ruleset.

**Request channel:**

- Best is no channel at all. The daemon polls GitHub (via `StartInterval`) for open PRs whose scope is REQUIRED and fetches the head itself.
- The agent then has no input surface beyond "open a PR", which it already has.
- If a trigger is wanted:
  - use a `Sockets` entry with `SockPathName` in `/var/run/kbsigner.sock`, `SockPathOwner=_kbsigner`, and a mode letting group `staff` connect. Accept only `{pr:int, head:40-hex}` and re-derive everything from GitHub;
  - or use a `QueueDirectories` spool such as `/Users/Shared/kbsigner-queue`, mode 1733 (sticky, so writers cannot read or delete each other's entries), and parse it as untrusted data.
- Never accept files or paths from the agent, and never use `WatchPaths` (the man page calls it race-prone).

**Key exposure:**

- Agent user `rmanaloto`: cannot read the key, provided the 0700 home and 0600 key hold, the agent has no sudo, and FileVault plus SIP are on.
- Root can read it. The human, using the password, can read it.

**What the agent can and cannot do afterwards:**

- It **can** open PRs and trigger runs.
- It **cannot** sign, or write to the evidence branch, once P7 removes its admin GitHub token. Without P7 the agent's `repo`+`admin:org` PAT can still edit `allowed-signers` on main by merging around the check, or delete protection (prior report, fact 1). **So P-A is meaningless without P7.**

**Keeping PR code away from the key:** the daemon must not run the cases as `_kbsigner`. Use a third user (`_kbrunner`) or the P-F sandbox, so PR code cannot read `_kbsigner`'s home. Running the cases as `_kbsigner` puts PR code next to the key: a single `cat ~/.ssh/receipt_ed25519` in a hostile extraction script takes the key.

**What a hostile PR can still do:** all of T2. Its graphify code can emit whatever outputs the assertions want. If the runner is not sandboxed, it can also exfiltrate the LLM credentials the runner holds (claude/codex logins) and pivot to the other user's files.

**Pros:** native, free, and exactly what the producer already assumes ("The private key stays on the authenticated host"). It closes T1 fully.

**Cons:**

- The laptop must be on and logged in.
- LLM logins for claude and codex must exist under the runner user. Their OAuth and keychain items are per-user, and whether `claude`'s OAuth works from a daemon with no GUI session is UNVERIFIED, so a `setup-token`-style long-lived token may be needed.
- Admin-group pitfalls apply (section 1).

**Effort:** medium, about 1-2 sessions of code plus a human hour.

**One-time human steps:**

1. Create the user(s) in System Settings.
2. `sudo` to install the plist and its program and set the 0700/0600 modes.
3. Log the runner into claude and codex.
4. Create the evidence-branch credential.
5. Do P7.

### P-B: hardware-backed key (Secure Enclave, Secretive, YubiKey)

**Mechanism options:**

- **Secure Enclave via `sc_auth … -t none`** plus `SSH_SK_PROVIDER=/usr/lib/ssh-keychain.dylib`. Zero-human, non-exportable. *But any process running as the key's user can sign*, so it must be owned by `_kbsigner` (P-A), not by the owner.
- **Secure Enclave or Secretive with `-t bio` / Touch ID:** the key is unusable without a human touch. **Not zero-human.**
- **YubiKey FIDO2 (`ed25519-sk`):**
  - With default user-presence it needs a touch per signature, so **not zero-human**.
  - With `-O no-touch-required` it is zero-human, but any same-user process with the key handle can sign while the token is plugged in.
- `ssh-keygen -Y sign` works with all of these. The verifier needs no change (key-type agnostic); only the producer may need the `.pub` / agent change.

**Where the key lives:** in the chip. It cannot be stolen, only *used*.

**What this buys over P-A:**

- It turns "steal the key once, forge forever" into "use the signer only while on this machine".
- Revocation is rarely needed.
- It does **not** help if the agent's user can invoke it.

**Keeping PR code away:** same as P-A. Signing access is per-user, so PR code must run as another user or in a sandbox.

**What a hostile PR can still do:** T2 unchanged.

**Pros:** no key file to exfiltrate, and a signature proves "made on this Mac by that user".

**Cons:**

- Secure Enclave access from a LaunchDaemon with no login session is UNVERIFIED. CTK identities live in the user's data-protection keychain, which may require a GUI/login session, which would push this to a LaunchAgent plus an always-logged-in `_kbsigner` session.
- Not portable or backed up; losing the Mac means re-enrolling the public key in `allowed-signers`.
- Touch variants defeat zero-human.

**Effort:** low on top of P-A, plus one probe session to arm `sc_auth`/`-Y sign`/daemon context.

**Human steps:** create the identity while logged in as `_kbsigner`, then commit its `.pub` to `allowed-signers` through a human merge.

**Recommended variant:** P-A plus a Secure Enclave `-t none` key owned by `_kbsigner`, if the daemon-context probe passes. Otherwise P-A with a file key.

### P-C: keychain item with an access-control list restricted to one app

**Mechanism:**

- A small code-signed signer app or tool stores the key in the login keychain. Either use a legacy file-keychain item whose ACL trusted-app list is the app's designated requirement, or use a data-protection keychain item in an access group.
- Same-user processes are refused, or prompted, when they read the item.

**Key exposure:** better than a plain file, because other binaries cannot silently read the item. But:

- The app is a **signing oracle**: any same-user process (the agent) can ask it to sign unless it authenticates the caller, and the agent can always run it.
- A legacy ACL prompt ("Always Allow") is a human click, and a careless click widens the ACL.
- Data-protection access groups need entitlements, which means a provisioning profile and an Apple Developer account. UNVERIFIED cost.
- The agent is admin and owns `/opt/homebrew`; if the app lives in an agent-writable path it can be replaced. Its code signature then changes, so the ACL denies it, which is good, but it then prompts the human.

**What the agent can do afterwards:** invoke the app. It cannot copy the key.

**What a hostile PR can still do:** T2, plus T1 *through the oracle*, unless the app itself runs the cases and refuses ad-hoc payloads. If it does that, it has become P-A in the same user, and PR code runs as the same user, so it can drive the oracle.

**Pros:** no second user.

**Cons:** the same-user boundary is weak by design on macOS. App and keychain ACLs protect secrets from *other apps*, not from code that runs as you and can invoke the trusted app. These are also the most macOS-specific and least documented APIs in the set.

**Effort:** medium-high (Swift tool, signing, entitlements).

**Verdict: not recommended.** It looks like isolation but stays inside the agent's trust boundary.

### P-D: sign in GitHub Actions on a GitHub-hosted runner (no laptop key)

**Mechanism:**

- A workflow on a trusted trigger runs the 8 cases on `ubuntu-latest`. Use `pull_request_target` with an `if:` that requires `head.repo.full_name == github.repository` and an allowlisted actor, or `workflow_run`.
- It then either:
  - **D1:** signs with an SSH key held in an *environment secret* (environment `live-signer`, deployment branches restricted), or
  - **D2:** emits a **GitHub artifact attestation** (`actions/attest@v4`, OIDC, keyless Sigstore) over the receipt.
- The verifier changes for D2 to `gh attestation verify receipt.json -R ray-manaloto/knowledge-base --signer-workflow .github/workflows/<file>@refs/heads/main`.
- Alternatively, make the live job itself the required check, so no receipt is needed at all.

**Where the key lives:** D1 in GitHub's secret store; D2 nowhere, since it is an ephemeral Fulcio certificate bound to the workflow identity. The laptop holds nothing.

**What the agent can do afterwards:** with its current admin PAT it can edit the workflow on main (by merging around the check) or the environment. P7 is still a prerequisite. With P7, the agent cannot sign at all.

**Keeping PR code away from the key:** this is the crux. The cases *must* execute PR code (graphify from the head's `uv.lock`) with LLM credentials. On `pull_request_target` that is literally the "pwn request" pattern.

- Mitigation is two jobs:
  1. Job 1 has no secrets except the LLM credentials. It runs the head in a container or VM-less runner and uploads outputs as an artifact.
  2. Job 2 has `attestations: write` and `id-token: write`, never checks out PR code, and attests job 1's artifact after running base-code assertions on it.
- On a GitHub-hosted runner each job is a fresh VM, so job 1's PR code cannot reach job 2's OIDC token.
- **The LLM credential in job 1 is still exposed to PR code.**
  - Claude: a subscription `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`), or OIDC workload identity federation to a Console service account, which is metered and conflicts with `do-not.md` #4.
  - Codex: the docs say to use an API key for CI (metered); a copied ChatGPT `auth.json` is for trusted environments only.

**What a hostile PR can still do:**

- T2 as always.
- It can steal the LLM token in job 1. That cost is bounded and revocable; the signing key is not exposed.
- Fork PRs: blocked by the `if:` guard. Otherwise a stranger's fork PR would run with secrets on a public repo.

**Zero-human:** D1 is zero-human only if the environment has **no required reviewers**, using just deployment-branch restrictions. Required reviewers make it a human click. D2 is zero-human.

**Pros:**

- No laptop key, no laptop uptime, an auditable run log, and Sigstore transparency (D2).
- Fresh VM per job.
- The verifier can pin the *workflow identity* rather than a key.

**Cons:**

- LLM credentials in CI: subscription tokens in CI are the risky part, and codex metering conflicts with policy.
- Hosted-runner minutes (free for public repos).
- The 8-case runtime has to fit the hosted runner.
- The "pwn request" design must be done right, and two-job artifact passing must be integrity-checked (attest the digest job 1 produced; job 2 recomputes it).

**Effort:** medium-high (2-3 sessions).

**Human steps:** create the environment and secrets, generate `CLAUDE_CODE_OAUTH_TOKEN`, decide codex billing, and do P7.

### P-E: self-hosted runner under a separate macOS user

**Mechanism:** install the GitHub Actions runner on the laptop as user `_kbrunner` (launchd service), with labels used only by the live-receipt workflow. The cases run there with the laptop's subscription logins; signing is P-D's D2 (attestation via OIDC, so no local key) or D1.

**Key exposure:** with D2 there is no key on the laptop. The runner's registration token and OIDC capability are the asset, and they live in `_kbrunner`'s home.

**What the agent can do afterwards:** open PRs that trigger the runner. On a public repo, so can **anyone**: GitHub says self-hosted runners "should almost never be used for public repositories". Needs a strict `if:` (same-repo head, actor allowlist) and, ideally, a repo setting requiring approval for outside contributors' workflow runs.

**Keeping PR code away:** it isn't, by default. Jobs run as `_kbrunner` directly, non-ephemeral ("can be persistently compromised"). A container or VM per job (P-F) is required. A hostile PR can backdoor the runner and then forge future runs.

**What a hostile PR can still do:** T2, plus persistent compromise of the runner user, and through it every later "attested" run. Note the attestation then proves only "this workflow ran on that runner", not that the runner is honest.

**Pros:** uses the existing laptop logins (no metered CI LLM), keyless attestation, and GitHub drives scheduling and retries.

**Cons:** GitHub's own guidance against public-repo self-hosted runners; runner upkeep; laptop uptime.

**Effort:** medium.

**Human steps:** create the user, register the runner (a token from the repo settings), and do P7.

**Verdict:** strictly worse than P-A plus P-D2 unless jobs are VM-isolated.

### P-F: raise hostile-PR (T2) resistance: base-owned harness, sandboxed run, separate signer

This is not an alternative to P-A, P-D or P-E. It is how any of them runs the cases.

**Mechanism, in three phases:**

1. **Prepare** (trusted, base code). The signer side checks out the **base** commit's harness and case definitions and the **head's** inputs only: `uv.lock`, `sources/graphify.manifest`, the extraction tasks. This mirrors what the workflow already does (`graphify-live-receipt.yml` reads only `uv.lock` and the manifest from the head). Assertions, expected node/edge floors and fact audits come from base, so a PR cannot weaken the test.
2. **Execute** (untrusted, sandboxed). Run the head's graphify inside one of:
   - a VM-backed container (Apple `container` on macOS 26+, not installed here; or OrbStack or colima, both present), or
   - `sandbox-exec` with a deny-default profile (deprecated but working).

   The sandbox has a read-only mount of inputs, one writable output directory, **no access to either user's home**, and network egress limited to the LLM endpoints.

   Better still: no LLM credential inside the sandbox at all. A credential-injecting **egress proxy** owned by the signer side adds auth headers, so PR code never sees the token, and the proxy's log gives the signer independent evidence that real model calls happened (count, model id, bytes).
   - Claude Code honours `ANTHROPIC_BASE_URL`.
   - Whether `claude-cli` subscription OAuth and `codex` ChatGPT auth can be proxied this way is **UNVERIFIED** and likely the hard part.
3. **Sign** (trusted). A separate process reads only the output files, runs base-code assertions plus cross-checks against the proxy log, and signs. It never imports or executes anything from the head.

**What a hostile PR can still do:**

- Its graphify is still the thing under test. It can detect the harness and behave well only under test, or emit plausible fabricated graphs that pass base assertions.
- Without a credential proxy, it can steal the LLM token, and it can always burn quota.

**Pros:** turns "signature over self-reported numbers" into "signature over base-checked outputs from a box that could not touch the key". That is the strongest local position available.

**Cons:**

- The most engineering by far.
- Docker/OrbStack egress allowlisting needs a proxy or firewall container, since neither does per-domain allowlists natively. Apple `container` network controls are UNVERIFIED.
- `sandbox-exec` is officially deprecated.

**Effort:** high (3-5 sessions). **Human steps:** install the container runtime if Apple `container` is chosen; otherwise none beyond P-A.

### P-G: drop option C; fix false positives (#860) and keep a human merge for real extraction changes

**Mechanism:**

- Make `live_receipt_scope.py` precise: TOML-parsed `mise.toml`, an AST diff of `cli.py`, fail-closed (prior report P4).
- Most PRs then become EXEMPT. The few that truly change extraction (a graphify pin, `uv.lock` deps of graphify, extraction tasks) are merged by the human, after the human or a laptop run checks them.
- Optionally keep the producer as a convenience, signing with a Touch ID Secretive or YubiKey key. The touch *is* the human step, which makes the signature mean "the owner was present" honestly.

**Key exposure:** with a touch-required key, none worth stealing.

**What the agent can do afterwards:** merge every EXEMPT PR alone (with P7, via kb-land only), and nothing REQUIRED.

**What a hostile PR can still do:** the PR is visible to a human at exactly the moments it matters. A hostile PR could still try to make itself look EXEMPT; that is the scope classifier's fail-closed burden.

**Pros:** cheapest, no new infrastructure, no LLM credentials anywhere new, honest semantics.

**Cons:** not zero-human for the real cases. How rarely that bites depends on the post-#860 REQUIRED rate, which is unmeasured: the prior report found most triggers are false positives (96 of 108 tasks trip `\buv\b`).

**Effort:** low-medium (1 session plus one bootstrap human merge).

### P-H (prerequisite for every option): least-privilege agent credential (the prior report's P7)

- Replace the agents' classic `repo`/`workflow`/`admin:org` PAT with a repo-scoped fine-grained token: Contents, Pull requests and Issues write; Administration at most read; and **no write to `.github/graphify/allowed-signers` via an admin merge**.
- Add a ruleset making the evidence branch writable only by the signer identity, and keep `enforce_admins`.

Without this, every signer design is policy only, because the agent can edit the allowlist or protection. Only the owner can do it. Effort is low, roughly 15 minutes of human clicks.

## 4. Comparison

T1 is a forged receipt; T2 is a lying PR. "Agent-user key exposure" means the exposure after P-H is in place.

| Proposal | Agent-user key exposure | Zero-human | T1 resistance | T2 (hostile-PR) resistance | Ongoing cost | Effort |
|---|---|---|---|---|---|---|
| Status quo / P1-weak (key in agent's user) | **full**: readable file | yes | **none** | none | none | done |
| P-A separate user + LaunchDaemon, file key | none, if 0700 home, non-Homebrew binaries, no sudo | yes | strong | none alone; low with P-F | laptop uptime, LLM quota per head | medium |
| P-B Secure Enclave `-t none` under `_kbsigner` | none, and no file exists to steal | yes | strongest local | as P-A | as P-A | P-A + low (daemon-context probe UNVERIFIED) |
| P-B touch / bio / YubiKey-touch | none | **no** | strong, and proves presence | as P-A | a human touch per head | low |
| P-C keychain ACL, same user | **oracle**: cannot copy, can invoke | yes (or prompts) | weak | none | low | medium-high |
| P-D1 hosted runner + environment secret | none on laptop | yes, unless required reviewers | strong | low-medium (two-job split); LLM token exposed | CI LLM credentials, possibly metered | medium-high |
| P-D2 hosted runner + attestation (OIDC) | **no key exists** | yes | strongest | as D1 | as D1 | medium-high |
| P-E self-hosted runner, separate user | none (with D2) | yes | medium, since the runner can be persistently backdoored | low unless VM per job | laptop uptime; public-repo risk | medium |
| P-F base harness + sandbox + separate signer | n/a (layer) | yes | n/a | **best achievable**, still not complete | high maintenance | high |
| P-G fix #860, human merges real changes | n/a, or touch key | **no** for REQUIRED PRs | n/a | **human review** | human time on rare PRs | low-medium |
| P-H least-privilege agent token | prerequisite | n/a | **required for every row above** | n/a | none | low (human only) |

## 5. Recommendation

1. **Do P-H now.** It is the owner's action, and until it is done every signature is policy only. The agent can rewrite `allowed-signers` or protection with its current token.
2. **Do P-G next (fix #860).** It removes most of the pressure for zero-human: most REQUIRED verdicts are false positives. Measure the REQUIRED rate after the fix before building anything bigger.
3. **If zero-human is still wanted for real extraction changes, build P-A + P-B(`-t none`) + P-F-lite:**
   - a `_kbsigner` LaunchDaemon that polls GitHub (no request channel), so there is no agent input surface;
   - cases run as a third user (`_kbrunner`) inside an OrbStack, colima or Apple `container` VM with egress limited to the LLM endpoints;
   - assertions from **base**;
   - signing with a Secure Enclave key owned by `_kbsigner`, or a 0600 file key if the daemon-context probe fails;
   - evidence pushed with a credential only `_kbsigner` holds;
   - every binary from `/usr/bin` or `_kbsigner`'s own home, never `/opt/homebrew` or the owner's mise.
4. **Say plainly in the check's own docs** that the receipt proves "the base-defined live cases ran against this head on the owner's Mac and passed". It does not prove "this head is safe". A hostile graphify change can still pass, so T2 remains a human-review concern for supply-chain-shaped changes, such as a pin pointing at a new fork commit.
5. **Prefer P-D2 over P-E** if the owner would rather keep no key anywhere, accepting CI LLM credentials. Reject P-C (a same-user oracle) and P-E without per-job VMs.
6. **Before any build, arm the UNVERIFIED items:**
   - (a) `ssh-keygen -Y sign` with an `sc_auth -t none` key from a LaunchDaemon context;
   - (b) claude and codex auth from a non-GUI daemon user;
   - (c) the egress-allowlist mechanism for the chosen container runtime;
   - (d) whether a `no-touch-required` sk signature verifies (expected yes, per `sshsig.c`).

## 6. UNVERIFIED or ambiguous (do not rely on these without a probe)

- Secure Enclave `ssh-keychain.dylib` behaviour, from community write-ups only:
  - `-Y sign` through it;
  - use from a LaunchDaemon with no login session.
- Claude Code subscription OAuth and Codex ChatGPT auth under a daemon or runner user, and through a credential-injecting proxy.
- Apple `container` egress controls (not in the README).
- Secretive's no-auth option and socket path (not in the README).
- The plan availability of artifact attestations. That page did not state it.
- Whether `-Y verify` rejects a no-touch sk signature. Inferred "accepts" from the man page and `sshsig.c` option parsing; not armed.
- Keychain ACL details for P-C, from general knowledge of the Keychain Services ACL model; no Apple page fetched in this session.

## Citations

**Local man pages (this host):**

- `ssh-keygen(1)`: `-Y sign`, `-Y verify`, FIDO AUTHENTICATOR, ALLOWED SIGNERS, `SSH_SK_PROVIDER`
- `launchd.plist(5)`: `UserName`, `Sockets`/`SockPath*`, `QueueDirectories`, `WatchPaths`
- `sandbox-exec(1)`: DEPRECATED

**Web sources:**

- OpenSSH `sshsig.c`, master: https://github.com/openssh/openssh-portable/blob/master/sshsig.c
- macOS Secure Enclave SSH:
  - https://gist.github.com/arianvp/5f59f1783e3eaf1a2d4cd8e952bb4acf
  - https://ewpratten.com/blog/ssh-secure-enclave/
  - https://notes.billmill.org/link_blog/2025/11/Native_Secure_Enclave_backed_ssh_keys_on_MacOS.html
- Secretive: https://github.com/maxgoedjen/secretive
- Apple container: https://github.com/apple/container
- GitHub events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub secure use: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub environments: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- Claude Code GitHub Actions: https://code.claude.com/docs/en/github-actions
- Codex auth: https://learn.chatgpt.com/docs/auth (redirected from developers.openai.com/codex/auth)

**Repo:**

- `.github/workflows/graphify-live-receipt.yml`
- `python/src/kb_setup/live_receipt.py:280-318`
- `4b31be8d:python/src/kb_setup/live_receipt_produce.py:1-30, 670-720`
- `.agent/kb/reports/agents/zero-human-merge-research-final.md`

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base): workflow, verifier, unmerged producer and prior report (local, read-only)
- [openssh/openssh-portable](https://github.com/openssh/openssh-portable): `sshsig.c` allowed-signers option parsing and user-presence handling
- [maxgoedjen/secretive](https://github.com/maxgoedjen/secretive): Secure Enclave SSH agent capabilities
- [apple/container](https://github.com/apple/container): requirements and isolation model
- [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action): CI auth for the Claude cases (via the Claude Code docs)
