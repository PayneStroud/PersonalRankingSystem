# Personal Ranking System App Build

This project can be packaged as a desktop app for macOS and Windows using PyInstaller.

## Local build (macOS or Windows)

1. Install dependencies:

```bash
python3 -m pip install -r requirements-app.txt
```

2. Build app:

```bash
python3 build_personal_ranking_app.py --clean
```

3. Find output in `dist/`:
- macOS: `dist/Personal Ranking System.app`
- Windows: `dist/Personal Ranking System/` (or `.exe` if built with `--onefile`)

## Downloadable builds for Mac + Windows (GitHub Actions)

The workflow file is at `.github/workflows/build-desktop-app.yml`.

If you push this project to GitHub, then:
- Trigger manually via **Actions > Build Desktop App > Run workflow**, or
- Push a tag like `v1.0.0`.

The workflow uploads macOS and Windows build artifacts for download.
