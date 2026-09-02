import shutil
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


class GitError(RuntimeError):
    pass


def _authenticated_url(git_url: str, token: Optional[str]) -> str:
    if not token:
        return git_url

    parts = urlsplit(git_url)
    if parts.scheme not in ("http", "https"):
        raise GitError("Private Repositories erfordern eine http(s)-URL.")

    netloc = f"{token}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _redact(text: str, token: Optional[str]) -> str:
    return text.replace(token, "***") if token else text


def clone_or_pull(git_url: str, branch: str, token: Optional[str], target_dir: Path) -> None:
    env = {"GIT_TERMINAL_PROMPT": "0"}

    if (target_dir / ".git").exists():
        cmd = ["git", "-C", str(target_dir), "pull", "--ff-only", "origin", branch]
    else:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        auth_url = _authenticated_url(git_url, token)
        cmd = ["git", "clone", "--branch", branch, "--depth", "1", auth_url, str(target_dir)]

    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=120, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git-Deployment abgebrochen: Zeitüberschreitung nach 120s.") from exc

    if result.returncode != 0:
        raise GitError(f"Git-Deployment fehlgeschlagen: {_redact(result.stderr, token).strip()}")
