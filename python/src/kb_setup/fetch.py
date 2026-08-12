# Copyright (c) 2026 Raymond Manaloto
"""Lossless source ingestion for the KB, with a verbatim-token roundtrip contract.

Why this module exists
----------------------
`graphify add <url>` truncates. Measured against graphify 0.9.25 on 2026-07-24,
`ingest.py:159` slices the converted page at ``markdown[:12000]`` after running
the WHOLE page through ``markdownify`` with no boilerplate removal:

===================================  =======  ======  =====
page                                 full     kept    lost
===================================  =======  ======  =====
docs.astro.build config reference    109,913  12,000  89%
docs.scrapy.org topics/settings      92,886   12,000  87%
jestjs.io/docs/expect                84,864   12,000  86%
===================================  =======  ======  =====

Silently, exiting 0. That is this repo's signature defect class — a declaration
nothing observes.

The fix is NOT to compress or to hand-roll a splitter. Both were measured and
rejected:

* Compression cannot work even at its advertised rate: 67-71k chars minus a
  claimed 65% is still ~23-25k, twice the cap. It would corrupt the corpus AND
  still truncate.
* A splitter is unnecessary — graphify's FILE path already slices losslessly at
  heading boundaries. Verified byte-exact on the real sources (astro 84,110 ->
  5 slices, jest 67,249 -> 4, scrapy 68,189 -> 4; every rebuild equal to the
  original, control-armed by dropping a slice, which correctly failed).

So the whole fix is: **stop going through the URL path.** Fetch, extract, write a
file, and hand graphify the file — where its own tested oversize machinery
(``_FILE_CHAR_CAP``, ``expand_oversized_files``, ``slice_boundaries``) takes over.

The roundtrip contract
----------------------
The deciding risk is silent fidelity loss *upstream* of ingestion: a corpus that
looks complete, builds a graph, answers queries, and is wrong about a default,
with nothing able to notice. Truncation is the milder form — it loses a
contiguous tail. A rewriter is worse: it perturbs tokens scattered through
content that remains present and plausible.

:func:`sample_verbatim_tokens` + :func:`roundtrip_missing` are the observer.
Sample the load-bearing tokens from the RAW source, assert each survives
byte-exact downstream. Both directions are pinned in ``tests/test_fetch.py``: a
truncation, a flipped default, and a dropped code fence must each FAIL it.

Reproducibility
---------------
Nothing here stamps a timestamp into the written file. graphify's own
``_fetch_webpage`` writes ``captured_at: <now>``, which makes the same URL
produce a different file on every run. Provenance that changes per run is not
provenance — it is noise that defeats content hashing. The source URL and a
content hash go in the front matter instead; both are functions of the content.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# A fetch boundary returns (status, text, content_type). Injected so the unit
# tests need no network and no patching (tests/AGENTS.md: "prefer injecting the
# dependency over constructing it inside the function").
Fetcher = Callable[[str], "tuple[int, str, str]"]

# Below this, a 200 is a shell, not an article. An SPA bootstrap satisfies every
# render/HTTP success signal while carrying no content, so the acceptance gate
# must key on extracted VOLUME, never on status alone.
MIN_BODY_CHARS = 200

# Named so the gate reads as intent, not a magic literal.
HTTP_OK = 200

# graphify's own caps, named so a drift in either shows up as a diff here.
GRAPHIFY_URL_CAP = 12_000
GRAPHIFY_FILE_CAP = 20_000

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
# A fence line worth pinning: has real substance, not a lone brace or bracket.
_MIN_TOKEN_CHARS = 3


class FetchRejectedError(Exception):
    """A fetch failed the acceptance gate.

    The message ALWAYS carries the observed status code. `kb_setup.pr` printing
    "PR create failed" with the HTTP status discarded is why: a hard 500 was
    indistinguishable from flakiness and got retried three times before anyone
    looked.
    """


@dataclass(frozen=True)
class FetchResult:
    """A fetched source that passed the gate. `text` is never truncated."""

    url: str
    status: int
    text: str
    content_type: str

    @property
    def exceeds_url_cap(self) -> bool:
        """True when graphify's URL path would have silently discarded a tail."""
        return len(self.text) > GRAPHIFY_URL_CAP


