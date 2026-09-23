"""Planning and execution helpers for incremental dataset synchronization."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .api import I14YDatasetsAPI, LindasDatasetsAPI
from .config import DatasetConfig


@dataclass(frozen=True)
class DatasetSourceManifest:
    """Frozen i14y dataset inventory shared by every job of one workflow run."""

    datasets: list[dict[str, Any]]
    structured_dataset_identifiers: list[str]

    @property
    def structured_dataset_count(self) -> int:
        return len(self.structured_dataset_identifiers)

    @property
    def source_identifiers(self) -> list[str]:
        return sorted(DatasetSynchronizer._source_by_identifier(self.datasets))

    @property
    def dataset_ids(self) -> set[str]:
        return {
            str(dataset["id"])
            for dataset in self.datasets
            if dataset.get("id") is not None
        }

    def validate_batch_ids(self, dataset_ids: list[str]) -> None:
        unexpected = sorted(set(dataset_ids) - self.dataset_ids)
        if unexpected:
            raise ValueError(
                "Dataset batch contains id(s) absent from the frozen source manifest: "
                + ", ".join(unexpected)
            )

    def write(self, path: str | Path) -> None:
        payload = {"schemaVersion": 2, **asdict(self)}
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def read(cls, path: str | Path) -> "DatasetSourceManifest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != 2:
            raise RuntimeError(f"Unsupported dataset source manifest schema in {path}")
        datasets = payload.get("datasets")
        structured_dataset_identifiers = payload.get("structured_dataset_identifiers")
        if (
            not isinstance(datasets, list)
            or not isinstance(structured_dataset_identifiers, list)
            or not all(isinstance(identifier, str) and identifier for identifier in structured_dataset_identifiers)
        ):
            raise RuntimeError(f"Invalid dataset source manifest {path}")
        manifest = cls(
            datasets=datasets,
            structured_dataset_identifiers=sorted(structured_dataset_identifiers),
        )
        # Validate identifiers and duplicate primary identifiers before any
        # separate workflow job can use the artifact.
        source_identifiers = set(DatasetSynchronizer._source_by_identifier(manifest.datasets))
        unknown_structured_identifiers = set(manifest.structured_dataset_identifiers) - source_identifiers
        if unknown_structured_identifiers:
            raise RuntimeError(
                "Structured dataset identifiers absent from the source manifest: "
                + ", ".join(sorted(unknown_structured_identifiers))
            )
        if len(manifest.structured_dataset_identifiers) != len(set(manifest.structured_dataset_identifiers)):
            raise RuntimeError("Duplicate structured dataset identifiers in the source manifest")
        return manifest


@dataclass(frozen=True)
class SyncPlan:
    process_ids: list[str]
    delete_identifiers: list[str]
    source_identifiers: list[str]

    @property
    def has_work(self) -> bool:
        return bool(self.process_ids or self.delete_identifiers)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def read(cls, path: str | Path) -> "SyncPlan":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


class DatasetSynchronizer:
    def __init__(self, config: DatasetConfig, i14y: I14YDatasetsAPI, lindas: LindasDatasetsAPI):
        self.config = config
        self.i14y = i14y
        self.lindas = lindas

    @staticmethod
    def parse_modified_at(dataset: dict[str, Any]) -> datetime | None:
        value = (dataset.get("system") or {}).get("modifiedAt")
        if not value:
            return None
        value = value.strip()
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"

        def normalize_fraction(match: re.Match[str]) -> str:
            return f".{match.group(1)[:6].ljust(6, '0')}"

        value = re.sub(r"\.(\d+)(?=(?:[+-]\d{2}:?\d{2})?$)", normalize_fraction, value)
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _source_by_identifier(datasets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for dataset in datasets:
            identifiers = dataset.get("identifiers") or []
            dataset_id = dataset.get("id")
            if not identifiers or not identifiers[0] or not dataset_id:
                raise ValueError(f"Dataset {dataset_id or '<unknown>'} has no identifier or id")
            identifier = str(identifiers[0])
            if identifier in result:
                raise ValueError(f"Multiple i14y datasets have primary identifier '{identifier}'")
            result[identifier] = dataset
        return result

    def build_plan(
        self,
        datasets: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
        structured_dataset_identifiers: set[str] | None = None,
    ) -> SyncPlan:
        source_by_identifier = self._source_by_identifier(datasets or self.i14y.get_all_datasets())
        source_identifiers = sorted(source_by_identifier)
        source_identifier_set = set(source_identifiers)
        source_structured_identifiers = (
            set(structured_dataset_identifiers)
            if structured_dataset_identifiers is not None
            else self.i14y.get_structured_dataset_identifiers()
        )
        unknown_structured_identifiers = source_structured_identifiers - source_identifier_set
        if unknown_structured_identifiers:
            raise ValueError(
                "i14y reported structured dataset identifier(s) absent from /api/datasets: "
                + ", ".join(sorted(unknown_structured_identifiers))
            )
        if self.config.clear_graph:
            return SyncPlan(
                process_ids=[str(source_by_identifier[identifier]["id"]) for identifier in source_identifiers],
                delete_identifiers=[],
                source_identifiers=source_identifiers,
            )

        known_identifiers = self.lindas.get_existing_dataset_identifiers()
        known_structured_identifiers = self.lindas.get_existing_structured_dataset_identifiers()
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=self.config.modified_lookback_hours)
        process_ids: list[str] = []
        deletes: set[str] = set(known_identifiers - set(source_identifiers))
        for identifier in source_identifiers:
            dataset = source_by_identifier[identifier]
            if identifier not in known_identifiers:
                process_ids.append(str(dataset["id"]))
                continue
            structure_differs = (
                identifier in source_structured_identifiers
            ) != (
                identifier in known_structured_identifiers
            )
            try:
                modified_at = self.parse_modified_at(dataset)
            except ValueError:
                modified_at = None
            if structure_differs or modified_at is None or modified_at >= cutoff:
                deletes.add(identifier)
                process_ids.append(str(dataset["id"]))
        return SyncPlan(
            process_ids=process_ids,
            delete_identifiers=sorted(deletes),
            source_identifiers=source_identifiers,
        )

    def apply_deletions(self, plan: SyncPlan) -> None:
        for identifier in plan.delete_identifiers:
            self.lindas.delete_dataset(identifier)
