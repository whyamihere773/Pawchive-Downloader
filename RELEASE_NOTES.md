### 📊 Built for Huge Libraries

* **Tested at scale**: This version was tested with 2 million archived files, 100,000 archive creators, 50,000 Watchlist artists, 500,000 queued files and a Link Vault with 10,000 creators. The window stays responsive throughout.
* **Moved over automatically**: The archive, Watchlist, download history, Link Vault and saved download progress now live in small databases, and your existing data is moved over the first time you start this version. Every old file is kept next to it as a backup (renamed to `.migrated`), so nothing is lost.

---

### 🗄️ Big Archives, No More Freezes

Numbers below are for an archive with 2 million files from 20,000 creators.

* **Archive tab opens instantly**: The creator list loads in under 0.1 seconds instead of 4.8 seconds (at 200,000 files the old version froze for 5.4 seconds). Even with 100,000 creators the tab opens in under 0.1 seconds.
* **Opening a creator is instant**: A creator's posts appear right away instead of taking up to 10 seconds, and load a page at a time.
* **Much faster search**: Searching file names, post titles and creators takes 0.02–0.04 seconds instead of 2.7 seconds, and still finds any part of a name.
* **Instant filters**: The site filter takes 0.02 seconds instead of 1 second, and the file-type filter under 0.1 seconds instead of 4.2 seconds.
* **Statistics in a blink**: The archive statistics load in 0.2 seconds instead of 3.3 seconds.
* **One-time preparation**: The first time you start this version, a big archive is prepared in the background (about 2 minutes for 2 million files). The tab works as before meanwhile, and the archive file grows by roughly a third to a half to make room for the search index.
* **Downloads keep going while you browse**: Looking through or searching the archive no longer holds up running downloads.
* **Export works and tells you if it can't**: Exporting the archive runs in the background, and if something goes wrong you now get a clear message instead of "Exported 0 records".
* **Weekly health check**: Once a week the archive is checked for damage in the background, and a safety copy is kept next to it when your drive has at least 3 times the archive's size free. Damage found is repaired automatically.

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
* **Pawchive shortcut**: Pawchive artists who haven't posted since their last check are skipped using one request for the whole site instead of one per artist, so checking a big watchlist takes minutes instead of hours. Everyone still gets a full check at least once a week.
* **Stop and continue**: The Check All button shows how far the check is, and clicking it again stops the check; the next check picks up where it stopped.
* **Auto-check is respected**: The check at start-up now only includes artists with auto-check turned on.
* **Connection problems don't hide updates**: If an artist can't be checked, the updates found earlier stay listed and the artist is tried again next time.
* **Daily backup**: A copy of your watchlist is kept and used automatically if the file ever gets damaged.
* **Long update lists**: Long update lists open 50 posts at a time.

---

### ⚡ A Smoother Window Everywhere

* **Calmer scrolling**: The mouse wheel no longer flings long lists far past where you wanted to go.
* **Link Vault opens instantly**: A vault with 10,000 creators opens without any pause; with tens of thousands of links the old version took minutes.
* **Link Vault keeps up with big vaults**: Saving links from a scan, checking link health and editing passwords no longer slow down as the vault grows. Each change saves only what changed instead of rewriting the whole vault.
* **Less disk activity while downloading**: The download history and the log file are written in small batches a few times a second instead of being rewritten or reopened for every file. The history no longer forgets files beyond the last 50,000.
* **Gallery stays responsive**: Opening folders, moving files and undoing a move no longer freeze the window, even when moving to another drive.
* **Background imports and exports**: Importing or exporting the download queue, exporting logs and clearing or importing the archive run in the background.
* **No hiccup after start-up**: A freeze of up to 0.3 seconds a few seconds after opening the app is gone.
* **Fewer random micro-freezes**: With very large queues, watchlists or archives, the app no longer pauses for 0.1–0.2 seconds every now and then to tidy up memory.
* **Freezes report themselves**: If the window ever stops responding, the log now says for how long and what it was busy with, which makes bug reports much easier to fix.

---

### 🌍 Translations

* **Russian layout fixed**: Buttons, switches and option cards no longer overflow or cut off text with longer translations, in Russian and every other language.
* **New messages translated**: All new messages are available in all 13 languages.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