def content_hash(text: str) -> str:
    """SHA-256 of the content. The repeatability witness."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sample_verbatim_tokens(text: str, *, minimum: int = 20) -> list[str]:
    """Load-bearing tokens that MUST survive ingestion byte-exact.

    Deterministic: first-appearance order, de-duplicated, no randomness — the
    same input yields the same sample, which is what makes repeatability
    measurable at all.

    Drawn from inline code spans and fenced-code lines rather than from prose,
    for two reasons. First, those are the tokens whose exactness IS the product
    of a reference corpus (identifiers, types, defaults, signatures). Second, a
    sampler that returned every word would make the contract tautological — any
    superset of the source would pass. `test_sampling_ignores_pure_prose_words`
    pins that.

    Headings are folded in only if the code-derived sample is thin, so a
    prose-heavy document still gets a usable contract.
    """
    tokens: list[str] = []
    seen: set[str] = set()

    def take(candidate: str) -> None:
        tok = candidate.strip()
        if len(tok) < _MIN_TOKEN_CHARS or tok in seen:
            return
        seen.add(tok)
        tokens.append(tok)

    for span in _INLINE_CODE.findall(text):
        take(span)
    for block in _FENCE.findall(text):
        for line in block.splitlines():
            take(line)
    if len(tokens) < minimum:
        for heading in _HEADING.findall(text):
            take(heading)
    return tokens


def roundtrip_missing(tokens: list[str], ingested: str) -> list[str]:
    """Sampled tokens absent from `ingested`, byte-exact. Empty list == passed.

    Substring, not fuzzy, and deliberately so: the failure this guards against
    is a rewriter that produces *plausible* text. Any tolerance here would let
    exactly the defect through.
    """
    return [t for t in tokens if t not in ingested]


def gate(*, status: int, text: str, min_chars: int = MIN_BODY_CHARS) -> str | None:
    """Reject reason, or None when the response is a usable article.

    Two arms, both earned:

    * **status** — measured 2026-07-24, `docs.astro.build/...index.md` returned
      404 with 38,469 bytes of HTML and `jestjs.io/llms.txt` 404 with 21,651. A
      status-blind fetcher ingests a 404 page as an article.
    * **volume** — an SPA shell returns 200 with nav chrome and no body.
    """
    if status != HTTP_OK:
        return f"HTTP {status}"
    body = text.strip()
    if len(body) < min_chars:
        return f"body too small: {len(body)} chars < {min_chars}"
    return None


def fetch_source(url: str, *, fetcher: Fetcher) -> FetchResult:
    """Fetch `url` through the injected boundary and gate the result.

    Never truncates. That is the entire point of this module.

    Raises:
        FetchRejected: with the observed status in the message.
    """
    status, text, content_type = fetcher(url)
    reason = gate(status=status, text=text)
    if reason is not None:
        msg = f"{url}: rejected ({reason})"
        raise FetchRejectedError(msg)
    return FetchResult(url=url, status=status, text=text, content_type=content_type)


def source_document(text: str, *, url: str) -> str:
    """The on-disk document: deterministic front matter + the untouched body.

    No timestamp, by design — see the module docstring. Every field here is a
    function of the content, so the same input produces the same bytes.
    """
    return (
        "---\n"
        f'source_url: "{url}"\n'
        f"content_sha256: {content_hash(text)}\n"
        f"content_chars: {len(text)}\n"
        "---\n\n"
        f"{text}"
    )


def write_source(target_dir: Path, stem: str, text: str, *, url: str) -> Path:
    """Write the source as `<target_dir>/<stem>.md` and return its path.

    Byte-identical for identical input, so two runs hash the same.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{stem}.md"
    out.write_text(source_document(text, url=url), encoding="utf-8")
    return out


def _source_body(text: str) -> tuple[str, str] | None:
    """Return ``(front_matter, body)`` for a file written by :func:`write_source`."""
    if not text.startswith("---\n"):
        return None
    front_matter, marker, body = text[4:].partition("\n---\n\n")
    return (front_matter, body) if marker else None


def _page_fields(receipt: Path, index: int, item: object) -> tuple[str, str, str, int] | str:
    """Validate one receipt row and return its typed fields or one error."""
    if not isinstance(item, dict):
        return f"{receipt}: page {index} is not a table"
    stem = item.get("stem")
    url = item.get("url")
    expected_hash = item.get("content_sha256")
    expected_chars = item.get("content_chars")
    if not isinstance(stem, str) or re.fullmatch(r"[A-Za-z0-9._-]+", stem) is None:
        return f"{receipt}: page {index} has an unsafe stem"
    if not isinstance(url, str) or not url.startswith("https://"):
        return f"{receipt}: {stem}: url must be https"
    if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        return f"{receipt}: {stem}: invalid content_sha256"
    if (
        not isinstance(expected_chars, int)
        or isinstance(expected_chars, bool)
        or expected_chars < 1
    ):
        return f"{receipt}: {stem}: invalid content_chars"
    return stem, url, expected_hash, expected_chars


