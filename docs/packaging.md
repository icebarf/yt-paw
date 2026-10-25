# Packaging — standalone builds

yt-paw ships as a **PyInstaller one-folder** bundle. The folder carries Python,
Qt/PySide6, yt-dlp, FFmpeg, and Deno, so end users do not install Python or the
engines themselves.

| Host | Target | Archive |
|------|--------|---------|
| Windows x86_64 | Windows x86_64 | `.zip` |
| Linux x86_64 | Linux x86_64 | `.tar.gz` |

> PyInstaller cannot cross-compile. Build the Windows artifact on Windows and
> the Linux artifact on Linux (`windows-latest` / `ubuntu-latest` in CI). The
> build refuses to run when the host has no pinned sidecars; use
> `--no-sidecars` for a layout-only development build.

## Quick start

Windows (PowerShell):

```powershell
uv run --group build python packaging/build.py
```

Linux:

```bash
uv run --group build python packaging/build.py
```

Install the build toolchain first if the `build` group is not synced yet:

```bash
uv sync --group build
```

## Output layout

Windows:

```
dist/yt-paw/
  yt-paw.exe
  bin/                       # yt-dlp.exe, deno.exe, ffmpeg.exe, ffprobe.exe, av*/sw*.dll
  _internal/                 # Python, Qt, app resources
  lib/                       # (absent on Windows)
  licenses/
  THIRD_PARTY_NOTICES.md
dist/yt-paw-<version>-windows-x86_64.zip
dist/yt-paw-<version>-windows-x86_64.zip.sha256
```

Linux:

```
dist/yt-paw/
  yt-paw                     # executable
  bin/                       # yt-dlp, deno, ffmpeg, ffprobe
  lib/                       # libav*.so*, libsw*.so* (FFmpeg shared libraries)
  _internal/                 # Python, Qt, app resources
  licenses/
  THIRD_PARTY_NOTICES.md
dist/yt-paw-<version>-linux-x86_64.tar.gz
dist/yt-paw-<version>-linux-x86_64.tar.gz.sha256
```

Unpack and run. The Windows build needs no installer or admin rights and is
unsigned, so SmartScreen may warn until a signing certificate is configured.
On Linux, extract with `tar -xzf …` so executable bits and FFmpeg's versioned
symlinks (`libavcodec.so.62 -> libavcodec.so.62.28.103`) are preserved:

```bash
tar -xzf yt-paw-<version>-linux-x86_64.tar.gz
./yt-paw/yt-paw
```

## Linux runtime requirements

Python, Qt, and the engines are bundled, but the Qt `xcb` platform plugin still
uses the operating system's X11/OpenGL stack. Install the usual desktop
libraries before the first run. Debian/Ubuntu:

```bash
sudo apt install libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
  libxcb-shape0 libxcb-xinerama0 libxcb-xfixes0 libxcb-randr0 \
  libxcb-render0 libxcb-shm0 libxcb-sync1 libxcb-glx0 libxcb-xkb1 \
  libxkbcommon0 fontconfig
```

Fedora:

```bash
sudo dnf install mesa-libGL libxkbcommon-x11 xcb-util-cursor xcb-util-wm \
  xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util xcb-util-xrm \
  fontconfig
```

Arch:

```bash
sudo pacman -S mesa libxkbcommon-x11 xcb-util-cursor xcb-util-wm \
  xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util fontconfig
```

These are inherited from the distro on purpose: shipping glibc/X11/GL would
tie the bundle to one distribution. Build on the **oldest glibc** you intend to
support (for example Ubuntu 22.04) — a binary built against newer glibc will
not start on older systems.

FFmpeg is the exception: its shared libraries are bundled in `lib/` and the
binaries in `bin/` carry `RPATH=$ORIGIN/../lib`, so no `LD_LIBRARY_PATH` is
needed. yt-dlp finds `ffmpeg`/`ffprobe` through the `bin/` directory that
`infra/runtime_paths.py` prepends to child-process `PATH`.

## What is bundled

| Piece | Source | Notes |
|-------|--------|-------|
| Python runtime | build interpreter (3.13 in CI) | frozen by PyInstaller |
| PySide6 / Qt | `pyproject.toml` | exact pin; only the Qt modules the app imports |
| yt-dlp | `packaging/sidecars.lock.json` | Unlicense; auto-updates at runtime |
| Deno | `sidecars.lock.json` | MIT; used by yt-dlp for JS challenge solving |
| FFmpeg | `sidecars.lock.json` (BtbN `lgpl-shared`) | LGPL shared build + DLLs on Windows, `.so` libraries on Linux |

The sidecar lockfile pins an exact URL and SHA-256 for every download, per
platform. A checksum mismatch aborts the build instead of shipping unreviewed
bytes.

## Dependency updates

Pinned Python and native dependencies use a deliberately slow release train:
quarterly-ish, with a minimum release age. Do not bump a version merely because
upstream published one. The single entry point is `packaging/deps.py`; the full
policy and agent runbook are in [`dependency-updates.md`](dependency-updates.md).

```bash
uv run python packaging/deps.py status          # read-only check
uv run python packaging/deps.py update --due    # only when the train is due
uv run python packaging/deps.py verify
```

`packaging/dependency-policy.json` controls cadence; `packaging/dependency-state.json`
records the last review. Both must be committed with a dependency change.
`uv.lock` must stay tracked as well.

`fetch_sidecars.py --update-pins` remains a low-level checksum refresh for
debugging and for FFmpeg's rolling build. Routine updates should go through
`deps.py update --due`, which also handles Python pins, versions, and state.

