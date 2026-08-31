import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: root

    property var bridge: null
    contentWidth: availableWidth
    contentHeight: settingsCol.implicitHeight + 16
    clip: true

    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    ColumnLayout {
        id: settingsCol
        width: root.availableWidth
        spacing: 12

        // Network & Authentication
        CardSection {
            Layout.fillWidth: true
            title: "Network & Authentication (Cloudflare / Cookies)"
            iconText: "🌐"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: "Session Cookie (Useful for Patreon / Fanbox / Cloudflare bypass):"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: "e.g., session=eyJhbGci... or cf_clearance=..."
                    text: root.bridge ? root.bridge.cookieString : ""
                    onTextChanged: if (root.bridge && root.bridge.cookieString !== text) root.bridge.cookieString = text
                }

                Text {
                    text: "Custom User-Agent:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: "Leave blank for default Chromium browser header"
                    text: root.bridge ? root.bridge.userAgent : ""
                    onTextChanged: if (root.bridge && root.bridge.userAgent !== text) root.bridge.userAgent = text
                }

                Text {
                    text: "HTTP / HTTPS / SOCKS5 Proxy:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: "e.g., http://127.0.0.1:8080 or socks5://127.0.0.1:1080"
                    text: root.bridge ? root.bridge.proxyUrl : ""
                    onTextChanged: if (root.bridge && root.bridge.proxyUrl !== text) root.bridge.proxyUrl = text
                }
            }
        }

        // Storage & Naming Options
        CardSection {
            Layout.fillWidth: true
            title: "Storage & File Processing"
            iconText: "💾"

            ColumnLayout {
                width: parent.width
                spacing: 10

                StyledCheckBox {
                    text: "Auto-sync Known.txt on startup"
                    checked: true
                }

                StyledCheckBox {
                    text: "Show external links & media URLs in live console"
                    checked: true
                }

                StyledCheckBox {
                    text: "Extract and download inline post images from HTML content"
                    checked: root.bridge ? root.bridge.scanContentImages : true
                    onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                }

                StyledCheckBox {
                    text: "Download embedded media players (Vimeo, YouTube, Streamable) via yt-dlp"
                    checked: root.bridge ? root.bridge.downloadEmbeds : true
                    onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                }

                StyledCheckBox {
                    text: "Convert downloaded PNG/JPG to WebP format"
                    checked: root.bridge ? root.bridge.compressWebp : false
                    onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                }
            }
        }

        // Action Buttons & About
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Version info
            RowLayout {
                spacing: 6
                Text {
                    text: "Pawchive Downloader"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: "#94A3B8"
                }
                Rectangle {
                    height: 20
                    implicitWidth: sVerText.implicitWidth + 10
                    radius: 10
                    color: "#1E293B"
                    Text {
                        id: sVerText
                        anchors.centerIn: parent
                        text: "v1.0.0"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: "#38BDF8"
                    }
                }
            }

            Item { Layout.fillWidth: true }

            StyledButton {
                text: "Export Console Logs"
                iconText: "📄"
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.exportLogs()
            }

            StyledButton {
                text: "Save Preferences"
                iconText: "💾"
                variant: "primary"
                onClicked: if (root.bridge) root.bridge.saveSettings()
            }
        }
    }
}
