"""Entity configuration: loaded from config/*.yaml and validated at startup."""
import glob
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


class Connectors(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ga4: bool = False
    search_console: bool = False
    merchant_center: bool = False
    business_profile: bool = False


class Entity(BaseModel):
    """One legal entity in the group. Unknown keys are rejected so typos fail loudly."""
    model_config = ConfigDict(extra="forbid")
    name: str
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    entity_type: Literal["pure_holding", "subsidiary"]
    parent: str | None = None
    domain: str | None = None
    contact_email: str | None = None
    ecommerce_enabled: bool = False
    ga4_property_env: str | None = None
    search_console_site: str | None = None
    search_console_page_contains: str | None = None
    search_console_page_excludes: str | None = None
    business_profile_location_env: str | None = None
    connectors: Connectors = Connectors()

    def as_dict(self) -> dict:
        return self.model_dump()


def _read(path: Path | str) -> Entity:
    # utf-8-sig tolerates a byte-order mark if a file is ever re-saved from Windows.
    with open(path, encoding="utf-8-sig") as fh:
        return Entity.model_validate(yaml.safe_load(fh)["entity"])


@lru_cache(maxsize=1)
def load_entities() -> tuple[Entity, ...]:
    entities = [_read(CONFIG_DIR / "holdings.yaml")]
    entities += [_read(p) for p in sorted(glob.glob(str(CONFIG_DIR / "subsidiaries" / "*.yaml")))]
    slugs = [e.slug for e in entities]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"Duplicate entity slugs in config: {slugs}")
    for e in entities:
        if e.parent and e.parent not in slugs:
            raise ValueError(f"{e.slug}: parent '{e.parent}' is not a configured entity")
        if e.connectors.search_console and not e.search_console_site:
            raise ValueError(f"{e.slug}: search_console is on but search_console_site is missing")
        if e.connectors.ga4 and not e.ga4_property_env:
            raise ValueError(f"{e.slug}: ga4 is on but ga4_property_env is missing")
        if e.connectors.business_profile and not e.business_profile_location_env:
            raise ValueError(f"{e.slug}: business_profile is on but business_profile_location_env is missing")
    return tuple(entities)
