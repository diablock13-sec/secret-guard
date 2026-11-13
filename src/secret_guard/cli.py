import argparse
import os
import shlex
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from rich.console import Console
from rich.text import Text

from secret_guard.ignore import IGNORE_FILE, IgnoreError, is_ignored, parse_ignore
from secret_guard.scanner import Finding, scan_diff

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

HOOK_NAME = "pre-commit"
HOOK_MARKER = "# secret-guard-hook"


class GitError(RuntimeError):
    """Perintah git gagal atau git tidak tersedia."""


def run_git(*args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git", *args], capture_output=True, check=False)
    except FileNotFoundError:
        raise GitError("git tidak ditemukan di PATH") from None


def _git_error(proc: subprocess.CompletedProcess[bytes], what: str) -> GitError:
    lines = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
    detail = lines[0] if lines else f"kode keluar {proc.returncode}"
    return GitError(f"{what}: {detail}")


def staged_diff() -> str:
    """Diff dari perubahan yang sudah di-`git add`. Opsi dipaku supaya konfigurasi
    pengguna (prefiks, warna, textconv, rename) tidak mengubah format yang diparse."""
    proc = run_git(
        "-c", "core.quotepath=false",
        "diff", "--cached", "--no-color", "--no-ext-diff", "--no-textconv",
        "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", "-U0",
    )  # fmt: skip
    if proc.returncode != 0:
        raise _git_error(proc, "git diff gagal")
    return proc.stdout.decode("utf-8", errors="replace")


def load_ignore(explicit: str | None) -> list[str]:
    if explicit:
        path, required = Path(explicit), True
    else:
        proc = run_git("rev-parse", "--show-toplevel")
        root = (
            Path(proc.stdout.decode("utf-8", errors="replace").strip())
            if proc.returncode == 0
            else Path.cwd()
        )
        path, required = root / IGNORE_FILE, False
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if required:
            raise IgnoreError(f"file ignore tidak ditemukan: {path}") from None
        return []
    except (OSError, UnicodeDecodeError):
        raise IgnoreError(f"tidak bisa membaca {path}") from None
    return parse_ignore(text, path.name)


def _clean(value: str) -> str:
    """Ganti karakter yang tidak bisa dicetak (misalnya ESC) dengan '?'. Path dan isi
    baris berasal dari diff, jadi tidak boleh mengendalikan terminal."""
    return "".join(ch if ch.isprintable() else "?" for ch in value)


def report(findings: list[Finding]) -> None:
    """Cetak laporan ke stderr. Memakai Text (bukan string) supaya isi dari diff
    tidak ditafsirkan sebagai markup atau emoji rich."""
    console = Console(stderr=True, highlight=False, emoji=False)

    def out(*parts: str | tuple[str, str]) -> None:
        console.print(Text.assemble(*parts), soft_wrap=True)

    out(("secret-guard:", "bold red"), f" {len(findings)} kemungkinan secret ditemukan")
    console.print()
    current = None
    for item in sorted(findings, key=lambda x: (x.path, x.line, x.rule)):
        if item.path != current:
            out((_clean(item.path), "bold"))
            current = item.path
        out(
            f"  baris {item.line:<5} ",
            (f"{item.rule:<20} ", "yellow"),
            (_clean(item.preview), "dim"),
        )
    console.print()
    out(("Cara menangani:", "bold"))
    out("  - Hapus secret dari file, lalu git add lagi. Kalau sudah pernah ter-commit")
    out("    atau ter-push, anggap sudah bocor dan ganti (rotate) kuncinya.")
    out("  - False positive: tambahkan '# secret-guard:ignore' di baris itu,")
    out(f"    atau pola path di {IGNORE_FILE}.")
    out("  - Lewati sekali (tidak disarankan): git commit --no-verify")


def cmd_scan(*, use_stdin: bool, ignore_file: str | None, quiet: bool) -> int:
    try:
        diff = (
            sys.stdin.buffer.read().decode("utf-8", errors="replace")
            if use_stdin
            else staged_diff()
        )
        patterns = load_ignore(ignore_file)
    except (GitError, IgnoreError) as e:
        print(f"secret-guard: {e}", file=sys.stderr)
        return EXIT_ERROR

    findings = scan_diff(diff)
    kept = [f for f in findings if not is_ignored(f.path, patterns)]
    skipped = len(findings) - len(kept)
    if skipped:
        print(
            f"secret-guard: {skipped} temuan diabaikan oleh {IGNORE_FILE}",
            file=sys.stderr,
        )
    if kept:
        report(kept)
        return EXIT_FINDINGS
    if not quiet:
        print("secret-guard: tidak ada secret ditemukan")
    return EXIT_OK


# ---- hook ----


def hook_script(python: str) -> str:
    return f"""#!/bin/sh
{HOOK_MARKER}: dibuat oleh `secret-guard install-hook`, aman ditimpa dengan menjalankannya lagi.
PY={shlex.quote(python)}
if [ ! -x "$PY" ]; then
    echo "secret-guard: interpreter tidak ditemukan: $PY" >&2
    echo "secret-guard: jalankan 'secret-guard install-hook' lagi, atau lewati dengan 'git commit --no-verify'." >&2
    exit 1
fi
exec "$PY" -m secret_guard scan --quiet
"""


def hooks_dir() -> Path:
    proc = run_git("rev-parse", "--git-path", "hooks")
    if proc.returncode != 0:
        raise _git_error(proc, "bukan repositori Git")
    return Path(proc.stdout.decode("utf-8", errors="replace").strip()).resolve()


def _is_ours(path: Path) -> bool:
    try:
        return HOOK_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _backup_path(target: Path) -> Path:
    candidate = target.with_name(target.name + ".bak")
    n = 0
    while candidate.exists() or candidate.is_symlink():
        n += 1
        candidate = target.with_name(f"{target.name}.bak.{n}")
    return candidate


def _write_hook(target: Path, script: str) -> None:
    tmp = target.with_name(target.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o755)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(tmp, 0o755)  # umask bisa mencabut bit eksekusi
    os.replace(tmp, target)


def cmd_install_hook(*, force: bool) -> int:
    try:
        hooks = hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        target = hooks / HOOK_NAME
        backup = None
        if (target.exists() or target.is_symlink()) and not _is_ours(target):
            if not force:
                print(
                    f"secret-guard: sudah ada hook {HOOK_NAME} lain di {target}\n"
                    "Hook itu tidak ditimpa. Pakai --force untuk memindahkannya ke "
                    "cadangan lalu memasang hook ini.",
                    file=sys.stderr,
                )
                return EXIT_ERROR
            backup = _backup_path(target)
            target.rename(backup)
        _write_hook(target, hook_script(sys.executable))
    except (GitError, OSError) as e:
        print(f"secret-guard: gagal memasang hook: {e}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Hook dipasang: {target}")
    if backup:
        print(f"Hook lama dipindahkan ke: {backup}")
    return EXIT_OK


def cmd_uninstall_hook() -> int:
    try:
        target = hooks_dir() / HOOK_NAME
        if not (target.exists() or target.is_symlink()):
            print("Tidak ada hook pre-commit.")
            return EXIT_OK
        if not _is_ours(target):
            print(
                f"secret-guard: {target} bukan hook secret-guard, tidak dihapus.",
                file=sys.stderr,
            )
            return EXIT_ERROR
        target.unlink()
    except (GitError, OSError) as e:
        print(f"secret-guard: gagal menghapus hook: {e}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Hook dihapus: {target}")
    return EXIT_OK


# ---- argparse ----


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secret-guard",
        description="Cegah API key dan password ikut ter-commit.",
        epilog="Kode keluar: 0 bersih, 1 ada temuan, 2 kesalahan.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {metadata.version('secret-guard')}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="pindai perubahan yang sudah di-git add")
    scan.add_argument(
        "--stdin", action="store_true", help="baca diff dari stdin, bukan dari staged"
    )
    scan.add_argument("--ignore-file", metavar="FILE", help=f"ganti {IGNORE_FILE}")
    scan.add_argument(
        "--quiet", action="store_true", help="tidak mencetak apa pun kalau bersih"
    )

    install = sub.add_parser("install-hook", help="pasang hook pre-commit")
    install.add_argument(
        "--force",
        action="store_true",
        help="pindahkan hook pre-commit lain ke cadangan lalu pasang hook ini",
    )
    sub.add_parser("uninstall-hook", help="hapus hook pre-commit milik secret-guard")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return cmd_scan(
            use_stdin=args.stdin, ignore_file=args.ignore_file, quiet=args.quiet
        )
    if args.command == "install-hook":
        return cmd_install_hook(force=args.force)
    return cmd_uninstall_hook()
