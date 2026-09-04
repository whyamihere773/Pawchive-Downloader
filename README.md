# Pawchive Downloader

<p align="center">
  <img src="assets/icon.png" alt="Pawchive Downloader Logo" width="96" height="96" />
</p>

<p align="center">
  <strong>A modern, high-speed desktop media archiver and downloader for Pawchive, Kemono, Coomer, and external cloud hosts.</strong><br>
  Built with Python, PySide6, and modern reactive QML.
</p>

<p align="center">
  <a href="https://github.com/whyamihere773/Pawchive-Downloader/releases/latest"><img src="https://img.shields.io/github/v/release/whyamihere773/Pawchive-Downloader?style=for-the-badge&color=blue&label=Latest%20Release" alt="Latest Release"></a>
  <a href="https://github.com/whyamihere773/Pawchive-Downloader/releases"><img src="https://img.shields.io/github/downloads/whyamihere773/Pawchive-Downloader/total?style=for-the-badge&color=success&label=Downloads" alt="Total Downloads"></a>
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
</p>

<p align="center">
  <a href="https://github.com/whyamihere773/Pawchive-Downloader/releases/latest">
    <img src="https://img.shields.io/badge/Download-Windows%20Executable%20(.zip)-2ea44f?style=for-the-badge&logo=windows&logoColor=white" height="42" alt="Download Windows Executable">
  </a>
</p>

<p align="center">
  <em>(Portable — no Python or command-line setup required! Just extract and run <code>Pawchive Downloader.exe</code>)</em>
</p>

---

## 📸 Interface Preview

<p align="center">
  <img src="assets/screenshots/01_downloader.png" alt="Pawchive Downloader Main Screen" width="95%" />
</p>

<details>
<summary><strong>🖼️ Click to expand more interface screenshots</strong></summary>
<br>

### Task Queue & Batch Actions
<img src="assets/screenshots/02_task_queue.png" alt="Task Queue" width="90%" />

### Download History & Archive Records
<img src="assets/screenshots/03_download_history.png" alt="Download History" width="90%" />

### Settings: Multi-Language & Network Authentication
<img src="assets/screenshots/04_settings_language.png" alt="Settings - Multi-Language & Network" width="90%" />

### Settings: Franchise & Known Character Engine
<img src="assets/screenshots/05_settings_engine.png" alt="Settings - Franchise & Known Engine" width="90%" />

</details>

---

## ✨ Key Features

- ⚡ **Adaptive Multi-Threaded Engine:** Parallel chunked downloads with dynamic concurrency scaling and manual thread-locking.
- 🌐 **Full 14-Language Localization (i18n):** Instant in-app language switching and real-time dynamically translated console activity logs (English, Chinese, Japanese, Korean, Spanish, French, German, Russian, Portuguese, and more).
- 🔓 **Built-in Cloud Decryptor:** Downloads and decrypts entire **Mega** folders directly with client-side AES decryption, plus direct streaming for **Google Drive**, **Dropbox**, and **GoFile**.
- 📊 **Active Large File Monitor (≥ 50 MB):** Dedicated real-time monitoring panel displaying individual progress bars, speed, and ETA for large media downloads.
- 🛡️ **SSD Stall & Disk Saturation Protection:** Hardened speed estimation engine prevents freeze glitches and auto-pauses gracefully upon out-of-disk space (`WinError 112` / `Errno 28`) without crashing worker threads.
- 🎯 **Advanced Smart Filtering:** Filter by character names, series, keywords, file categories (images, videos, audio, archives), or minimum file size thresholds.
- 🗂️ **Automated Organization & Franchise Recognition:** Automatically structures downloaded files into clean creator/franchise folders using an integrated franchise database and custom `Known.txt` rules.
- 📖 **Manga & Comic Order:** Chronologically sequences files and folders (`001 - Title`) so chapters stay in proper sequential order in image viewers.
- 🔗 **Link Harvesting & Export:** Extracts external cloud drive links and embedded player URLs from post bodies and comments; download them immediately or export to text files.
- 🎬 **Embedded Player Downloads:** Auto-updating `yt-dlp` integration grabs videos from Vimeo, YouTube, Streamable, RedGifs, Twitter/X, and more.
- 💾 **Session Recovery & Queue Persistence:** Pause and resume transfers anytime. Safely restores interrupted queues after an unexpected shutdown or crash.

---

## 🌐 Supported Platforms & Hosts

### Creator Archives & Portals
- **Pawchive** (`pawchive.pw`)
- **Kemono** (`kemono.su`)
- **Coomer** (`coomer.su`)
- **Cum.st** (`cum.st`)
- *Supported creator services:* Patreon, Pixiv Fanbox, Fantia, Subscribestar, Gumroad, Boosty, Discord, OnlyFans, Fansly, Afdian, DLsite, and more.

### Cloud Drives & Direct Storage
- **Mega** (folders and individual files with automatic AES decryption)
- **Google Drive** (shared files and public folders)
- **Dropbox** (direct download links and auto-extracted archives)
- **GoFile** (direct albums and folders)

### Media Galleries & File Lockers
- **Bunkr**, **Erome**, **nHentai**, **Saint2**, **Pixeldrain**, **Catbox**, **Mediafire**, **SimpCity**

### Video & Stream Embeds
- **YouTube**, **Vimeo**, **Streamable**, **RedGifs**, **Twitter/X**, **Bilibili**, **SoundCloud**, **Dailymotion**

---

## 🚀 Getting Started

### Option A: Pre-compiled Windows Binary (Recommended for most users)

1. Head over to the **[Latest Release](https://github.com/whyamihere773/Pawchive-Downloader/releases/latest)** page.
2. Download `Pawchive-Downloader-v1.0.5-Windows.zip`.
3. Extract the ZIP archive anywhere on your computer.
4. Run `Pawchive Downloader.exe` — that's it!

---

### Option B: Running from Source (Developers)

Ensure you have **Python 3.10 or newer** installed.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/whyamihere773/Pawchive-Downloader.git
   cd Pawchive-Downloader
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

4. **Build a Windows package:**
   ```bash
   python build.py
   ```
   The portable distribution will be output to `dist/Pawchive Downloader/` alongside a compressed release ZIP archive.

---

## 🤝 Contributing & Community

Feedback, bug reports, and pull requests are warmly welcome!
- **Have a suggestion or found a bug?** Please open an **[Issue](https://github.com/whyamihere773/Pawchive-Downloader/issues)**.
- **Want to add a new host or feature?** Fork the repository, create a feature branch, and submit a **Pull Request**.

---

## ⚖️ Disclaimer

This tool is intended strictly for personal archiving and backup purposes. Please respect content creators' terms of service and rights.
