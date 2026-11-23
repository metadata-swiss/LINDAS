"""Shared test helpers."""

from __future__ import annotations

from dataclasses import replace

from municipalities2lindas.src.config import MunicipalitiesConfig


def make_test_config(**overrides) -> MunicipalitiesConfig:
    base = MunicipalitiesConfig(
        source_url="https://www.agvchapp.bfs.admin.ch/file/xml/dz-b-00.04-hgv-02.zip",
        ech0071_version="1.1",
        canton_geometry_year="2023",
        municipality_geometry_year="2026",
        target_graph="https://lindas.admin.ch/fso/register",
        lindas_query_url="https://lindas.example/query",
        lindas_update_url="https://lindas.example/update",
        user=None,
        password=None,
        max_removed_ratio=0.05,
        allow_large_change=False,
        debug_local_test=False,
        user_agent="municipalities2lindas",
    )
    return replace(base, **overrides)
