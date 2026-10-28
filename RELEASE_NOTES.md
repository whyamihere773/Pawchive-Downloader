### 🔧 Updater Reliability & Rate Limit Fix

* **In-app updates rate limit fix**: Resolved the "GitHub is limiting requests right now" error that prevented updates on VPNs, proxies, and shared connections by adding an automatic fallback that doesn't consume API limits.
* **Smarter update checks**: Background startup checks are now cached so restarting or opening the app multiple times no longer gets you temporarily blocked by GitHub.

---

### 🏷️ Smart Batch Renamer Enhancements

* **Post caption renaming token**: Added `{captionText}` to the Batch Renamer so you can rename downloaded media with each post's caption or description.
* **Automatic caption detection**: Works seamlessly across posts and creator folders by extracting captions directly from local post information files.

---

### 🛠️ Download & Compression Fixes

* **Compressed videos no longer re-download**: Files you compressed with Pawchive or external tools are no longer mistakenly treated as low-resolution thumbnails on subsequent downloads.
* **Format conversion detection**: Converted videos (such as MP4 converted to MKV or WebM) and compressed images (such as AVIF or WebP) are properly recognized as already saved.

---

> I hope you enjoy using Pawchive Downloader! If you run into any issues, notice unexpected behavior, or have ideas for improvements, please don't hesitate to open a bug report. Your feedback helps me make the app better with every update.

> I work on Pawchive simply because I enjoy it, and it will always be free. If you'd ever like to support it, I have a Ko-fi page, but please only do so if you can comfortably afford it. It's never expected, and using the app and sharing your feedback already means a lot to me. 💙
