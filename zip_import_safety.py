"""Limits for reading backup and Takeout zip archives (zip bombs / oversized imports)."""

from __future__ import annotations

import os
import shutil
import zipfile
from typing import BinaryIO

CHUNK_SIZE = 64 * 1024
MAX_ZIP_MEMBERS = 10_000
MAX_MEMBER_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100


class ZipImportLimitError(ValueError):
    """Archive rejected: size, member count, or compression ratio over limit."""


class ZipImportBudget:
    """Tracks total uncompressed bytes consumed while reading a zip."""

    def __init__(self) -> None:
        self.total_uncompressed = 0

    def add(self, nbytes: int) -> None:
        if nbytes <= 0:
            return
        self.total_uncompressed += nbytes
        if self.total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ZipImportLimitError(
                "This archive is too large to import safely "
                f"(over {MAX_TOTAL_UNCOMPRESSED_BYTES // (1024 * 1024)} MB uncompressed total). "
                "Use a smaller backup or split the export."
            )


def _format_mb(num_bytes: int) -> str:
    return f"{num_bytes // (1024 * 1024)} MB"


def check_zip_info(info: zipfile.ZipInfo) -> None:
    """Validate declared member metadata before reading body."""
    if info.is_dir():
        return
    name = info.filename
    if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
        raise ZipImportLimitError(
            f"Archive member '{name}' is too large "
            f"(declared {_format_mb(info.file_size)}; limit {_format_mb(MAX_MEMBER_UNCOMPRESSED_BYTES)})."
        )
    compress_size = info.compress_size
    if compress_size > 0 and info.file_size > 0:
        ratio = info.file_size / compress_size
        if ratio > MAX_COMPRESSION_RATIO:
            raise ZipImportLimitError(
                f"Archive member '{name}' has suspicious compression "
                f"(ratio {ratio:.0f}:1; limit {MAX_COMPRESSION_RATIO}:1)."
            )


def validate_zip_member_count(members: list[str]) -> None:
    if len(members) > MAX_ZIP_MEMBERS:
        raise ZipImportLimitError(
            f"This archive has too many files ({len(members)}; limit {MAX_ZIP_MEMBERS})."
        )


def prepare_zip_import(zf: zipfile.ZipFile) -> ZipImportBudget:
    """Check member count and metadata; return a fresh budget for reading."""
    validate_zip_member_count(zf.namelist())
    for name in zf.namelist():
        check_zip_info(zf.getinfo(name))
    return ZipImportBudget()


def _read_stream_limited(
    stream: BinaryIO,
    budget: ZipImportBudget,
    *,
    member_label: str,
    member_cap: int | None = None,
) -> bytes:
    cap = member_cap if member_cap is not None else MAX_MEMBER_UNCOMPRESSED_BYTES
    chunks: list[bytes] = []
    member_read = 0
    while True:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            break
        member_read += len(chunk)
        if member_read > cap:
            raise ZipImportLimitError(
                f"Archive member '{member_label}' exceeds the safe size limit "
                f"({_format_mb(cap)} per file) while decompressing."
            )
        budget.add(len(chunk))
        chunks.append(chunk)
    return b"".join(chunks)


def read_zip_member_bytes(
    zf: zipfile.ZipFile,
    name: str,
    budget: ZipImportBudget,
) -> bytes:
    info = zf.getinfo(name)
    check_zip_info(info)
    with zf.open(name, "r") as src:
        return _read_stream_limited(src, budget, member_label=name)


def copy_zip_member_to_file(
    zf: zipfile.ZipFile,
    name: str,
    dest_path: str,
    budget: ZipImportBudget,
) -> None:
    info = zf.getinfo(name)
    check_zip_info(info)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    member_read = 0
    try:
        with zf.open(name, "r") as src, open(dest_path, "wb") as dst:
            while True:
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break
                member_read += len(chunk)
                if member_read > MAX_MEMBER_UNCOMPRESSED_BYTES:
                    raise ZipImportLimitError(
                        f"Archive member '{name}' exceeds the safe size limit "
                        f"({_format_mb(MAX_MEMBER_UNCOMPRESSED_BYTES)} per file) while decompressing."
                    )
                budget.add(len(chunk))
                dst.write(chunk)
    except PermissionError as exc:
        raise ZipImportLimitError(
            f"Could not extract '{name}' (file access was blocked). "
            "If antivirus quarantined part of the archive, restore the file and try again."
        ) from exc


def read_plain_file_bytes(path: str) -> bytes:
    """Read a single Takeout JSON file with the same per-file cap."""
    budget = ZipImportBudget()
    with open(path, "rb") as handle:
        return _read_stream_limited(handle, budget, member_label=os.path.basename(path))
