#!/usr/bin/env python3
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

APP_NAME = "Personal Ranking System"
SCRIPT_PATH = Path(__file__).resolve().parent / "Personal Ranking System 2.0 Beta.py"


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build(clean: bool, onefile: bool):
    if not SCRIPT_PATH.exists():
        raise FileNotFoundError(f"App script not found: {SCRIPT_PATH}")

    common = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        APP_NAME,
        "--collect-all",
        "customtkinter",
        "--hidden-import",
        "customtkinter",
        str(SCRIPT_PATH),
    ]

    if clean:
        common.insert(3, "--clean")

    system = platform.system().lower()
    if system == "darwin":
        common.extend(["--osx-bundle-identifier", "com.paynestroud.personalrankingsystem"])
    elif system == "windows":
        common.extend(["--icon", "NONE"])

    if onefile:
        common.append("--onefile")

    run(common)


def main():
    parser = argparse.ArgumentParser(description="Build Personal Ranking System desktop app.")
    parser.add_argument("--clean", action="store_true", help="Clean build cache before packaging")
    parser.add_argument("--onefile", action="store_true", help="Build onefile binary instead of folder bundle")
    args = parser.parse_args()

    build(clean=args.clean, onefile=args.onefile)

    dist = Path("dist")
    system = platform.system().lower()
    if system == "darwin":
        artifact = dist / f"{APP_NAME}.app"
    elif system == "windows":
        artifact = dist / (f"{APP_NAME}.exe" if args.onefile else APP_NAME)
    else:
        artifact = dist / APP_NAME

    print("\nBuild complete.")
    print(f"Artifact: {artifact}")


if __name__ == "__main__":
    main()
