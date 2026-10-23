### 🛡️ Privacy Shield & PIN Protection

* **Instant screen blur**: Click the eye icon in the top bar or press `Ctrl+P` to instantly blur the entire window with smooth animations, hiding URLs, creator names, and previews.
* **Optional 4-digit PIN**: Protect sensitive content with a custom 4-digit PIN, or leave it off for instant one-click unblur.
* **Auto-lock when idle**: Automatically engages Privacy Mode after 5 minutes of inactivity (customizable up to 30 minutes in Settings).
* **Anti-brute-force security**: Entering an incorrect PIN 5 times locks the session to prevent unauthorized access.
* **Safe Mode on startup**: If a PIN reset is requested, sensitive tabs are quarantined on the next launch until unlocked or reconfigured.
* **Uninterrupted downloads**: All active downloads and background tasks continue running normally while the screen is blurred or locked.
* **Disguised window title**: The window title switches to a discrete generic label while blurred.
> ⚠️ **NOTICE**: PRIVACY SHIELD IS NOT INTENDED AS A FORMAL SECURITY OR DATA ENCRYPTION SYSTEM. IT IS DESIGNED SOLELY AS A CONVENIENT VISUAL PRIVACY LAYER TO PREVENT CASUAL ONLOOKERS FROM VIEWING YOUR SCREEN WHILE YOU ARE TEMPORARILY AWAY FROM YOUR WORKSTATION.

---

### 💬 Creator Direct Messages (DMs)

* **Direct message downloading**: You can now download creator direct messages and private chat attachments on supported platforms (cum.st and Pawchive).
* **Automatic DMs with posts**: Enable "Download Direct Messages (DMs)" in the downloader or in Settings to automatically fetch and archive all direct messages alongside an artist's regular posts.
* **Direct DM links supported**: Pasting a direct message URL (such as links ending in `/dms` or `?tab=dms`) now automatically discovers and downloads the creator's private messages.

---

### ⏱️ Video Duration Filter

* **Filter posts by video length**: Download only posts containing videos within a specific runtime window (e.g. `0:30`, `5m`, `15:00`), complete with one-click quick presets for clips and full-length media.
* **Scan overhead notice**: Because direct video hosting platforms do not provide duration in their API metadata, Pawchive inspects video headers over the network during post scanning, which may slightly increase scan times when this filter is enabled.

---

### 🏷️ Post Title & Caption Filenames

* **Automatic caption fallback for untitled posts**: Downloads from creators who don't provide explicit post titles (such as on OnlyFans, Fansly, or cum.st) now automatically use their post caption instead of saving as "Untitled" or "Post".
* **New `{captionText}` template tag**: You can now use `{captionText}` (or `{caption}`) in your custom filename template under Settings → Storage & File Processing, complete with automatic character sanitization and safe length limits.

---

### 🛠️ Fixes & Polish

* **Faster Watchlist checks**: Checking creators for updates now stops immediately on the first page if their newest post is already downloaded, eliminating unnecessary page requests for up-to-date artists.
* **Accurate platform badges in favorites**: Favorite creator cards from cum.st now correctly display their platform instead of defaulting to Pawchive.
* **Streamlined mode labels**: Cleaned up the dropdown text by removing redundant platform tags from Favorite Mode.
* **Duplicate window title fixed**: The title bar no longer repeats the app name twice on Windows.
* **Batch import mode awareness**: Opening the Batch Importer while Favorite Mode is active now displays a prominent warning with a 1-click button to switch back to standard mode.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
