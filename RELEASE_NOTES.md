### ⚡ Smoother Multi-Hour Pawchive Downloads & Live Footer Guard

* **Always-visible Rate Guard in the bottom bar**: Your live Pawchive pace, active connections, and 60-minute download count now stay visible at the bottom of the window across every tab — even when idle. Choose between **Full Length**, **Compact**, **Minimal**, **Tiny Dot**, or **Hidden** styles, hover anytime to inspect every exact unshortened stat, or click the badge to switch modes and reset on the fly.
* **True state memory across restarts & back-to-back downloads**: Your rolling 60-minute download count, recent rate-limit history, active cooldown timers, and **Quota Cruise** state are now saved on exit and carried across app restarts and consecutive creator queues.
* **No more stop-and-go cooldown loops on long downloads**: When Pawchive's hourly download allowance tightens after an hour of heavy downloading, the app now settles into a steady **Quota Cruise** pace instead of repeatedly stopping for two-minute waits every couple of minutes. Once your hourly allowance refreshes, speeds automatically ramp back up on their own.
* **Smarter marathon pacing**: Large multi-hour queues now ease their pace slightly before reaching Pawchive's hourly limit, keeping long creator downloads flowing smoothly from start to finish.
* **Even load across Pawchive file servers**: Queued posts spread downloads evenly across available Pawchive servers and automatically favor idle servers whenever another server gets busy.

---

### 🛠️ Fixes

* **New Watchlist creators no longer auto-check on startup**: Newly added or downloaded creators now start with automatic startup update checks turned off by default unless you enable **Auto-check** for them.
* **Interrupted downloads during rate-limit pauses fixed**: Active file transfers on other workers are no longer cut off mid-download when a rate-limit pause begins.
* **Faster skipping for missing Pawchive files**: Files that do not exist on Pawchive's servers now fail immediately on the first check instead of waiting and checking the same missing link twice.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
