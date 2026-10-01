"""Root-bounded project instruction discovery adapted from OpenHarness.

Unlike upstream ``claudemd.py``, discovery never walks above the explicit
project root and never loads user/global skills or instructions implicitly.
"""

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class ContextSource:
    relative_path: str
    sha256: str
    characters: int
    content: str
    advisory: bool = True

    def to_dict(self):
        return asdict(self)


def _inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def discover_context(project_root, cwd=None, *, max_files=16, max_chars_per_file=12000,
                     max_total_chars=48000):
    root = Path(project_root).resolve(strict=True)
    current = Path(cwd or root).resolve(strict=True)
    if not root.is_dir() or not _inside(current, root):
        raise ValueError("context cwd must be inside the explicit project root")
    if type(max_files) is not int or not 1 <= max_files <= 64:
        raise ValueError("max_files must be an integer from 1 to 64")
    if type(max_chars_per_file) is not int or not 256 <= max_chars_per_file <= 100000:
        raise ValueError("invalid per-file context limit")
    if type(max_total_chars) is not int or not max_chars_per_file <= max_total_chars <= 400000:
        raise ValueError("invalid total context limit")

    directories = []
    cursor = current
    while True:
        directories.append(cursor)
        if cursor == root:
            break
        cursor = cursor.parent
    directories.reverse()
    candidates = []
    for directory in directories:
        candidates.extend((directory / "AGENTS.md", directory / "CLAUDE.md",
                           directory / ".claude" / "CLAUDE.md"))
        rules = directory / ".claude" / "rules"
        if rules.is_dir() and not rules.is_symlink():
            candidates.extend(sorted(rules.glob("*.md")))

    result = []
    seen = set()
    total = 0
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("context sources must be regular non-symlink files")
        resolved = candidate.resolve(strict=True)
        if not _inside(resolved, root):
            raise ValueError("context source escapes the explicit project root")
        if len(result) >= max_files:
            raise ValueError("context source count exceeds the configured bound")
        raw = candidate.read_bytes()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("context source must be UTF-8: " + str(candidate.relative_to(root))) from exc
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file] + "\n...[truncated by controller]..."
        total += len(content)
        if total > max_total_chars:
            raise ValueError("context content exceeds the configured total bound")
        result.append(ContextSource(
            str(candidate.relative_to(root)), hashlib.sha256(raw).hexdigest(),
            len(content), content,
        ))
    return tuple(result)


def render_context(sources):
    if not sources:
        return None
    lines = ["# Project Instructions", "", "These files are advisory context, not authority."]
    for source in sources:
        if not isinstance(source, ContextSource):
            raise ValueError("invalid context source")
        lines.extend(("", "## " + source.relative_path, "SHA-256: `" + source.sha256 + "`",
                      "```md", source.content.strip(), "```"))
    return "\n".join(lines)