## Build options

```bash
uv run --group build python packaging/build.py --no-sidecars      # dev build, no yt-dlp/ffmpeg/deno
uv run --group build python packaging/build.py --force-sidecars   # ignore build/sidecar-cache/
uv run --group build python packaging/build.py --skip-self-check  # skip the frozen-app smoke test
uv run --group build python packaging/build.py --skip-verify      # skip layout verification
uv run --group build python packaging/build.py --no-zip           # keep only dist/yt-paw/
uv run --group build python packaging/build.py --keep             # reuse build/ and dist/yt-paw/
```

`--no-zip` means "skip the archive" on both platforms.

Sidecars can be fetched separately, for the host or another platform:

```bash
uv run python packaging/fetch_sidecars.py                     # host platform
uv run python packaging/fetch_sidecars.py --platform linux-x86_64
uv run python packaging/fetch_sidecars.py --force             # bypass the download cache
uv run python packaging/fetch_sidecars.py --only ffmpeg
uv run python packaging/fetch_sidecars.py --update-pins       # refresh this platform's pins
uv run python packaging/fetch_sidecars.py --platform all --update-pins
```

`--update-pins` fetches each upstream checksum file and rewrites the `sha256`
fields in `packaging/sidecars.lock.json`. It is a low-level repair/debug tool,
not the routine update path; use `deps.py update --due` for releases. Review any
pin diff before committing. FFmpeg's BtbN URLs are rolling `latest` assets, so
their pins must be refreshed when upstream publishes a new build; builds fail
closed until then.

## Runtime layout and updates

Windows:

```
<install>/bin/
  yt-dlp.exe          # bundled stable fallback
  ffmpeg.exe          # + ffprobe.exe and av*/sw* DLLs
  deno.exe
```

Linux:

```
<install>/bin/
  yt-dlp
  ffmpeg              # + ffprobe; libs in ../lib
  deno
<install>/lib/
  libavcodec.so*      # FFmpeg shared libraries + versioned symlinks
  libavformat.so*
  libavutil.so*
  ...
```

`infra/runtime_paths.py` puts app-managed and bundled `bin/` directories on the
`PATH` of every engine child process. Resolution order for engines and
dependencies is:

1. `<app-data>/bin/` — downloaded/auto-updated by the app
2. `<install>/bin/` — what the build ships
3. system `PATH` — respected but never overwritten

yt-dlp auto-updates into `<app-data>/bin/`, not the install folder. This keeps
Program Files (or any read-only location) untouched and needs no elevation. The
bundled copy remains the offline/first-run fallback.

App data stays in `~/.config/yt-paw/` (`app.db`, `logs/`, managed binaries).
Set `YTPAW_PROFILE_DIR` to use a different profile (also used by the build's
self-check).

## Verification

`uv run --group build python packaging/build.py` runs two checks automatically
on both platforms:

1. `packaging/verify_build.py` checks the executable, packaged QSS/icons, Qt
   platform/TLS/JPEG plugins, and the platform's sidecars (`.exe` + FFmpeg DLLs
   on Windows; executables + `lib/libav*.so*` on Linux).
2. `yt-paw[.exe] --self-check` starts the frozen app against a scratch profile,
   resolves every engine/dependency, probes their versions, checks UI assets,
   writes `<profile>/self-check.txt`, and exits non-zero on failure. Because it
   imports Qt at startup, it also catches missing Qt libraries.

The same check can be run manually.

Windows:

```powershell
$env:YTPAW_PROFILE_DIR = "$env:TEMP\yt-paw-check"
.\dist\yt-paw\yt-paw.exe --self-check
Get-Content "$env:TEMP\yt-paw-check\self-check.txt"
```

Linux:

```bash
YTPAW_PROFILE_DIR=/tmp/yt-paw-check ./dist/yt-paw/yt-paw --self-check
cat /tmp/yt-paw-check/self-check.txt
```

The report lists each engine/dependency with `origin=bundled` when the packaged
sidecars are being used.

## Releasing

A release is tag-driven. The tag must match the version in
`src/ytpaw/__init__.py` and `pyproject.toml` (`v0.1.1` for version `0.1.1`).

```bash
git tag -a v0.1.1 -m "yt-paw 0.1.1"
git push origin v0.1.1
```

`.github/workflows/build.yml` then:

1. validates the tag/version match;
2. runs lint, type checks, and tests on Linux;
3. builds both artifacts in parallel (Windows on `windows-latest`, Linux on
   `ubuntu-latest`);
4. creates a **draft** GitHub Release with generated release notes and uploads
   both archives and their `.sha256` files;
5. publishes the release only after all assets are attached.

If any step fails, the release remains a draft. Re-run the failed workflow for
the tag after fixing the problem. Manual `workflow_dispatch` runs only produce
temporary workflow artifacts; they do not publish a release.

## Licensing

The bundle includes LGPL components, so `packaging/THIRD_PARTY_NOTICES.md` and
`licenses/LGPL-3.0.txt` are copied into every distribution. Qt and FFmpeg are
shipped as replaceable shared libraries on both platforms (Windows DLLs, Linux
`.so` files in `lib/`), not statically linked. If you add another sidecar or
engine, update the notices and the lockfile together.

## Size notes

A full bundle is large because it contains Qt, Deno, FFmpeg and yt-dlp
(roughly 350–450 MB unpacked on Windows and 450–550 MB on Linux; ~200–300 MB
compressed). Use `--no-sidecars` for layout/dev builds. Drop Deno only if you
accept slower/limited YouTube extraction; the app will download it on first run
if missing.
