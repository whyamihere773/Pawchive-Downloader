### 🌐 Built-In Creator & Local Library Browser

* **New Browser tab**: Browse creators, posts, direct messages, and tags directly inside Pawchive Downloader across Pawchive, cum.st, and CoomerFans without leaving the app.
* **Account favorites & sign-in**: Favorite or unfavorite creators directly from creator cards and profiles with instant sync to your Pawchive or cum.st account, plus a dedicated **Favorites** category and an in-app sign-in prompt when logged out.
* **Scrollable service bar**: Browse through all supported creator platforms smoothly using horizontal scrolling and quick left/right arrow controls.
* **Multi-drive Local On-Disk mode**: Switch between online browsing and your saved local library across multiple drives, move creator folders to another drive in one click, and check for new online posts.
* **Selection cart & in-app media viewer**: Mark creators and posts across pages to download or follow in your Watchlist together, and preview photos, animated GIFs, videos, and audio directly inside the post viewer.
* **One-click link copying & preview notices**: Copy the link to any creator, post, or individual attachment straight from the viewer or full-screen preview, and see clear warning badges on creators and posts that have not been imported in full yet.
* **Responsive narrow layout**: Toolbars, search and sort controls, creator headers, post details, and the bottom selection tray wrap cleanly when the log console panel is open.

---

### 🖼️ Gallery Previews, Layout & Visual Sorter

* **Folder preview thumbnails**: Folders in the Gallery tab now show cover previews of the images and media inside them so navigating creator folders is much faster.
* **Whole-image & custom frame styles**: Switch between **Fit (Whole Image)** to view tall or wide artwork without cropping edges, or **Fill Frame (Crop)**, alongside **Square**, **Portrait**, and **Landscape** card shapes and a **Clean Cards** toggle.
* **Organize media by visual style & mood**: Open **Visual Sort** in the Gallery tab to group files automatically by visual medium, resolution and framing, color mood, character tags, or custom text prompts.
* **Safe virtual preview & undo**: Preview how files will be grouped before touching anything on disk, commit approved folders when ready, and undo changes anytime with Ctrl+Z.
* **Optional vision model support**: Download the lightweight Visual Sorter vision model in Settings → Character & Franchise Recognition for stronger visual clustering and custom prompt sorting.

---

### ☑️ Post Selector Overhaul

* **Play videos & animated GIFs directly**: Watch videos and animated GIFs right inside the post selector preview instead of seeing a "No Preview" warning, and check clear warning badges on unimported posts.
* **Shift-click range selection**: Click any post or attachment, then hold Shift and click another to select or deselect the entire range in one step.
* **Faster switching between previewing & selecting**: Click to open a post (or turn on **Select Mode** in the header for one-click toggling) and hold Ctrl while clicking to do the opposite without aiming for small checkboxes.
* **Larger window & kept progress**: The post selector now uses nearly the full window width, ignores accidental clicks on the outside backdrop or title bar, and keeps your checked posts, search text, and loaded list if you close and reopen it.

---

### ⚡ Mid-Download Settings & Watchlist Upgrades

* **Change settings mid-download**: Editing folders, filters, naming rules, or download options while transfers are active now prompts you to continue with the new settings, restart cleanly from scratch, or apply changes only to future downloads.
* **Edit Watchlist creator settings anytime**: Change custom folders, cutoffs, and download filters directly on any Watchlist creator, with a clear prompt if that creator is currently downloading.
* **Fixed Watchlist folder & path bugs**: Shortening or changing a creator's download folder no longer gets overridden by old settings or saves to the wrong place, and missing creator folders are created automatically.
* **Safer full re-downloads**: Choosing to re-download a creator now warns you clearly, deletes old files and archive history for that creator first, and starts fresh using your updated settings.

---

### 📊 New Statistics Tab

* **Your download stats in one place**: A new **Statistics** tab shows how much you've downloaded and uploaded, how much space your library takes, and how many artists, posts, files and folders you have.
* **Breakdowns by drive, file type and site**: See how your library is spread across drives, file types (images, videos, archives…) and creator platforms.
* **Export & share**: Copy a quick summary, or save the full numbers as a CSV or JSON file.

---

### 🐧 Linux & Startup Fixes

* **Linux startup crash fixed**: The Linux build no longer closes a second after opening with a "bool_dealloc" error (seen on Linux Mint, Arch, CachyOS and others).
* **yt-dlp updates work on Linux again**: The automatic yt-dlp update no longer fails with a "symbol lookup error", and opening folders, extracting archives and compressing videos run reliably with your system's own tools.
* **No more freeze on PCs without a graphics card**: The app no longer hangs at startup on virtual machines or computers without hardware video encoding when FFmpeg is installed.

---

### 🛠️ Updater, Link & Workspace Fixes

* **Windows updater exit & deep-folder fixes**: Installing updates inside long Windows folder paths works properly without misleading "No permission" errors, and the updater window now closes cleanly when finished.
* **cum.st post & creator links fixed**: Copied links and saved post info links for cum.st now use the right website address format so every post opens directly in your browser.
* **Live progress in Archive on large creators**: Removing or refreshing creators with huge libraries no longer makes the Archive tab look frozen—live status indicators keep you informed while the app stays responsive.
* **Hide or show workspace tabs**: Customize which top-level tabs appear in Settings → Workspace & Tab Bar Visibility to keep your workspace clutter-free.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
