### ⚡ Pawchive Rate Guard & Anti-Ban Calibration

* **Smart automatic speed & connection tuning**: Pawchive Downloader now tracks per-server and overall rate limits together, opening extra connections when downloads are running smoothly and stepping down quietly whenever servers ask to slow down. Your learned safe pace is saved between sessions and steadily heals back up on its own so temporary slowdowns never leave downloads crawling.
* **New Rate Guard controls & Recalibrate**: Pick **Smart Auto**, **Cautious (Ban-Safe)**, or **Custom Manual** sliders under **Downloader → Structure & Engine**, view your live files-per-minute pace, or click **Recalibrate** anytime (with an automatic safety pause if repeated test files are still blocked).
* **Instant local copy for reposted files**: When a creator includes the exact same file in multiple posts (such as an individual post and a monthly pack), your already-downloaded local copy is reused instantly instead of downloading it again.

---

### 🔄 Browser Mode: Sync Missing & Mismatched Only

* **Download only missing or incomplete posts**: Click **Sync Missing / Mismatched** on any creator in Browser Mode (or choose **Missing & Mismatched**, **Not on Disk Only**, or **Mismatched Only** in the download dialog) to skip finished posts and grab only what is missing or incomplete.
* **Automatic folder & naming match**: Syncing automatically locates the creator's existing folder on disk and reuses its folder structure and file-naming style so new files fit right in.

---

### 📅 Date Folder Sorting

* **Sort creator downloads by Year and Month**: Organize posts into **By Year** (`Creator/2025/...`), **By Month** (`Creator/2025-03/...`), or **Year → Month** (`Creator/2025/03 - March/...`) under **Downloader → Structure & Engine** or **Settings → Storage & File Processing**. Posts without a publication date are placed in `Unknown Date/`.

---

### 🛠️ Fixes

* **Broken cum.st post links fixed**: Opening, copying, or redownloading a `cum.st` post from Browser Mode, Gallery, or older saved folders now always uses the working `cum.st/creators/...` post link instead of broken `cum.st/.../post/...` addresses.
* **Pause & recovery reliability fixes**: Clicking **Pause** immediately freezes active retry timers without re-waiting already-elapsed cooldowns on resume, and manual thread counts recover smoothly after temporary rate-limit slowdowns instead of staying stuck at 1 thread.
* **Linux & Python 3.11/3.12 startup fix**: Fixed a startup crash affecting Linux builds and Python 3.11/3.12 environments.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
