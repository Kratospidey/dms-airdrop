"""Explicit release boundary, shared by auditing and packaging."""
from pathlib import Path


def public_files(root):
    root = Path(root).resolve()
    names = (root / "PUBLIC_FILES.txt").read_text().splitlines()
    if len(names) != len(set(names)) or not names: raise ValueError("Invalid public file inventory")
    files = []
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name != relative.as_posix():
            raise ValueError("Unsafe public path: " + name)
        path = root / relative
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
            raise ValueError("Public file is missing or uses a symlink: " + name)
        if not path.resolve().is_relative_to(root): raise ValueError("Public path escaped source")
        files.append(path)
    return files
