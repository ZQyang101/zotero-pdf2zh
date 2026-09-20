# Codex CLI translation (experimental)

This fork adds a `Codex CLI` translation service to Zotero PDF2zh.

## How it works

The Zotero plugin stores only the selected Codex model, reasoning effort, and
the local Codex executable path. No OpenAI API key is required or stored.

The server maps the `codex` service to pdf2zh_next's generic
`CLITranslator`, which invokes `server/utils/codex_cli_bridge.py`.
The bridge reads the source fragment from stdin, calls `codex exec`, and
returns only the final translation on stdout.

## Local prerequisites

1. Install the OpenAI Codex CLI.
2. Sign in locally with `codex login`.
3. Verify `codex exec --help` works in the same Windows account that runs the
   PDF2zh server.
4. In Zotero PDF2zh, select **Codex CLI** and choose a model and reasoning
   effort. Leave the Codex CLI path as `codex` unless it is not on PATH.

The first version intentionally serializes Codex translation requests
(`qps=1`, one worker) to reduce concurrent session usage.
