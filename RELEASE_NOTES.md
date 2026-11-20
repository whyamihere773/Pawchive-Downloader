### 🏗️ Architecture & Performance Improvements

* **Cleaner modular structure**: Reorganized the existing codebase by splitting oversized all-in-one files into smaller, focused modules with a plug-and-play layout for cloud and media providers, making future updates faster and safer.
* **Smoother interface under heavy load**: Pinned the interface to a dedicated high-performance CPU core and moved heavy work — like browsing huge folders, saving settings, testing AI recognition, exporting links, checking disk space, and refreshing Browser badges — to background workers so the window stays responsive.
* **Faster large-library handling**: Sped up Queue updates, failed-task counters, Post Selector inspection, and Favorites Browser scrolling, and stopped a hidden Link Vault animation from running while closed.
* **Consistent browser-style text inputs**: Every search bar and text field across the app now highlights all text on first click, scrolls long text cleanly without overflowing, and includes a right-click menu.
* **Crash-proof session logs**: Logs now save immediately to disk as events happen and automatically write a dedicated crash report if the app ever closes unexpectedly.

---

### 🖼️ Gallery, Visual Sorter & Media Viewer

* **Gallery empty-space gap fixed**: Removed the large blank gap that appeared above the Gallery grid whenever no alert banners were active.
* **Visual Sorter controls fixed**: Fixed invisible card overlays that blocked clicks on bucket rename, filter, inline rename, and keep/skip buttons.
* **Character & Series filter restored**: Brought back the missing Character & Series filter button in the Gallery toolbar.
* **Safer Gallery Cleaner & tidy Batch Rename**: Prevented accidental scans of entire system drives, fixed the live scan indicator, and stopped long Batch Rename destination paths from overflowing.
* **Media Lightbox & Favorites Browser fixes**: Retrying a failed video stream in the Lightbox now properly restarts playback instead of freezing, and Favorites Browser grids resize cleanly without lag.

---

### ⬇️ Downloads, Queue & Cloud Providers

* **Video duration & DM date filters fixed**: Filtering downloads by video length no longer crashes before transfers begin, and date range filters now properly apply when fetching creator direct messages.
* **Reliable Mega, Dropbox & GoFile downloads**: Resuming partial Mega downloads no longer corrupts files, and canceling Mega, Dropbox, or GoFile transfers cleanly removes incomplete temporary files on Windows.
* **Google Drive & Telegram fixes**: Google Drive folder downloads now report properly when filters skip all files, and Telegram handles private channel links, missing attachments, and wait-timer cancellations reliably.
* **Queue & Post Selector fixes**: Starting selected posts no longer clears unrelated Queue items, re-queuing right after clearing the Queue works cleanly, empty batch resumes no longer freeze the downloading state, text-only posts stay selectable, paused counts stay accurate, and all download requests respect your proxy settings.
* **Watchlist improvements**: Renaming a creator's folder keeps their Watchlist paths updated automatically, mixed date formats sort reliably, and refresh animations reset smoothly.

---

### 📦 Decompressor, Archive, Browser & Settings

* **Compression settings respected**: Custom video encoding presets, audio codecs, and custom video options in the Bulk Decompressor are now applied instead of being silently ignored.
* **Password prompt polished**: Reopening the password prompt for a new encrypted archive now clears the previous entry and focuses the input box automatically.
* **Archive integrity, Video Fingerprinting & macOS fixes**: Video Fingerprinting works on folders with spaces or special characters, deleting archived paths and verifying creator integrity keep totals in sync, Watchlist folders appear in archive rebuild suggestions, confirmation popups block stray clicks behind them, and revealing folders works properly on macOS.
* **Browser & Statistics fixes**: Toggling creator favorites and clicking "Accounts in Settings" in the Browser now work reliably, direct messages stay tracked properly, and Graphics & Documents totals show up accurately in Statistics.
* **Settings, Console & Updater fixes**: Fixed the Connected Accounts indicator in Settings, wired up the "Auto-sync Known.txt" and "Show console links" toggles, fixed Console copy shortcuts (`Ctrl+Shift+C` / `Shift+C`) and right-click copy, and fixed the standalone Updater getting stuck in a repeat update-check loop.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
