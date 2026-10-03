> 👋 **A quick note before you dive in:** Sorry for the long wait since the last update, and sorry that this one is so big! A lot has changed, including a whole new Gallery and early Linux support, so take your time looking through it. I also went through the entire codebase again looking for bugs, so hopefully (fingers crossed 🤞) everything just works. If anything feels off after updating, please let me know.

---

### ⚠️ Kemono and Coomer Turned Off (for now)

* **Kemono and Coomer are switched off**: Both sites are mostly not working at the moment, so Pawchive no longer uses them. When you use a Kemono link, the app offers the same link on Pawchive, which has the same creators and posts; for Coomer creators, use cum.st.
* **Clear status in Settings**: Kemono and Coomer show as "Turned off" under Accounts, with a note on where to go instead.

---

### 🔒 Safer Logins

* **Your login only goes to its own site**: Your login cookie is now sent only to the site it belongs to, never to other file hosts.
* **Passwords stay private**: Your password is only used to log in. It's never stored, never sent as a cookie, and never shown in the app or the log.
* **Cookie kept out of plain files**: The cookie lives only in the encrypted vault. It's removed from settings.json and no longer included when you export your queue.
* **Linux logins keep working**: Saved logins on Linux no longer stop working after changing network hardware, like a USB Wi-Fi adapter or a dock.
* **Shared queue files are safe**: An imported queue file can no longer save files outside your download folders.
* **Telegram files stay in their folder**: A file posted with a name that points somewhere else on your computer is saved inside the channel's folder.
* **Saved logins kept safe on Linux and macOS**: If the login key can't be read for a moment (for example on a drive that isn't ready yet), your saved logins are no longer replaced and lost.

---

### 📥 More Reliable Downloads

* **No more half-finished files**: Files are downloaded under a temporary name and only get their real name once complete, so an interrupted download is never mistaken for a finished one. It continues where it stopped next time.
* **Damaged downloads are caught**: Pawchive files are checked against their fingerprint (SHA-256) and downloaded again if anything got corrupted on the way.
* **Your old copy stays until the new one is ready**: When a small preview is upgraded to the full-size file, the old copy is only replaced once the new one has fully downloaded.
* **Pawchive works on fresh installs**: Linux and source installs that were missing a small component could fail to load anything from Pawchive. It's now installed with the app.
* **Long names on Windows**: Very long post or file names are shortened automatically instead of failing to save.
* **Disk space checked per file**: A file only starts downloading when there's room for all of it, instead of failing halfway through.
* **Names with # or & download correctly**: File names containing special characters no longer break their download link.
* **Files with the same name are all downloaded**: When an album (Bunkr, Telegram…) has different files with the same name, each one is saved, as "name (2).png" and so on. Before, only the first was kept, or the files could overwrite each other.

---

### 🔢 Choose Which File Comes First

* **File order in posts** *(new option)*: Pick "As posted", "Reversed" or "By file name" in Downloader → Engine → Folder Organization & Naming. Useful for creators who upload the newest version first, so the original gets #1 with the index prefix or numbered file names.
* **Name order that works in any language**: "By file name" counts numbers properly (2 before 10, "page 9" before "page_10") and understands Japanese and Chinese numerals, full-width characters, accents and other alphabets.
* **Same order in Select Posts…**: The post preview lists files in the chosen order and has the same switch, so the #1 you see is the #1 you get.

---

### 📅 Watchlist & Scheduler

* **Posts count as downloaded only when they are**: The Watchlist now records your progress from posts whose files actually finished. Posts that failed, were cancelled or were left out by a date filter are offered again on the next check.
* **Watchlist Sync downloads new posts**: Scheduled Watchlist Syncs now download what they find, instead of only counting it.
* **Computer stays awake while downloading**: "Sleep prevention" now keeps the computer awake for the whole download, on Windows, Linux and macOS. Before, it only lasted for the moment a schedule started.
* **Your queue is kept**: Starting a new link no longer throws away files you queued or the copy saved after a crash; the new files are added to the queue. Scheduled creator downloads join a running download instead of being skipped.
* **Queued files survive closing the app**: Files added with "Add to Queue" but not started yet are saved when you close Pawchive and offered again next time.
* **"Sweep auto-retry" works**: Scheduled downloads with this option now retry failed files once more at the end.
* **"Re-download All" joins the queue**: Re-downloading a Watchlist creator replaces only that creator in the queue, even while other files are downloading. You can re-download several creators in a row without waiting, and the rest of your queue is kept.

