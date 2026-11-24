### 📅 Date Folder Sorting

* **Organize creator downloads by Year and Month**: Choose **By Year** (`Creator/2025/...`), **By Month** (`Creator/2025-03/...`), or **Year → Month** (`Creator/2025/03 - March/...`) under **Downloader → Structure & Engine** or **Settings → Storage & File Processing**. Posts without a publication date are placed in `Unknown Date/`.
* **Works everywhere**: Date folder sorting works alongside Subfolder per post, Group by File Type, and custom per-creator Watchlist settings, and shows up in the Browser download summary.

---

### ⚡ Smarter Pawchive Rate-Limit Protection

* **Smoother downloads without 429 stalls**: Downloads now automatically spread across different Pawchive storage servers, balance large and small files, and pace requests per server before rate limits are ever reached. If one storage server does ask to slow down, files on other servers keep downloading normally instead of stalling the whole queue.
* **Instant local copy for reposted files**: When a creator attaches the exact same file in multiple posts (such as an individual post and a monthly pack), Pawchive Downloader now copies your already-verified local file instantly instead of downloading it all over again.

---

### 🛠️ Fixes

* **Pause & rate-limit recovery fixes**: Clicking **Pause** immediately freezes all retry timers (and resuming after a pause no longer waits out already-elapsed cooldowns). Manual thread counts also recover automatically after a temporary slowdown instead of staying stuck at 1 thread.
* **Linux & older Python startup fix**: Resolved a startup crash on Linux builds and Python 3.11/3.12 environments.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
