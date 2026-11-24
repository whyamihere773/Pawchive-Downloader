### ⚡ Smoother Multi-Hour Pawchive Downloads

* **No more stop-and-go cooldown loops on long downloads**: When Pawchive's hourly download allowance tightens after an hour of heavy downloading, the app now settles into a steady **Quota Cruise** pace instead of repeatedly stopping for two-minute waits every couple of minutes. Once your hourly allowance refreshes, speeds automatically ramp back up on their own.
* **Smarter marathon pacing**: Large multi-hour queues now ease their pace slightly before reaching Pawchive's hourly limit, keeping long creator downloads flowing smoothly from start to finish.
* **Even load across Pawchive file servers**: Queued posts spread downloads evenly across available Pawchive servers and automatically favor idle servers whenever another server gets busy.

---

### 🛠️ Fixes

* **Interrupted downloads during rate-limit pauses fixed**: Active file transfers on other workers are no longer cut off mid-download when a rate-limit pause begins.
* **Faster skipping for missing Pawchive files**: Files that do not exist on Pawchive's servers now fail immediately on the first check instead of waiting and checking the same missing link twice.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