---

### ⚡ Faster & Smoother

* **Faster start**: Tabs are built the first time you open them, so Pawchive starts quicker and uses less memory.
* **Tabs open without freezing**: That first build happens in the background with a small loading animation, so the window keeps responding. Settings and the Gallery also open noticeably faster.
* **No freezes in the Archive tab**: Big download archives load in the background, so the window stays responsive.
* **Huge queues stay smooth**: Queues with tens of thousands of files no longer slow the app down while downloading.
* **Telegram login no longer freezes the window** while waiting for Telegram's servers.
* **Adding a creator to the Watchlist no longer freezes the window** while the creator is looked up.
* **Cancel works quickly when a site is busy**: Waiting out a site's rate limit no longer keeps Cancel from responding for minutes.
* **No console window flashing**: Checking your graphics hardware and running updates no longer pop up a black console window.

---

### 🌍 Translations

* **All 13 languages complete**: Hundreds of new buttons, tips and messages are now translated in every language instead of showing English.
* **Decompressor tab translated**: The Decompressor tab always showed English; it now follows your language like the rest of the app.

---

### 🔄 Brand-New Updater

* **A proper update window**: Updates now open in a window that matches the app, showing each step, the download speed and time left, and what's new in the version you're getting.
* **See what you're running**: The update dialog shows your version and whether you're using the Windows build, the Linux build or the source code.
* **A failed update can't break the app**: If anything goes wrong while installing, your previous version is put back automatically, and the updater explains what happened with a button to fix it (try again, run as administrator, and so on).
* **Every download is checked**: Damaged or incomplete downloads are never installed, and a download meant for a different system (like a Windows build on Linux) is refused.
* **Nothing of yours is touched**: Your settings, downloads, logs and any files you put in the app folder are left alone. Only files that belonged to the old version are replaced.
* **Your queue survives updates**: Pawchive now closes normally before updating, so running downloads are saved and offered to resume when it opens again.

---

### 🐧 New: Linux Support (Early Access)

> ⚠️ **Linux support is new and still a work in progress.** It has been tested on far fewer systems than Windows, so expect rough edges. Keep backups of anything important, try new features on a small download first, and please report anything that doesn't work as expected.

* **Linux builds in every release**: A Linux package is attached to each release, and the in-app updater can install it.
* **Runs on most distros**: Works on Ubuntu, Debian, Fedora, Arch, Mint and others, without installing extra system libraries.
* **Updates that work anywhere**: The updater runs on systems without tkinter, and switches to updating in the terminal when no window can be shown.
* **Known differences from Windows**: Some features depend on your desktop and distro, such as keeping the computer awake, shutting down after downloads and importing browser cookies. If one of them doesn't work on your system, the log usually says why.

---

### 🔧 Running From Source

* **No more endless update prompts**: Source installs with your own commits, or installed from a zip, no longer keep asking you to update when you're already up to date.
* **Clear version numbers**: Source installs show the version plus the exact commit, like "1.2.1 (ad0390c)", and updates tell you how many new changes are waiting.
* **Your edits are safe**: Git updates only ever move forward cleanly. If you've changed app files, the updater asks whether to save your changes with git stash or skip the update, instead of overwriting them.
* **Works where pip doesn't**: Dependencies install with uv when it's available and fall back to pip. On distros that block pip, the updater tells you what to run instead of breaking your system Python.
* **Works on mounted drives**: Updating now works when the app lives on a drive owned by another user, like /mnt on Linux.

