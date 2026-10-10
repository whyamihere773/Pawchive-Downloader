### 📊 Built for Huge Libraries

* **Tested at scale**: This version was tested with 2 million archived files, 100,000 archive creators, 50,000 Watchlist artists, 500,000 queued files and a Link Vault with 10,000 creators. The window stays responsive throughout.
* **Moved over automatically**: The archive, Watchlist, download history, Link Vault and saved download progress now live in small databases, and your existing data is moved over the first time you start this version. Every old file is kept next to it as a backup (renamed to `.migrated`), so nothing is lost.

---

### 🗄️ Big Archives, No More Freezes

Numbers below are for an archive with 2 million files from 20,000 creators.

* **Archive tab opens instantly**: The creator list loads in under 0.1 seconds instead of 4.8 seconds (at 200,000 files the old version froze for 5.4 seconds). Even with 100,000 creators the tab opens in under 0.1 seconds.
* **Opening a creator is instant**: A creator's posts appear right away instead of taking up to 10 seconds, and load a page at a time.
* **Much faster search**: Searching file names, post titles and creators takes 0.02–0.04 seconds instead of 2.7 seconds, and still finds any part of a name. Typing a new search stops the previous one right away, and one- or two-letter searches only look through creator names, so they answer in about 0.01 seconds.
* **Instant filters**: The site filter takes 0.02 seconds instead of 1 second, and the file-type filter under 0.1 seconds instead of 4.2 seconds.
* **Statistics in a blink**: The archive statistics load in 0.2 seconds instead of 3.3 seconds.
* **One-time preparation**: The first time you start this version, a big archive is prepared in the background (about 2 minutes for 2 million files). Start-up isn't slowed down and downloads keep recording files meanwhile. The tab stays usable but loads slowly until it's done (several seconds per refresh at 2 million files), and the archive file grows by about 10–20% to make room for the search index.
* **Downloads keep going while you browse**: Looking through or searching the archive no longer holds up running downloads.
* **Export works and tells you if it can't**: Exporting the archive runs in the background, and if something goes wrong you now get a clear message instead of "Exported 0 records".
* **Weekly health check**: Once a week the archive is checked for damage in the background, and a safety copy of your records is kept next to it when your drive has room for it plus 1 GB. Damage found is repaired automatically.

---

### 🩹 Damaged Archive Repair

* **Automatic repair**: If the archive database gets damaged ("database disk image is malformed"), Pawchive repairs it by itself in the background and keeps a backup copy of the damaged file first.
* **Nothing thrown away by mistake**: Every record that can still be read is kept, and an archive that can't be read at all is never replaced by an empty one.
* **Removing a creator works again**: Deleting a creator, a post or a file from the archive now succeeds after a repair, and failures are explained instead of silently doing nothing.

---

### 🔁 Downloads & Retry

* **No more endless "Unfinished Download" prompt**: The prompt only appears when files really never got their turn. Files that failed stay in Retry Failed instead of bringing the prompt back at every start.
* **Retry Failed count is always right**: The button no longer keeps showing a failed file after you cleared it.
* **Retry Failed opens instantly**: With 5,000 failed files the window used to freeze for over 2 minutes; it now opens in under 0.1 seconds and fills in as you watch.
* **Retrying doesn't freeze**: Retrying 20,000 failed files used to freeze the window for about 4 seconds, sometimes several times in a row. It now starts instantly, and even with 500,000 files in the queue the window never pauses for more than about 0.1 seconds.
* **Only the files you picked are retried**: Retrying or clearing selected failed files no longer also picks up other posts' files that happen to share a name (like "001.jpg").
* **No more re-downloading the same images**: Small original pictures and pictures you converted to WebP are no longer "upgraded" again on every run.
* **Huge queues stay smooth**: A queue of 500,000 files loads in 0.2 seconds instead of 3.5 seconds, and no longer freezes the app for good.
* **Lighter crash protection**: Download progress is still saved every 30 seconds, but only what changed is written: a fraction of a second instead of rewriting up to 700 MB for a million queued files.
* **Filters keep up**: With a status filter on, thousands of files skipped at once update the list in 0.2 seconds instead of 9 seconds, and each batch of finished files takes a few thousandths of a second.
* **Resuming doesn't freeze**: Resuming an interrupted download prepares the queue in the background.

