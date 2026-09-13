import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

SmoothFlickable {
    id: root

    property var bridge: null

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    contentWidth: width
    contentHeight: contentCol.implicitHeight + 16

    ColumnLayout {
        id: contentCol
        width: root.width - (root.verticalScrollBar && root.verticalScrollBar.visible ? 10 : 0)
        spacing: 12

        // Section 1: Download Location
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_destination", "Download Destination")
            iconText: "📁"

            RowLayout {
                width: parent.width
                spacing: 8

                StyledTextField {
                    id: dirInput
                    Layout.fillWidth: true
                    text: root.bridge ? root.bridge.downloadDir : ""
                    leadingIcon: "💾"
                    showClearButton: false
                    onTextChanged: {
                        if (root.bridge && root.bridge.downloadDir !== text) {
                            root.bridge.downloadDir = text
                        }
                    }
                }

                StyledButton {
                    text: root.tr("btn_browse", "Browse...")
                    iconText: "📂"
                    variant: "outline"
                    tooltip: root.tr("btn_browse_tip", "Select destination folder for downloads")
                    onClicked: {
                        if (root.bridge) root.bridge.selectDownloadDirectory()
                    }
                }

                StyledButton {
                    text: root.tr("btn_open", "Open")
                    iconText: "↗"
                    variant: "ghost"
                    implicitWidth: 70
                    tooltip: root.tr("btn_open_tip", "Open current downloads directory in Windows File Explorer")
                    onClicked: {
                        if (root.bridge) root.bridge.openDownloadFolder()
                    }
                }
            }
        }

        // Section 2: Character & Keyword Filters
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_filters", "Filters & Keyword Rules")
            iconText: "🎯"

            ColumnLayout {
                width: parent.width
                spacing: 10

                // Filter by Characters
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            text: root.tr("label_filter_characters", "Filter by Character(s) (comma-separated):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledTextField {
                            Layout.fillWidth: true
                            placeholderText: root.tr("placeholder_characters", "e.g., Tifa, Aerith, (Cloud, Zack)")
                            text: root.bridge ? root.bridge.filterCharacters : ""
                            onTextChanged: {
                                if (root.bridge && root.bridge.filterCharacters !== text) {
                                    root.bridge.filterCharacters = text
                                }
                            }
                        }
                    }

                    // Scope selector
                    ColumnLayout {
                        spacing: 4
                        Text {
                            text: root.tr("label_scope", "Scope:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledButton {
                            implicitWidth: 100
                            text: {
                                if (!root.bridge) return root.tr("scope_filter_title", "Filter: Title")
                                var s = root.bridge.characterScope
                                if (s === "content") return root.tr("scope_filter_content", "Filter: Content")
                                if (s === "both") return root.tr("scope_filter_both", "Filter: Both")
                                return root.tr("scope_filter_title", "Filter: Title")
                            }
                            variant: "outline"
                            tooltip: root.tr("tooltip_scope_character", "Switch character filtering scope (Title, Content, or Both)")
                            onClicked: {
                                if (!root.bridge) return
                                if (root.bridge.characterScope === "title") root.bridge.characterScope = "content"
                                else if (root.bridge.characterScope === "content") root.bridge.characterScope = "both"
                                else root.bridge.characterScope = "title"
                            }
                        }
                    }
                }

                // Skip words & Remove words row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    // Skip words
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 3
                        spacing: 4

                        Text {
                            text: root.tr("label_skip_words", "🚫 Skip with words (comma-separated):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            StyledTextField {
                                Layout.fillWidth: true
                                placeholderText: root.tr("placeholder_skip_words", "e.g., WM, WIP, sketch, preview")
                                text: root.bridge ? root.bridge.skipWords : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.skipWords !== text) {
                                        root.bridge.skipWords = text
                                    }
                                }
                            }

                            StyledButton {
                                implicitWidth: 100
                                text: {
                                    if (!root.bridge) return root.tr("scope_skip_posts", "Scope: Posts")
                                    return (root.bridge.skipScope === "files")
                                        ? root.tr("scope_skip_files", "Scope: Files")
                                        : root.tr("scope_skip_posts", "Scope: Posts")
                                }
                                variant: "outline"
                                tooltip: root.tr("tooltip_skip_scope", "Switch skip filter scope between Post Titles and Filenames")
                                onClicked: {
                                    if (!root.bridge) return
                                    root.bridge.skipScope = (root.bridge.skipScope === "posts") ? "files" : "posts"
                                }
                            }
                        }
                    }

                    // Remove words
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 2
                        spacing: 4

                        Text {
                            text: root.tr("label_remove_words", "✂️ Remove words from name:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        StyledTextField {
                            Layout.fillWidth: true
                            placeholderText: root.tr("placeholder_remove_words", "e.g., patreon, HD, [sample]")
                            text: root.bridge ? root.bridge.removeWords : ""
                            onTextChanged: {
                                if (root.bridge && root.bridge.removeWords !== text) {
                                    root.bridge.removeWords = text
                                }
                            }
                        }
                    }
                }
            }
        }


        // Section 3: File Types & Content Filters
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_file_types", "Filter Files & Content Mode")
            iconText: "🗂️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                // Media type filter pills (Single-select category)
                Flow {
                    Layout.fillWidth: true
                    spacing: 6

                    FilterCheckbox {
                        label: root.tr("filter_all_files", "All Files")
                        iconText: "📁"
                        tooltip: root.tr("filter_all_files_tip", "Download all attachments and media files")
                        checked: root.bridge ? root.bridge.filterType === "all" : true
                        onClicked: if (root.bridge) root.bridge.filterType = "all"
                    }

                    FilterCheckbox {
                        label: root.tr("filter_images", "Images/GIFs")
                        iconText: "🖼️"
                        tooltip: root.tr("filter_images_tip", "Download image formats (PNG, JPG, GIF, WebP, BMP)")
                        checked: root.bridge ? root.bridge.filterType === "images" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "images"
                    }

                    FilterCheckbox {
                        label: root.tr("filter_videos", "Videos")
                        iconText: "🎬"
                        tooltip: root.tr("filter_videos_tip", "Download video formats (MP4, MKV, WebM, MOV, M4V)")
                        checked: root.bridge ? root.bridge.filterType === "videos" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "videos"
                    }

                    FilterCheckbox {
                        label: root.tr("filter_archives", "Archives")
                        iconText: "📦"
                        tooltip: root.tr("filter_archives_tip", "Download compressed archive packages (ZIP, RAR, 7Z, TAR)")
                        checked: root.bridge ? root.bridge.filterType === "archives" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "archives"
                    }

                    FilterCheckbox {
                        label: root.tr("filter_audio", "Audio")
                        iconText: "🎵"
                        tooltip: root.tr("filter_audio_tip", "Download audio formats (MP3, FLAC, WAV, M4A, OGG)")
                        checked: root.bridge ? root.bridge.filterType === "audio" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "audio"
                    }

                    FilterCheckbox {
                        label: root.tr("filter_links_only", "Links Only")
                        iconText: "🔗"
                        tooltip: root.tr("filter_links_only_tip", "Scan post descriptions & comments for external cloud links (Mega.nz, Google Drive, Dropbox, Pixeldrain, etc.) — no media files are downloaded. Use 'Export Links' in Queue tab to save results.")
                        checked: root.bridge ? root.bridge.filterType === "links" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "links"
                    }
                }

                // Checkbox & Modifier options
                Flow {
                    Layout.fillWidth: true
                    spacing: 12

                    FilterCheckbox {
                        label: root.tr("opt_favorite_mode", "Favorite Mode")
                        iconText: "⭐"
                        activeColor: "#FBBF24"
                        tooltip: root.tr("opt_favorite_mode_tip", "Only download posts favorited/bookmarked by the creator")
                        checked: root.bridge ? root.bridge.favoriteMode : false
                        onClicked: if (root.bridge) root.bridge.favoriteMode = !root.bridge.favoriteMode
                    }

                    StyledCheckBox {
                        text: root.tr("opt_skip_archives", "Skip Archives")
                        tooltip: root.tr("opt_skip_archives_tip", "Skip all archive files (.zip, .rar, .7z) regardless of active category")
                        checked: root.bridge ? root.bridge.skipArchives : false
                        onCheckedChanged: if (root.bridge) root.bridge.skipArchives = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_thumbnails_only", "Download thumbnails only")
                        tooltip: root.tr("opt_thumbnails_only_tip", "Download lightweight preview thumbnails instead of full original files")
                        checked: root.bridge ? root.bridge.downloadThumbnailsOnly : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadThumbnailsOnly = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_scan_content_images", "Scan content for images")
                        tooltip: root.tr("opt_scan_content_images_tip", "Scan HTML post descriptions for embedded inline artwork")
                        checked: root.bridge ? root.bridge.scanContentImages : true
                        onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_compress_webp", "Compress to WebP")
                        tooltip: root.tr("opt_compress_webp_tip", "Convert downloaded PNG and JPG images to compressed WebP format")
                        checked: root.bridge ? root.bridge.compressWebp : false
                        onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_download_embeds", "Download Embedded Media (yt-dlp)")
                        tooltip: root.tr("opt_download_embeds_tip", "Download embedded video players (Vimeo, YouTube, Streamable, RedGifs, etc.) via standalone yt-dlp")
                        checked: root.bridge ? root.bridge.downloadEmbeds : true
                        onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_keep_duplicates", "Keep Duplicates")
                        tooltip: root.tr("opt_keep_duplicates_tip", "Re-download files even if identical files already exist in destination")
                        checked: root.bridge ? root.bridge.keepDuplicates : false
                        onCheckedChanged: if (root.bridge) root.bridge.keepDuplicates = checked
                    }
                }
            }
        }

        // Section 4: Advanced Settings
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_advanced", "Advanced Structure & Performance")
            iconText: "⚙️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Flow {
                    Layout.fillWidth: true
                    spacing: 14

                    StyledCheckBox {
                        text: root.tr("opt_subfolder_per_post", "Subfolder per post")
                        tooltip: root.tr("opt_subfolder_per_post_tip", "Organize downloads into subfolders named after each post")
                        checked: root.bridge ? root.bridge.subfolderPerPost : true
                        onCheckedChanged: if (root.bridge) root.bridge.subfolderPerPost = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_date_prefix", "Date Prefix")
                        tooltip: root.tr("opt_date_prefix_tip", "Prefix subfolder names with the post publication date [YYYY-MM-DD]")
                        checked: root.bridge ? root.bridge.datePrefix : true
                        onCheckedChanged: if (root.bridge) root.bridge.datePrefix = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_file_index_prefix", "Index Prefix (001_...)")
                        tooltip: root.tr("opt_file_index_prefix_tip", "Prefix downloaded filenames with sequential index numbers (001_, 002_, ...) so they can be browsed in order without relying on time sorting")
                        checked: root.bridge ? root.bridge.fileIndexPrefix : false
                        onCheckedChanged: if (root.bridge) root.bridge.fileIndexPrefix = checked
                    }

                    RowLayout {
                        spacing: 6
                        StyledCheckBox {
                            text: root.tr("opt_tag_folder_mode", "Sort by Tag Folder")
                            tooltip: root.tr("opt_tag_folder_mode_tip", "(Pawchive & cum.st only) Groups downloaded files into subfolders named after the post's primary tag")
                            checked: root.bridge ? root.bridge.tagFolderMode : false
                            onCheckedChanged: if (root.bridge) root.bridge.tagFolderMode = checked
                        }

                        Rectangle {
                            readonly property string curUrl: root.bridge ? (root.bridge.currentUrl || "").toLowerCase() : ""
                            readonly property bool isNonTagDomain: curUrl.length > 0 && curUrl.indexOf("pawchive.pw") === -1 && curUrl.indexOf("cum.st") === -1
                            visible: isNonTagDomain
                            implicitHeight: 20
                            implicitWidth: tagWarnText.implicitWidth + 10
                            radius: 4
                            color: "#1E1B18"
                            border.color: "#854D0E"
                            border.width: 1

                            Text {
                                id: tagWarnText
                                anchors.centerIn: parent
                                text: "⚠ Pawchive/cum.st only"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#FBBF24"
                            }
                        }
                    }

                    StyledCheckBox {
                        text: root.tr("opt_separate_known", "Separate folders by Known.txt")
                        tooltip: root.tr("opt_separate_known_tip", "Sort files into subfolders corresponding to matched characters/series from Known.txt")
                        checked: root.bridge ? root.bridge.separateFoldersByKnown : false
                        onCheckedChanged: if (root.bridge) root.bridge.separateFoldersByKnown = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_download_revisions", "Download Revisions")
                        tooltip: root.tr("opt_download_revisions_tip", "Download older superseded revisions of edited posts")
                        checked: root.bridge ? root.bridge.downloadRevisions : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadRevisions = checked
                    }

                    StyledCheckBox {
                        id: adaptiveCheck
                        text: root.tr("opt_adaptive_threading", "Adaptive Threading")
                        tooltip: (root.bridge && root.bridge.threadsLocked)
                                 ? root.tr("opt_adaptive_disabled_tip", "Adaptive Threading is disabled because Thread Lock is active")
                                 : root.tr("opt_adaptive_threading_tip", "Automatically scale worker thread count based on network conditions and 429 rate limits")
                        enabled: root.bridge ? !root.bridge.threadsLocked : true
                        opacity: enabled ? 1.0 : 0.38
                        Behavior on opacity { NumberAnimation { duration: 180 } }
                        checked: root.bridge ? root.bridge.adaptiveThreading : false
                        onCheckedChanged: if (root.bridge && enabled) root.bridge.adaptiveThreading = checked
                    }

                    StyledCheckBox {
                        text: root.tr("opt_manga_mode", "Manga Mode (Oldest First)")
                        tooltip: root.tr("opt_manga_mode_tip", "Sort posts chronologically (oldest first) so chapters and pages download in reading order")
                        checked: root.bridge ? root.bridge.mangaMode : false
                        onCheckedChanged: if (root.bridge) root.bridge.mangaMode = checked
                    }
                }

                // Concurrency & Threads with CPU Detection & Thread Lock
                RowLayout {
                    spacing: 10
                    // Dim the slider when Adaptive Threading is on
                    opacity: (root.bridge && root.bridge.adaptiveThreading) ? 0.38 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    Text {
                        text: root.tr("label_concurrent_workers", "Concurrent Workers:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }

                    Slider {
                        id: threadSlider
                        from: 1
                        to: root.bridge ? root.bridge.maxCpuThreads : 24
                        stepSize: 1
                        value: root.bridge ? root.bridge.threadsCount : 4
                        implicitWidth: 180
                        implicitHeight: 32
                        // Disable interaction when Adaptive Threading is managing concurrency
                        enabled: root.bridge ? !root.bridge.adaptiveThreading : true
                        onMoved: if (root.bridge) root.bridge.threadsCount = Math.round(value)

                        background: Item {
                            x: threadSlider.leftPadding
                            y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                            width:  threadSlider.availableWidth
                            implicitHeight: 6
                            height: 6

                            // Empty track
                            Rectangle {
                                width: parent.width; height: parent.height
                                radius: 3
                                color: "#101827"
                                border.color: "#1E2D42"
                                border.width: 1
                            }
                            // Filled portion
                            Rectangle {
                                width: Math.max(6, threadSlider.visualPosition * parent.width)
                                height: parent.height
                                radius: 3
                                color: "#38BDF8"
                                opacity: threadSlider.enabled ? 1.0 : 0.35
                            }
                        }

                        handle: Item {
                            x: threadSlider.leftPadding + threadSlider.visualPosition * (threadSlider.availableWidth - width)
                            y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                            width: 28; height: 28

                            // Outer glow ring — appears on hover / press
                            Rectangle {
                                anchors.centerIn: parent
                                width: 28; height: 28; radius: 14
                                color: "transparent"
                                border.color: "#38BDF8"
                                border.width: 1
                                opacity: (threadSlider.pressed || threadSlider.hovered) ? 0.5 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 160 } }
                            }
                            // Core circle
                            Rectangle {
                                anchors.centerIn: parent
                                width: 16; height: 16; radius: 8
                                color: "#38BDF8"
                                opacity: threadSlider.enabled ? 1.0 : 0.3
                                scale: threadSlider.pressed ? 0.78 : 1.0
                                Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutBack } }
                            }
                        }
                    }

                    // Value chip
                    Rectangle {
                        implicitWidth: workerVal.implicitWidth + 18
                        height: 24; radius: 12
                        color: "#0C1828"
                        border.color: (root.bridge && root.bridge.threadsLocked) ? "#7F1D1D" : "#164E63"
                        border.width: 1
                        Text {
                            id: workerVal
                            anchors.centerIn: parent
                            text: root.bridge && root.bridge.adaptiveThreading
                                  ? root.bridge.threadsCount.toString()
                                  : Math.round(threadSlider.value).toString()
                            font.family: "Segoe UI, sans-serif"
                            font.bold: true
                            font.pixelSize: 11
                            color: (root.bridge && root.bridge.threadsLocked) ? "#FCA5A5" : "#7DD3FA"
                        }
                    }

                    // Thread Lock Button (toggles sweetspot thread lock)
                    Rectangle {
                        id: lockBtn
                        height: 24
                        radius: 5
                        implicitWidth: lockRow.implicitWidth + 16
                        color: (root.bridge && root.bridge.threadsLocked)
                               ? (lockMouse.containsMouse ? "#3A1A1C" : "#2D1517")
                               : (lockMouse.containsMouse ? "#1E293B" : "#161E2E")
                        border.color: (root.bridge && root.bridge.threadsLocked)
                                      ? (lockMouse.containsMouse ? "#F87171" : "#EF4444")
                                      : (lockMouse.containsMouse ? "#475569" : "#242A38")
                        border.width: 1
                        scale: lockMouse.pressed ? 0.95 : (lockMouse.containsMouse ? 1.03 : 1.0)

                        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutBack } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        RowLayout {
                            id: lockRow
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                text: (root.bridge && root.bridge.threadsLocked) ? "🔒" : "🔓"
                                font.pixelSize: 11
                            }

                            Text {
                                text: (root.bridge && root.bridge.threadsLocked)
                                      ? root.tr("btn_thread_locked", "Locked")
                                      : root.tr("btn_thread_lock", "Lock")
                                font.family: "Segoe UI, sans-serif"
                                font.bold: true
                                font.pixelSize: 11
                                color: (root.bridge && root.bridge.threadsLocked) ? "#F87171" : "#94A3B8"
                            }
                        }

                        MouseArea {
                            id: lockMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) {
                                    root.bridge.threadsLocked = !root.bridge.threadsLocked
                                }
                            }
                        }

                        ToolTip {
                            id: lockToolTip
                            visible: lockMouse.containsMouse
                            delay: 400
                            timeout: 5000
                            text: (root.bridge && root.bridge.threadsLocked)
                                  ? (root.tr("tip_thread_locked_active", "Thread Lock Active: Worker concurrency is locked. Adaptive scaling is disabled and HTTP 429 cooldown is 30s."))
                                  : (root.tr("tip_thread_lock", "Lock Thread Sweetspot: Lock current concurrency. Disables adaptive scaling and prevents rate limits from altering your thread count."))
                            contentItem: Text {
                                text: lockToolTip.text
                                font.family: "Segoe UI, Inter, sans-serif"
                                font.pixelSize: 11
                                color: "#F1F5F9"
                            }
                            background: Rectangle {
                                color: "#181B24"
                                border.color: (root.bridge && root.bridge.threadsLocked) ? "#EF4444" : "#38BDF8"
                                border.width: 1
                                radius: 6
                            }
                        }
                    }

                    Rectangle {
                        height: 22
                        radius: 4
                        color: "#161E2E"
                        border.color: "#1E293B"
                        border.width: 1
                        implicitWidth: cpuBadgeText.implicitWidth + 12

                        Text {
                            id: cpuBadgeText
                            anchors.centerIn: parent
                            text: (root.bridge && root.bridge.threadsLocked)
                                  ? ("🔒 " + root.tr("badge_locked", "Locked:") + " " + root.bridge.threadsCount + "T")
                                  : (root.bridge && root.bridge.adaptiveThreading
                                     ? root.tr("badge_adaptive", "⚡ Adaptive")
                                     : (root.bridge ? (root.tr("badge_cpu_cores", "⚡ CPU Cores:") + " " + root.bridge.maxCpuThreads) : root.tr("badge_cpu_auto", "⚡ CPU Auto")))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: (root.bridge && root.bridge.threadsLocked)
                                   ? "#F87171"
                                   : (root.bridge && root.bridge.adaptiveThreading ? "#FBBF24" : "#38BDF8")
                        }
                    }
                }

                // Post-Download Delay per Thread (Anti-429 Rate-Limit Mitigation)
                RowLayout {
                    spacing: 10

                    Text {
                        text: root.tr("label_thread_delay", "⏱️ Thread Delay After Download:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }

                    Slider {
                        id: delaySlider
                        from: 0.0
                        to: 10.0
                        stepSize: 0.5
                        value: root.bridge ? root.bridge.downloadDelay : 2.0
                        implicitWidth: 180
                        implicitHeight: 32
                        onMoved: if (root.bridge) root.bridge.downloadDelay = value

                        background: Item {
                            x: delaySlider.leftPadding
                            y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                            width: delaySlider.availableWidth
                            implicitHeight: 6
                            height: 6

                            // Empty track
                            Rectangle {
                                width: parent.width; height: parent.height
                                radius: 3
                                color: "#100D1E"
                                border.color: "#231A40"
                                border.width: 1
                            }
                            // Filled portion
                            Rectangle {
                                width: Math.max(6, delaySlider.visualPosition * parent.width)
                                height: parent.height
                                radius: 3
                                color: "#A78BFA"
                            }
                        }

                        handle: Item {
                            x: delaySlider.leftPadding + delaySlider.visualPosition * (delaySlider.availableWidth - width)
                            y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                            width: 28; height: 28

                            // Outer glow ring
                            Rectangle {
                                anchors.centerIn: parent
                                width: 28; height: 28; radius: 14
                                color: "transparent"
                                border.color: "#A78BFA"
                                border.width: 1
                                opacity: (delaySlider.pressed || delaySlider.hovered) ? 0.5 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 160 } }
                            }
                            // Core circle
                            Rectangle {
                                anchors.centerIn: parent
                                width: 16; height: 16; radius: 8
                                color: "#A78BFA"
                                scale: delaySlider.pressed ? 0.78 : 1.0
                                Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutBack } }
                            }
                        }
                    }

                    // Value chip
                    Rectangle {
                        implicitWidth: delayVal.implicitWidth + 18
                        height: 24; radius: 12
                        color: "#0D0A1E"
                        border.color: "#3B2A6B"
                        border.width: 1
                        Text {
                            id: delayVal
                            anchors.centerIn: parent
                            text: (root.bridge ? root.bridge.downloadDelay.toFixed(1) : "2.0") + "s"
                            font.family: "Segoe UI, sans-serif"
                            font.bold: true
                            font.pixelSize: 11
                            color: "#C4B5FD"
                        }
                    }

                    Text {
                        text: root.tr("label_anti_429", "(anti-429 cooldown)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }
                }


                // Post-completion toggles
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    // ── Save post_info.txt toggle ──────────────────────────────
                    Rectangle {
                        id: saveMetaToggle
                        property bool active: root.bridge ? root.bridge.savePostMetadata : true
                        implicitWidth: 230
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#1E1B35" : "#141922"
                        border.color: active ? "#7C3AED" : "#1E2433"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        // Left accent bar
                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            // Pill switch track
                            Rectangle {
                                id: metaTrack
                                width: 32; height: 18; radius: 9
                                color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    id: metaThumb
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: saveMetaToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                                }
                            }

                            ColumnLayout {
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    text: root.tr("toggle_save_post_info", "Save post_info.txt")
                                    color: saveMetaToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    text: root.tr("toggle_save_post_info_sub", "caption, tags & comments")
                                    color: saveMetaToggle.active ? "#7C3AED" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.savePostMetadata = !saveMetaToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onSavePostMetadataChanged() {
                                saveMetaToggle.active = root.bridge.savePostMetadata
                            }
                        }
                    }

                    // ── Open folder when done toggle ───────────────────────────
                    Rectangle {
                        id: openFolderToggle
                        property bool active: root.bridge ? root.bridge.openFolderOnComplete : false
                        implicitWidth: 210
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#0D1F1A" : "#141922"
                        border.color: active ? "#10B981" : "#1E2433"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: openFolderToggle.active ? "#10B981" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            Rectangle {
                                id: folderTrack
                                width: 32; height: 18; radius: 9
                                color: openFolderToggle.active ? "#10B981" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: openFolderToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                                }
                            }

                            ColumnLayout {
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    text: root.tr("toggle_open_folder", "Open folder when done")
                                    color: openFolderToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    text: root.tr("toggle_open_folder_sub", "auto-opens on completion")
                                    color: openFolderToggle.active ? "#10B981" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.openFolderOnComplete = !openFolderToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onOpenFolderOnCompleteChanged() {
                                openFolderToggle.active = root.bridge.openFolderOnComplete
                            }
                        }
                    }

                    // ── Desktop report toggle ───────────────────────────────
                    Rectangle {
                        id: desktopReportToggle
                        property bool active: root.bridge ? root.bridge.saveDesktopReport : false
                        implicitWidth: 210
                        implicitHeight: 36
                        radius: 10
                        color: active ? "#0C202F" : "#141922"
                        border.color: active ? "#0284C7" : "#1E2433"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 3
                            height: parent.height - 10
                            radius: 2
                            anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                            color: desktopReportToggle.active ? "#38BDF8" : "#2D3748"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 8

                            Rectangle {
                                id: reportTrack
                                width: 32; height: 18; radius: 9
                                color: desktopReportToggle.active ? "#0284C7" : "#2D3748"
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    width: 12; height: 12; radius: 6
                                    color: "white"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: desktopReportToggle.active ? parent.width - width - 3 : 3
                                    Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                                }
                            }

                            ColumnLayout {
                                spacing: 1
                                Layout.fillWidth: true
                                Text {
                                    text: root.tr("toggle_desktop_report", "Desktop report")
                                    color: desktopReportToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    text: root.tr("toggle_desktop_report_sub", "summary log on desktop")
                                    color: desktopReportToggle.active ? "#38BDF8" : "#374151"
                                    font.pixelSize: 9
                                    font.family: "Segoe UI, sans-serif"
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.bridge) root.bridge.saveDesktopReport = !desktopReportToggle.active
                            }
                        }

                        Connections {
                            target: root.bridge
                            function onSaveDesktopReportChanged() {
                                desktopReportToggle.active = root.bridge.saveDesktopReport
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }

        // Batch Queue Section
        CardSection {
            Layout.fillWidth: true
            title: root.tr("section_batch_queue", "Batch Download Queue")
            iconText: "📋"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: root.tr("desc_batch_queue", "Paste multiple creator / album URLs below, one per line. Each URL uses its own folder inside the download destination.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                ScrollView {
                    Layout.fillWidth: true
                    implicitHeight: 120
                    clip: true

                    TextArea {
                        id: batchInput
                        placeholderText: "https://kemono.su/patreon/user/12345\nhttps://coomer.su/onlyfans/user/67890\nhttps://cum.st/creators/onlyfans/32696630\nhttps://bunkr.cr/a/example"
                        background: Rectangle {
                            color: "#141922"
                            border.color: batchInput.activeFocus ? "#7C3AED" : "#1E2433"
                            border.width: 1
                            radius: 6
                        }
                        color: "#E2E8F0"
                        font.family: "Consolas, monospace"
                        font.pixelSize: 11
                        wrapMode: TextArea.Wrap
                        padding: 10
                    }
                }

                RowLayout {
                    spacing: 8

                    StyledButton {
                        text: root.tr("btn_add_all_queue", "Add All to Queue")
                        iconText: "▶"
                        variant: "primary"
                        tooltip: root.tr("btn_add_all_queue_tip", "Parse and start downloading all URLs above")
                        enabled: batchInput.text.trim().length > 0 && root.bridge && !root.bridge.isDownloading
                        onClicked: {
                            if (root.bridge) {
                                var count = root.bridge.batchLoadUrls(batchInput.text)
                                if (count > 0) {
                                    batchInput.text = ""
                                }
                            }
                        }
                    }

                    StyledButton {
                        text: root.tr("btn_clear", "Clear")
                        iconText: "✕"
                        variant: "ghost"
                        onClicked: batchInput.text = ""
                    }

                    Text {
                        id: batchCountLabel
                        text: batchInput.text.trim().length > 0 ?
                              (batchInput.text.split("\n").filter(function(l){ return l.trim().startsWith("http") }).length + " " + root.tr("label_urls_detected", "URL(s) detected")) : ""
                        color: "#64748B"
                        font.pixelSize: 11
                        font.family: "Segoe UI, sans-serif"
                    }
                }
            }
        }


    }

    // Modal popup dialog for selecting failed downloads to retry
    RetryModal {
        id: retryModal
        bridge: root.bridge
    }
}

