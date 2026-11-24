"""Build the desktop app with PyInstaller, then check that it starts.

    pip install pyinstaller pillow    # pillow turns the PNG icon into .icns on macOS
    python packaging/build.py                       # app only
    python packaging/build.py --installer --package # what the release workflow runs

Output in dist/:
  Windows  ClaudeTokenMeter/ClaudeTokenMeter.exe, and with --installer
           ClaudeTokenMeter-Setup-<version>.exe (needs Inno Setup 6)
  macOS    ClaudeTokenMeter.app
  Linux    ClaudeTokenMeter/ClaudeTokenMeter
--package also writes the release files (installer, zip or tar.gz) to dist/release/.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from token_meter import __version__  # noqa: E402

NAME = "ClaudeTokenMeter"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
WINDOWS = os.name == "nt"
MAC = sys.platform == "darwin"


def version_file() -> Path:
    """Windows file properties, so Task Manager and Explorer show the app's name."""
    nums = tuple(int(x) for x in re.findall(r"\d+", __version__)[:3]) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Claude Token Meter contributors'),
      StringStruct('FileDescription', 'Claude Token Meter'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'Claude Token Meter'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    BUILD.mkdir(exist_ok=True)
    path = BUILD / "version_info.txt"
    path.write_text(text, encoding="utf-8")
    return path


def build_app() -> None:
    pkg = ROOT / "token_meter"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--name", NAME,
           "--icon", str(ROOT / "packaging" / "icon.ico" if WINDOWS else pkg / "icon.png"),
           "--distpath", str(DIST), "--workpath", str(BUILD), "--specpath", str(BUILD),
           "--paths", str(ROOT),
           "--add-data", f"{pkg / 'dashboard.html'}{os.pathsep}token_meter",
           "--add-data", f"{pkg / 'icon.png'}{os.pathsep}token_meter"]
    if WINDOWS:
        cmd += ["--version-file", str(version_file())]
    if MAC:
        cmd += ["--osx-bundle-identifier", "io.github.phuocs0n.claude-token-meter"]
    subprocess.run(cmd + [str(ROOT / "packaging" / "app_main.py")], check=True)


def app_exe() -> Path:
    if MAC:
        return DIST / f"{NAME}.app" / "Contents" / "MacOS" / NAME
    return DIST / NAME / (NAME + (".exe" if WINDOWS else ""))


def self_test() -> None:
    proc = subprocess.run([str(app_exe()), "--self-test"], capture_output=True, text=True, timeout=300)
    print((proc.stdout + proc.stderr).strip() or f"self-test exit code {proc.returncode}")
    if proc.returncode != 0:
        raise SystemExit(f"self-test of the built app failed (exit code {proc.returncode})")


def find_iscc():
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        for sub in (("Inno Setup 6",), ("Programs", "Inno Setup 6")):
            exe = Path(base, *sub, "ISCC.exe") if base else None
            if exe and exe.is_file():
                return str(exe)
    return shutil.which("iscc")


def build_installer() -> Path:
    iscc = find_iscc()
    if not iscc:
        raise SystemExit("Inno Setup 6 not found. Install it from https://jrsoftware.org/isinfo.php "
                         "(or: winget install JRSoftware.InnoSetup) and run again.")
    subprocess.run([iscc, "/Q", f"/DAppVersion={__version__}", f"/DSourceDir={DIST / NAME}",
                    f"/DOutputDir={DIST}", str(ROOT / "packaging" / "windows" / "installer.iss")], check=True)
    return DIST / f"{NAME}-Setup-{__version__}.exe"


def package(installer) -> None:
    out = DIST / "release"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    v, arch = __version__, platform.machine().lower().replace("amd64", "x64").replace("x86_64", "x64")
    if WINDOWS:
        if installer:
            shutil.copy2(installer, out)
        shutil.make_archive(str(out / f"{NAME}-{v}-windows-{arch}-portable"), "zip", DIST, NAME)
    elif MAC:
        # ditto keeps the symlinks inside the .app bundle
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(DIST / f"{NAME}.app"),
                        str(out / f"{NAME}-{v}-macos-{arch}.zip")], check=True)
    else:
        with tarfile.open(out / f"{NAME}-{v}-linux-{arch}.tar.gz", "w:gz") as tar:
            tar.add(DIST / NAME, arcname=NAME)
    for f in sorted(out.iterdir()):
        print(f"{f.name}  {f.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--installer", action="store_true", help="Windows: also build the Setup .exe with Inno Setup")
    p.add_argument("--package", action="store_true", help="write the release files to dist/release/")
    args = p.parse_args()
    build_app()
    self_test()
    installer = build_installer() if args.installer and WINDOWS else None
    if args.package:
        package(installer)


if __name__ == "__main__":
    main()