---

### 📅 Watchlist

* **No more looping updates**: Posts whose files are gone from the site (missing, private or removed videos) no longer show up as new after every download.
* **Only what's really new**: Update checks list only the posts that still have something to download.
* **Built for big watchlists**: With 50,000 artists, scrolling, searching and filtering all respond in under 0.1 seconds. A change saves just that artist instead of rewriting the whole watchlist file.
* **Updates are remembered**: New posts found by a check are still listed after you restart the app.
* **Much faster Check All**: Different sites are checked at the same time, the most active artists go first, and results appear one by one while the check runs.
* **Pawchive and cum.st shortcut**: Artists who haven't posted since their last check are skipped using the site's list of all creators instead of one request per artist, so checking a big watchlist takes minutes instead of hours. In a live test, 45 artists on both sites were checked in 3 seconds with 11 requests. On cum.st this kicks in from about 1,700 artists, where reading its list is cheaper than checking everyone.
* **Shortcut double-checks itself**: Each check, a few of the skipped artists are checked anyway. If one of them did post, everyone on that site is checked, and anyone the site has no update time for is always checked. Everyone still gets a full check at least once a week.
* **Stop and continue**: The Check All button shows how far the check is, and clicking it again stops the check; the next check picks up where it stopped.
* **Auto-check is respected**: The check at start-up now only includes artists with auto-check turned on.
* **Connection problems don't hide updates**: If an artist can't be checked, the updates found earlier stay listed and the artist is tried again next time.
* **Daily backup**: A copy of your watchlist is kept and used automatically if the file ever gets damaged.
* **Long update lists**: Long update lists open 50 posts at a time.
* **Change an artist's download folder**: The 📂 button now really changes the folder. If the artist already has files, you can move them to the new folder (the download archive follows them) or use the new folder only for new downloads.
* **Moving shows its progress**: Moving an artist's files shows how far it is and can be stopped. Files already moved stay in the new folder, the rest stay in the old one, and the artist keeps both.
* **Your folder choice sticks**: A folder you chose for an artist is no longer moved back into the main download folder on the next download, and multi-drive storage doesn't override it. "Add Drive/Folder" adds a location again instead of replacing the folder.
* **No more doubled locations**: An artist's folder no longer shows up twice ("Multi-Drive Spanned (2 locations)") just because it was saved with different slashes.

---

### 🗜️ Decompressor

