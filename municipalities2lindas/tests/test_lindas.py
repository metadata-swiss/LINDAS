import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests
import rdflib

from municipalities2lindas.tests.helpers import make_test_config
from municipalities2lindas.src.lindas import LindasClient, publish

GRAPH = "https://lindas.admin.ch/fso/register"


def response(status=200, text="", json_data=None):
    fake = Mock()
    fake.status_code = status
    fake.text = text
    fake.content = text.encode("utf-8")
    fake.json.return_value = json_data
    return fake


def count_response(n):
    return response(json_data={"results": {"bindings": [{"n": {"value": str(n)}}]}})


class LindasClientTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.nt = Path(self._tmp.name) / "g.nt"
        self.nt.write_text("<a:s> <a:p> <a:o> .\n", encoding="utf-8")

    def test_fetch_graph_keeps_lexical_form(self):
        session = Mock()
        session.post.return_value = response(
            text='<a:a> <a:b> "01"^^<http://www.w3.org/2001/XMLSchema#integer> .\n'
        )
        before = rdflib.NORMALIZE_LITERALS
        triples = LindasClient(make_test_config(), session).fetch_graph()
        self.assertEqual([str(o) for _, _, o in triples], ["01"])
        self.assertEqual(rdflib.NORMALIZE_LITERALS, before)

    def test_fetch_graph_decodes_content_as_utf8(self):
        fake = response(text="mojibake")
        fake.content = '<a:a> <a:b> "Zürich" .\n'.encode("utf-8")
        fake.text = '<a:a> <a:b> "ZÃ¼rich" .\n'
        session = Mock()
        session.post.return_value = fake
        triples = LindasClient(make_test_config(), session).fetch_graph()
        self.assertEqual([str(o) for _, _, o in triples], ["Zürich"])

    def test_fetch_graph_query_targets_graph(self):
        session = Mock()
        session.post.return_value = response(text="")
        LindasClient(make_test_config(), session).fetch_graph()
        kwargs = session.post.call_args.kwargs
        self.assertIn(f"GRAPH <{GRAPH}>", kwargs["data"]["query"])
        self.assertEqual(kwargs["headers"]["Accept"], "application/n-triples")
        self.assertEqual(kwargs["timeout"], 600)

    def test_replace_graph_put_with_context(self):
        session = Mock()
        session.put.return_value = response(204)
        config = make_test_config(
            lindas_update_url="https://graphdb.example/statements", user="u", password="p"
        )
        LindasClient(config, session).replace_graph(self.nt)
        kwargs = session.put.call_args.kwargs
        self.assertEqual(kwargs["params"], {"context": f"<{GRAPH}>"})
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/n-triples")
        self.assertEqual(kwargs["auth"], ("u", "p"))

    def test_replace_graph_requires_graphdb_url(self):
        for url in ("", "https://stardog.example/db"):
            session = Mock()
            client = LindasClient(make_test_config(lindas_update_url=url), session)
            with self.assertRaises(ValueError):
                client.replace_graph(self.nt)
            session.put.assert_not_called()

    def test_replace_graph_non_204_raises(self):
        session = Mock()
        session.put.return_value = response(500, text="boom")
        config = make_test_config(lindas_update_url="https://graphdb.example/statements")
        with self.assertRaisesRegex(RuntimeError, "500"):
            LindasClient(config, session).replace_graph(self.nt)

    def test_count_verification_retries_until_match(self):
        session = Mock()
        session.post.side_effect = [count_response(n) for n in (10, 10, 12)]
        sleep = Mock()
        LindasClient(make_test_config(), session).verify_count(12, sleep=sleep)
        self.assertEqual(sleep.call_count, 2)

        session = Mock()
        session.post.side_effect = [count_response(10) for _ in range(5)]
        with self.assertRaises(RuntimeError) as ctx:
            LindasClient(make_test_config(), session).verify_count(12, sleep=Mock())
        self.assertIn("10", str(ctx.exception))
        self.assertIn("12", str(ctx.exception))

    def test_count_verification_survives_transient_errors(self):
        session = Mock()
        session.post.side_effect = [
            requests.RequestException("502"),
            requests.RequestException("503"),
            count_response(12),
        ]
        sleep = Mock()
        LindasClient(make_test_config(), session).verify_count(12, sleep=sleep)
        self.assertEqual(sleep.call_count, 2)

    def test_count_verification_all_attempts_error(self):
        session = Mock()
        session.post.side_effect = requests.RequestException("503 final")
        with self.assertRaisesRegex(RuntimeError, "503 final"):
            LindasClient(make_test_config(), session).verify_count(12, sleep=Mock())


class PublishTest(unittest.TestCase):
    def test_publish_counts_lines_not_unicode_separators(self):
        with tempfile.TemporaryDirectory() as tmp:
            nt = Path(tmp) / "g.nt"
            nt.write_bytes('<a:s> <a:p> "x\u2028y\x85z" .\n'.encode("utf-8"))
            session = Mock()
            session.put.return_value = response(204)
            session.post.return_value = count_response(1)
            config = make_test_config(lindas_update_url="https://graphdb.example/statements")
            self.assertEqual(publish(config, nt, session=session, sleep=Mock()), 1)
            session.put.assert_called_once()
            session.post.assert_called_once()

    def test_publish_replaces_before_verifying(self):
        with tempfile.TemporaryDirectory() as tmp:
            nt = Path(tmp) / "g.nt"
            nt.write_text("<a:s> <a:p> <a:o> .\n<a:s> <a:p> <a:q> .\n", encoding="utf-8")
            calls = []
            session = Mock()
            session.put.side_effect = lambda *a, **k: calls.append("put") or response(204)
            session.post.side_effect = lambda *a, **k: calls.append("count") or count_response(2)
            config = make_test_config(lindas_update_url="https://graphdb.example/statements")
            self.assertEqual(publish(config, nt, session=session, sleep=Mock()), 2)
            self.assertEqual(calls, ["put", "count"])


if __name__ == "__main__":
    unittest.main()
