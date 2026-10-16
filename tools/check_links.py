#!/usr/bin/env python3
"""Check public HTTP(S) references separately from the offline documentation gate."""

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urlsplit
from urllib.request import Request, urlopen

from tools.validate_repo import ROOT, markdown_targets, repo_files


def external_links(root: Path = ROOT) -> dict[str, set[str]]:
    references = {}
    for path in repo_files(root):
        if path.suffix != ".md" or path.is_symlink():
            continue
        for target in markdown_targets(path.read_text(encoding="utf-8")):
            if urlsplit(target).scheme in {"http", "https"}:
                url = urldefrag(target)[0]
                references.setdefault(url, set()).add(str(path.relative_to(root)))
    return references


def check_url(url: str) -> tuple[str, str]:
    request = Request(
        url, headers={"User-Agent": "engineering-skills documentation link check"}
    )
    try:
        # GET avoids servers that reject HEAD; close without downloading the body.
        with urlopen(request, timeout=15) as response:
            status = response.status
            return ("OK" if 200 <= status < 300 else "UNVERIFIED", f"HTTP {status}")
    except HTTPError as exc:
        exc.close()
        state = "BROKEN" if exc.code in {404, 410} else "UNVERIFIED"
        return state, f"HTTP {exc.code}"
    except (URLError, OSError, ValueError, HTTPException) as exc:
        return "UNVERIFIED", str(exc)


def check(root: Path = ROOT) -> int:
    references = external_links(root)
    urls = sorted(references)
    counts = {"OK": 0, "BROKEN": 0, "UNVERIFIED": 0}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for url, (state, detail) in zip(urls, executor.map(check_url, urls)):
            counts[state] += 1
            if state != "OK":
                sources = ", ".join(sorted(references[url]))
                print(f"{state}: {url} — {detail} ({sources})", flush=True)
    print(
        f"External links: {len(urls)} URLs; {counts['OK']} responding, "
        f"{counts['BROKEN']} broken, {counts['UNVERIFIED']} unverified."
    )
    return int(bool(counts["BROKEN"] or counts["UNVERIFIED"]))


if __name__ == "__main__":
    raise SystemExit(check())