def _verify_source_page(
    repo_root: Path,
    receipt: Path,
    fields: tuple[str, str, str, int],
) -> list[str]:
    """Verify one offline source body against its already typed receipt row."""
    stem, url, expected_hash, expected_chars = fields
    source = repo_root / "sources" / f"{stem}.md"
    if source.is_symlink() or not source.is_file():
        return [f"{receipt}: {stem}: source file missing or symlinked"]
    parsed = _source_body(source.read_text(encoding="utf-8"))
    if parsed is None:
        return [f"{receipt}: {stem}: malformed source front matter"]
    front_matter, body = parsed
    problems: list[str] = []
    if f'source_url: "{url}"' not in front_matter:
        problems.append(f"{receipt}: {stem}: source_url mismatch")
    if f"content_sha256: {expected_hash}" not in front_matter:
        problems.append(f"{receipt}: {stem}: front-matter hash mismatch")
    if f"content_chars: {expected_chars}" not in front_matter:
        problems.append(f"{receipt}: {stem}: front-matter char count mismatch")
    if content_hash(body) != expected_hash:
        problems.append(f"{receipt}: {stem}: body hash mismatch")
    if len(body) != expected_chars:
        problems.append(f"{receipt}: {stem}: body char count mismatch")
    return problems


def _receipt_tool(receipt: Path) -> tuple[str, dict[str, object]] | str:
    """Load a page receipt and return its currency-tool identity plus contents."""
    try:
        parsed = tomllib.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return f"{receipt}: unreadable receipt ({exc})"
    raw = {str(key): value for key, value in parsed.items()}
    tool = raw.get("tool")
    if not isinstance(tool, str) or not tool:
        return f"{receipt}: tool must name a currency.toml tool"
    return tool, raw


def verify_page_receipt(
    repo_root: Path,
    receipt: Path,
    *,
    required_urls: tuple[str, ...],
) -> tuple[str, ...]:
    """Verify every lossless offline page named by a ``*.pages.toml`` receipt.

    The receipt is a source manifest, not an extraction claim: this checks exact
    bytes/provenance while leaving semantic coverage to the Graphify build and
    extraction receipts. Unknown or malformed rows fail closed.
    """
    loaded = _receipt_tool(receipt)
    if isinstance(loaded, str):
        return (loaded,)
    _tool, raw = loaded
    pages = raw.get("page")
    if not isinstance(pages, list) or not pages:
        return (f"{receipt}: page must be a non-empty array",)

    problems: list[str] = []
    seen: set[str] = set()
    receipt_urls: set[str] = set()
    for index, item in enumerate(pages, start=1):
        fields = _page_fields(receipt, index, item)
        if isinstance(fields, str):
            problems.append(fields)
            continue
        stem = fields[0]
        if stem in seen:
            problems.append(f"{receipt}: duplicate stem {stem!r}")
            continue
        seen.add(stem)
        url = fields[1]
        if url in receipt_urls:
            problems.append(f"{receipt}: duplicate url {url!r}")
            continue
        receipt_urls.add(url)
        problems.extend(_verify_source_page(repo_root, receipt, fields))
    required = set(required_urls)
    problems.extend(
        f"{receipt}: required url missing from receipt: {url}"
        for url in sorted(required - receipt_urls)
    )
    problems.extend(
        f"{receipt}: receipt url is not required by currency.toml: {url}"
        for url in sorted(receipt_urls - required)
    )
    return tuple(problems)


def _required_urls(repo_root: Path, receipt: Path) -> tuple[str, ...] | str:
    """Resolve a receipt's independent required URL set from currency.toml."""
    loaded = _receipt_tool(receipt)
    if isinstance(loaded, str):
        return loaded
    tool, _raw = loaded
    from kb_setup.currency import config

    try:
        specs = config.load(repo_root)
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        return f"{receipt}: cannot load currency.toml ({exc})"
    spec = next((candidate for candidate in specs if candidate.name == tool), None)
    if spec is None:
        return f"{receipt}: currency.toml has no [tool.{tool}]"
    if not spec.docs_watch:
        return f"{receipt}: [tool.{tool}] docs_watch must be non-empty"
    return spec.docs_watch


