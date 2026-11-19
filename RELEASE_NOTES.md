> **Heads up:** The next update might take a little longer than usual — I'm taking some time to clean up the codebase a bit so future updates are smoother and faster to ship.

---

### ⚡ Pawchive Speed & Rate-Limit Fixes

* **Fixed ultra-slow Pawchive downloads & 429 rate-limit loops**: Downloading creators with unimported posts or lots of small images no longer triggers waves of failed or burst requests that cause Pawchive to throttle speeds to a crawl.
* **Smoother pacing & smarter automatic slowdowns**: Pawchive downloads now request files from the right server at a steady pace, automatically step down active threads on the very first rate-limit warning, and pause briefly instead of hammering the server nonstop or saving small thumbnails instead.
* **Faster scanning of unimported posts**: Scanning creators with unimported posts skips unnecessary extra page checks so scans finish much faster.

---

### ⚠️ Unimported Pawchive Post Handling

* **Clear notice without stopping downloads**: When a post or creator hasn't been physically imported onto Pawchive's servers yet, the app marks those items as Not Imported and keeps downloading everything else without stopping. The notice modal includes a "Do not show again" option (while keeping the warning in the Progress Log) and an "Open Settings" button that jumps straight to the thumbnail fallback toggle and highlights it.
* **Visible in Queue & Retry window, with retrying disabled**: Unimported files still show up in your Queue and Retry Failed window with a clear amber warning so you don't miss them, while retrying is disabled since those files aren't on the server yet.
* **Automatic Watchlist pickup later**: Unimported posts are no longer marked as finished in your Watchlist, so they will be detected and downloaded automatically once Pawchive imports them.

---

### 📦 Download Archive Improvements

* **Rebuild archive in the background with crash recovery**: You can now minimize an active Archive Rebuild to a compact progress bar at the bottom of the app and keep using every tab normally. Progress is saved automatically after every batch (and on pause or exit), so if the app closes or power cuts out, you can resume right where it left off without re-scanning finished files.
* **Creators & file paths preserved on backup**: Exporting your Download Archive now defaults to a full JSON backup that keeps creator names and file locations intact instead of turning everything into "Unknown Creator" on re-import.
* **Direct database import & text import fix**: You can now import an archive database file directly, and importing older text-list backups no longer breaks on filenames that contain spaces.

---

### 🌐 Browser Download Dialog & Layout Fixes

* **Choose where Browser downloads go**: Starting or queueing any download from the Browser now opens a confirmation dialog where you can pick your save folder, automatically remember the last folder you chose, and access all Downloader settings right from the dialog.
* **Automatic separate folders for multiple creators**: Selecting multiple creators in the Browser automatically gives each creator its own subfolder inside your chosen destination so files never mix together.
* **At-a-glance on-disk post indicators in Online Browser**: When viewing a creator you already have on disk, posts you own in full are outlined in green, partially downloaded or pruned posts are outlined in yellow (with file counts like `4/12`), and posts not on disk stay unoutlined.
* **Fixed Browser card overflow**: Creator cards and post cards in the Browser now keep buttons, stats, and action links cleanly inside card borders without clipping off the right edge.

---

### ✨ Interface Improvements

* **Consistent text bars & right-click menus everywhere**: Every search bar, password field, URL input, and text box across the app now supports mouse text selection, full-bar click-to-focus, and the right-click context menu (Paste, Copy, Cut, Select All, Clear) — even inside pop-up dialogs.
* **Fixed Gallery shortcuts hijacking typing**: Pressing Ctrl+A, Delete, or Ctrl+Z while typing in the Gallery search bar now edits your search text instead of selecting or deleting gallery files.

---

### 🐧 Linux & CachyOS Fixes

* **Fixed Linux startup crash & Fontconfig warnings**: Stopped bundling conflicting Ubuntu system libraries so the app uses your system's own graphics and font drivers, and added an automatic fallback to software rendering (plus a `--software-render` launch option) if hardware OpenGL isn't available.
* **One-click Linux desktop installer & cleaner archive folder**: Added an included desktop installer script to set up the application menu shortcut, icon, and `pawchive://` link handler from any portable folder, removed spaces from the extracted folder name, and fixed misleading `.exe` log labels on Linux.
* **New experimental Flatpak & Arch/CachyOS packages**: Added experimental universal Flatpak and Arch `pacman` builds alongside the portable Linux download, with Windows builds now listed first on GitHub Releases.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
