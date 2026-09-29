Requires Python 3.13, FFmpeg/ffprobe in PATH, and Pillow.

Install the isolated image dependency with `python -m pip install --target vendor -r requirements.txt`.

Run extraction, rendering, catalog generation, and validation in that order:

```powershell
python archive_menu.py --source "G:\_new\STAY_ALIVE\VIDEO_TS" --out "D:\StayAlive\MenuArchive"
python render_assets.py "D:\StayAlive\MenuArchive"
python build_catalog.py "D:\StayAlive\MenuArchive"
python validate_archive.py "D:\StayAlive\MenuArchive"
```

Rendering resumes completed asset directories. The source is only read. This is a binary-table extraction and static disassembly, not a DVD virtual-machine emulator.

Structure references: https://github.com/mirror/libdvdread (ifo_types.h, nav_types.h, nav_read.c), https://github.com/mirror/libdvdnav (vmcmd.c), and https://github.com/FFmpeg/FFmpeg (dvdsubdec.c).

The interactive gallery additionally loads `menu-navigation.js`. `test_navigation.js` checks all widescreen button routes and gallery interactions when injected after the gallery script. `check_live_navigation.py` checks actual Chrome playback, automatic transitions, and browser history using DevTools. The gallery implements the menu command subset found on this disc, with external title destinations; it does not play or modify the separate movie export.

For UI changes, rebuild only the HTML without Pillow or changes to the extracted archive:

```powershell
python build_catalog.py "D:\StayAlive\MenuArchive" --page-only
```

The **Menu-only view** link enters `index.html?view=menu` within the click gesture so playback can start with sound. Direct visits attempt the same, with muted autoplay and first-interaction sound activation when browser policy requires it. This mode shares the gallery's menu state, overlays, routes, and media files.

Run `python check_menu_only.py` for focused local Chrome checks with fresh test profiles: normal and restricted autoplay, first-click sound, explicit mute, keyboard and touch navigation, browser history, deep links, automatic transitions, external destinations, and the existing 515 button routes. It also verifies a Play control when both autoplay attempts are denied and ignores delayed playback failures from old screens. Reports and desktop/mobile screenshots are written to a temporary directory printed by the command. Use `--only normal`, `--only restricted`, or `--only gallery` to run one group. Runtime inspection does not grant user gestures; clicks and keys use browser input events.

`python build_site.py` creates a new `_site/` directory containing only website assets and linked documents. It requires Python 3.9 or newer and no external packages. The GitHub Pages workflow runs it on Ubuntu and deploys the bundle on pushes to `main`; enable Pages with **GitHub Actions** as the publishing source. To verify a served site, pass its full viewer URL to `check_menu_only.py --url URL`.