---

### 📜 Better Logs

* **Logs sorted by version**: Each session's log is saved next to the app in a folder for its version (like `logs/v1.2.1`), and the updater keeps its own logs in `logs/updater`. Older logs are moved into `logs/older`; nothing is deleted.
* **Crashes are recorded**: Unexpected errors, problems in the interface, and hard crashes are now written to the log with full details, and the next session tells you if the previous one didn't close normally.
* **More useful details**: Each log starts with the app version, edition and system. Failed files show where they came from and which servers were tried, and every download records the settings it used.
* **Gallery changes are logged**: Deleting, moving and renaming files in the Gallery now lists exactly which files were affected.
* **Private details stay private**: Archive passwords, MEGA keys, proxy logins and your Windows/Linux user folder are hidden in logs, so they're safe to attach to bug reports.
* **Clear logs and see their size**: The Logs card in Settings shows how much space logs take, with buttons to open the folder or clear them. Logs are never deleted unless you press it.
* **Full log export**: "Export logs" now saves the whole session, not just the last lines shown in the log panel.

---

### 🧠 Smoother & Lighter on Memory

* **No more small stutters every minute**: The background memory cleanup no longer pauses the app once a minute. It now runs after downloads finish and while the window is minimized.
* **AI models free their memory when idle**: The offline AI models are unloaded after 5 minutes without use and load again when needed. Deleting a model in Settings now works even right after it was used.
* **Memory warnings**: The log notes how much memory Pawchive uses each hour and warns when it gets unusually high, including what's using it. Memory is now measured correctly on Linux too.

---

### ⚙️ Watchlist Enhancements

* **Apply current settings to updates**: New toggle in Watchlist settings to apply your active global filters and options when updating saved creators instead of using outdated settings.
* **Smooth batch queueing**: Updating multiple creators at once now queues sequentially to prevent connection congestion and ensure steady downloads.

---

### 🖼️ New: Gallery Tab

* **Browse your downloads**: The Gallery tab shows your download folders with real thumbnails of your pictures and videos. Thumbnails are saved, so folders you've visited before open instantly.
* **Grid or list**: Switch between thumbnails and a detailed list with sortable columns. Resize the thumbnails with the slider or Ctrl + mouse wheel.
* **Works like File Explorer**: Click to select, double-click or Enter to open, Backspace to go up, and arrow keys to move around. Type a name or number to jump straight to it.
* **Select many files at once**: Ctrl+click, Shift+click or tick the box on any item, then copy paths, move, rename or delete them together. Ctrl+A, Esc, Delete and F2 work as shortcuts.
* **Right-click menu**: Open a file, show it in File Explorer, copy its path, rename, move or delete it, or open the post it came from in your browser.
* **Back, Forward and Undo**: Go back with the arrows in the path bar, Alt + ← / → or your mouse's side buttons. Moves, renames, new folders and copies can be undone with Ctrl+Z.
* **Drives and shortcuts**: Every drive is listed with its free space, and the Shortcuts bar jumps to Favourites, your download folders, Pictures and Videos. You can pin any folder as a shortcut too.
* **Status bar**: Shows how many folders and files are in the open folder and how much space is left on its drive.
* **Always up to date**: New downloads appear in the open folder as they finish.
* **Big folders**: Shows up to 20,000 files per folder and tells you when a folder has more. Scrolling picks up speed when you spin the wheel fast, and Page Up / Page Down work too.

---

### 🔎 Gallery: Find & Sort