* **Compress after extracting** *(opt-in)*: Turn on "Compress pictures and videos after extracting" to save the pictures and videos from each archive in a smaller format. Pick the format (JPG, PNG, WebP or AVIF for pictures; H.265, H.264, MKV or AV1 for videos) and the quality with a slider. In a test, WebP at the default quality cut pictures to about half their size, and H.265 cut a video from 5.5 MB to 2.2 MB.
* **GIFs stay GIFs**: GIFs are compressed as GIFs, with every frame, its timing and transparency kept (a test animation went from 525 KB to 381 KB).
* **MKV keeps everything**: The MKV option keeps every audio track, subtitles and attached fonts exactly as they were.
* **You decide about the originals**: Compressed copies are saved next to the originals and only kept when they're at least 5% smaller. When everything's done you're asked whether to keep the originals or move them to the Recycle Bin.
* **Videos need FFmpeg**: Video compression uses FFmpeg, a free video tool. It isn't included with the app, but one click downloads the official build (about 200 MB, a few seconds on a fast connection) and checks it before use.
* **Extracting is up to twice as fast**: Every archive used to be fully unpacked once in memory just to check whether it needed a password. That check now reads only the file list (1.7 seconds down to 0.1 seconds on a 52 MB test archive).
* **Big split archives work**: Parts 10 to 19 of a split archive (like "comic.part12.rar") were treated as separate archives. Only the first part is extracted now, and split archives get the right folder name.
* **Nothing thrown away after a warning**: When 7-Zip finished with a warning (for example one file it couldn't write), everything it had extracted was deleted. Those files are kept now, and the archive is kept too.
* **Settings are remembered**: Parallel archives, threads, the Recycle Bin option, password prompts and your added folders no longer reset every time the app starts.
* **Smoother list while extracting**: The archive list updates a few times a second instead of being rebuilt with every progress tick.
* **Clearer results**: Archives you stop are no longer counted as failed, and the disk space check no longer assumes deleted archives free up space (they go to the Recycle Bin).

---

### ⚡ A Smoother Window Everywhere

* **Calmer scrolling**: The mouse wheel no longer flings long lists far past where you wanted to go.
* **Link Vault opens instantly**: A vault with 10,000 creators opens without any pause; with tens of thousands of links the old version took minutes.
* **Link Vault keeps up with big vaults**: Saving links from a scan, checking link health and editing passwords no longer slow down as the vault grows. Each change saves only what changed instead of rewriting the whole vault.
* **Less disk activity while downloading**: The download history and the log file are written in small batches a few times a second instead of being rewritten or reopened for every file. The history no longer forgets files beyond the last 50,000.
* **Gallery stays responsive**: Opening folders, moving files and undoing a move no longer freeze the window, even when moving to another drive.
* **Background imports and exports**: Importing or exporting the download queue, exporting logs and clearing or importing the archive run in the background.
* **No hiccup after start-up**: A freeze of up to 0.3 seconds a few seconds after opening the app is gone.
* **Fewer random micro-freezes**: With very large queues, watchlists or archives, the app no longer pauses for 0.1–0.2 seconds every now and then to tidy up memory. The bigger tidy-up now happens while the app is minimised or you've been away from the computer for 10 minutes.
* **Much smaller log files**: Files skipped because they're already downloaded, or renamed to keep two files apart, are still listed in the log panel but counted in a single line in the log file. Your two biggest logs would have been about 95% smaller (294 KB down to 13 KB).
* **Freezes report themselves**: If the window ever stops responding, the log now says for how long and what it was busy with, which makes bug reports much easier to fix.

---

### ⚙️ New Settings & Options

* **Site in Folder Name** *(on by default)*: Turn off "Site in Folder Name" in Downloader → Folder Organization & Naming to name creator folders "Artist" instead of "Artist [onlyfans]". Existing folders are still found under either name, so nothing gets split.
* **Windows and Linux share your data**: Folders saved on Windows ("D:\Art") work on Linux and WSL ("/mnt/d/Art") and the other way round, for a drive shared between both systems. Drives mounted elsewhere on Linux (like "/media/you/DATA") are found too, and Gallery favourites and ratings follow along.
* **Use browser sign-in for embedded videos** *(off by default)*: In Settings, under "Download embedded media players", pick a browser so videos that only play while you're logged in (RedGifs, private Vimeo, age-restricted YouTube) can download. Firefox works best; Chrome, Edge and Brave have to be closed, and their newest versions can't be read at all. If the browser can't be read, videos download without it as before.

---

### 🛠️ Fixes

* **Gallery copy, compress and extract work again**: Since v1.2.5 every file failed with "name 'time' is not defined".
* **Gfycat links recognised as gone**: Gfycat shut down in 2023, so its links now count as permanently failed instead of being retried and offered again by the Watchlist.
* **RedGifs "410" explained**: When RedGifs reports a video as deleted, the error now says so plainly and points to the new browser sign-in setting. The post stays retryable instead of being marked done, since some of these still play in a browser.

---

### 🌍 Translations

* **Russian layout fixed**: Buttons, switches and option cards no longer overflow or cut off text with longer translations, in Russian and every other language.
* **New messages translated**: All new messages are available in all 13 languages.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
