### 📅 Date Folder Sorting

* **Organize creator downloads by Year and Month**: Choose **By Year** (`Creator/2025/...`), **By Month** (`Creator/2025-03/...`), or **Year → Month** (`Creator/2025/03 - March/...`) under **Downloader → Structure & Engine** or **Settings → Storage & File Processing**. Posts without a publication date are placed in `Unknown Date/`.
* **Works everywhere**: Date folder sorting works alongside Subfolder per post, Group by File Type, and custom per-creator Watchlist settings, and shows up in the Browser download summary.

---

### 🔄 Browser Mode: Sync Missing & Mismatched Only

* **Download only missing or mismatched posts**: Use the new **Sync Missing / Mismatched** button on any creator in Browser Mode (or pick **Missing & Mismatched**, **Not on Disk Only**, or **Mismatched Only** in the Browser download dialog) to skip complete posts and grab only missing or incomplete ones.
* **Automatic path & layout matching**: Syncing automatically finds the creator's existing folder on disk and reuses its exact folder layout and naming style so new and repaired files blend right in.

---

### ⚡ Smarter Pawchive Rate-Limit Protection

* **Two-layer anti-ban speed & connection calibration**: Pawchive Downloader now balances both per-server (`n1`–`n4`) and shared IP limits automatically, dynamically opening extra connections when transfers are smooth and closing them down on rate limits while steadily healing speed back up so downloads never crawl.
* **Pawchive Rate Guard controls & Recalibrate**: Choose **Smart Auto**, **Cautious (Ban-Safe)**, or **Custom Manual** sliders under **Downloader → Structure & Engine**, watch live files-per-minute telemetry, or click **Recalibrate** anytime (with automatic emergency pause if repeated test files are still blocked).
* **Instant local copy for reposted files**: When a creator attaches the exact same file in multiple posts (such as an individual post and a monthly pack), Pawchive Downloader now copies your already-verified local file instantly instead of downloading it all over again.

---

### 🛠️ Fixes

* **Pause & rate-limit recovery fixes**: Clicking **Pause** immediately freezes all retry timers (and resuming after a pause no longer waits out already-elapsed cooldowns). Manual thread counts also recover automatically after a temporary slowdown instead of staying stuck at 1 thread.
* **Linux & older Python startup fix**: Resolved a startup crash on Linux builds and Python 3.11/3.12 environments.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
