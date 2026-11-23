"""Download and parse the BFS eCH-0071 municipality nomenclature into raw records."""

from __future__ import annotations

import hashlib
import logging
import posixpath
import random
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from fnmatch import fnmatchcase
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple

import requests
from dateutil.relativedelta import relativedelta

from .config import MunicipalitiesConfig

logger = logging.getLogger(__name__)

Record = Dict[str, str]

MIN_COUNTS = {"cantons": 26, "districts": 300, "municipalities": 5000}
DOWNLOAD_ATTEMPTS = 3


class SourceError(RuntimeError):
    """The source file is missing, malformed or implausible."""


@dataclass(frozen=True)
class Nomenclature:
    valid_from: str
    cantons: List[Record]
    districts: List[Record]
    municipalities: List[Record]


@dataclass(frozen=True)
class SourceInfo:
    url: str
    member: str
    sha256: str
    size: int
    valid_from: str
    last_modified: Optional[str]

    def to_json(self) -> dict:
        return asdict(self)


def download_zip(
    config: MunicipalitiesConfig,
    dest: Path,
    session: Optional[requests.Session] = None,
) -> Tuple[Path, Optional[str]]:
    session = session or requests.Session()
    last_error: Optional[Exception] = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            response = session.get(
                config.source_url,
                headers={"User-Agent": config.user_agent},
                timeout=120,
                verify=not config.debug_local_test,
            )
            response.raise_for_status()
            dest.write_bytes(response.content)
            return dest, response.headers.get("Last-Modified")
        except requests.RequestException as error:
            last_error = error
            if attempt < DOWNLOAD_ATTEMPTS:
                sleep(random.uniform(1, 2))
    raise SourceError(
        f"Download failed after {DOWNLOAD_ATTEMPTS} attempts: {config.source_url}"
    ) from last_error


def select_member(zf: zipfile.ZipFile, version: str) -> str:
    candidates = []
    folders = set()
    for name in zf.namelist():
        folder, _, filename = name.rpartition("/")
        if not filename:
            continue
        folder = posixpath.basename(folder)
        folders.add(folder)
        if (folder == version or folder.startswith(version + " ")) and fnmatchcase(
            filename, "eCH0071_*.xml"
        ):
            candidates.append(name)
    if not candidates:
        raise SourceError(
            f"No eCH0071_*.xml under a '{version}' folder in the zip; "
            f"check ECH0071_VERSION (folders found: {sorted(folders)}) "
            "(v1.1 folder dropped by BFS? switch ECH0071_VERSION to 1.2.0 - see docs/agent/municipalities2lindas-ech0071-v1.2.0.md)"
        )
    if len(candidates) > 1:
        raise SourceError(f"Ambiguous source: {len(candidates)} members match: {sorted(candidates)}")
    return candidates[0]


def _records(section: Optional[ET.Element]) -> List[Record]:
    records: List[Record] = []
    if section is None:
        return records
    for item in section:
        record: Record = {}
        for child in item:
            if child.text is None or child.text == "":
                logger.warning("Empty element <%s> in <%s> treated as missing", child.tag, item.tag)
                continue
            record[child.tag] = child.text
        records.append(record)
    return records


def parse_nomenclature(xml_bytes: bytes, expected_namespace: str) -> Nomenclature:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise SourceError(f"Source is not well-formed XML: {error}") from error
    expected_tag = f"{{{expected_namespace}}}nomenclature"
    if root.tag != expected_tag:
        raise SourceError(
            f"Unexpected root element {root.tag!r}; expected namespace "
            f"{expected_namespace} (check ECH0071_VERSION)"
        )
    valid_from = root.findtext("validFrom")
    if not valid_from:
        raise SourceError("Source has no <validFrom>")
    return Nomenclature(
        valid_from=valid_from,
        cantons=_records(root.find("cantons")),
        districts=_records(root.find("districts")),
        municipalities=_records(root.find("municipalities")),
    )


def load_source(
    path: Path,
    config: MunicipalitiesConfig,
    url: str = "",
    last_modified: Optional[str] = None,
) -> Tuple[Nomenclature, SourceInfo]:
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() == ".xml":
        member, xml_bytes = path.name, data
    else:
        try:
            with zipfile.ZipFile(path) as zf:
                member = select_member(zf, config.ech0071_version)
                xml_bytes = zf.read(member)
        except zipfile.BadZipFile as error:
            raise SourceError(f"{path.name} is not a valid zip file (truncated or error page?)") from error
    nomenclature = parse_nomenclature(xml_bytes, config.expected_namespace)
    info = SourceInfo(
        url=url,
        member=member,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        valid_from=nomenclature.valid_from,
        last_modified=last_modified,
    )
    return nomenclature, info


def check_counts(n: Nomenclature, minimums: Dict[str, int] = MIN_COUNTS) -> None:
    for kind, minimum in minimums.items():
        count = len(getattr(n, kind))
        if count < minimum:
            raise SourceError(f"Too few {kind} in source: {count} < {minimum}")


def is_stale(valid_from: str, today: date) -> bool:
    # xs:date may carry a timezone suffix; only the date part matters
    return date.fromisoformat(valid_from[:10]) < today - relativedelta(months=13)
