#!/usr/bin/env python3
"""Check portable links, structured files, text hygiene and secret-like filenames."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "dist",
    "build",
    "tmp",
    "temp",
}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\n]*)\)")
SECRET_NAMES = {
    "credentials.json",
    "secrets.json",
    "service-account.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}


def repo_files(root: Path) -> list[Path]:
    files = []
    for directory, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        files.extend(Path(directory) / name for name in sorted(names))
    return files


def secret_like(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".example"):
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or name in SECRET_NAMES
        or path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"}
        or any(
            part in name
            for part in ("private_key", "access_token", "refresh_token", "api_key")
        )
    )


def without_fences(text: str) -> str:
    """Ignore examples, including long fences containing shorter fenced examples."""
    lines = []
    fence = ""
    for line in text.splitlines():
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line
            ):
                fence = ""
            continue
        marker = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if marker:
            fence = marker[1]
        else:
            lines.append(line)
    return "\n".join(lines)


def markdown_targets(text: str) -> list[str]:
    """Read the inline-link syntax used here, excluding fenced and inline code."""
    text = re.sub(r"(`+).*?\1", "", without_fences(text))
    targets = []
    for match in LINK.finditer(text):
        raw = match[1].strip()
        target = raw[1 : raw.index(">")] if raw.startswith("<") and ">" in raw else raw
        targets.append(
            target if raw.startswith("<") else (raw.split()[0] if raw else "")
        )
    return targets


def heading_anchors(text: str) -> set[str]:
    """GitHub-style anchors for this repo's ATX headings, with duplicate suffixes."""
    anchors = set()
    for match in re.finditer(r"^ {0,3}#{1,6}[ \t]+(.+)$", without_fences(text), re.M):
        heading = re.sub(r"\s+#+\s*$", "", match[1]).strip()
        heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"(\*{1,2}|~~)(.*?)\1", r"\2", heading)
        heading = re.sub(r"(?<!\w)(_{1,2})(.*?)\1(?!\w)", r"\2", heading)
        heading = re.sub(r"<[^>]*>", "", heading).replace("`", "")
        base = re.sub(r"[^\w -]", "", unescape(heading).lower()).replace(" ", "-")
        anchor, suffix = base, 0
        while anchor in anchors:
            suffix += 1
            anchor = f"{base}-{suffix}"
        anchors.add(anchor)
    return anchors


def markdown_errors(path: Path, text: str, root: Path) -> list[str]:
    errors = []
    for target in markdown_targets(text):
        raw = target
        if not raw:
            errors.append(f"{path.relative_to(root)}: empty link")
            continue
        if "\\" in target or re.match(r"^[a-zA-Z]:", target):
            errors.append(f"{path.relative_to(root)}: non-portable link: {raw}")
            continue
        parsed = urlsplit(target)
        if parsed.scheme in {"https", "http", "mailto", "tel"}:
            continue
        local, fragment = unquote(parsed.path), unquote(parsed.fragment)
        resolved = (path.parent / local).resolve() if local else path.resolve()
        if local.startswith("/") or not resolved.is_relative_to(root):
            errors.append(
                f"{path.relative_to(root)}: link outside the repository: {raw}"
            )
        elif not resolved.exists():
            errors.append(f"{path.relative_to(root)}: broken link: {raw}")
        elif fragment:
            if resolved.suffix.lower() != ".md":
                errors.append(
                    f"{path.relative_to(root)}: fragment target is not Markdown: {raw}"
                )
                continue
            contents = resolved.read_text(encoding="utf-8") if local else text
            if fragment not in heading_anchors(contents):
                errors.append(
                    f"{path.relative_to(root)}: missing heading anchor: {raw}"
                )
    return errors


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    files = repo_files(root)
    errors = []
    for path in files:
        if path.is_symlink():
            errors.append(
                f"{path.relative_to(root)}: symbolic links are not supported in this repository"
            )
            continue
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                text = handle.read()
        except UnicodeDecodeError:
            continue
        label = path.relative_to(root)
        if text and (not text.endswith("\n") or "\r" in text):
            errors.append(f"{label}: use LF line endings and a final newline")
        for number, line in enumerate(text.splitlines(), 1):
            if line.endswith((" ", "\t")):
                errors.append(f"{label}:{number}: trailing whitespace")
        try:
            if path.suffix == ".json":
                json.loads(text)
            elif path.suffix == ".toml":
                tomllib.loads(text)
        except ValueError as exc:
            errors.append(f"{label}: invalid format: {exc}")
        if path.suffix == ".md":
            errors.extend(markdown_errors(path, text, root))
    # Include force-added ignored files, but do not inspect untracked local secrets.
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            timeout=30,
            text=True,
        )
        if result.returncode:
            errors.append("Could not read the Git file inventory.")
            return errors
        candidates = [root / name for name in result.stdout.split("\0") if name]
    else:
        candidates = files
    for path in candidates:
        if path.exists() and secret_like(path):
            errors.append(
                f"File with a potentially sensitive name: {path.relative_to(root)}"
            )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("Documentation, formats, and file hygiene: OK (not a secrets scanner).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
