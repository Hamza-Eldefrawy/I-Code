import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from src import config

CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Return the contents of all fenced code blocks joined together, or None."""
    blocks = [b.strip("\n") for b in CODE_BLOCK.findall(text)]
    return "\n\n".join(blocks) if blocks else None


def _clean_env() -> dict:
    """Pass only what Python needs, so the code can't read your API keys."""
    keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")
    return {k: v for k, v in os.environ.items() if k in keep}


def _cap(text: str) -> str:
    if len(text) <= config.MAX_OUTPUT_CHARS:
        return text
    return text[:config.MAX_OUTPUT_CHARS] + "\n... [output truncated]"


def run_code(code: str, timeout: int = config.RUN_TIMEOUT) -> dict:
    """Run a Python source string in a separate process.
    Returns {"stdout", "stderr", "returncode", "timed_out", "duration"}."""
    start = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],   # -I: isolated mode
                cwd=tmp,                               # any files it writes land in the temp dir
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,              # input() fails fast instead of hanging
                env=_clean_env(),
            )
            return {"stdout": _cap(proc.stdout), "stderr": _cap(proc.stderr),
                    "returncode": proc.returncode, "timed_out": False,
                    "duration": round(time.time() - start, 2)}
        except subprocess.TimeoutExpired as e:
            def text(x):
                return x.decode(errors="replace") if isinstance(x, bytes) else (x or "")
            return {"stdout": _cap(text(e.stdout)),
                    "stderr": _cap(text(e.stderr)) + f"\nTimed out after {timeout}s.",
                    "returncode": None, "timed_out": True,
                    "duration": round(time.time() - start, 2)}


def format_result(r: dict) -> str:
    """Markdown summary for showing the result to the user."""
    status = ("Timed out" if r["timed_out"]
              else "Success" if r["returncode"] == 0
              else f"Failed (exit code {r['returncode']})")
    parts = [f"**{status}** in {r['duration']}s"]
    if r["stdout"].strip():
        parts.append("**Output:**\n```\n" + r["stdout"].rstrip() + "\n```")
    if r["stderr"].strip():
        parts.append("**Errors:**\n```\n" + r["stderr"].rstrip() + "\n```")
    return "\n\n".join(parts)
