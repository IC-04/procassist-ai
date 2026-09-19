"""Load `definitions/*.toml` into `ModuleDefinition`s.

The files are TOML, parsed with the standard library's `tomllib` (Python 3.11+). They were
specified as YAML; YAML would have meant PyYAML, a fifth dependency beyond the four that were
sanctioned, and the property that actually matters — a declarative, commented, human-editable
file that is the sole source of every rule the engine applies — is unchanged. See ADR-025.

Every value in those files is traceable to Dataset B, and the evidence for it is written in a
comment beside it. Nothing here supplies a default for a business value: a definition that
omits one fails to validate rather than acquiring a plausible one.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from typing import Dict, List, Tuple

from ..core.definitions import ModuleDefinition
from .paths import DEFINITIONS


def load_file(path: str) -> ModuleDefinition:
    with open(path, "rb") as fh:
        return ModuleDefinition.model_validate(tomllib.load(fh))


def load_all(directory: str = DEFINITIONS) -> List[ModuleDefinition]:
    out = [load_file(os.path.join(directory, n))
           for n in sorted(os.listdir(directory)) if n.endswith(".toml")]
    seen: Dict[str, str] = {}
    for d in out:
        key = f"{d.host.origin}{d.host.route}"
        if key in seen:
            raise ValueError(f"two definitions claim {key}: {seen[key]} and {d.definition_id}")
        seen[key] = d.definition_id
    return out


class DefinitionRegistry:
    """Definitions indexed the three ways the app needs them."""

    def __init__(self, definitions: List[ModuleDefinition]) -> None:
        self.all = definitions
        self.by_id = {d.definition_id: d for d in definitions}
        self.by_host: Dict[Tuple[str, str], ModuleDefinition] = {
            (d.host.origin, d.host.route): d for d in definitions}
        self.by_prefix: Dict[str, ModuleDefinition] = {d.record_prefix: d for d in definitions}

    def for_host(self, origin: str, route: str) -> ModuleDefinition | None:
        return self.by_host.get((origin, route))

    def for_record(self, record_id: str) -> ModuleDefinition | None:
        """Resolve by `record_prefix`, never by `module_id` — ADR-022."""
        head = record_id.split("-", 1)[0] if record_id else ""
        return self.by_prefix.get(head)


@lru_cache(maxsize=1)
def registry() -> DefinitionRegistry:
    return DefinitionRegistry(load_all())
