import shlex
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import toml

from utils.config import Config


def _request(model="gpt-5.6-terra", reasoning="medium", codex_path="codex"):
    extra = {}
    if reasoning:
        extra["codex_reasoning_effort"] = reasoning
    return {
        "engine": "pdf2zh_next",
        "next_service": "codex",
        "sourceLang": "en",
        "targetLang": "zh-CN",
        "qps": 10,
        "poolSize": 0,
        "llm_api": {
            "apiKey": "",
            "apiUrl": codex_path,
            "model": model,
            "extraData": extra,
        },
    }


def _write_config(path):
    with path.open("w", encoding="utf-8") as config_file:
        toml.dump(
            {
                "translation": {},
                "pdf": {},
                "clitranslator_detail": {
                    "translate_engine_type": "CLITranslator",
                    "support_llm": "no",
                    "clitranslator_command": "",
                    "clitranslator_timeout": 60,
                    "clitranslator_postprocess_command": "null",
                },
            },
            config_file,
        )


class CodexConfigTest(unittest.TestCase):
    def test_codex_builds_cli_translator_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(path)

            config = Config(_request())
            with redirect_stdout(StringIO()):
                config.update_config_file(path)

            saved = toml.load(path)
            detail = saved["clitranslator_detail"]
            args = shlex.split(detail["clitranslator_command"])

            self.assertEqual(detail["translate_engine_type"], "CLITranslator")
            self.assertEqual(detail["support_llm"], "no")
            self.assertEqual(detail["clitranslator_timeout"], 300)
            self.assertEqual(detail["clitranslator_postprocess_command"], "null")
            self.assertIn("codex_cli_bridge.py", args[1])
            self.assertIn("--codex-path", args)
            self.assertIn("codex", args)
            self.assertIn("--model", args)
            self.assertIn("gpt-5.6-terra", args)
            self.assertIn("--reasoning-effort", args)
            self.assertIn("medium", args)
            self.assertIn("--source-lang", args)
            self.assertIn("en", args)
            self.assertIn("--target-lang", args)
            self.assertIn("zh-CN", args)

            # Codex starts conservatively: one active translation at a time.
            self.assertEqual(config.qps, 1)
            self.assertEqual(config.pool_size, 1)
            self.assertEqual(saved["translation"]["pool_max_workers"], 1)

    def test_codex_allows_cli_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(path)

            config = Config(_request(model="", reasoning="", codex_path="codex.cmd"))
            with redirect_stdout(StringIO()):
                config.update_config_file(path)

            args = shlex.split(
                toml.load(path)["clitranslator_detail"]["clitranslator_command"]
            )
            self.assertNotIn("--model", args)
            self.assertNotIn("--reasoning-effort", args)
            self.assertIn("codex.cmd", args)

    def test_invalid_reasoning_effort_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            _write_config(path)

            config = Config(_request(reasoning="ultra"))
            with self.assertRaises(ValueError):
                with redirect_stdout(StringIO()):
                    config.update_config_file(path)


if __name__ == "__main__":
    unittest.main()
