# Pawchive Downloader

A desktop media grabber and archiving tool for Pawchive, Kemono, Coomer, and external file hosts, built with Python, PySide6, and QML.

## Overview

Pawchive Downloader lets you paste a creator link or single post and pull down photos, videos, audio, and archives straight to your computer. It handles the organization for you—sorting files into clean folders, filtering out unwanted content, and even grabbing media hosted on third-party cloud drives like Mega, Google Drive, and Dropbox.

## Highlights

- **Parallel downloads:** Grabs multiple files and links at once to speed up large creator backlogs.
- **Built-in cloud decryptor:** Downloads and decrypts entire Mega folders directly, along with file streaming for Google Drive, Dropbox, and GoFile.
- **Flexible filtering:** Narrow down downloads by character/series names, file types (images, videos, audio, archives), keywords, or minimum file size thresholds.
- **Smart folder sorting:** Automatically organizes files by creator, post date, or custom series groupings using a customizable `Known.txt` list.
- **Comic & Manga ordering:** Numbers image files and folders chronologically (`001 - Title`) so chapters stay in proper reading order in your favorite viewer.
- **Link harvesting & export:** Scans post bodies and comments for external drive links or stream embeds, letting you download them directly or save the raw URLs to a text file.
- **Embedded player downloads:** Uses an integrated, auto-updating `yt-dlp` runner to grab videos from Vimeo, YouTube, Streamable, RedGifs, and more.
- **Resume & session memory:** Pause and resume transfers at any point. If you close the window midway, your queue is automatically saved and ready to restore on the next launch.

## Where you can download from

### Creator Archives & Portals
- **Pawchive** (`pawchive.pw`)
- **Kemono** (`kemono.su`)
- **Coomer** (`coomer.su`)
- **Cum.st** (`cum.st`)
- *Supported services:* Patreon, Pixiv Fanbox, Fantia, Subscribestar, Gumroad, Boosty, Discord, OnlyFans, Fansly, Afdian, DLsite, and more.

### Cloud Storage
- **Mega** (folders and standalone files with automatic AES decryption)
- **Google Drive** (shared files and folders)
- **Dropbox** (direct downloads and auto-unzipped archives)
- **GoFile** (direct albums and folders)

### Media Galleries & Lockers
- **Bunkr**, **Erome**, **nHentai**, **Saint2**, **Pixeldrain**, **Catbox**, **Mediafire**, **SimpCity**

### Video & Stream Embeds
- **YouTube**, **Vimeo**, **Streamable**, **RedGifs**, **Twitter/X**, **Bilibili**, **SoundCloud**, **Dailymotion**

## Getting Started

Make sure you have **Python 3.10 or newer** installed.

### 1. Install Requirements

```bash
pip install -r requirements.txt
```

### 2. Launch the Application

```bash
python main.py
```

### 3. Build a Windows Executable (Optional)

To compile the application into a standalone Windows directory package:

```bash
python build.py
```

The output folder will be generated in `dist/PawchiveDownloader/` with `PawchiveDownloader.exe` ready to run.

## Contributing & Suggestions

Contributions, feature suggestions, and feedback are all very welcome! Whether you have ideas for new sites to support, quality-of-life tweaks, UI improvements, or bug fixes, community input is always appreciated.

### Have a suggestion or feature request?
- Open an **Issue** or share your thoughts if you'd like to see a specific host supported, have an idea for a new filter option, or want to report broken links and site changes. All suggestions are considered!

### Want to contribute code?
1. **Fork the repository** and create a feature branch for your work.
2. **Make your changes** and check that existing unit tests continue to pass.
3. **Submit a Pull Request** describing what you added or improved.
