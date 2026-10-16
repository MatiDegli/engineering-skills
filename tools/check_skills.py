#!/usr/bin/env python3
"""Check skill metadata, self-contained references, and the criteria catalog."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.validate_repo import ROOT, markdown_targets

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CRITERION_ID = re.compile(r"[A-Z]+-\d{2}")
XML_TAG = re.compile(r"<[^>]+>")
RESERVED_WORDS = ("anthropic", "claude")
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_BODY_LINES = 500


def frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Read the single-line `key: value` frontmatter that this repository's skills use."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return None
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if not separator or not key or key != key.strip():
            return None
        fields[key] = value.strip()
    return fields, "\n".join(lines[end + 1 :])


def criteria_rows(text: str) -> list[list[str]]:
    """Return the rows of every table whose header starts with an ID column."""
    rows, in_table = [], False
    for line in text.splitlines():
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "ID":
            in_table = True
        elif in_table and not set(cells[0]) <= set("-: "):
            rows.append(cells)
    return rows


def criteria_ids(text: str) -> list[str]:
    return [cells[0] for cells in criteria_rows(text)]


def criteria_errors(path: Path, root: Path) -> list[str]:
    label = path.relative_to(root)
    errors, seen = [], set()
    for cells in criteria_rows(path.read_text(encoding="utf-8")):
        identifier = cells[0]
        if not CRITERION_ID.fullmatch(identifier):
            errors.append(f"{label}: malformed criterion ID: {identifier}")
        elif identifier in seen:
            errors.append(f"{label}: duplicate criterion ID: {identifier}")
        seen.add(identifier)
        if len(cells) != 4 or not markdown_targets(cells[-1]):
            errors.append(
                f"{label}: {identifier} needs a check, applicability, and a guide link"
            )
    if not seen:
        errors.append(f"{label}: no criteria found")
    return errors


def link_errors(skill: Path, root: Path) -> tuple[list[str], set[Path]]:
    """Reject links that leave the skill; return the files SKILL.md links to."""
    errors, linked = [], set()
    for document in sorted(skill.rglob("*.md")):
        for target in markdown_targets(document.read_text(encoding="utf-8")):
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            resolved = (document.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(skill.resolve()):
                errors.append(
                    f"{document.relative_to(root)}: link leaves the skill directory: {target}"
                )
            elif document.name == "SKILL.md" and document.parent == skill:
                linked.add(resolved)
    return errors, linked


def skill_errors(skill: Path, root: Path) -> list[str]:
    label = skill.relative_to(root)
    path = skill / "SKILL.md"
    if not path.is_file():
        return [f"{label}: missing SKILL.md"]
    parsed = frontmatter(path.read_text(encoding="utf-8"))
    if parsed is None:
        return [f"{label}/SKILL.md: frontmatter must be single-line 'key: value' pairs between '---' lines"]
    fields, body = parsed
    errors = []
    unknown = sorted(set(fields) - SPEC_FIELDS)
    if unknown:
        errors.append(
            f"{label}/SKILL.md: fields outside the Agent Skills specification: {', '.join(unknown)}"
        )
    name = fields.get("name", "")
    if not (NAME.fullmatch(name) and len(name) <= 64):
        errors.append(f"{label}/SKILL.md: name must be 1-64 lowercase letters, digits, and single hyphens")
    elif name != skill.name:
        errors.append(f"{label}/SKILL.md: name must match the directory name")
    elif any(word in name for word in RESERVED_WORDS):
        errors.append(f"{label}/SKILL.md: name must not contain a reserved word")
    description = fields.get("description", "")
    if not description or len(description) > 1024 or XML_TAG.search(description):
        errors.append(f"{label}/SKILL.md: description must be 1-1024 characters without XML tags")
    if len(body.splitlines()) > MAX_BODY_LINES:
        errors.append(f"{label}/SKILL.md: body exceeds {MAX_BODY_LINES} lines")
    found, linked = link_errors(skill, root)
    errors.extend(found)
    references = skill / "references"
    for reference in sorted(references.rglob("*")) if references.is_dir() else []:
        if reference.is_file() and reference.resolve() not in linked:
            errors.append(f"{reference.relative_to(root)}: not linked from SKILL.md")
    if (references / "criteria.md").is_file():
        errors.extend(criteria_errors(references / "criteria.md", root))
    return errors


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    skills_dir = root / "skills"
    skills = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    if not skills:
        return ["skills/: no skill directories found"]
    return [error for skill in skills for error in skill_errors(skill, root)]


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("Skill metadata, self-contained references, and criteria: OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
