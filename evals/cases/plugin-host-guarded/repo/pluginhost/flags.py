"""Release flags: switches for a change that is still rolling out."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Flag:
    """A release flag; remove it, keeping the new behavior, by its expiry date."""

    name: str
    purpose: str
    owner: str
    expires: date
    default: bool = False


FLAGS = {
    flag.name: flag
    for flag in (
        Flag(
            "skip_private_files",
            purpose="do not treat files whose names start with an underscore as plugins",
            owner="ines-rao",
            expires=date(2027, 3, 31),
        ),
    )
}


def enabled(name: str, overrides: dict[str, bool]) -> bool:
    """Whether the flag is on: the setting if there is one, else the flag's default."""
    return overrides.get(name, FLAGS[name].default)
