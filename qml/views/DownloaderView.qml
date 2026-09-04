import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

ScrollView {
    id: root

    property var bridge: null

    contentWidth: availableWidth
    contentHeight: contentCol.implicitHeight + 16
    clip: true

    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    ColumnLayout {
        id: contentCol
        width: root.availableWidth
        spacing: 12

        // Section 1: Download Location
        CardSection {
            Layout.fillWidth: true
            title: "Download Destination"
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
                    text: "Browse..."
                    iconText: "📂"
                    variant: "outline"
                    tooltip: "Select destination folder for downloads"
                    onClicked: {
                        if (root.bridge) root.bridge.selectDownloadDirectory()
                    }
                }

                StyledButton {
                    text: "Open"
                    iconText: "↗"
                    variant: "ghost"
                    implicitWidth: 70
                    tooltip: "Open current downloads directory in Windows File Explorer"
                    onClicked: {
                        if (root.bridge) root.bridge.openDownloadFolder()
                    }
                }
            }
        }

        // Section 2: Character & Keyword Filters
        CardSection {
            Layout.fillWidth: true
            title: "Filters & Keyword Rules"
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
                            text: "Filter by Character(s) (comma-separated):"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledTextField {
                            Layout.fillWidth: true
                            placeholderText: "e.g., Tifa, Aerith, (Cloud, Zack)"
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
                            text: "Scope:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                        StyledButton {
                            implicitWidth: 100
                            text: root.bridge ? ("Filter: " + (root.bridge.characterScope.charAt(0).toUpperCase() + root.bridge.characterScope.slice(1))) : "Filter: Title"
                            variant: "outline"
                            tooltip: "Switch character filtering scope (Title, Content, or Both)"
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
                            text: "🚫 Skip with words (comma-separated):"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            StyledTextField {
                                Layout.fillWidth: true
                                placeholderText: "e.g., WM, WIP, sketch, preview"
                                text: root.bridge ? root.bridge.skipWords : ""
                                onTextChanged: {
                                    if (root.bridge && root.bridge.skipWords !== text) {
                                        root.bridge.skipWords = text
                                    }
                                }
                            }

                            StyledButton {
                                implicitWidth: 100
                                text: root.bridge ? ("Scope: " + (root.bridge.skipScope.charAt(0).toUpperCase() + root.bridge.skipScope.slice(1))) : "Scope: Posts"
                                variant: "outline"
                                tooltip: "Switch skip filter scope between Post Titles and Filenames"
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
                            text: "✂️ Remove words from name:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        StyledTextField {
                            Layout.fillWidth: true
                            placeholderText: "e.g., patreon, HD, [sample]"
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
            title: "Filter Files & Content Mode"
            iconText: "🗂️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                // Media type filter pills (Single-select category)
                Flow {
                    Layout.fillWidth: true
                    spacing: 6

                    FilterCheckbox {
                        label: "All Files"
                        iconText: "📁"
                        tooltip: "Download all attachments and media files"
                        checked: root.bridge ? root.bridge.filterType === "all" : true
                        onClicked: if (root.bridge) root.bridge.filterType = "all"
                    }

                    FilterCheckbox {
                        label: "Images/GIFs"
                        iconText: "🖼️"
                        tooltip: "Download image formats (PNG, JPG, GIF, WebP, BMP)"
                        checked: root.bridge ? root.bridge.filterType === "images" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "images"
                    }

                    FilterCheckbox {
                        label: "Videos"
                        iconText: "🎬"
                        tooltip: "Download video formats (MP4, MKV, WebM, MOV, M4V)"
                        checked: root.bridge ? root.bridge.filterType === "videos" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "videos"
                    }

                    FilterCheckbox {
                        label: "Archives"
                        iconText: "📦"
                        tooltip: "Download compressed archive packages (ZIP, RAR, 7Z, TAR)"
                        checked: root.bridge ? root.bridge.filterType === "archives" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "archives"
                    }

                    FilterCheckbox {
                        label: "Audio"
                        iconText: "🎵"
                        tooltip: "Download audio formats (MP3, FLAC, WAV, M4A, OGG)"
                        checked: root.bridge ? root.bridge.filterType === "audio" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "audio"
                    }

                    FilterCheckbox {
                        label: "Links Only"
                        iconText: "🔗"
                        tooltip: "Scan post descriptions & comments for external cloud links (Mega.nz, Google Drive, Dropbox, Pixeldrain, etc.) — no media files are downloaded. Use 'Export Links' in Queue tab to save results."
                        checked: root.bridge ? root.bridge.filterType === "links" : false
                        onClicked: if (root.bridge) root.bridge.filterType = "links"
                    }
                }

                // Checkbox & Modifier options
                Flow {
                    Layout.fillWidth: true
                    spacing: 12

                    FilterCheckbox {
                        label: "Favorite Mode"
                        iconText: "⭐"
                        activeColor: "#FBBF24"
                        tooltip: "Only download posts favorited/bookmarked by the creator"
                        checked: root.bridge ? root.bridge.favoriteMode : false
                        onClicked: if (root.bridge) root.bridge.favoriteMode = !root.bridge.favoriteMode
                    }

                    StyledCheckBox {
                        text: "Skip Archives"
                        tooltip: "Skip all archive files (.zip, .rar, .7z) regardless of active category"
                        checked: root.bridge ? root.bridge.skipArchives : false
                        onCheckedChanged: if (root.bridge) root.bridge.skipArchives = checked
                    }

                    StyledCheckBox {
                        text: "Download thumbnails only"
                        tooltip: "Download lightweight preview thumbnails instead of full original files"
                        checked: root.bridge ? root.bridge.downloadThumbnailsOnly : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadThumbnailsOnly = checked
                    }

                    StyledCheckBox {
                        text: "Scan content for images"
                        tooltip: "Scan HTML post descriptions for embedded inline artwork"
                        checked: root.bridge ? root.bridge.scanContentImages : true
                        onCheckedChanged: if (root.bridge) root.bridge.scanContentImages = checked
                    }

                    StyledCheckBox {
                        text: "Compress to WebP"
                        tooltip: "Convert downloaded PNG and JPG images to compressed WebP format"
                        checked: root.bridge ? root.bridge.compressWebp : false
                        onCheckedChanged: if (root.bridge) root.bridge.compressWebp = checked
                    }

                    StyledCheckBox {
                        text: "Download Embedded Media (yt-dlp)"
                        tooltip: "Download embedded video players (Vimeo, YouTube, Streamable, RedGifs, etc.) via standalone yt-dlp"
                        checked: root.bridge ? root.bridge.downloadEmbeds : true
                        onCheckedChanged: if (root.bridge) root.bridge.downloadEmbeds = checked
                    }

                    StyledCheckBox {
                        text: "Keep Duplicates"
                        tooltip: "Re-download files even if identical files already exist in destination"
                        checked: root.bridge ? root.bridge.keepDuplicates : false
                        onCheckedChanged: if (root.bridge) root.bridge.keepDuplicates = checked
                    }
                }
            }
        }

        // Section 4: Advanced Settings
        CardSection {
            Layout.fillWidth: true
            title: "Advanced Structure & Performance"
            iconText: "⚙️"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Flow {
                    Layout.fillWidth: true
                    spacing: 14

                    StyledCheckBox {
                        text: "Subfolder per post"
                        tooltip: "Organize downloads into subfolders named after each post"
                        checked: root.bridge ? root.bridge.subfolderPerPost : true
                        onCheckedChanged: if (root.bridge) root.bridge.subfolderPerPost = checked
                    }

                    StyledCheckBox {
                        text: "Date Prefix"
                        tooltip: "Prefix subfolder names with the post publication date [YYYY-MM-DD]"
                        checked: root.bridge ? root.bridge.datePrefix : true
                        onCheckedChanged: if (root.bridge) root.bridge.datePrefix = checked
                    }

                    StyledCheckBox {
                        text: "Separate folders by Known.txt"
                        tooltip: "Sort files into subfolders corresponding to matched characters/series from Known.txt"
                        checked: root.bridge ? root.bridge.separateFoldersByKnown : false
                        onCheckedChanged: if (root.bridge) root.bridge.separateFoldersByKnown = checked
                    }

                    StyledCheckBox {
                        text: "Download Revisions"
                        tooltip: "Download older superseded revisions of edited posts"
                        checked: root.bridge ? root.bridge.downloadRevisions : false
                        onCheckedChanged: if (root.bridge) root.bridge.downloadRevisions = checked
                    }

                    StyledCheckBox {
                        id: adaptiveCheck
                        text: "Adaptive Threading"
                        tooltip: (root.bridge && root.bridge.threadsLocked)
                                 ? "Adaptive Threading is disabled because Thread Lock is active"
                                 : "Automatically scale worker thread count based on network conditions and 429 rate limits"
                        enabled: root.bridge ? !root.bridge.threadsLocked : true
                        opacity: enabled ? 1.0 : 0.38
                        Behavior on opacity { NumberAnimation { duration: 180 } }
                        checked: root.bridge ? root.bridge.adaptiveThreading : false
                        onCheckedChanged: if (root.bridge && enabled) root.bridge.adaptiveThreading = checked
                    }

                    StyledCheckBox {
                        text: "Manga Mode (Oldest First)"
                        tooltip: "Sort posts chronologically (oldest first) so chapters and pages download in reading order"
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
                        text: "Concurrent Workers:"
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
                        implicitWidth: 140
                        // Disable interaction when Adaptive Threading is managing concurrency
                        enabled: root.bridge ? !root.bridge.adaptiveThreading : true
                        onMoved: if (root.bridge) root.bridge.threadsCount = Math.round(value)
                    }

                    Rectangle {
                        width: 32
                        height: 24
                        radius: 4
                        color: "#242A38"
                        Text {
                            anchors.centerIn: parent
                            text: root.bridge && root.bridge.adaptiveThreading
                                  ? root.bridge.threadsCount.toString()
                                  : Math.round(threadSlider.value).toString()
                            font.bold: true
                            font.pixelSize: 11
                            color: (root.bridge && root.bridge.threadsLocked) ? "#F87171" : "#38BDF8"
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
                                text: (root.bridge && root.bridge.threadsLocked) ? "Locked" : "Lock"
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
                            visible: lockMouse.containsMouse
                            delay: 400
                            timeout: 5000
                            text: (root.bridge && root.bridge.threadsLocked)
                                  ? "Thread Lock Active: Worker concurrency is locked at " + (root.bridge ? root.bridge.threadsCount : 4) + ". Adaptive scaling is disabled and HTTP 429 cooldown is 30s."
                                  : "Lock Thread Sweetspot: Lock current concurrency. Disables adaptive scaling and prevents rate limits from altering your thread count."
                            contentItem: Text {
                                text: parent.text
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
                                  ? ("🔒 Locked: " + root.bridge.threadsCount + "T")
                                  : (root.bridge && root.bridge.adaptiveThreading
                                     ? "⚡ Adaptive"
                                     : (root.bridge ? ("⚡ CPU Cores: " + root.bridge.maxCpuThreads) : "⚡ CPU Auto"))
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
                        text: "⏱️ Thread Delay After Download:"
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
                        implicitWidth: 140
                        onMoved: if (root.bridge) root.bridge.downloadDelay = value
                    }

                    Rectangle {
                        width: 44
                        height: 24
                        radius: 4
                        color: "#242A38"
                        Text {
                            anchors.centerIn: parent
                            text: (root.bridge ? root.bridge.downloadDelay.toFixed(1) : "2.0") + "s"
                            font.bold: true
                            font.pixelSize: 11
                            color: "#A78BFA"
                        }
                    }

                    Text {
                        text: "(anti-429 cooldown)"
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
                                    text: "Save post_info.txt"
                                    color: saveMetaToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    text: "caption, tags & comments"
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
                                    text: "Open folder when done"
                                    color: openFolderToggle.active ? "#E2E8F0" : "#64748B"
                                    font.pixelSize: 12
                                    font.family: "Segoe UI, sans-serif"
                                    font.weight: Font.Medium
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                                Text {
                                    text: "auto-opens on completion"
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

                    Item { Layout.fillWidth: true }
                }
            }
        }

        // Batch Queue Section
        CardSection {
            Layout.fillWidth: true
            title: "Batch Download Queue"
            iconText: "📋"

            ColumnLayout {
                width: parent.width
                spacing: 10

                Text {
                    text: "Paste multiple creator / album URLs below, one per line. Each URL uses its own folder inside the download destination."
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
                        placeholderText: "https://kemono.su/patreon/user/12345\nhttps://coomer.su/onlyfans/user/67890\nhttps://cum.st/creators/onlyfans/32696630\nhttps://bunkr.is/a/example"
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
                        text: "Add All to Queue"
                        iconText: "▶"
                        variant: "primary"
                        tooltip: "Parse and start downloading all URLs above"
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
                        text: "Clear"
                        iconText: "✕"
                        variant: "ghost"
                        onClicked: batchInput.text = ""
                    }

                    Text {
                        id: batchCountLabel
                        text: batchInput.text.trim().length > 0 ?
                              batchInput.text.split("\n").filter(function(l){ return l.trim().startsWith("http") }).length + " URL(s) detected" : ""
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

