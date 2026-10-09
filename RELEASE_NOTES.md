### 🗄️ Big Archives, No More Freezes

* **Archive tab opens instantly**: Even with hundreds of thousands of downloaded files, the Archive tab now opens in a fraction of a second instead of freezing the app for several seconds. A creator's posts load when you open them, a page at a time.
* **Thousands of creators, no slowdown**: Only the creators on screen are drawn, so very long creator lists scroll smoothly and keep your place when the list refreshes.
* **Downloads keep going while you browse**: Looking through or searching the archive no longer holds up running downloads.
* **Export works and tells you if it can't**: Exporting the archive runs in the background, and if something goes wrong you now get a clear message instead of "Exported 0 records".
* **Ready for millions of files**: The creator list, statistics, site filter and file-type filter now load in a fraction of a second even with millions of downloaded files, and opening a creator is instant. The first time you start this version, your archive is prepared for this in the background (a minute or so for very large archives); until then the tab works as before.
* **Much faster search**: Searching file names, post titles and creators takes milliseconds instead of seconds and still finds any part of a name.
* **Weekly health check**: Once a week the archive is checked for damage in the background and a safety copy is kept next to it, if your drive has room for one. Damage found is repaired automatically.

---

### 🩹 Damaged Archive Repair

* **Automatic repair**: If the archive database gets damaged ("database disk image is malformed"), Pawchive repairs it by itself in the background and keeps a backup copy of the damaged file first.
* **Nothing thrown away by mistake**: Every record that can still be read is kept, and an archive that can't be read at all is never replaced by an empty one.
* **Removing a creator works again**: Deleting a creator, a post or a file from the archive now succeeds after a repair, and failures are explained instead of silently doing nothing.

---

### 🔁 Downloads & Retry

* **No more endless "Unfinished Download" prompt**: The prompt only appears when files really never got their turn. Files that failed stay in Retry Failed instead of bringing the prompt back at every start.
* **Retry Failed count is always right**: The button no longer keeps showing a failed file after you cleared it.
* **Retry Failed opens instantly**: With thousands of failed files the window used to freeze, sometimes for minutes; it now opens right away and fills in as you watch.
* **No more re-downloading the same images**: Small original pictures and pictures you converted to WebP are no longer "upgraded" again on every run.
* **Huge queues stay smooth**: Queues with hundreds of thousands of files load in a moment, and the window keeps up while files finish.
* **Lighter crash protection**: Download progress is still saved every 30 seconds, but only what changed is written, so big queues no longer keep your disk busy. Your saved progress from the previous version is moved over automatically.
* **Resuming doesn't freeze**: Resuming an interrupted download prepares the queue in the background.

---

### 📅 Watchlist

* **No more looping updates**: Posts whose files are gone from the site (missing, private or removed videos) no longer show up as new after every download.
* **Only what's really new**: Update checks list only the posts that still have something to download.
* **Built for big watchlists**: The Watchlist is now kept in a small database where only changes are saved, so it stays fast with tens of thousands of artists. Your watchlist is moved over automatically the first time you start this version, and the old file is kept as a backup.
* **Updates are remembered**: New posts found by a check are still listed after you restart the app.
* **Much faster Check All**: Different sites are checked at the same time, the most active artists go first, and results appear one by one while the check runs.
* **Pawchive shortcut**: Pawchive artists who haven't posted since their last check are skipped, so checking a big watchlist takes minutes instead of hours. Everyone still gets a full check at least once a week.
* **Stop and continue**: The Check All button shows how far the check is, and clicking it again stops the check; the next check picks up where it stopped.
* **Auto-check is respected**: The check at start-up now only includes artists with auto-check turned on.
* **Connection problems don't hide updates**: If an artist can't be checked, the updates found earlier stay listed and the artist is tried again next time.
* **Daily backup**: A copy of your watchlist is kept and used automatically if the file ever gets damaged.
* **Long update lists**: Changes are saved in the background, and long update lists open 50 posts at a time.

---

### ⚡ A Smoother Window Everywhere

* **Calmer scrolling**: The mouse wheel no longer flings long lists far past where you wanted to go.
* **Link Vault opens fast**: Large vaults now open in a moment instead of freezing the app; with tens of thousands of links it used to take minutes.
* **Link Vault keeps up with big vaults**: Saving links found by a scan, checking link health and editing passwords stay quick with tens of thousands of links (they used to slow down with every link added). The vault is now kept in a small database and moved over automatically; the old file is kept as a backup.
* **Less disk activity while downloading**: The download history and the log file are written in small batches instead of being rewritten or reopened for every file. The history is moved over automatically and no longer forgets older files.
* **Gallery stays responsive**: Opening folders, moving files and undoing a move no longer freeze the window, even when moving to another drive.
* **Background imports and exports**: Importing or exporting the download queue, exporting logs and clearing or importing the archive run in the background.
* **No hiccup after start-up**: A short freeze a few seconds after opening the app is gone.
* **Fewer random micro-freezes**: With very large queues, watchlists or archives, the app no longer pauses for a moment every now and then to tidy up memory.
* **Freezes report themselves**: If the window ever stops responding, the log now says for how long and what it was busy with, which makes bug reports much easier to fix.

---

### 🌍 Translations

* **Russian layout fixed**: Buttons, switches and option cards no longer overflow or cut off text with longer translations, in Russian and every other language.
* **New messages translated**: All new messages are available in all 13 languages.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
