"""Ownership and containment checks for local managed artifacts."""
from pathlib import Path
from uuid import UUID


def managed_document_path(user_id: UUID, storage_key: str) -> Path:
    """Resolve an existing document inside the owner's managed directory."""
    root = (Path("storage/documents") / str(user_id)).absolute()
    if root.resolve() != root or root.is_symlink():
        raise ValueError("Managed storage directories cannot be symlinks.")
    candidate = Path(storage_key)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError("Document must be inside the owner's managed document directory.")
    if any(parent.is_symlink() for parent in candidate.parents) or candidate.is_symlink() or not resolved.is_file():
        raise ValueError("Document must be an existing regular managed file.")
    return resolved


def remove_managed_file(path: Path, root: Path) -> bool:
    """Delete only a regular file contained in the supplied managed root."""
    resolved = path.resolve()
    if root.resolve() != root.absolute() or not resolved.is_relative_to(root.absolute()) or path.is_symlink():
        return False
    if resolved.is_file():
        resolved.unlink()
        return True
    return False
