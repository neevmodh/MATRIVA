"""Check repository-relative Markdown links without requesting external websites."""

from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=ROOT).decode().split("\0")
    failures = []
    checked = 0
    for name in filter(None, files):
        document = ROOT / name
        text = re.sub(r"```[\s\S]*?```", "", document.read_text(encoding="utf-8"))
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = match.group(1).strip()
            if target.startswith("<"):
                target = target[1:].split(">", 1)[0]
            else:
                target = re.split(r'\s+[\"\']', target, maxsplit=1)[0]
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            checked += 1
            if not (document.parent / unquote(url.path)).exists():
                failures.append(f"{name}: missing {target}")
    for failure in failures:
        print(failure)
    print(f"Documentation links: {checked} local targets, {len(failures)} missing")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
