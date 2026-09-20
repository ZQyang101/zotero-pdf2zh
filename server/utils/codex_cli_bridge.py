"""Bridge pdf2zh_next CLITranslator to the OpenAI Codex CLI.

The bridge deliberately uses the local Codex CLI login state. It never accepts
or stores an OpenAI API key. pdf2zh_next writes each source fragment to stdin;
this script sends that fragment to `codex exec` as extra context and prints
only Codex's final message to stdout.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


TRANSLATION_PROMPT = """You are a professional academic translator.
Translate only the text provided through stdin from {source_lang} to {target_lang}.
Return only the translated text: no preface, explanation, quotation marks, or Markdown fences.
Do not summarize, omit, expand, or answer the source text.
Preserve paragraph boundaries and preserve mathematical notation, LaTeX, placeholders,
XML/HTML-like tags, citation markers, URLs, numbers, code-like tokens, and special symbols
exactly unless they are ordinary natural-language content that must be translated.
Use precise terminology appropriate for a scientific paper.
"""


def _resolve_codex_path(value: str) -> str:
    value = (value or "codex").strip()
    candidate = Path(value).expanduser()

    if candidate.is_absolute() or candidate.parent != Path("."):
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError(
            f"Codex CLI was not found at '{value}'. "
            "Set the Codex CLI path in Zotero PDF2zh."
        )

    resolved = shutil.which(value)
    if not resolved:
        raise FileNotFoundError(
            f"Codex CLI command '{value}' was not found on PATH. "
            "Install Codex CLI and run 'codex login' first."
        )
    return resolved


def _windows_batch_command(executable: str, args: list[str]) -> list[str]:
    """Run npm-installed .cmd/.bat launchers safely without shell=True."""
    comspec = os.environ.get("COMSPEC") or "cmd.exe"
    command_line = subprocess.list2cmdline([executable, *args])
    return [comspec, "/d", "/s", "/c", command_line]


def build_codex_command(
    codex_path: str,
    model: str = "",
    reasoning_effort: str = "",
) -> list[str]:
    executable = _resolve_codex_path(codex_path)
    args = [
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
    ]

    if model:
        args.extend(["-m", model])
    if reasoning_effort:
        args.extend(
            [
                "-c",
                f'model_reasoning_effort="{reasoning_effort}"',
            ]
        )

    # With prompt + stdin, Codex treats the prompt as the instruction and the
    # piped stdin as additional context. This is exactly what CLITranslator
    # needs for per-fragment translation.
    args.append("__PROMPT_PLACEHOLDER__")

    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        return _windows_batch_command(executable, args)
    return [executable, *args]


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate stdin through Codex CLI")
    parser.add_argument("--codex-path", default="codex")
    parser.add_argument("--model", default="")
    parser.add_argument("--reasoning-effort", default="")
    parser.add_argument("--source-lang", default="en")
    parser.add_argument("--target-lang", default="zh-CN")
    args = parser.parse_args()

    source_text = sys.stdin.read()
    if not source_text:
        return 0

    prompt = TRANSLATION_PROMPT.format(
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    ).strip()

    try:
        cmd = build_codex_command(
            args.codex_path,
            model=args.model.strip(),
            reasoning_effort=args.reasoning_effort.strip(),
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 127

    # Replace the placeholder after Windows command-line wrapping so the prompt
    # remains one argument in either native-executable or .cmd launcher mode.
    if os.name == "nt" and len(cmd) >= 5 and cmd[1:4] == ["/d", "/s", "/c"]:
        # Rebuild the batch command with the real prompt; parsing an already
        # quoted command string would be lossy.
        executable = _resolve_codex_path(args.codex_path)
        inner_args = [
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        if args.model.strip():
            inner_args.extend(["-m", args.model.strip()])
        if args.reasoning_effort.strip():
            inner_args.extend(
                [
                    "-c",
                    f'model_reasoning_effort="{args.reasoning_effort.strip()}"',
                ]
            )
        inner_args.append(prompt)
        cmd = _windows_batch_command(executable, inner_args)
    else:
        cmd[-1] = prompt

    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("RUST_LOG", "error")

    # Run in an empty directory so repository-local AGENTS.md files and source
    # trees cannot affect a translation request.
    with tempfile.TemporaryDirectory(prefix="pdf2zh-codex-") as temp_dir:
        process = subprocess.run(
            cmd,
            input=source_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=temp_dir,
            env=env,
            check=False,
        )

    if process.returncode != 0:
        if process.stderr:
            print(process.stderr.rstrip(), file=sys.stderr)
        return process.returncode

    sys.stdout.write(process.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
