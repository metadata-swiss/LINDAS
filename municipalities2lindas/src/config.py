"""Runtime configuration for the municipalities exporter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

ECH0071_NAMESPACES: Dict[str, str] = {
    "1.1": "http://www.ech.ch/xmlns/eCH-0071/1",
    "1.2.0": "http://www.ech.ch/xmlns/eCH-0071/2",
}


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional(name: str) -> Optional[str]:
    return os.environ.get(name) or None


@dataclass(frozen=True)
class MunicipalitiesConfig:
    source_url: str
    ech0071_version: str
    canton_geometry_year: str
    municipality_geometry_year: str
    target_graph: str
    lindas_query_url: str
    lindas_update_url: str
    user: Optional[str]
    password: Optional[str]
    max_removed_ratio: float
    allow_large_change: bool
    debug_local_test: bool
    user_agent: str

    def __post_init__(self) -> None:
        if self.ech0071_version not in ECH0071_NAMESPACES:
            raise ValueError(
                f"Unsupported ECH0071_VERSION {self.ech0071_version!r}; "
                f"expected one of {sorted(ECH0071_NAMESPACES)}"
            )

    @property
    def expected_namespace(self) -> str:
        return ECH0071_NAMESPACES[self.ech0071_version]

    @classmethod
    def from_env(cls) -> "MunicipalitiesConfig":
        return cls(
            source_url=os.environ.get(
                "MUNICIPALITIES_SOURCE_URL",
                "https://www.agvchapp.bfs.admin.ch/file/xml/dz-b-00.04-hgv-02.zip",
            ),
            ech0071_version=os.environ.get("ECH0071_VERSION", "1.1"),
            canton_geometry_year=os.environ.get("CANTON_GEOMETRY_YEAR", "2023"),
            municipality_geometry_year=os.environ.get("MUNICIPALITY_GEOMETRY_YEAR", "2026"),
            target_graph=os.environ.get("TARGET_GRAPH", "https://lindas.admin.ch/fso/register"),
            lindas_query_url=os.environ.get("LINDAS_QUERY_URL", "https://lindas.admin.ch/query"),
            lindas_update_url=os.environ.get("LINDAS_UPDATE_URL", ""),
            user=_optional("GRAPHDB_USER"),
            password=_optional("GRAPHDB_PASSWORD"),
            max_removed_ratio=float(os.environ.get("MAX_REMOVED_RATIO", "0.05")),
            allow_large_change=_as_bool(os.environ.get("ALLOW_LARGE_CHANGE", "false")),
            debug_local_test=_as_bool(os.environ.get("DEBUG_LOCAL_TEST", "false")),
            user_agent="municipalities2lindas",
        )
