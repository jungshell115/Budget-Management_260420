from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def sorted_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([p for p in path.iterdir() if p.is_dir()])


def sorted_json(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json"])


def prune_outputs(root: Path, keep: int) -> list[Path]:
    output_dir = root / "output"
    dirs = sorted_dirs(output_dir)
    if len(dirs) <= keep:
        return dirs
    to_delete = dirs[: len(dirs) - keep]
    for d in to_delete:
        shutil.rmtree(d, ignore_errors=True)
    return sorted_dirs(output_dir)


def prune_web_edits(root: Path, keep_output_dirs: list[Path]) -> None:
    edits_dir = root / "web_edits"
    keep_stems = {p.name for p in keep_output_dirs}
    for p in sorted_json(edits_dir):
        if p.stem not in keep_stems:
            p.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Keep only the latest sync data.")
    parser.add_argument("--root", default=".", help="Project root path")
    parser.add_argument("--keep", type=int, default=1, help="How many latest output folders to keep")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    keep = max(1, int(args.keep))
    kept = prune_outputs(root, keep)
    prune_web_edits(root, kept)

    print(f"kept_outputs={len(kept)}")
    if kept:
        print(f"latest_output={kept[-1].name}")
    else:
        print("latest_output=none")


if __name__ == "__main__":
    main()