def fetch_verify_main(repo_root: Path, receipts: list[Path]) -> int:
    """CLI boundary for the offline-page receipt gate."""
    if not receipts:
        print("kb-setup fetch-verify <sources/*.pages.toml>")
        return 2
    problems: list[str] = []
    for receipt in receipts:
        required_urls = _required_urls(repo_root, receipt)
        if isinstance(required_urls, str):
            problems.append(required_urls)
            continue
        problems.extend(verify_page_receipt(repo_root, receipt, required_urls=required_urls))
    for problem in problems:
        print(f"[kb-fetch-verify] FAIL: {problem}")
    if problems:
        return 1
    print(f"[kb-fetch-verify] OK: {len(receipts)} receipt(s)")
    return 0


class _UpstreamRule(Protocol):
    def __call__(self, path: str) -> str | None: ...


def _jest(path: str) -> str | None:
    """jestjs.io/docs/<slug> -> the Docusaurus source in jestjs/jest."""
    m = re.fullmatch(r"/docs/(?:next/)?([\w-]+)/?", path)
    if not m:
        return None
    slug = m.group(1)
    known = {"expect": "ExpectAPI", "getting-started": "GettingStarted", "api": "GlobalAPI"}
    name = known.get(slug)
    if name is None:
        return None
    return f"https://raw.githubusercontent.com/jestjs/jest/main/docs/{name}.md"


def _scrapy(path: str) -> str | None:
    m = re.fullmatch(r"/en/latest/(.+?)\.html", path)
    if not m:
        return None
    return f"https://raw.githubusercontent.com/scrapy/scrapy/master/docs/{m.group(1)}.rst"


def _astro(path: str) -> str | None:
    m = re.fullmatch(r"/en/(.+?)/?", path)
    if not m:
        return None
    return (
        "https://raw.githubusercontent.com/withastro/docs/main/src/content/docs/en/"
        f"{m.group(1)}.mdx"
    )


# A CURATED table, not a guesser. Returning None is the safe answer: the caller
# falls back to fetching the rendered page, which always works. A mapper that
# answered for every host would silently 404 into the fallback anyway, so
# guessing buys nothing and costs a wrong-source risk.
_UPSTREAM_RULES: dict[str, _UpstreamRule] = {
    "jestjs.io": _jest,
    "docs.scrapy.org": _scrapy,
    "docs.astro.build": _astro,
}


def http_fetcher(url: str) -> tuple[int, str, str]:
    """The real network boundary. Kept out of the pure core so tests inject.

    Two layers restrict the scheme, and neither is a silenced warning:

    * an explicit ``startswith`` guard — ruff S310's *documented* fix; and
    * a **scheme-restricted opener**, built from only the http/https handlers.
      The default opener carries a ``FileHandler``; this one does not, so
      ``file:`` cannot be opened at all. The property holds by construction.

    The second layer is load-bearing, and finding that out took a probe rather
    than a guess. Ruff's own documented fix does NOT silence S310 in 0.15.22 —
    copying the doc's "Recommended Fix" example verbatim still raises it
    (control arm: `--select S` correctly flagged a genuinely-unguarded file, so
    the probe discriminates). Upstream astral-sh/ruff#7918, "Avoid raising S310
    if user explicitly checks for URL scheme", is still OPEN. So the docs
    describe an intended behaviour the implementation has not shipped.

    Uses urllib rather than a bespoke ``HTTPSConnection`` loop: urllib already
    follows redirects and handles keep-alive/chunked correctly, and
    `use-tool-builtins` says reimplementing that is the wrong trade.

    A non-200 is RETURNED, never raised, so :func:`gate` decides — and so the
    observed status reaches the caller's error message intact.
    """
    import urllib.error
    import urllib.request

    if not url.startswith(("http:", "https:")):
        msg = f"{url}: refused (http/https only)"
        raise FetchRejectedError(msg)
    opener = urllib.request.build_opener(urllib.request.HTTPHandler, urllib.request.HTTPSHandler)
    opener.addheaders = [("User-Agent", _USER_AGENT)]
    try:
        with opener.open(url, timeout=60) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8", errors="replace"),
                resp.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), ""
    except urllib.error.URLError as exc:
        msg = f"{url}: unreachable ({exc.reason})"
        raise FetchRejectedError(msg) from exc


