# Pawchive Downloader — `experimental` Branch

<p align="center">
  <img src="assets/icon.png" alt="Pawchive Downloader Logo" width="96" height="96" />
</p>

<p align="center">
  <strong>Cutting-edge testing branch for Pawchive Downloader</strong><br>
  <em>Active development branch for native Linux / CachyOS support, cross-platform engine updates, and experimental features.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Branch-Experimental-orange?style=for-the-badge&logo=git&logoColor=white" alt="Branch: Experimental">
  <img src="https://img.shields.io/badge/Status-Bleeding--Edge-red?style=for-the-badge" alt="Status: Bleeding Edge">
  <a href="https://discord.gg/YBrKkzVq8"><img src="https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord Server"></a>
</p>

---

> [!WARNING]
> ### ⚠️ EXPERIMENTAL & BLEEDING-EDGE WARNING
> **Expect bugs, instability, UI glitches, and crashes!**
> 
> * **Not recommended for daily/production use**: Features on this branch are actively being developed, tested, and iterated on.
> * **Experimental Linux Port**: Native Linux ELF compilation, display server handling (Wayland/X11), and desktop integration are under active testing.
> * **Always back up your files**: Configuration schemas and databases on this branch may change without automated migration.
> 
> 👉 **Looking for the stable, tested version?** Switch to the **[`main`](https://github.com/whyamihere773/Pawchive-Downloader/tree/main)** branch or download the latest release from **[Releases](https://github.com/whyamihere773/Pawchive-Downloader/releases)**.

---

## 🔬 What is on this Branch?

This branch serves as the sandbox for cross-platform portability and upcoming architecture improvements:

* **Native Linux / CachyOS Distribution**: Complete ELF binary compilation with bundled Qt6/QML environments, `pawchive.desktop` integration, and native process launching.
* **Automated GitHub Actions Compilation**: Pushes to this branch trigger automated Linux builds on GitHub's Ubuntu runners, publishing standalone `.tar.gz` packages directly to the **Actions** tab.
* **Cross-Platform Engine Upgrades**: Unified path handling, POSIX process management, and cross-platform desktop opening (`xdg-open` / `open` / `os.startfile`).

---

## 📖 About Pawchive Downloader

**Pawchive Downloader** is a high-speed desktop media archiver and batch downloader for Pawchive, Kemono, Coomer, Telegram, and external cloud hosts, built with Python, PySide6, and modern reactive QML.

Key capabilities include:
* Multi-threaded parallel downloading with bandwidth throttling and polite rate-limit pacing.
* Scheduled background syncing & automated artist watchlist monitoring.
* Multi-drive storage pools with automatic overflow management.
* Built-in media decompressor, offline AI character tagger, and link vaulting.

---

## 💬 Need Help, Support, or Want to Chat?

If you run into any issues, notice unexpected crashes, or want to share feedback on the experimental builds:

* **Join our community:** Chat directly on our **[Discord Server](https://discord.gg/YBrKkzVq8)**.
* **Report a bug:** Open an issue on the **[GitHub Issues](https://github.com/whyamihere773/Pawchive-Downloader/issues)** tracker with logs from the `logs/` directory.

---
