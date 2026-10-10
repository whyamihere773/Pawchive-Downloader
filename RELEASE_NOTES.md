### ⚡ Faster With Huge Libraries

Tested with 2 million archived files, 50,000 Watchlist artists, 500,000 queued files, 10,000 Link Vault creators and more. Times are how long the window used to freeze → now.

* **Archive tab**: Opening 4.8 s → under 0.1 s, search 2.7 s → 0.04 s, file-type filter 4.2 s → 0.1 s, statistics 3.3 s → 0.2 s. Opening a creator: up to 10 s → instant.
* **Download queue**: Loading 500,000 files 3.5 s → 0.2 s. Thousands of files changing at once 9 s → 0.2 s.
* **Retry Failed**: Opening with 5,000 failed files over 2 minutes → under 0.1 s. Retrying 20,000 files 4 s → 0.1 s.
* **Watchlist**: Scrolling, searching and filtering 50,000 artists under 0.1 s. Check All on Pawchive and cum.st: hours → minutes (45 artists checked in 3 s).
* **Link Vault**: Opening 10,000 creators took minutes → instant.
* **Known Series**: Adding or removing a character with 10,000 in the list 0.85 s → under 0.1 s.
* **Decompressor**: Showing, scrolling and selecting 5,000 archives 2–5 s → under 0.1 s. Extracting is up to twice as fast (the password check 1.7 s → 0.1 s per archive).
* **Saving download progress**: Rewriting up to 700 MB every 30 s → only what changed.
* **Log files**: About 95% smaller (294 KB → 13 KB).

---

### ✨ New

* **Compress pictures and videos** *(opt-in)*: In the Decompressor after extracting, or from the Gallery's right-click menu. Pick a format and quality for pictures, videos and animated pictures, and choose at the end whether to keep the originals.
* **Change an artist's download folder**: The 📂 button in the Watchlist now really changes it and can move the files already downloaded, with progress and Stop.
* **Site in Folder Name** *(on by default)*: Turn it off to name folders "Artist" instead of "Artist [platform]".
* **Windows and Linux share your data**: Folders saved on one system work on the other ("D:\Art" ↔ "/mnt/d/Art").
* **Browser sign-in for embedded videos** *(off by default)*: Lets videos that need you to be logged in, like RedGifs, download. Firefox works best.
* **Tidier Decompressor**: The page scrolls, its options fold away, and its settings are remembered.

---

### 🛠️ Fixes

* **No more endless "Unfinished Download" prompt**: It only appears when files really never got their turn.
* **Gallery copy, compress and extract work again**: Every file failed with "name 'time' is not defined".
* **Watchlist stops repeating itself**: Posts with missing or removed files no longer show up as new after every download, and updates found are kept after a restart.
* **Watchlist folders stick**: A folder you chose is no longer moved back or shown twice, and auto-check is respected at start-up.
* **Retry picks the right files**: Only the files you selected are retried, the count is always right, and small or WebP pictures aren't downloaded again.
* **Archive repairs itself**: A damaged archive is fixed automatically, removing a creator works again, and a failed export says why.
* **Split archives with 10+ parts**: Parts 10–19 are no longer extracted as separate archives.
* **Nothing lost after a 7-Zip warning**: Files already extracted are kept instead of deleted.
* **Clearer video errors**: Gfycat links count as gone, and RedGifs "410" errors are explained.
* **Long translations fit**: Buttons and options no longer cut off text in Russian and other languages.

---

### 📦 Good to Know

* **Your data moves over automatically**: The archive, Watchlist, history and Link Vault move to faster storage on first start; the old files are kept as backups (`.migrated`).
* **One-time preparation**: A big archive is prepared in the background on first start (about 2 minutes for 2 million files), and the Archive tab is slower until it's done.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
