### ⚡ Archive Performance Overhaul

* **Folded file-trees by default**: In the Archive tab, creator and post folders are now folded by default. Opening the Archive tab with 10,000 to 100,000+ downloaded files is now instantaneous with no freezing or stuttering.
* **Instant search expansion**: Searching in the Archive tab automatically opens all matching creators and posts, and cleanly folds them back when you clear your search.
* **On-demand loading**: Folder contents are now loaded only when expanded, keeping the app snappy and keeping memory usage ultra-light.

---

### 🛡️ Download Integrity & Hash Verification

* **False SHA-256 mismatch warnings fixed**: Integrity verification now checks the raw downloaded file before any optional conversion or tagging, so verified files will no longer display false mismatch warnings.
* **Dual hash algorithm support**: The downloader now reliably recognizes both SHA-256 and MD5 integrity hashes across all supported platforms and download mirrors.
* **Video files protected**: Videos (`.mp4`) are now strictly excluded from audio tagging, ensuring video files remain untouched.
* **Audio tagging disabled by default**: Audio tagging is now opt-in across the application and can be enabled whenever you want automatic artist and title tags added to your music tracks.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.
