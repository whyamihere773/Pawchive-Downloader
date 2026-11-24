import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: storageProcCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    interactive: !storageProcCard.view.isScrolling
    title: tr("section_storage", "Storage & File Processing")
    iconText: "💾"
    entranceOffsetY: storageProcCard.view.tabEntranceOffsetY
    entranceOpacity: storageProcCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        spacing: 10

        StyledCheckBox {
            text: tr("opt_auto_sync_known", "Auto-sync Known.txt on startup")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.autoSyncKnown : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.autoSyncKnown = checked
        }

        StyledCheckBox {
            text: tr("opt_show_console_links", "Show external links & media URLs in live console")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.showConsoleLinks : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.showConsoleLinks = checked
        }

        StyledCheckBox {
            text: tr("opt_extract_inline", "Extract and download inline post images from HTML content")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.scanContentImages : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.scanContentImages = checked
        }

        StyledCheckBox {
            text: tr("opt_download_dms", "Download creator direct messages (DMs) when available (cum.st / Pawchive)")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.downloadDms : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.downloadDms = checked
        }

        StyledCheckBox {
            text: tr("opt_download_embeds", "Download embedded media players (Vimeo, YouTube, Streamable) via yt-dlp")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.downloadEmbeds : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.downloadEmbeds = checked
        }

        // Videos that only play while logged in (only while downloading embeds)
        Row {
            visible: storageProcCard.view.bridge ? storageProcCard.view.bridge.downloadEmbeds : true
            spacing: 8
            leftPadding: 28

            Text {
                text: tr("embed_cookies_label", "Use browser sign-in:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
                anchors.verticalCenter: parent.verticalCenter
            }

            StyledComboBox {
                objectName: "embed_cookies_browser"
                implicitHeight: 28
                implicitWidth: 140
                model: [
                        { text: tr("embed_cookies_off", "Off"), value: "" },
                        { text: "Firefox", value: "firefox" },
                        { text: "Chrome", value: "chrome" },
                        { text: "Edge", value: "edge" },
                        { text: "Brave", value: "brave" },
                        { text: "Opera", value: "opera" },
                        { text: "Vivaldi", value: "vivaldi" },
                        { text: "Chromium", value: "chromium" }
                    ]
                value: storageProcCard.view.bridge ? storageProcCard.view.bridge.embedCookiesBrowser : ""
                tooltip: tr("embed_cookies_tip", "Embedded videos that only play while you're logged in (RedGifs, private Vimeo, age-restricted YouTube) are downloaded with that browser's sign-in. Firefox works best; Chrome, Edge and Brave have to be closed, and their newest versions can't be read at all.")
                onValuePicked: function(v) { if (storageProcCard.view.bridge) storageProcCard.view.bridge.embedCookiesBrowser = v }
            }
        }

        StyledCheckBox {
            text: tr("opt_compress_webp", "Convert downloaded PNG/JPG to WebP format")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.compressWebp : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.compressWebp = checked
        }

        // How strongly (only while compressing)
        Row {
            visible: storageProcCard.view.bridge ? storageProcCard.view.bridge.compressWebp : false
            spacing: 8
            leftPadding: 28

            Text {
                text: tr("webp_quality_label", "WebP quality:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
                anchors.verticalCenter: parent.verticalCenter
            }

            StyledComboBox {
                implicitHeight: 28
                implicitWidth: 140
                model: [
                        { text: tr("webp_q_lossless", "Lossless"), value: "lossless" },
                        { text: tr("webp_q_high", "High"), value: "high" },
                        { text: tr("webp_q_balanced", "Balanced"), value: "balanced" },
                        { text: tr("webp_q_small", "Small"), value: "small" },
                        { text: tr("webp_q_smallest", "Smallest"), value: "smallest" }
                    ]
                value: storageProcCard.view.bridge ? storageProcCard.view.bridge.webpQuality : "balanced"
                tooltip: tr("webp_quality_tip", "How strongly pictures are compressed. Lossless keeps every pixel; Balanced is barely visible and much smaller; Small and Smallest save the most space. A picture is kept as it was if the WebP wouldn't be smaller.")
                onValuePicked: function(v) { if (storageProcCard.view.bridge) storageProcCard.view.bridge.webpQuality = v }
            }
        }

        StyledCheckBox {
            text: tr("opt_tag_audio_files_settings", "Write creator and post tags to downloaded audio files (MP3/FLAC/M4A)")
            tooltip: tr("opt_tag_audio_files_tip", "Automatically sets Artist to creator name and Title to post title for seamless import into music managers")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.writeAudioMetadata : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.writeAudioMetadata = checked
        }

        StyledCheckBox {
            text: tr("opt_write_sidecars", "Generate metadata sidecar files (for Hydrus Network, Eagle, Booru taggers)")
            tooltip: tr("opt_write_sidecars_tip", "Saves companion metadata files alongside downloads containing creator, title, post URL, published date, and tags for automated gallery ingestion.")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.writeSidecars : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.writeSidecars = checked
        }

        // Sidecar options (only while writeSidecars is active)
        Row {
            visible: storageProcCard.view.bridge ? storageProcCard.view.bridge.writeSidecars : false
            spacing: 16
            leftPadding: 28

            Row {
                spacing: 8
                Text {
                    text: tr("sidecar_format_label", "Format:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#94A3B8"
                    anchors.verticalCenter: parent.verticalCenter
                }
                StyledComboBox {
                    implicitHeight: 28
                    implicitWidth: 170
                    model: [
                        { text: "Universal JSON (.json)", value: "json" },
                        { text: "Hydrus & Booru (.txt)", value: "txt" },
                        { text: "Both (.json + .txt)", value: "both" }
                    ]
                    value: storageProcCard.view.bridge ? storageProcCard.view.bridge.sidecarFormat : "json"
                    tooltip: tr("sidecar_format_tip", "JSON is universally readable by Eagle, scripts, and databases. TXT is structured for native tag ingestion in Hydrus Network.")
                    onValuePicked: function(v) { if (storageProcCard.view.bridge) storageProcCard.view.bridge.sidecarFormat = v }
                }
            }

            Row {
                spacing: 8
                Text {
                    text: tr("sidecar_scope_label", "Scope:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#94A3B8"
                    anchors.verticalCenter: parent.verticalCenter
                }
                StyledComboBox {
                    implicitHeight: 28
                    implicitWidth: 170
                    model: [
                        { text: "Per Media File (1:1)", value: "per_file" },
                        { text: "Per Post Folder", value: "per_post" }
                    ]
                    value: storageProcCard.view.bridge ? storageProcCard.view.bridge.sidecarScope : "per_file"
                    tooltip: tr("sidecar_scope_tip", "Per Media File creates companion files with matching names for 1:1 auto-tagging on drag-and-drop. Per Post Folder saves one summary file in the post folder.")
                    onValuePicked: function(v) { if (storageProcCard.view.bridge) storageProcCard.view.bridge.sidecarScope = v }
                }
            }
        }

        StyledCheckBox {
            text: tr("opt_download_pawchive_temp", "Download Pawchive temporary oversized files (t1.pawchive.pw)")
            tooltip: tr("opt_download_pawchive_temp_tip", "Download oversized files that Pawchive keeps in temporary 30-day storage")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.downloadPawchiveTemporaryFiles : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.downloadPawchiveTemporaryFiles = checked
        }

        StyledCheckBox {
            text: tr("opt_desktop_report", "Generate completion report on Desktop (HTML & TXT)")
            tooltip: tr("opt_desktop_report_tip", "Automatically save a visual summary report and failure log to your Desktop upon completion")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.generateDesktopReport : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.generateDesktopReport = checked
        }

        StyledCheckBox {
            text: tr("opt_video_duration_filter_settings", "Filter posts by video length / duration")
            tooltip: tr("opt_video_duration_filter_settings_tip", "Only download posts containing videos within the duration window specified in Filters & Dates")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.videoDurationFilterEnabled : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.videoDurationFilterEnabled = checked
        }

        // Warning when enabled in Settings
        Row {
            visible: storageProcCard.view.bridge ? storageProcCard.view.bridge.videoDurationFilterEnabled : false
            spacing: 8
            leftPadding: 28

            Text {
                text: "⚠️ " + tr("warn_duration_scanning_short", "Probing video duration requires checking media headers over the network, which may increase post scan times.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#FBBF24"
            }
        }

        StyledCheckBox {
            text: tr("opt_skip_retry_404_settings", "Skip HTTP 404 (Not Found) errors during retries")
            tooltip: tr("opt_skip_retry_404_tip", "Exclude HTTP 404 (Not Found) errors from retries and hide them from the retry window")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.skipRetry404 : false
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.skipRetry404 = checked
        }

        StyledCheckBox {
            text: tr("opt_watchlist_apply_global", "Apply current global settings to Watchlist updates")
            tooltip: tr("opt_watchlist_apply_global_tip", "When queueing downloads from the Watchlist, use your active global download settings (naming templates, folder structure, compression, filters) instead of frozen creator snapshots")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.watchlistApplyGlobalSettings : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.watchlistApplyGlobalSettings = checked
        }

        StyledCheckBox {
            text: tr("opt_watchlist_check_startup", "Auto-check Watchlist on application startup")
            tooltip: tr("opt_watchlist_check_startup_tip", "Automatically check tracked artists for newly posted content when Pawchive Downloader starts")
            checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.watchlistCheckOnStartup : true
            onCheckedChanged: if (storageProcCard.view.bridge) storageProcCard.view.bridge.watchlistCheckOnStartup = checked
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            StyledCheckBox {
                id: groupTypeSettingsCheck
                text: tr("opt_group_file_type_settings", "Group downloaded attachments by file type (/Images, /Video, /Archive, ...)")
                tooltip: tr("opt_group_file_type_tip", "Organize attachments into /Images, /Video, /Archive, /Audio, /Other folders")
                checked: storageProcCard.view.bridge ? (storageProcCard.view.bridge.groupFileType !== "none") : false
                onCheckedChanged: {
                    if (storageProcCard.view.bridge) {
                        storageProcCard.view.bridge.groupFileType = checked ? (storageProcCard.view.bridge.groupFileType !== "none" ? storageProcCard.view.bridge.groupFileType : "post") : "none"
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                visible: groupTypeSettingsCheck.checked
                implicitHeight: 28
                implicitWidth: settingsScopeRow.implicitWidth + 18
                radius: 6
                color: settingsScopeMouse.containsMouse ? "#2A364E" : "#182030"
                border.color: settingsScopeMouse.containsMouse ? "#38BDF8" : "#2A364E"
                border.width: 1

                scale: settingsScopeMouse.pressed ? 0.94 : (settingsScopeMouse.containsMouse ? 1.03 : 1.0)
                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.005 } }

                RowLayout {
                    id: settingsScopeRow
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                        text: storageProcCard.view.bridge && storageProcCard.view.bridge.groupFileType === "creator" ? "📁" : "📂"
                        font.pixelSize: 11
                    }

                    Text {
                        text: storageProcCard.view.bridge && storageProcCard.view.bridge.groupFileType === "creator"
                              ? tr("opt_group_scope_creator", "Creator Root (Creator/Type/Post)")
                              : tr("opt_group_scope_post", "Inside Post (Creator/Post/Type)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#38BDF8"
                    }
                }

                MouseArea {
                    id: settingsScopeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (storageProcCard.view.bridge) {
                            storageProcCard.view.bridge.groupFileType = (storageProcCard.view.bridge.groupFileType === "creator" ? "post" : "creator")
                        }
                    }
                }

                ToolTip {
                    visible: settingsScopeMouse.containsMouse
                    delay: 400
                    timeout: 5000
                    text: storageProcCard.view.bridge && storageProcCard.view.bridge.groupFileType === "creator"
                          ? storageProcCard.view.tr("tip_group_scope_creator", "Files grouped by type at creator level: Creator/Images/Post/... (click to switch)")
                          : storageProcCard.view.tr("tip_group_scope_post", "Files grouped inside post folders: Creator/Post/Images/... (click to switch)")
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "📅 " + tr("opt_date_folder_mode_settings", "Sort creator downloads into date folders (Year / Month)")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                color: (storageProcCard.view.bridge && storageProcCard.view.bridge.dateFolderMode !== "none") ? "#F1F5F9" : "#CBD5E1"
                Layout.fillWidth: true
                elide: Text.ElideRight
                Behavior on color { ColorAnimation { duration: 150 } }
            }

            StyledComboBox {
                id: settingsDateFolderCombo
                implicitHeight: 30
                implicitWidth: 210
                model: [
                    { text: tr("date_folder_none", "Off"), value: "none" },
                    { text: tr("date_folder_year", "By Year (2025)"), value: "year" },
                    { text: tr("date_folder_month", "By Month (2025-03)"), value: "month" },
                    { text: tr("date_folder_year_month", "Year → Month (2025/03)"), value: "year_month" }
                ]
                value: storageProcCard.view.bridge ? storageProcCard.view.bridge.dateFolderMode : "none"
                tooltip: tr("opt_date_folder_mode_tip", "Organize a creator's posts into date folders based on publication date:\n• By Year: Creator/2025/...\n• By Month: Creator/2025-03/...\n• Year → Month: Creator/2025/03 - March/...\nPosts without a date go into Unknown Date.")
                onValuePicked: function(v) { if (storageProcCard.view.bridge) storageProcCard.view.bridge.dateFolderMode = v }
            }
        }

        // Download Archive Database Sub-Card (gallery-dl style)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: archiveCol.implicitHeight + 22
            radius: 8
            color: "#141A26"
            border.color: archiveBoxHover.hovered ? "#38BDF8" : "#233147"
            border.width: 1

            HoverHandler { id: archiveBoxHover }

            transform: Translate {
                y: archiveBoxHover.hovered ? -1.5 : 0
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                }
            }

            Behavior on border.color { ColorAnimation { duration: 160 } }

            ColumnLayout {
                id: archiveCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "🗃️"
                        font.pixelSize: 14
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: tr("opt_download_archive", "Download Archive Database")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#F1F5F9"
                        Layout.fillWidth: true
                    }

                    Rectangle {
                        implicitHeight: 18
                        implicitWidth: galleryDlBadgeText.implicitWidth + 10
                        radius: 9
                        color: "#0F2942"
                        border.color: "#0284C7"
                        border.width: 1

                        Text {
                            id: galleryDlBadgeText
                            anchors.centerIn: parent
                            text: "gallery-dl style"
                            font.pixelSize: 9
                            font.weight: 600
                            color: "#38BDF8"
                        }
                    }

                    StyledSwitch {
                        checked: storageProcCard.view.bridge ? storageProcCard.view.bridge.enableDownloadArchive : false
                        accentColor: "#38BDF8"
                        onToggled: function(isChecked) {
                            if (storageProcCard.view.bridge) storageProcCard.view.bridge.enableDownloadArchive = isChecked
                        }
                    }
                }

                Text {
                    text: tr("desc_download_archive", "Records downloaded files in an isolated local database. Subsequent downloads will skip files even if they have been unzipped, moved to another drive, or deleted locally.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // Dynamic drawer revealed when enabled
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: storageProcCard.view.bridge ? storageProcCard.view.bridge.enableDownloadArchive : false

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warningRow.implicitHeight + 12
                        radius: 6
                        color: "#2A1F0D"
                        border.color: "#B45309"
                        border.width: 1

                        RowLayout {
                            id: warningRow
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 6

                            Text {
                                text: "⚠️"
                                font.pixelSize: 11
                            }

                            Text {
                                text: tr("tip_download_archive_warning", "Note: Files deleted from disk will not re-download while this is active unless you click Clear Archive.")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#FDE68A"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle {
                            implicitHeight: 28
                            implicitWidth: recordCountText.implicitWidth + 16
                            radius: 14
                            color: "#1E293B"
                            border.color: "#334155"
                            border.width: 1

                            Text {
                                id: recordCountText
                                anchors.centerIn: parent
                                text: tr("badge_archive_records", "Archived files: ") + (storageProcCard.view.bridge ? storageProcCard.view.bridge.archiveRecordCount : 0)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#CBD5E1"
                            }
                        }

                        Item { Layout.fillWidth: true }

                        StyledButton {
                            text: tr("btn_open_archive_tab", "Open Archive Tab ➔")
                            iconText: "🗃️"
                            variant: "outline"
                            implicitHeight: 28
                            onClicked: {
                                if (typeof appWindow !== "undefined" && appWindow) {
                                    appWindow.currentTab = 9
                                }
                            }
                        }

                        StyledButton {
                            text: tr("btn_clear_archive", "Clear Archive")
                            iconText: "🗑️"
                            variant: "danger"
                            implicitHeight: 28
                            onClicked: {
                                if (storageProcCard.view.bridge) {
                                    storageProcCard.view.bridge.clearDownloadArchiveAsync("settings-clear-archive")
                                }
                            }
                        }
                    }
                }
            }
        }

        SettingsFilenameTemplateCard {
            view: storageProcCard.view
        }
    }
}
