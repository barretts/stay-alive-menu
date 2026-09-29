# Stay Alive — original NTSC DVD menu archive

Open **index.html** for the local asset gallery. Open **Menu-Map.md** for the navigation summary. No server or internet connection is needed.

86 unique menu assets; 34 menu program chains; 61 assets with buttons; 36 character combinations; 138 original subpicture packets; 2116 selected/activated highlight PNGs.

## Contents

- `original/`: unchanged original IFO, BUP, and menu VOB files.
- `assets/`: one directory per unique physical cell, with original VOB sectors, playable MP4, original AC3 and AAC audio where present, thumbnails, button diagrams, original SPU packets, indexed masks, normal overlays, and selected/activated button sprites.
- `manifest.json`: complete machine-readable inventory, palettes, timings, DVD registers/commands, button boxes, and asset references.
- `navigation-map.json`, `buttons.csv`, `assets.csv`: navigation and spreadsheet inventories.
- `contact-sheet-*.jpg`: visual inventory.
- `validation.json`: verification results.
- `utilities/`: reproducible extraction scripts and requirements.

## Git contents

The Git checkout includes the working gallery and menu-only view, playback MP4s, thumbnails, normal/highlight overlays, button diagrams, navigation data, contact sheets, and utilities. `.gitignore` excludes original DVD files, raw extracted VOB/audio/subpicture packets, duplicate AAC files, rendering intermediates, per-asset caches, and logs. Those files remain in the local archive; excluding them from Git does not delete them.

A fresh checkout can play and navigate the menus. Original VOB download links and full source validation require the excluded local files. Re-extraction and re-encoding require the original DVD source described below.

## Interpretation and timing

- Original VIDEO_TS/VTS menu VOBs, IFOs and BUPs are copied unchanged. All 86 unique menu sector ranges are retained.
- The gallery follows the extracted menu commands for screen navigation, customization, activation, and stream selections. Full movie playback and DVD resume behavior are external destinations; raw conditional commands remain in the map.
- Some menu cells are a single still frame held by DVD navigation. Their MP4 video track can be shorter than the IFO hold or audio.
- Browser previews retain the background video/audio. Original normal subpictures and selected/activated button graphics are separate PNG assets, with PTS timing.
- Movie, trailers, and visual-effects title bodies are external navigation targets; this menu archive does not duplicate them.
- Preview size is 854×480 square pixels; original video and button coordinates are 720×480 anamorphic. Pan-and-scan button groups are separately retained.

Choose **Explore the DVD menu**, or open any asset. Click the original menu hotspots or sidebar buttons to move between screens. Arrow keys follow the DVD directional links; Enter selects. Character, shirt, weapon, activation, setup, and return routes keep the current menu state. Browser Back and Forward restore the previous screen and selection. Each screen has an `#asset=...` link. Original transitions advance automatically and can be skipped. Short black dispatcher holds are skipped. Movie, commentary, chapter, and bonus-video destinations show a link to the separate video file. These menu choices do not change the existing movie export. The three successful activation combinations are identified in the map from their actual Activate commands.

The source rip is `G:\_new\STAY_ALIVE\VIDEO_TS`. The movie upscale remains separate in `D:\StayAlive`.

Choose **Menu-only view**, or open `index.html?view=menu`, for a viewport-fitted menu with automatic video and sound, original hotspots, and keyboard navigation. Small sound and Archive controls appear on movement or keyboard focus. If the browser blocks audible autoplay, video starts muted and sound enables on the first click or menu selection; an explicit mute stays muted across screens. Browser history and `#asset=...` links work in both views.
