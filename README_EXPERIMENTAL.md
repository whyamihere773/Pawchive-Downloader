# Pawchive Downloader — Experimental Branch

<p align="center">
  <img src="assets/icon.png" alt="Pawchive Downloader Logo" width="80" height="80" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Branch-Experimental-orange?style=for-the-badge&logo=git&logoColor=white" alt="Branch: Experimental">
  <img src="https://img.shields.io/badge/Status-Bleeding--Edge-red?style=for-the-badge" alt="Status: Bleeding Edge">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-blue?style=for-the-badge" alt="Platform: Linux | Windows">
  <a href="https://discord.gg/YBrKkzVq8"><img src="https://img.shields.io/badge/Discord-Join%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord Server"></a>
</p>

---

> [!WARNING]
> ### ⚠️ EXPERIMENTAL & BLEEDING-EDGE WARNING
> **This branch is under active, rapid development. Expect bugs, instability, UI glitches, and potential crashes!**
> 
> * **Not recommended for daily/production use**: Features and code changes here are tested in progress and may break between commits.
> * **First-Time Native Linux Port**: Linux ELF compilation, display servers (Wayland/X11), and desktop integration are experimental.
> * **Always back up your files**: Configuration schemas and databases on this branch may change without automated migration.
> 
> 👉 **Looking for the stable, tested release?** Switch to the **[`main`](https://github.com/whyamihere773/Pawchive-Downloader/tree/main)** branch or download the verified release from **[Releases](https://github.com/whyamihere773/Pawchive-Downloader/releases)**.

---

## 🔬 What This Branch Does

This branch serves as the development bed for cross-platform portability and upcoming engine upgrades:

1. **Native Linux / CachyOS Distribution**:
   - Native Linux ELF standalone binary (`pawchive`) with bundled PySide6/Qt6 runtime.
   - Cross-platform process and path handling (desktop file openers via `xdg-open` / `open` / `os.startfile`).
   - Desktop integration via `pawchive.desktop` and PKGBUILD packaging.

2. **Automated GitHub Actions Compilation**:
   - Pushes to this branch trigger the automated Linux build workflow on GitHub's Ubuntu runners.
   - Compiles and outputs downloadable `.tar.gz` packages directly to the **Actions** tab with zero local compilation setup needed.

---

## 💬 Need Help, Support, or Want to Report Bugs?

If you run into any issues, experience unexpected crashes, or want to share feedback on these experimental builds:

* **Join our community:** Chat directly with me on our **[Discord Server](https://discord.gg/YBrKkzVq8)**!
* **Report a bug or crash:** Open an issue on our **[GitHub Issues](https://github.com/whyamihere773/Pawchive-Downloader/issues)** tracker with logs from your `logs/` directory.