* **Search everywhere**: Search looks through every subfolder. Type `.png`, `.mp4` or `emma .jpg` to find files of a certain type.
* **Saved searches**: Click 📌 in the search box to keep a search in the Shortcuts bar and run it again with one click.
* **Sorting**: Sort by name, date, size, type or rating. Numbers in names sort naturally (2 before 10), and your choice is remembered.
* **Group by post or by date**: Show each post's files as one stack, or split the folder into sections like Today, Earlier this week and March 2025. Click a date tile to select everything in it.
* **Filter by character**: The 👤 button lists the characters and series from your Known list found in the folder's file names. Pick one to see only their files.
* **Favourites and ratings**: Star files with Ctrl+D and rate them 1–5. Everything you starred is in the ⭐ Favourites shortcut.
* **Check for new posts**: Inside a creator's folder, see what they've posted since your latest download (and older posts you're missing), then download them straight into that folder.
* **Privacy blur**: The Privacy button or Ctrl+H blurs every thumbnail and preview at once. It stays on until you turn it off, even after a restart.

---

### 🎬 Gallery: Viewer & Player

* **Picture viewer**: Zoom smoothly toward your cursor, drag to move around, and double-click or press 0 to fit. Rotate, copy, star, rate, see file details, open the source post or delete without leaving the viewer.
* **Video player**: Controls fade away while you watch. Scrub the timeline with a time preview, change the speed, loop, or go full screen with F or a double-click. Volume, speed and loop are remembered.
* **Keyboard shortcuts**: Space or K to pause, ← / → to skip 5 seconds, J / L for 10, ↑ / ↓ for volume, M to mute, 0–9 to jump through the video, < / > for speed and , / . to step one frame. Press ? to see them all.
* **Hover previews**: Hover over a video or animation for a moment to watch a silent preview right in its card.
* **Many formats**: Pictures including AVIF, HEIC, TIFF, PSD and JPEG XL, videos including MKV, WebM, FLV, WMV, MPEG and 3GP, and animated GIF, WebP, APNG and AVIF. Files saved with the wrong extension open anyway, and files that can't be read say so.

---

### 🗂️ Gallery: Organize & Archives

* **New folder, Copy to… and drag and drop**: Create folders, copy files to another folder, drag files onto a folder to move them, or drag them out to other apps. Files dropped in from File Explorer are copied in.
* **Clean & Organize**: Find duplicates (keep the newest or oldest copy) and broken or empty files. Sort files into folders by type, extension or month, or flatten everything into one folder, with an Undo button for flattening.
* **Batch Rename**: Rename many files at once with find and replace, prefixes, suffixes, numbering and letter case, and see every new name before applying. Number files across subfolders in one sequence, or move them all into one folder while renaming.
* **Storage view**: See which folders and files take up the most space and jump straight to them.
* **Compress**: Pack files and folders into ZIP or 7Z, all together or one archive each, with an optional password. With "delete originals" on, nothing is deleted if a file couldn't be added.
* **Extract and look inside**: Extract one or many archives, each into its own folder, with your saved archive passwords tried automatically. Double-click an archive to browse it and view its pictures and videos without extracting.
* **Safe by default**: Deleted files go to the Recycle Bin, and Clean & Organize and Batch Rename refuse to run on your system drive, Windows and program folders, or your Linux home folder.
* **Progress you can see**: Compressing, extracting and copying show the speed and time left, and big jobs can run in the background while you keep browsing.

---

### 🛠️ Fixes

* **Downloads work again after cancelling a scan**: Cancelling while a creator's posts were still loading could make every later download do nothing until the app was restarted. New downloads now start normally after a cancel.
* **Clearer cancel message**: A cancelled download now shows "Cancelled" instead of wrongly saying that all files were filtered out.
* **Known Series list now saves your changes**: Names you add or remove are kept after restarting and are used for sorting straight away. Before, they were lost on restart.
* **No more junk names in the Known Series list**: Words from post titles like "Soon" or "comics" are no longer added to your list automatically.
* **Auto-Retry leaves cancelled downloads alone**: Turning on Auto-Retry after cancelling a download no longer restarts everything you just stopped. Only downloads that actually failed are retried.
* **Interrupted downloads resume**: When a connection drops partway through a file, the retry continues from where it stopped instead of starting over, and the error no longer wrongly blames your disk.
* **Donation links skipped**: PayPal, Ko-fi and similar links in posts are no longer treated as videos, so they stop showing up as failed downloads.
* **Tidier log**: The watchlist check message no longer appears twice, and post scans report the correct page count.
* **Watchlist stops reporting phantom updates**: Posts from the same day as your last download no longer show up as "new" forever.
* **Full-size images more often**: When the full-size server is busy, the app tries again before settling for a smaller preview, and a saved preview no longer stops you from getting the full image later.
* **More videos download**: Private Vimeo links, Picarto videos and Vimeo videos embedded on a creator's site now download.
* **Fewer failed downloads**: Ordinary web page links in posts no longer count as failed downloads.
* **Files land in the right folder**: With multi-drive storage on, a creator's files go into their own folder instead of straight into your main download folder.
* **No more freezes on slow drives**: Saving download progress no longer pauses downloads for half a minute at a time on slow or network drives.
* **Closing is quicker**: The app now closes within a few seconds, even in the middle of a download.
* **Pawchive login check fixed**: Checking a Pawchive login no longer fails with an error when no username was saved yet.
* **Links to other posts work again**: Posts that point to another post for their download links or passwords no longer cause an error while scanning.
* **Bunkr failures explained**: When a Bunkr file can't be downloaded, the log now says why instead of failing silently.
* **Scheduler fixes**: A schedule with a broken run time is now reported instead of silently never running, and the Night Owl "waiting" message no longer repeats every 10 seconds.
* **Log buttons stay visible**: The buttons above the log panel no longer get pushed off the edge with wider fonts on Linux.
* **Settings survive crashes**: Settings, the Watchlist, your Known list and download history are saved safely, so a crash or power cut can no longer reset or empty them.
* **Downloader options are remembered**: "Subfolder per post", the thread count and other Downloader options are now saved as soon as you change them. Before, they could switch back after restarting the app, bringing back post folders you had turned off.
* **No more false "unfinished download" prompts**: Finished downloads, and files that simply don't exist anymore, no longer bring up the recovery prompt at every start.
* **Japanese, Chinese, Korean and Thai filters work**: Character and skip-word filters now find names inside titles written without spaces.
* **Size filters no longer crash**: Filters like [>1 GiB] or [<500MiB] work, and unusual ones are ignored instead of stopping the scan.
* **More pictures count as images**: AVIF, HEIC, JFIF and TIFF files are now kept by the "Images" filter.
* **"Re-download small files" works with the Download Archive**: Small preview copies are now replaced by the full-size files even when the Download Archive is on.
* **Date filters start empty**: The date range filter no longer stays on silently after restarting the app.
* **Right creator name shown**: The name next to the link box always belongs to the link you entered, even when switching links quickly.
* **Decompressor is gentler**: "Delete archive after extracting" now moves the archive to the Recycle Bin, and extracting into an existing folder no longer overwrites files that are already there.
* **Cloud downloads with special names**: GoFile, MEGA, Google Drive and Dropbox files with names like "Part 1: Intro.mp4" now save correctly.
* **Dead MEGA links are spotted**: The Link Vault's health check now asks MEGA whether a link still exists, saves faster, and stops right away when cancelled.
* **Firefox import uses your main profile**: 1-Click Import reads the Firefox profile you actually use, including cookies saved moments ago.
* **AI models checked after download**: A model that didn't download completely is downloaded again instead of being marked ready, and missing AI packages are now reported in the log.
* **yt-dlp downloads verified**: The video helper is checked before it's installed, and a yt-dlp installed by your Linux distro is used as is.
* **Shutting down after downloads**: Shutdown and restart now work for normal Linux users, and Windows no longer force-closes your other programs (which could lose unsaved work).
* **Erome files get the right extension**: Files from Erome links without an extension no longer get broken names.
* **All your favorites are downloaded**: Favorite Mode reads every page of your favorites instead of sometimes stopping after the first.
* **Clearer archive import/export**: The Archive tab no longer claims its text lists work with gallery-dl.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
>
> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a [Ko-fi page](https://ko-fi.com/whyamihere773), but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
