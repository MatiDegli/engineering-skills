"""Pure slug conversion without input or output."""

import re
import unicodedata

MAX_TITLE_LENGTH = 200
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Return a lowercase ASCII slug with single hyphens and no hyphen at either end.

    Raises TypeError for non-strings and ValueError for titles longer than
    MAX_TITLE_LENGTH characters or without letters or digits after normalization.
    """
    if not isinstance(title, str):
        raise TypeError("title must be a string")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"title exceeds {MAX_TITLE_LENGTH} characters")
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = _SEPARATORS.sub("-", ascii_title.lower()).strip("-")
    if not slug:
        raise ValueError("title has no letters or digits")
    return slug
