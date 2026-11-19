Pawchive Downloader (Linux)
===========================

1. Portable Tarball (`Pawchive-Linux-v*-Portable-x86_64.tar.gz`)
----------------------------------------------------------------
This archive already contains a single `pawchive-downloader/` folder.
Use "Extract here" in your file manager (or `tar -xzf Pawchive-Linux-*.tar.gz`)
so you do not end up with a doubled folder.

Run from inside `pawchive-downloader/`:

    ./pawchive

To add Pawchive Downloader to your Application Menu, install its icon, link
`~/.local/bin/pawchive`, and register `pawchive://` links:

    ./install.sh

Run `./uninstall.sh` later to remove those desktop entries (your settings and
downloads are never touched).

2. Flatpak — Experimental (`Pawchive-Linux-v*-Flatpak-Experimental-x86_64.flatpak`)
-----------------------------------------------------------------------------------
Universal package for any Linux distro with Flatpak installed (Arch, CachyOS,
Fedora, Ubuntu, Mint, Debian, openSUSE, SteamOS/Bazzite, NixOS):

    flatpak install --user Pawchive-Linux-*-Flatpak-Experimental-x86_64.flatpak
    flatpak run io.github.whyamihere773.PawchiveDownloader

To uninstall:

    flatpak uninstall io.github.whyamihere773.PawchiveDownloader

3. Arch / CachyOS Package — Experimental (`Pawchive-Linux-v*-Arch-Experimental-x86_64.pkg.tar.zst`)
---------------------------------------------------------------------------------------------------
Install directly with pacman on Arch, CachyOS, EndeavourOS, or Manjaro:

    sudo pacman -U Pawchive-Linux-*-Arch-Experimental-x86_64.pkg.tar.zst

(An AUR-ready `PKGBUILD` is also provided under `packaging/aur/PKGBUILD`.)

4. Graphics / OpenGL Troubleshooting
------------------------------------
If your GPU / Wayland / X11 driver cannot create an OpenGL context, the app
automatically falls back to software rendering. You can also force software
rendering manually at any time:

    ./pawchive --software-render
