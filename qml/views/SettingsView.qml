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

        // Character & Franchise Recognition Engine (Master Database vs Auto-Learning)
        CardSection {
            Layout.fillWidth: true
            title: "Character & Franchise Recognition (Known Engine)"
            iconText: "🏷️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: "Choose how the engine identifies characters and structures folders (Franchise ➔ Character):"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    FilterCheckbox {
                        label: "Master DB + Auto-Learn (Hybrid)"
                        iconText: "✨"
                        activeColor: "#38BDF8"
                        tooltip: "Combines the comprehensive 100k+ game & anime database with automatic learning of new tags into Known.txt (Recommended)"
                        checked: root.bridge ? (root.bridge.knownRecognitionMode === "hybrid" || root.bridge.knownRecognitionMode === "") : true
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "hybrid"
                    }

                    FilterCheckbox {
                        label: "Master Database Only"
                        iconText: "📚"
                        activeColor: "#818CF8"
                        tooltip: "Only matches against the curated 100k+ video game/anime database (prevents modifying Known.txt)"
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "database_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "database_only"
                    }

                    FilterCheckbox {
                        label: "Custom Known.txt Only"
                        iconText: "📝"
                        activeColor: "#34D399"
                        tooltip: "Only uses your custom Known.txt and learns new character tags as downloads run"
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "learning_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "learning_only"
                    }
                }

                Text {
                    text: "ℹ️ When 'Separate folders by Known' is enabled, downloads will automatically sort into: 'Franchise Name / Character Name / Post Folder'."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }
        }

        // Post-Download & System Actions (What to do after done)
        CardSection {
            Layout.fillWidth: true
            title: "Post-Download & System Actions"
            iconText: "⚡"

            ColumnLayout {
                width: parent.width
                spacing: 12

                // Convenient checkboxes for notifications / folders
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    StyledCheckBox {
                        text: "Open download directory when complete"
                        tooltip: "Automatically open Windows File Explorer to the downloaded creator folder"
                        checked: root.bridge ? root.bridge.openFolderOnComplete : false
                        onCheckedChanged: if (root.bridge) root.bridge.openFolderOnComplete = checked
                    }

                    StyledCheckBox {
                        text: "Play chime sound when complete"
                        tooltip: "Play an audible notification chime when all download tasks finish"
                        checked: root.bridge ? root.bridge.playCompletionSound : false
                        onCheckedChanged: if (root.bridge) root.bridge.playCompletionSound = checked
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#1E293B"
                }

                // Power/App Action Selector
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "What to do after download finishes (one-time action):"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#94A3B8"
                        }
                        Text {
                            text: "• Resets to 'Do Nothing' after each task. Can also be set directly in the bottom action bar."
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.fillWidth: true
                        }
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        FilterCheckbox {
                            label: "Do Nothing"
                            iconText: "⏸️"
                            tooltip: "Keep application open and system running normally"
                            checked: root.bridge ? (root.bridge.postDownloadAction === "none" || root.bridge.postDownloadAction === "") : true
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "none"
                        }

                        FilterCheckbox {
                            label: "Close App"
                            iconText: "🚪"
                            activeColor: "#38BDF8"
                            tooltip: "Automatically exit Pawchive Downloader when all files finish downloading"
                            checked: root.bridge ? root.bridge.postDownloadAction === "close_app" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "close_app"
                        }

                        FilterCheckbox {
                            label: "Sleep System"
                            iconText: "🌙"
                            activeColor: "#A78BFA"
                            tooltip: "Put the computer into sleep / suspend mode after download completes"
                            checked: root.bridge ? root.bridge.postDownloadAction === "sleep" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "sleep"
                        }

                        FilterCheckbox {
                            label: "Hibernate (-F Force)"
                            iconText: "💤"
                            activeColor: "#818CF8"
                            tooltip: "Force save memory to disk and turn off power (Hibernate -F)"
                            checked: root.bridge ? root.bridge.postDownloadAction === "hibernate" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "hibernate"
                        }

                        FilterCheckbox {
                            label: "Shut Down (-F Force)"
                            iconText: "🔌"
                            activeColor: "#F43F5E"
                            tooltip: "Force close running applications and safely shut down the computer (includes 10s cancel buffer)"
                            checked: root.bridge ? root.bridge.postDownloadAction === "shutdown" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "shutdown"
                        }

                        FilterCheckbox {
                            label: "Restart (-F Force)"
                            iconText: "🔄"
                            activeColor: "#F59E0B"
                            tooltip: "Force close running applications and restart the operating system"
                            checked: root.bridge ? root.bridge.postDownloadAction === "restart" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "restart"
                        }
                    }
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
                        text: "v1.0.4"
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
