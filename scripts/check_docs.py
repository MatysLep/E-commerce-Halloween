"""Require a README.md in every source folder (generated/ignored folders excluded)."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = (
    subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    .decode()
    .split("\0")
)
directories = {ROOT}
for name in files:
    if not name or not (ROOT / name).exists():
        continue
    parent = (ROOT / name).parent
    while parent != ROOT:
        directories.add(parent)
        parent = parent.parent
missing = [
    str(path.relative_to(ROOT))
    for path in sorted(directories)
    if not (path / "README.md").is_file()
]
if missing:
    raise SystemExit(f"Missing README.md: {', '.join(missing)}")
print(f"Documentation present in {len(directories)} source directories.")
