> [!CAUTION]
> ### 🛑 A Note Regarding Pawchive Downloads
> Due to a direct request from the Pawchive site owner—and out of genuine respect for him and the service he provides to our community—I have made a few adjustments to how Pawchive downloads are handled in this update. 
> 
> I hope these changes won't impact your day-to-day experience too much, but if you run into any friction, please let me know and I will gladly continue fine-tuning things until I find the ideal sweet spot. Remember, Pawchive is a shared resource for all of us: please be courteous to their servers by keeping your active threads to **2** and setting a modest delay between downloads whenever possible.

---

### ✈️ Telegram Channel Support

* **Download directly from Telegram**: Paste any public channel, private link, or individual post URL (`t.me/...`) to download videos, photos, and files directly to your PC.
* **Interactive visual post browser**: Click "Select Posts…" to preview image thumbnails, check captions and dates, and select exactly which posts you want to download.
* **One-click criteria downloading**: Filter channel archives by date range, media types, or post limits and start downloading matching files immediately.
* **Effortless login**: Connect your Telegram account in seconds by scanning a QR code with your phone camera, entering an SMS code, or using a bot token.
* **Built-in account safety**: Downloads are automatically locked to 2 worker threads with automatic flood cooldowns to protect your account against temporary restrictions.
* **Fluid interface & smooth continuation**: Telegram dialogs feature tactile fluid animations, and logging in now transitions seamlessly into a "Continue →" button so you can jump straight to your downloads.

---

### 🛑 Instant Multi-Service Cancellation

* **Instant cancellation across all providers**: Pressing Cancel now immediately halts all active downloads—including multi-part files, video extractors, cloud storage links (Mega, Dropbox, GoFile), and Telegram—in less than a second.

---

### 🧹 Memory Cleanup Daemon *(WIP)*

* **Automatic background RAM cleaner** *(Work in Progress)*: The app now periodically runs background sweeps to free unused memory and prevent RAM buildup during long, heavy download sessions. This is my first time designing an automated memory management system like this, so it's currently a work-in-progress—hopefully it's enough to keep everything running light and smooth on your machine, but please let me know how it performs!

---

### 🌐 Server-Friendly Pawchive Downloads

* **Steady, single-stream downloads**: Pawchive files now download over a single steady connection that can be paused and resumed anytime, keeping Pawchive's servers fast and responsive for everyone.
* **Gentle request pacing**: Added brief breathing room between files and post pages on Pawchive to prevent you from getting hit with rate limits or temporary blocks.
* **Instant dead link detection**: When a file no longer exists on Pawchive, the app recognizes it immediately without making repeated wasted requests.

---

### 🎵 Automatic Audio Tagging

* **Built-in creator & title tags**: Downloaded music and audio tracks (`.mp3`, `.m4a`, `.flac`, `.ogg`, `.wav`) now automatically have the creator saved as the **Artist** and the post title saved as the **Title**. External music managers like iTunes, MusicBee, and Plex will organize them automatically.
* **Tagging controls**: Easily toggle automatic audio tagging on or off in the main download view or under Settings → Storage & File Processing.

---

### 🛠️ Fixes & UI Polish

* **Archive scroll skipping fixed**: Resolved an issue in the Archive tab where the scrollbar indicator would jump or skip erratically when browsing creators with large post histories.
* **Queue & Retry modal scroll fixed**: Mouse wheel scrolling inside the Queue view and Retry dialog is now completely smooth, preventing card hover areas from intercepting the scroll.
* **Queue batch cancellation fixed**: Cancelling active or pending download batches from the Queue tab now responds immediately and reliably halts the batch.
* **Clear failed downloads in Retry modal**: Added new options to permanently remove selected or all failed items from the queue directly inside the Retry dialog.
* **Snappier mouse wheel scrolling**: Scrolling through lists across the entire app is now noticeably faster and more responsive.
* **Flexible file size filtering**: Filter your downloads by exact file size ranges (e.g. `100MB` to `1GB`) with automatic formatting and input safeguards.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
