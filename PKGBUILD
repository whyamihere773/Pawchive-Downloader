# Maintainer: whyamihere773 <https://github.com/whyamihere773/Pawchive-Downloader>
pkgname=pawchive-downloader
pkgver=1.2.1
pkgrel=1
pkgdesc="Universal Cross-Platform Kemono, Coomer, Bunkr & Fanbox Archival Suite"
arch=('any')
url="https://github.com/whyamihere773/Pawchive-Downloader"
license=('MIT')
depends=(
    'python>=3.9'
    'pyside6'
    'qt6-declarative'
    'qt6-quickcontrols2'
    'qt6-svg'
    'python-pillow'
    'python-requests'
    'python-urllib3'
    'python-pycryptodome'
    'python-mutagen'
    'python-qrcode'
    'yt-dlp'
    'p7zip'
)
optdepends=(
    'python-telethon: Telegram MTProto downloader integration'
    'python-gdown: Google Drive album downloads'
    'uv: Blazing fast dependency resolution'
)
provides=('pawchive')
conflicts=('pawchive-downloader-git')
source=("$pkgname-$pkgver.tar.gz::https://github.com/whyamihere773/Pawchive-Downloader/archive/refs/tags/v$pkgver.tar.gz"
        "pawchive.desktop")
sha256sums=('SKIP'
            'SKIP')

package() {
    cd "$srcdir"
    # Find directory containing source if building from tarball, or use current dir
    if [ -d "$pkgname-$pkgver" ]; then
        cd "$pkgname-$pkgver"
    fi

    # Install application files to /usr/share/pawchive
    install -dm755 "$pkgdir/usr/share/pawchive"
    cp -r bridge core services qml assets locales config main.py "$pkgdir/usr/share/pawchive/"

    # Install executable wrapper to /usr/bin/pawchive
    install -dm755 "$pkgdir/usr/bin"
    cat << 'EOF' > "$pkgdir/usr/bin/pawchive"
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/pawchive/main.py "$@"
EOF
    chmod +x "$pkgdir/usr/bin/pawchive"

    # Install desktop launcher
    install -Dm644 "$srcdir/pawchive.desktop" "$pkgdir/usr/share/applications/pawchive.desktop"

    # Install application icon
    if [ -f "assets/icon.png" ]; then
        install -Dm644 "assets/icon.png" "$pkgdir/usr/share/icons/hicolor/256x256/apps/pawchive.png"
    fi
}
