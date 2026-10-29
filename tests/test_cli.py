import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stateful_tool_lab.__main__ import main


class CLITests(unittest.TestCase):
    def test_missing_traces_fail_and_remain_in_denominator(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "traces.json", Path(folder) / "result.json"
            source.write_text("[]", encoding="utf-8")
            with patch("sys.argv", ["lab", "evaluate", "--traces", str(source), "--output", str(output)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main()
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertEqual(report["summary"]["submitted_trace"]["tasks"], 24)
            self.assertEqual(report["summary"]["submitted_trace"]["passed"], 0)

    def test_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "traces.json", Path(folder) / "result.json"
            trace = {"case_id": "create-clean-en", "calls": [], "outcomes": []}
            source.write_text(json.dumps([trace, trace]), encoding="utf-8")
            with patch("sys.argv", ["lab", "evaluate", "--traces", str(source), "--output", str(output)]):
                with contextlib.redirect_stderr(io.StringIO()):
                    code = main()
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