def extract_markdown(html: str) -> str:
    """Article body as markdown, via trafilatura.

    trafilatura is Apache-2.0 — the same licence as graphify, which matters
    because graphify removed `html2text` purely on copyleft grounds (PR #586).
    Measured against the markdownify path graphify uses today, it removes 17-37%
    of a docs page, all of it nav/sidebar/footer chrome.

    Optional import: the upstream-source path needs no extractor at all, so a
    caller who only ever ingests authored markdown should not be forced to
    install one.
    """
    try:
        import trafilatura
    except ImportError as exc:  # pragma: no cover - environment-dependent
        msg = "trafilatura is required to extract HTML; install it or use an upstream .md source"
        raise FetchRejectedError(msg) from exc
    out = trafilatura.extract(
        html, output_format="markdown", include_tables=True, include_links=True
    )
    if not out:
        msg = "trafilatura extracted no article body (likely a JS-rendered shell)"
        raise FetchRejectedError(msg)
    return out


def upstream_raw_url(url: str) -> str | None:
    """The authored source for a rendered docs URL, or None if unmapped.

    Preferred over scraping wherever it exists: exact authored markdown, real
    code fences, no HTML artifacts, and SHA-pinnable so the same URL yields the
    same nodes forever.

    It does NOT reduce size — measured, the upstream sources are no smaller than
    the extracted HTML (astro 84,116 vs 71,014; jest 67,249 vs 70,100; scrapy
    68,193 vs 67,791). It buys fidelity and reproducibility. Size is graphify's
    slicing problem, and already solved there.
    """
    m = re.fullmatch(r"https?://([^/]+)(/.*)?", url)
    if not m:
        return None
    host, path = m.group(1), m.group(2) or "/"
    rule = _UPSTREAM_RULES.get(host)
    if rule is None:
        return None
    return rule(path)


def name_from_url(url: str) -> str:
    """A stable file stem for a URL. Deterministic — no clock, no counter."""
    slug = re.sub(r"^https?://", "", url).rstrip("/")
    slug = re.sub(r"[^\w.-]+", "-", slug).strip("-").lower()
    return slug[:120] or "source"


def fetch_main(
    repo_root: Path,
    url: str,
    *,
    stem: str | None = None,
    fetcher: Fetcher = http_fetcher,
) -> int:
    """Fetch `url` losslessly into `sources/` and print the ingest evidence.

    Order is upstream-source first, then the rendered page through trafilatura.
    Nothing is truncated at any step; sizing is graphify's slicing problem and is
    already solved there (verified lossless, heading-aligned).

    Prints the observed status, both hashes, and the roundtrip verdict, because a
    gate that does not report what it saw is how a hard failure gets mistaken for
    flakiness.
    """
    upstream = upstream_raw_url(url)
    chosen = upstream or url
    kind = "upstream-source" if upstream else "rendered-page"
    print(f"[kb-fetch] {kind}: {chosen}")

    try:
        result = fetch_source(chosen, fetcher=fetcher)
    except FetchRejectedError as exc:
        if upstream is None:
            print(f"[kb-fetch] REJECTED {exc}")
            return 1
        print(f"[kb-fetch] upstream failed ({exc}); falling back to the rendered page")
        try:
            result = fetch_source(url, fetcher=fetcher)
        except FetchRejectedError as fallback_exc:
            print(f"[kb-fetch] REJECTED {fallback_exc}")
            return 1
        kind = "rendered-page"

    body = result.text
    if kind == "rendered-page" and "html" in result.content_type.lower():
        body = extract_markdown(body)
        print(f"[kb-fetch] extracted {len(body):,} chars from {len(result.text):,} of HTML")

    tokens = sample_verbatim_tokens(body)
    out = write_source(repo_root / "sources", stem or name_from_url(url), body, url=url)
    written = out.read_text(encoding="utf-8")
    missing = roundtrip_missing(tokens, written)

    print(f"[kb-fetch] status={result.status} chars={len(body):,} -> {out}")
    print(f"[kb-fetch] content_sha256={content_hash(body)}")
    print(f"[kb-fetch] roundtrip: {len(tokens)} tokens sampled, {len(missing)} missing")
    if len(body) > GRAPHIFY_URL_CAP:
        lost = len(body) - GRAPHIFY_URL_CAP
        pct = 100 * lost / len(body)
        print(
            f"[kb-fetch] NOTE: `graphify add <url>` would have discarded "
            f"{lost:,} chars ({pct:.0f}%) of this page"
        )
    if missing:
        print(f"[kb-fetch] FAIL: tokens lost in write: {missing[:5]}")
        return 1
    print(f"[kb-fetch] OK — ingest with: graphify add {out}")
    return 0
