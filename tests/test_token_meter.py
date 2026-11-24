import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from token_meter import analysis, cli, loader
from token_meter.forecast import forecast, linear_fit
from token_meter.loader import Record
from token_meter.pricing import Pricer, normalize_model


def entry(msg_id, req_id, ts, model="claude-opus-5-5", inp=10, out=100, cw=0, cr=0, c1h=0, **extra):
    usage = {"input_tokens": inp, "output_tokens": out, "cache_creation_input_tokens": cw,
             "cache_read_input_tokens": cr,
             "cache_creation": {"ephemeral_1h_input_tokens": c1h, "ephemeral_5m_input_tokens": cw - c1h}}
    d = {"type": "assistant", "timestamp": ts, "sessionId": "sess-1", "cwd": "/work/demo",
         "requestId": req_id, "message": {"id": msg_id, "model": model, "role": "assistant", "usage": usage}}
    d.update(extra)
    return json.dumps(d)


def rec(ts, model="claude-opus-5-5", inp=1000, out=0, session="s", project="p"):
    return Record(ts=ts, model=model, input=inp, output=out, cache_5m=0, cache_1h=0, cache_read=0,
                  session=session, project=project)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        proj = os.path.join(self.tmp.name, "projects", "demo")
        os.makedirs(proj)
        lines = [
            # the same reply written twice while streaming: keep the larger one
            entry("msg_1", "req_1", "2026-11-01T10:00:00.000Z", out=5),
            entry("msg_1", "req_1", "2026-11-01T10:00:02.000Z", out=300, cw=2000, c1h=1500, cr=40000),
            entry("msg_2", "req_2", "2026-11-02T11:00:00Z", model="claude-sonnet-5-5", out=50),
            entry("msg_3", "req_3", "2026-11-02T11:05:00Z", model="<synthetic>", out=0),
            json.dumps({"type": "user", "timestamp": "2026-11-02T11:00:00Z", "message": {"role": "user"}}),
            '{"broken json "usage"',
        ]
        with open(os.path.join(proj, "sess-1.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        self.root = os.path.join(self.tmp.name, "projects")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedupe_and_parse(self):
        res = loader.load([self.root])
        self.assertEqual(res.files, 1)
        self.assertEqual(len(res.records), 2)
        self.assertEqual(res.duplicates, 1)
        self.assertEqual(res.bad_lines, 1)
        first = res.records[0]
        self.assertEqual(first.output, 300)
        self.assertEqual((first.cache_1h, first.cache_5m, first.cache_read), (1500, 500, 40000))
        self.assertEqual(first.total, 10 + 300 + 2000 + 40000)
        self.assertEqual(first.project, "/work/demo")
        self.assertEqual(res.records[1].model, "claude-sonnet-5-5")

    def test_filters(self):
        res = loader.load([self.root])
        since = datetime(2026, 11, 2, tzinfo=timezone.utc)
        self.assertEqual(len(loader.filter_records(res.records, since=since)), 1)
        self.assertEqual(len(loader.filter_records(res.records, models=["opus"])), 1)
        self.assertEqual(len(loader.filter_records(res.records, project="nothing")), 0)

    def test_cli_text_json_dashboard(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["--path", self.root, "--lang", "en"]), 0)
        self.assertIn("BY MODEL", out.getvalue())
        self.assertIn("opus-5-5", out.getvalue())

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.main(["models", "--path", self.root, "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual({m["model"] for m in data["models"]}, {"claude-opus-5-5", "claude-sonnet-5-5"})

        html = os.path.join(self.tmp.name, "d.html")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["dashboard", "--path", self.root, "--out", html, "--no-open"])
        with open(html, encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn('"claude-sonnet-5-5"', page)
        self.assertNotIn("/*__DATA__*/", page)

    def test_no_data(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.makedirs(empty)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["--path", empty]), 1)

    def test_serve_port_busy(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main(["serve", "--path", self.root, "--no-open", "--port", str(port), "--lang", "en"])
        self.assertEqual(code, 1)
        self.assertIn(f"Could not open port {port}", err.getvalue())


class PricingTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_model("us.anthropic.claude-opus-4-1-20250805-v1:0"), "claude-opus-4-1-20250805-v1:0")
        self.assertEqual(normalize_model("claude-opus-5-5[1m]"), "claude-opus-5-5")

    def test_longest_prefix(self):
        p = Pricer()
        self.assertEqual(p.lookup("claude-opus-4-1-20250805")["input"], 15)
        self.assertEqual(p.lookup("claude-opus-4-8")["input"], 5)
        self.assertEqual(p.lookup("claude-sonnet-5-5")["input"], 2)
        self.assertIsNone(p.lookup("gpt-4o"))

    def test_cost(self):
        p = Pricer()
        r = Record(ts=datetime.now(timezone.utc), model="claude-opus-5-5", input=1_000_000, output=1_000_000,
                   cache_5m=1_000_000, cache_1h=1_000_000, cache_read=1_000_000, session="s", project="p")
        # 4 + 20 + 4*1.25 + 4*2 + 0.20
        self.assertAlmostEqual(p.cost(r), 37.2)
        r.speed = "fast"
        self.assertAlmostEqual(p.cost(r), 74.4)

    def test_long_context_tier(self):
        p = Pricer()
        small = rec(datetime.now(timezone.utc), "claude-haiku-5-5", inp=50_000)
        big = rec(datetime.now(timezone.utc), "claude-haiku-5-5", inp=200_000)
        self.assertAlmostEqual(p.cost(small), 50_000 * 0.10 / 1e6)
        self.assertAlmostEqual(p.cost(big), 200_000 * 0.50 / 1e6)

    def test_override(self):
        p = Pricer({"my-model": {"input": 1, "output": 2}})
        self.assertAlmostEqual(p.cost(rec(datetime.now(timezone.utc), "my-model", inp=1_000_000)), 1.0)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        tz = datetime.now().astimezone().tzinfo
        self.day = datetime(2026, 11, 10, tzinfo=tz)
        self.records = [
            rec(self.day.replace(hour=10, minute=15), "claude-opus-5-5", 1000),
            rec(self.day.replace(hour=12), "claude-sonnet-5-5", 3000),
            rec(self.day.replace(hour=15, minute=30), "claude-opus-5-5", 500),
            rec(self.day + timedelta(days=1, hours=9), "claude-sonnet-5-5", 100),
        ]

    def test_by_model(self):
        models = analysis.by_model(self.records)
        self.assertEqual(models[0]["model"], "claude-sonnet-5-5")
        self.assertAlmostEqual(sum(m["share"] for m in models), 1.0)
        self.assertEqual(models[1]["days_used"], 1)

    def test_periods(self):
        days = analysis.by_period(self.records, "day")
        self.assertEqual([d["period"] for d in days], ["2026-11-10", "2026-11-11"])
        self.assertEqual(days[0]["total"], 4500)
        self.assertEqual(analysis.by_period(self.records, "month")[0]["period"], "2026-11")

    def test_switches(self):
        sw = analysis.model_switches(self.records)
        self.assertEqual([s["model"] for s in sw], ["claude-sonnet-5-5"])  # main model both days

    def test_blocks(self):
        bl = analysis.blocks(self.records, now=self.day + timedelta(days=5))
        self.assertEqual(len(bl), 3)
        self.assertEqual(bl[0]["start"].hour, 10)
        self.assertEqual(bl[0]["requests"], 2)
        self.assertEqual(bl[1]["start"].hour, 15)
        self.assertFalse(any(b["active"] for b in bl))


class ForecastTests(unittest.TestCase):
    def test_linear_fit(self):
        a, b = linear_fit([1, 3, 5, 7])
        self.assertAlmostEqual(a, 1)
        self.assertAlmostEqual(b, 2)

    def test_constant_rate(self):
        now = datetime.now().astimezone()
        records = [rec(now - timedelta(days=k, hours=1), inp=1000) for k in range(13, -1, -1)]
        fc = forecast(records, now, window=7)
        self.assertAlmostEqual(fc["rate"]["per_day"]["total"], 1000)
        self.assertAlmostEqual(fc["horizons"]["30d"]["tokens"], 30000)
        self.assertAlmostEqual(fc["horizons"]["7d"]["tokens"], 7000)
        self.assertGreaterEqual(fc["end_of_month"]["tokens"], fc["end_of_month"]["to_date"])

    def test_current_block(self):
        now = datetime.now().astimezone()
        records = [rec(now - timedelta(minutes=30), inp=600), rec(now - timedelta(minutes=10), inp=600)]
        fc = forecast(records, now)
        cb = fc["current_block"]
        self.assertIsNotNone(cb)
        self.assertAlmostEqual(cb["tokens_per_min"], 1200 / 30, places=3)
        self.assertGreater(cb["projected_total"], 1200)

    def test_empty(self):
        self.assertIsNone(forecast([]))


if __name__ == "__main__":
    unittest.main()
