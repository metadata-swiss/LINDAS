from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from municipalities2lindas.src.config import MunicipalitiesConfig
from municipalities2lindas.tests.helpers import make_test_config


class MunicipalitiesConfigTests(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = MunicipalitiesConfig.from_env()
        self.assertEqual(
            config.source_url,
            "https://www.agvchapp.bfs.admin.ch/file/xml/dz-b-00.04-hgv-02.zip",
        )
        self.assertEqual(config.ech0071_version, "1.1")
        self.assertEqual(config.canton_geometry_year, "2023")
        self.assertEqual(config.municipality_geometry_year, "2026")
        self.assertEqual(config.target_graph, "https://lindas.admin.ch/fso/register")
        self.assertEqual(config.lindas_query_url, "https://lindas.admin.ch/query")
        self.assertEqual(config.lindas_update_url, "")
        self.assertIsNone(config.user)
        self.assertIsNone(config.password)
        self.assertEqual(config.max_removed_ratio, 0.05)
        self.assertFalse(config.allow_large_change)
        self.assertFalse(config.debug_local_test)
        self.assertEqual(config.user_agent, "municipalities2lindas")
        self.assertEqual(config.expected_namespace, "http://www.ech.ch/xmlns/eCH-0071/1")

    def test_env_overrides(self):
        env = {
            "ECH0071_VERSION": "1.2.0",
            "MAX_REMOVED_RATIO": "0.1",
            "ALLOW_LARGE_CHANGE": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = MunicipalitiesConfig.from_env()
        self.assertEqual(config.ech0071_version, "1.2.0")
        self.assertEqual(config.max_removed_ratio, 0.1)
        self.assertTrue(config.allow_large_change)
        self.assertEqual(config.expected_namespace, "http://www.ech.ch/xmlns/eCH-0071/2")

    def test_unknown_version_rejected(self):
        with patch.dict(os.environ, {"ECH0071_VERSION": "9"}, clear=True):
            with self.assertRaises(ValueError):
                MunicipalitiesConfig.from_env()

    def test_credentials_from_env(self):
        env = {"GRAPHDB_USER": "u", "GRAPHDB_PASSWORD": "p"}
        with patch.dict(os.environ, env, clear=True):
            config = MunicipalitiesConfig.from_env()
        self.assertEqual((config.user, config.password), ("u", "p"))

    def test_empty_credentials_are_none(self):
        env = {"GRAPHDB_USER": "", "GRAPHDB_PASSWORD": ""}
        with patch.dict(os.environ, env, clear=True):
            config = MunicipalitiesConfig.from_env()
        self.assertIsNone(config.user)
        self.assertIsNone(config.password)

    def test_make_test_config_overrides(self):
        config = make_test_config(target_graph="https://example/g")
        self.assertEqual(config.target_graph, "https://example/g")
        self.assertTrue(config.lindas_query_url.startswith("https://lindas.example/"))
        self.assertTrue(config.lindas_update_url.startswith("https://lindas.example/"))


if __name__ == "__main__":
    unittest.main()
