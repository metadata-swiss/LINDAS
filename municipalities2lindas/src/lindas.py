"""LINDAS client: fetch the live graph, replace it via GraphDB, verify counts."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

from .config import MunicipalitiesConfig
from .mapper import Triple
from .serializer import parse_ntriples


class LindasClient:
    def __init__(self, config: MunicipalitiesConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    @property
    def _verify(self) -> bool:
        return not self.config.debug_local_test

    def _query(self, sparql: str, accept: str):
        response = self.session.post(
            self.config.lindas_query_url,
            data={"query": sparql},
            headers={
                "Accept": accept,
                "Accept-Encoding": "identity",
                "User-Agent": self.config.user_agent,
            },
            timeout=600,
            verify=self._verify,
        )
        response.raise_for_status()
        return response

    def fetch_graph(self) -> set[Triple]:
        graph = self.config.target_graph
        response = self._query(
            f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}",
            "application/n-triples",
        )
        return parse_ntriples(response.content.decode("utf-8"))

    def count_triples(self) -> int:
        graph = self.config.target_graph
        response = self._query(
            f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}",
            "application/sparql-results+json",
        )
        return int(response.json()["results"]["bindings"][0]["n"]["value"])

    def replace_graph(self, nt_path: Path) -> None:
        url = self.config.lindas_update_url
        if not url or "graphdb" not in url:
            raise ValueError("LINDAS_UPDATE_URL must be a GraphDB statements endpoint")
        auth = (self.config.user, self.config.password or "") if self.config.user else None
        with open(nt_path, "rb") as handle:
            response = self.session.put(
                url,
                params={"context": f"<{self.config.target_graph}>"},
                data=handle,
                headers={
                    "Content-Type": "application/n-triples",
                    "User-Agent": self.config.user_agent,
                },
                auth=auth,
                timeout=600,
                verify=self._verify,
            )
        if response.status_code != 204:
            raise RuntimeError(
                f"Graph replace failed: HTTP {response.status_code}: {response.text[:500]}"
            )

    def verify_count(
        self, expected: int, attempts: int = 5, delay_s: float = 30.0, sleep=time.sleep
    ) -> None:
        actual: int | None = None
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                actual = self.count_triples()
                last_error = None
                if actual == expected:
                    return
            except (requests.RequestException, ValueError, KeyError, IndexError) as error:
                last_error = error
            if attempt < attempts - 1:
                sleep(delay_s)
        detail = f"last error: {last_error}" if last_error else f"got {actual}"
        raise RuntimeError(
            f"Triple count mismatch after {attempts} attempts: expected {expected}, {detail}"
        )


def publish(
    config: MunicipalitiesConfig,
    nt_path: Path,
    session: requests.Session | None = None,
    sleep=time.sleep,
) -> int:
    # write_ntriples emits exactly one line per triple; str.splitlines would
    # also split on U+2028 and similar characters left raw in literals.
    expected = Path(nt_path).read_bytes().count(b"\n")
    client = LindasClient(config, session)
    client.replace_graph(nt_path)
    client.verify_count(expected, sleep=sleep)
    return expected


if __name__ == "__main__":
    count = publish(MunicipalitiesConfig.from_env(), Path(sys.argv[1]))
    print(f"PUBLISHED_TRIPLES={count}")
