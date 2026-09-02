import base64
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit


class GitError(RuntimeError):
    pass


def _auth_header_args(token: Optional[str], git_url: str) -> list:
    """Einmaliges -c http.extraHeader=... Argument fuer den Access-Token.

    Der Token wird bewusst NICHT in die Remote-URL eingebettet - git wuerde
    ihn sonst dauerhaft im Klartext in .git/config auf der Platte
    speichern. Stattdessen wird er per HTTP-Header nur fuer den jeweiligen
    Aufruf gesetzt und landet damit nirgends persistent im Dateisystem.
    """
    if not token:
        return []
    parts = urlsplit(git_url)
    if parts.scheme not in ("http", "https"):
        raise GitError("Private Repositories erfordern eine http(s)-URL.")
    encoded = base64.b64encode(f"{token}:".encode()).decode()
    return ["-c", f"http.extraHeader=Authorization: Basic {encoded}"]


def _redact(text: str, token: Optional[str]) -> str:
    return text.replace(token, "***") if token else text


def clone_or_pull(git_url: str, branch: str, token: Optional[str], target_dir: Path) -> None:
    env = {"GIT_TERMINAL_PROMPT": "0"}
    auth_args = _auth_header_args(token, git_url)

    if (target_dir / ".git").exists():
        cmd = ["git", *auth_args, "-C", str(target_dir), "pull", "--ff-only", "origin", branch]
    else:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        cmd = ["git", *auth_args, "clone", "--branch", branch, "--depth", "1", git_url, str(target_dir)]

    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=120, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git-Deployment abgebrochen: Zeitüberschreitung nach 120s.") from exc

    if result.returncode != 0:
        raise GitError(f"Git-Deployment fehlgeschlagen: {_redact(result.stderr, token).strip()}")
