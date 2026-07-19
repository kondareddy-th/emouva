"""Memory-tool backend: per-user ``/memories`` file store.

This is the durable, just-in-time state layer from ARCHITECTURE.md §2/§6. It
implements the command surface of Anthropic's memory tool (view/create/
str_replace/insert/delete/rename) so the same backend can either (a) be driven
directly by our runner, or (b) be wired to the model's `memory_20250818` tool
later — the model emits commands, we execute them here.

SECURITY: every path is confined to the user's root. Traversal attempts
(``..``, absolute escapes, symlinks) are rejected. See the memory-tool docs'
path-traversal warning.
"""
from __future__ import annotations

from pathlib import Path

from .config import MEMORY_ROOT


class MemoryError(Exception):
    pass


class MemoryStore:
    """File-backed memory rooted at ``MEMORY_ROOT/<user_id>``.

    The model addresses files as ``/memories/...``; we map that onto the user's
    sandbox directory. Nothing outside the sandbox is reachable.
    """

    def __init__(self, user_id: str, root: Path | None = None):
        self.user_id = user_id
        base = (root or MEMORY_ROOT) / user_id
        self.root = base.resolve()
        (self.root / "memories").mkdir(parents=True, exist_ok=True)

    # --- path safety ----------------------------------------------------------
    def _resolve(self, path: str) -> Path:
        """Map a model-facing ``/memories/...`` path to a safe absolute path."""
        p = (path or "").strip()
        if not p.startswith("/memories"):
            raise MemoryError("The path must start with /memories.")
        # strip the leading "/memories" segment; the remainder is relative to root/memories
        rel = p[len("/memories"):].lstrip("/")
        candidate = (self.root / "memories" / rel).resolve()
        sandbox = (self.root / "memories").resolve()
        if candidate != sandbox and sandbox not in candidate.parents:
            raise MemoryError(f"Path escapes the memory sandbox: {path}")
        return candidate

    # --- convenience API used by the runner -----------------------------------
    def load(self, path: str, default: str = "") -> str:
        target = self._resolve(path)
        if not target.is_file():
            return default
        return target.read_text(encoding="utf-8")

    def save(self, path: str, text: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def append(self, path: str, text: str) -> None:
        self.save(path, self.load(path) + text)

    # --- memory-tool command surface (for wiring to the model later) ----------
    def execute(self, command: str, **kw) -> str:
        """Dispatch a memory-tool command, returning the tool-result string."""
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            raise MemoryError(f"Unknown memory command: {command}")
        return handler(**kw)

    def _cmd_view(self, path: str, view_range: list[int] | None = None, **_) -> str:
        target = self._resolve(path)
        if target.is_dir():
            lines = [f"Directory {path}:"]
            for child in sorted(target.iterdir()):
                size = child.stat().st_size
                lines.append(f"{size}\t{path.rstrip('/')}/{child.name}")
            return "\n".join(lines)
        if not target.is_file():
            raise MemoryError(f"The path {path} does not exist. Please provide a valid path.")
        body = target.read_text(encoding="utf-8").splitlines()
        start, end = (view_range or [1, len(body)])
        sliced = body[start - 1:end]
        return "\n".join(f"{i + start:>6}\t{ln}" for i, ln in enumerate(sliced))

    def _cmd_create(self, path: str, file_text: str, **_) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_text, encoding="utf-8")
        return f"File created successfully at: {path}"

    def _cmd_str_replace(self, path: str, old_str: str, new_str: str, **_) -> str:
        target = self._resolve(path)
        text = target.read_text(encoding="utf-8")
        if text.count(old_str) == 0:
            raise MemoryError(f"No replacement was performed, old_str did not appear in {path}.")
        if text.count(old_str) > 1:
            raise MemoryError("No replacement was performed. Multiple occurrences of old_str; make it unique.")
        target.write_text(text.replace(old_str, new_str), encoding="utf-8")
        return "The memory file has been edited."

    def _cmd_insert(self, path: str, insert_line: int, insert_text: str, **_) -> str:
        target = self._resolve(path)
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        if not 0 <= insert_line <= len(lines):
            raise MemoryError(f"Invalid insert_line {insert_line}; must be within [0, {len(lines)}].")
        lines.insert(insert_line, insert_text if insert_text.endswith("\n") else insert_text + "\n")
        target.write_text("".join(lines), encoding="utf-8")
        return f"The file {path} has been edited."

    def _cmd_delete(self, path: str, **_) -> str:
        target = self._resolve(path)
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
        else:
            raise MemoryError(f"Error: The path {path} does not exist")
        return f"Successfully deleted {path}"

    def _cmd_rename(self, old_path: str, new_path: str, **_) -> str:
        src, dst = self._resolve(old_path), self._resolve(new_path)
        if not src.exists():
            raise MemoryError(f"Error: The path {old_path} does not exist")
        if dst.exists():
            raise MemoryError(f"Error: The destination {new_path} already exists")
        src.rename(dst)
        return f"Successfully renamed {old_path} to {new_path}"
