import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: root

    property var bridge: null

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    contentWidth: availableWidth
    contentHeight: settingsCol.implicitHeight + 16
    clip: true

    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    ColumnLayout {
        id: settingsCol
        width: root.availableWidth
        spacing: 12

        // Section 0: Language & Internationalization
        CardSection {
            Layout.fillWidth: true
            title: tr("section_language", "Language & Display")
            iconText: "🌐"

            ColumnLayout {
                width: parent.width
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: tr("label_language", "Interface Language:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: "#94A3B8"
                    }

                    ComboBox {
                        id: langCombo
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 32
                        model: Lang ? Lang.availableLanguages : []
                        textRole: "native"
                        valueRole: "code"

                        currentIndex: {
                            if (!Lang) return 0
                            var list = Lang.availableLanguages
                            for (var i = 0; i < list.length; i++) {
                                if (list[i].code === Lang.currentLanguage) return i
                            }
                            return 0
                        }

                        onActivated: function(index) {
                            if (Lang && model[index]) {
                                var selectedCode = model[index].code
                                Lang.setLanguage(selectedCode)
                                if (root.bridge) root.bridge.language = selectedCode
                            }
                        }

                        background: Rectangle {
                            color: "#141923"
                            border.color: langCombo.activeFocus ? "#38BDF8" : "#283042"
                            border.width: 1
                            radius: 6
                        }

                        contentItem: Text {
                            leftPadding: 10
                            rightPadding: langCombo.indicator.width + 10
                            text: langCombo.displayText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F1F5F9"
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        popup: Popup {
                            y: langCombo.height + 2
                            width: langCombo.width
                            implicitHeight: contentItem.implicitHeight + 10
                            padding: 4
                            background: Rectangle {
                                color: "#141923"
                                border.color: "#283042"
                                border.width: 1
                                radius: 6
                            }
                            contentItem: ListView {
                                clip: true
                                implicitHeight: Math.min(contentHeight, 300)
                                model: langCombo.popup.visible ? langCombo.delegateModel : null
                                currentIndex: langCombo.highlightedIndex
                                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
                            }
                        }

                        delegate: ItemDelegate {
                            width: langCombo.width - 8
                            height: 30
                            highlighted: langCombo.highlightedIndex === index
                            contentItem: Text {
                                text: modelData.native
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: highlighted ? "#38BDF8" : "#CBD5E1"
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: highlighted ? "#1E293B" : "transparent"
                                radius: 4
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }
                }

                // AI Translation Disclaimer Banner
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: disclaimerRow.implicitHeight + 16
                    radius: 6
                    color: "#141A26"
                    border.color: "#233147"
                    border.width: 1

                    RowLayout {
                        id: disclaimerRow
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        spacing: 8

                        Text {
                            text: "🤖"
                            font.pixelSize: 13
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            text: tr("disclaimer_translation", "Translations are generated by AI and Google Translate. Some phrasing may not be completely accurate.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // Network & Authentication
        CardSection {
            Layout.fillWidth: true
            title: tr("section_network", "Network & Authentication (Cloudflare / Cookies)")
            iconText: "🌐"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: tr("label_cookie", "Session Cookie (Useful for Patreon / Fanbox / Cloudflare bypass):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_cookie", "e.g., session=eyJhbGci... or cf_clearance=...")
                    text: root.bridge ? root.bridge.cookieString : ""
                    onTextChanged: if (root.bridge && root.bridge.cookieString !== text) root.bridge.cookieString = text
                }

                Text {
                    text: tr("label_user_agent", "Custom User-Agent:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_user_agent", "Leave blank for default Chromium browser header")
                    text: root.bridge ? root.bridge.userAgent : ""
                    onTextChanged: if (root.bridge && root.bridge.userAgent !== text) root.bridge.userAgent = text
                }

                Text {
                    text: tr("label_proxy", "HTTP / HTTPS / SOCKS5 Proxy:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                StyledTextField {
                    Layout.fillWidth: true
                    placeholderText: tr("placeholder_proxy", "e.g., http://127.0.0.1:8080 or socks5://127.0.0.1:1080")
                    text: root.bridge ? root.bridge.proxyUrl : ""
                    onTextChanged: if (root.bridge && root.bridge.proxyUrl !== text) root.bridge.proxyUrl = text
                }
            }
        }

        // Storage & Naming Options
        CardSection {
            Layout.fillWidth: true
            title: tr("section_storage", "Storage & File Processing")
            iconText: "💾"

            ColumnLayout {
                width: parent.width
                spacing: 10

                StyledCheckBox {
                    text: tr("opt_auto_sync_known", "Auto-sync Known.txt on startup")
                    checked: true
                }

                StyledCheckBox {
                    text: tr("opt_show_console_links", "Show external links & media URLs in live console")
                    checked: true
                }

                StyledCheckBox {
                    text: tr("opt_extract_inline", "Extract and download inline post images from HTML content")
                    checked: root.bridge ? root.bridge.scanContentImages : true
                    onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                }

                StyledCheckBox {
                    text: tr("opt_download_embeds", "Download embedded media players (Vimeo, YouTube, Streamable) via yt-dlp")
                    checked: root.bridge ? root.bridge.downloadEmbeds : true
                    onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                }

                StyledCheckBox {
                    text: tr("opt_compress_webp", "Convert downloaded PNG/JPG to WebP format")
                    checked: root.bridge ? root.bridge.compressWebp : false
                    onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                }
            }
        }

        // Character & Franchise Recognition Engine (Master Database vs Auto-Learning)
        CardSection {
            Layout.fillWidth: true
            title: tr("section_known_engine", "Character & Franchise Recognition (Known Engine)")
            iconText: "🏷️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: tr("desc_known_engine", "Choose how the engine identifies characters and structures folders (Franchise ➔ Character):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    FilterCheckbox {
                        label: tr("mode_hybrid", "Master DB + Auto-Learn (Hybrid)")
                        iconText: "✨"
                        activeColor: "#38BDF8"
                        tooltip: tr("mode_hybrid_tip", "Combines the comprehensive 100k+ game & anime database with automatic learning of new tags into Known.txt (Recommended)")
                        checked: root.bridge ? (root.bridge.knownRecognitionMode === "hybrid" || root.bridge.knownRecognitionMode === "") : true
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "hybrid"
                    }

                    FilterCheckbox {
                        label: tr("mode_database_only", "Master Database Only")
                        iconText: "📚"
                        activeColor: "#818CF8"
                        tooltip: tr("mode_database_only_tip", "Only matches against the curated 100k+ video game/anime database (prevents modifying Known.txt)")
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "database_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "database_only"
                    }

                    FilterCheckbox {
                        label: tr("mode_learning_only", "Custom Known.txt Only")
                        iconText: "📝"
                        activeColor: "#34D399"
                        tooltip: tr("mode_learning_only_tip", "Only uses your custom Known.txt and learns new character tags as downloads run")
                        checked: root.bridge ? root.bridge.knownRecognitionMode === "learning_only" : false
                        onClicked: if (root.bridge) root.bridge.knownRecognitionMode = "learning_only"
                    }
                }

                Text {
                    text: tr("note_known_structure", "ℹ️ When 'Separate folders by Known' is enabled, downloads will automatically sort into: 'Franchise Name / Character Name / Post Folder'.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }
        }

        // Post-Download & System Actions (What to do after done)
        CardSection {
            Layout.fillWidth: true
            title: tr("section_post_actions", "Post-Download & System Actions")
            iconText: "⚡"

            ColumnLayout {
                width: parent.width
                spacing: 12

                // Convenient checkboxes for notifications / folders
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    StyledCheckBox {
                        text: tr("opt_open_complete", "Open download directory when complete")
                        tooltip: tr("opt_open_complete_tip", "Automatically open Windows File Explorer to the downloaded creator folder")
                        checked: root.bridge ? root.bridge.openFolderOnComplete : false
                        onCheckedChanged: if (root.bridge) root.bridge.openFolderOnComplete = checked
                    }

                    StyledCheckBox {
                        text: tr("opt_chime_complete", "Play chime sound when complete")
                        tooltip: tr("opt_chime_complete_tip", "Play an audible notification chime when all download tasks finish")
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
                            text: tr("label_what_to_do", "What to do after download finishes (one-time action):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#94A3B8"
                        }
                        Text {
                            text: tr("note_what_to_do", "• Resets to 'Do Nothing' after each task. Can also be set directly in the bottom action bar.")
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
                            label: tr("action_none", "Do Nothing")
                            iconText: "⏸️"
                            tooltip: tr("action_none_tip", "Keep application open and system running normally")
                            checked: root.bridge ? (root.bridge.postDownloadAction === "none" || root.bridge.postDownloadAction === "") : true
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "none"
                        }

                        FilterCheckbox {
                            label: tr("action_close", "Close App")
                            iconText: "🚪"
                            activeColor: "#38BDF8"
                            tooltip: tr("action_close_tip", "Automatically exit Pawchive Downloader when all files finish downloading")
                            checked: root.bridge ? root.bridge.postDownloadAction === "close_app" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "close_app"
                        }

                        FilterCheckbox {
                            label: tr("action_sleep", "Sleep System")
                            iconText: "🌙"
                            activeColor: "#A78BFA"
                            tooltip: tr("action_sleep_tip", "Put the computer into sleep / suspend mode after download completes")
                            checked: root.bridge ? root.bridge.postDownloadAction === "sleep" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "sleep"
                        }

                        FilterCheckbox {
                            label: tr("action_hibernate", "Hibernate (-F Force)")
                            iconText: "💤"
                            activeColor: "#818CF8"
                            tooltip: tr("action_hibernate_tip", "Force save memory to disk and turn off power (Hibernate -F)")
                            checked: root.bridge ? root.bridge.postDownloadAction === "hibernate" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "hibernate"
                        }

                        FilterCheckbox {
                            label: tr("action_shutdown", "Shut Down (-F Force)")
                            iconText: "🔌"
                            activeColor: "#F43F5E"
                            tooltip: tr("action_shutdown_tip", "Force close running applications and safely shut down the computer (includes 10s cancel buffer)")
                            checked: root.bridge ? root.bridge.postDownloadAction === "shutdown" : false
                            onClicked: if (root.bridge) root.bridge.postDownloadAction = "shutdown"
                        }

                        FilterCheckbox {
                            label: tr("action_restart", "Restart (-F Force)")
                            iconText: "🔄"
                            activeColor: "#F59E0B"
                            tooltip: tr("action_restart_tip", "Force close running applications and restart the operating system")
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
                    text: tr("app_title", "Pawchive Downloader")
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
                        text: "v1.0.5"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: "#38BDF8"
                    }
                }
            }

            Item { Layout.fillWidth: true }

            StyledButton {
                text: tr("btn_export_console_logs", "Export Console Logs")
                iconText: "📄"
                variant: "outline"
                onClicked: if (root.bridge) root.bridge.exportLogs()
            }

            StyledButton {
                text: tr("btn_save_preferences", "Save Preferences")
                iconText: "💾"
                variant: "primary"
                onClicked: if (root.bridge) root.bridge.saveSettings()
            }
        }
    }
}
