import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root
    property var bridge: null

    function tr(key, fallback) {
        if (typeof appWindow !== "undefined") return appWindow.tr(key, fallback)
        return fallback !== undefined ? fallback : key
    }

    // ── Reactive Explorer State ──────────────────────────────────────────────
    property string currentPath: ""
    property var rawItems: []
    property var filteredItems: []
    property var breadcrumbs: []
    property var drives: []
    property string activeCategory: "all"
    property string searchFilter: ""
    property string viewMode: "grid" // "grid" | "list"
    property bool pathEditMode: false
    property bool isLoading: false

    // Counts
    property int folderCount: 0
    property int imageCount: 0
    property int videoCount: 0
    property int archiveCount: 0
    property int audioCount: 0
    property int otherCount: 0

    // ── Helper formatters ───────────────────────────────────────────────────
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function formatDate(ts) {
        if (!ts || ts <= 0) return ""
        var d = new Date(ts * 1000)
        return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    function getCategory(ext) {
        if (!ext) return "other"
        ext = ext.toLowerCase()
        if ([".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"].indexOf(ext) >= 0) return "image"
        if ([".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v"].indexOf(ext) >= 0) return "video"
        if ([".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"].indexOf(ext) >= 0) return "archive"
        if ([".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"].indexOf(ext) >= 0) return "audio"
        return "other"
    }

    function getItemIcon(item) {
        if (item.is_dir) return "📁"
        var cat = getCategory(item.ext)
        if (cat === "image") return "🖼️"
        if (cat === "video") return "🎬"
        if (cat === "archive") return "📦"
        if (cat === "audio") return "🎵"
        return "📄"
    }

    function getItemColor(item) {
        if (item.is_dir) return "#38BDF8"
        var cat = getCategory(item.ext)
        if (cat === "image") return "#EC4899"
        if (cat === "video") return "#8B5CF6"
        if (cat === "archive") return "#F59E0B"
        if (cat === "audio") return "#10B981"
        return "#94A3B8"
    }

    function formatFolderSize(item) {
        if (!item) return ""
        if (!item.is_dir) return formatBytes(item.size)
        if (item.size >= 0) return formatBytes(item.size)
        if (item.child_count >= 0) return item.child_count + (item.child_count === 1 ? " item" : " items")
        return "Calculating…"
    }

    function formatFolderSubtitle(item) {
        if (!item) return ""
        if (!item.is_dir) return formatDate(item.mtime)
        if (item.file_count >= 0) {
            var txt = item.file_count + (item.file_count === 1 ? " file" : " files")
            if (item.folder_count > 0) {
                txt += " • " + item.folder_count + (item.folder_count === 1 ? " dir" : " dirs")
            }
            if (item.size >= 0) {
                txt += " • " + formatBytes(item.size)
            }
            return txt
        }
        if (item.child_count >= 0) {
            return item.child_count + (item.child_count === 1 ? " item" : " items") + " • Calculating size…"
        }
        return "Folder • Calculating size…"
    }

    // ── Live background folder stats updates ────────────────────────────────
    Connections {
        target: root.bridge
        function onFolderStatsCalculated(path, size, fileCount, folderCount) {
            updateFolderStats(path, size, fileCount, folderCount)
        }
    }

    function updateFolderStats(path, size, fileCount, folderCount) {
        var changed = false
        var raw = root.rawItems || []
        for (var i = 0; i < raw.length; i++) {
            if (raw[i].path === path) {
                raw[i].size = size
                raw[i].file_count = fileCount
                raw[i].folder_count = folderCount
                changed = true
                break
            }
        }
        if (changed) {
            applyFilter()
        }
    }

    function getAllMediaItems() {
        var media = []
        var list = root.filteredItems || []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            if (!it.is_dir) {
                var cat = getCategory(it.ext)
                if (cat === "image" || cat === "video" || cat === "audio") {
                    media.push(it)
                }
            }
        }
        return media
    }

    function openLightbox(item) {
        var allMedia = getAllMediaItems()
        lightboxModal.open(item, allMedia)
    }

    // ── Directory Navigation ────────────────────────────────────────────────
    function navigateTo(path) {
        if (!root.bridge) return
        root.isLoading = true
        root.pathEditMode = false
        root.searchFilter = ""

        var targetPath = path || (root.bridge.getDownloadDir ? root.bridge.getDownloadDir() : "")
        root.currentPath = targetPath

        // Query drives & breadcrumbs
        if (root.bridge.getSystemDrives) {
            root.drives = root.bridge.getSystemDrives()
        }
        if (root.bridge.getBreadcrumbs) {
            root.breadcrumbs = root.bridge.getBreadcrumbs(targetPath)
        }

        // On-demand lazy directory list
        if (root.bridge.listDirectory) {
            var items = root.bridge.listDirectory(targetPath, 1500) || []
            root.rawItems = items
            updateCounts(items)
            applyFilter()
        }
        root.isLoading = false
    }

    function navigateUp() {
        if (!root.currentPath || root.breadcrumbs.length <= 1) return
        var parentCrumb = root.breadcrumbs[root.breadcrumbs.length - 2]
        if (parentCrumb && parentCrumb.path) {
            navigateTo(parentCrumb.path)
        }
    }

    function updateCounts(items) {
        var fc = 0, ic = 0, vc = 0, ac = 0, auc = 0, oc = 0
        for (var i = 0; i < items.length; i++) {
            var it = items[i]
            if (it.is_dir) {
                fc++
            } else {
                var cat = getCategory(it.ext)
                if (cat === "image") ic++
                else if (cat === "video") vc++
                else if (cat === "archive") ac++
                else if (cat === "audio") auc++
                else oc++
            }
        }
        root.folderCount = fc
        root.imageCount = ic
        root.videoCount = vc
        root.archiveCount = ac
        root.audioCount = auc
        root.otherCount = oc
    }

    function applyFilter() {
        var list = root.rawItems || []
        var cat = root.activeCategory
        var q = (root.searchFilter || "").trim().toLowerCase()

        var filtered = []
        for (var i = 0; i < list.length; i++) {
            var it = list[i]
            // Category filter
            if (cat === "folders" && !it.is_dir) continue
            if (cat === "images" && (it.is_dir || getCategory(it.ext) !== "image")) continue
            if (cat === "videos" && (it.is_dir || getCategory(it.ext) !== "video")) continue
            if (cat === "archives" && (it.is_dir || getCategory(it.ext) !== "archive")) continue
            if (cat === "audio" && (it.is_dir || getCategory(it.ext) !== "audio")) continue

            // Search query filter
            if (q.length > 0 && it.name.toLowerCase().indexOf(q) === -1) continue

            filtered.push(it)
        }
        root.filteredItems = filtered
    }

    onActiveCategoryChanged: applyFilter()
    onSearchFilterChanged: applyFilter()

    Component.onCompleted: {
        navigateTo("")
    }

    // ── Main UI Layout ──────────────────────────────────────────────────────
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // 1. TOP HEADER BAR
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            RowLayout {
                spacing: 8
                Text {
                    text: "🖼️"
                    font.pixelSize: 22
                }
                ColumnLayout {
                    spacing: 1
                    Text {
                        text: root.tr("tab_gallery_title", "File Explorer & Media Gallery")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 18
                        font.weight: 700
                        color: "#F8FAFC"
                    }
                    Text {
                        text: root.currentPath || root.tr("gallery_subheading", "Browse, preview, and organize your downloaded collections")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                        elide: Text.ElideMiddle
                        Layout.maximumWidth: 420
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Action: Jump to Downloads
            Rectangle {
                implicitHeight: 30
                implicitWidth: dlBtnRow.implicitWidth + 16
                radius: 6
                color: dlBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: dlBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                border.width: 1

                Row {
                    id: dlBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🏠"; font.pixelSize: 12 }
                    Text {
                        text: root.tr("gallery_btn_downloads", "Downloads")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                }
                MouseArea {
                    id: dlBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.getDownloadDir) {
                            navigateTo(root.bridge.getDownloadDir())
                        }
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Jump to your default Downloads directory"
                }
            }

            // Action: Open in OS Explorer
            Rectangle {
                implicitHeight: 30
                implicitWidth: openBtnRow.implicitWidth + 16
                radius: 6
                color: openBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: openBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                border.width: 1

                Row {
                    id: openBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "📂"; font.pixelSize: 12 }
                    Text {
                        text: root.tr("gallery_btn_open_system", "Open Folder")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                }
                MouseArea {
                    id: openBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.openFolder) {
                            root.bridge.openFolder(root.currentPath)
                        }
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Open current folder in File Explorer / OS file manager"
                }
            }

            // Action: Refresh
            Rectangle {
                width: 30
                height: 30
                radius: 6
                color: refBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: refBtnMouse.containsMouse ? "#38BDF8" : "#2E384D"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "🔄"
                    font.pixelSize: 13
                }
                MouseArea {
                    id: refBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: navigateTo(root.currentPath)
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Refresh current directory contents"
                }
            }

            // Action: Smart Batch Renamer
            Rectangle {
                implicitHeight: 30
                implicitWidth: renameBtnRow.implicitWidth + 16
                radius: 6
                color: renameBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: renameBtnMouse.containsMouse ? "#F59E0B" : "#2E384D"
                border.width: 1

                Row {
                    id: renameBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🏷️"; font.pixelSize: 12 }
                    Text {
                        text: "Batch Rename"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                }
                MouseArea {
                    id: renameBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        batchRenameModal.open(root.currentPath, root.filteredItems)
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Smart Batch Renamer\nBulk rename and organize files with metadata variables, sequential numbering, and flattening"
                }
            }

            // Action: Cleaner & Deduplicator
            Rectangle {
                implicitHeight: 30
                implicitWidth: cleanBtnRow.implicitWidth + 16
                radius: 6
                color: cleanBtnMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: cleanBtnMouse.containsMouse ? "#10B981" : "#2E384D"
                border.width: 1

                Row {
                    id: cleanBtnRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🧹"; font.pixelSize: 12 }
                    Text {
                        text: "Clean & Organize"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#E2E8F0"
                    }
                }
                MouseArea {
                    id: cleanBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        galleryCleanerModal.open(root.currentPath)
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Clean & Organize\nFind 0-byte broken files, detect duplicate downloads by SHA-256 hash, and auto-sort media into folders"
                }
            }

            // View Mode Toggle (Grid vs List)
            Rectangle {
                implicitHeight: 30
                implicitWidth: 64
                radius: 6
                color: "#12151E"
                border.color: "#252C3D"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 2

                    Rectangle {
                        width: 28
                        height: 24
                        radius: 4
                        color: root.viewMode === "grid" ? "#222D42" : "transparent"
                        border.color: root.viewMode === "grid" ? "#38BDF8" : "transparent"
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "⊞"; font.pixelSize: 13; color: root.viewMode === "grid" ? "#38BDF8" : "#64748B" }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.viewMode = "grid"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Grid View\nDisplay files and folders as visual cards with thumbnails"
                        }
                    }
                    Rectangle {
                        width: 28
                        height: 24
                        radius: 4
                        color: root.viewMode === "list" ? "#222D42" : "transparent"
                        border.color: root.viewMode === "list" ? "#38BDF8" : "transparent"
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "📑"; font.pixelSize: 12; color: root.viewMode === "list" ? "#38BDF8" : "#64748B" }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.viewMode = "list"
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "List View\nDisplay detailed file information: names, item counts, sizes, and modified dates"
                        }
                    }
                }
            }
        }

        // 2. BREADCRUMBS & DRIVE SELECTOR BAR
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 38
            radius: 8
            color: "#121622"
            border.color: "#232A3B"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                // Parent directory button
                Rectangle {
                    width: 28
                    height: 28
                    radius: 5
                    color: (upBtnMouse.containsMouse && root.breadcrumbs.length > 1) ? "#1E273A" : "#161B29"
                    border.color: (upBtnMouse.containsMouse && root.breadcrumbs.length > 1) ? "#38BDF8" : "#2B354C"
                    border.width: 1
                    opacity: root.breadcrumbs.length > 1 ? 1.0 : 0.4

                    Text {
                        anchors.centerIn: parent
                        text: "⬆"
                        font.pixelSize: 13
                        color: "#E2E8F0"
                    }
                    MouseArea {
                        id: upBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: root.breadcrumbs.length > 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: navigateUp()
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: root.breadcrumbs.length > 1 ? ("Go up to: " + (root.breadcrumbs.length >= 2 ? root.breadcrumbs[root.breadcrumbs.length - 2].path : "parent directory")) : "Already at root level"
                    }
                }

                // Drive quick selectors
                Repeater {
                    model: root.drives
                    delegate: Rectangle {
                        implicitHeight: 26
                        implicitWidth: driveText.implicitWidth + 14
                        radius: 5
                        color: driveMouse.containsMouse ? "#1E273A" : "#171D2B"
                        border.color: driveMouse.containsMouse ? "#38BDF8" : "#2B354C"
                        border.width: 1

                        Text {
                            id: driveText
                            anchors.centerIn: parent
                            text: modelData.name || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: driveMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: navigateTo(modelData.path)
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Switch to drive " + (modelData.name || modelData.path)
                        }
                    }
                }

                // Breadcrumbs strip (Flickable)
                Flickable {
                    Layout.fillWidth: true
                    implicitHeight: 28
                    contentWidth: crumbRow.implicitWidth
                    contentHeight: 28
                    flickableDirection: Flickable.HorizontalFlick
                    clip: true

                    Row {
                        id: crumbRow
                        spacing: 4
                        anchors.verticalCenter: parent.verticalCenter

                        Repeater {
                            model: root.breadcrumbs
                            delegate: Row {
                                spacing: 4
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    implicitHeight: 24
                                    implicitWidth: crumbText.implicitWidth + 12
                                    radius: 4
                                    color: (crumbMouse.containsMouse || index === (root.breadcrumbs.length - 1)) ? "#1E293D" : "transparent"
                                    border.color: index === (root.breadcrumbs.length - 1) ? "#38BDF8" : "transparent"
                                    border.width: 1

                                    Text {
                                        id: crumbText
                                        anchors.centerIn: parent
                                        text: modelData.name || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        font.weight: index === (root.breadcrumbs.length - 1) ? 700 : Font.Normal
                                        color: index === (root.breadcrumbs.length - 1) ? "#F8FAFC" : "#94A3B8"
                                    }
                                    MouseArea {
                                        id: crumbMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: navigateTo(modelData.path)
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 250
                                        ToolTip.text: "Navigate to " + modelData.path
                                    }
                                }

                                Text {
                                    visible: index < (root.breadcrumbs.length - 1)
                                    text: "›"
                                    font.pixelSize: 12
                                    color: "#475569"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        // 4. CATEGORY PILLS & REAL-TIME SEARCH TOOLBAR
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Filter Pills
            Row {
                spacing: 6
                Layout.alignment: Qt.AlignVCenter

                // All
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillAllText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "all" ? "#38BDF8" : "#161B28"
                    Text {
                        id: pillAllText
                        anchors.centerIn: parent
                        text: "All (" + root.rawItems.length + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "all" ? "#0F172A" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "all"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show all items in this folder (" + root.rawItems.length + " total)"
                    }
                }

                // Folders
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillFoldersText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "folders" ? "#38BDF8" : "#161B28"
                    Text {
                        id: pillFoldersText
                        anchors.centerIn: parent
                        text: "📁 Folders (" + root.folderCount + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "folders" ? "#0F172A" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "folders"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show only subdirectories (" + root.folderCount + " folders)"
                    }
                }

                // Images
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillImgText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "images" ? "#EC4899" : "#161B28"
                    Text {
                        id: pillImgText
                        anchors.centerIn: parent
                        text: "🖼️ Images (" + root.imageCount + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "images" ? "#FFFFFF" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "images"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show only images: JPG, PNG, GIF, WebP, SVG, BMP (" + root.imageCount + " images)"
                    }
                }

                // Videos
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillVidText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "videos" ? "#8B5CF6" : "#161B28"
                    Text {
                        id: pillVidText
                        anchors.centerIn: parent
                        text: "🎬 Videos (" + root.videoCount + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "videos" ? "#FFFFFF" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "videos"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show only videos: MP4, MKV, WebM, MOV, AVI (" + root.videoCount + " videos)"
                    }
                }

                // Archives
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillArcText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "archives" ? "#F59E0B" : "#161B28"
                    Text {
                        id: pillArcText
                        anchors.centerIn: parent
                        text: "📦 Archives (" + root.archiveCount + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "archives" ? "#0F172A" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "archives"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show only compressed archives: ZIP, RAR, 7Z, TAR, GZ (" + root.archiveCount + " archives)"
                    }
                }

                // Audio
                Rectangle {
                    implicitHeight: 26
                    implicitWidth: pillAudText.implicitWidth + 14
                    radius: 13
                    color: root.activeCategory === "audio" ? "#10B981" : "#161B28"
                    Text {
                        id: pillAudText
                        anchors.centerIn: parent
                        text: "🎵 Audio (" + root.audioCount + ")"
                        font.pixelSize: 11
                        font.weight: 600
                        color: root.activeCategory === "audio" ? "#0F172A" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activeCategory = "audio"
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Show only audio tracks: MP3, FLAC, WAV, OGG, M4A (" + root.audioCount + " audio files)"
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Search input
            Rectangle {
                implicitHeight: 28
                implicitWidth: 200
                radius: 6
                color: "#121622"
                border.color: searchInput.activeFocus ? "#38BDF8" : "#252D3E"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text { text: "🔍"; font.pixelSize: 11 }
                    TextInput {
                        id: searchInput
                        Layout.fillWidth: true
                        color: "#F8FAFC"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        selectByMouse: true
                        clip: true
                        onTextChanged: root.searchFilter = text

                        Text {
                            visible: !searchInput.text && !searchInput.activeFocus
                            text: "Filter by name..."
                            color: "#64748B"
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Text {
                        visible: searchInput.text.length > 0
                        text: "✕"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                searchInput.text = ""
                                root.searchFilter = ""
                            }
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 250
                            ToolTip.text: "Clear search filter"
                        }
                    }
                }
            }
        }

        // 5. VIRTUALIZED FILE & FOLDER BROWSER
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: "#0D1018"
            border.color: "#1E2536"
            border.width: 1
            clip: true

            // Empty state placeholder
            Item {
                anchors.centerIn: parent
                visible: root.filteredItems.length === 0
                ColumnLayout {
                    spacing: 8
                    anchors.centerIn: parent
                    Text {
                        text: "📭"
                        font.pixelSize: 32
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Text {
                        text: root.searchFilter.length > 0 ? "No files match your filter" : "This folder is empty"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.weight: 600
                        color: "#64748B"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            // GRID VIEW
            GridView {
                id: explorerGridView
                visible: root.viewMode === "grid"
                anchors.fill: parent
                anchors.margins: 10
                cellWidth: 160
                cellHeight: 110
                model: root.filteredItems
                clip: true

                delegate: Rectangle {
                    width: explorerGridView.cellWidth - 8
                    height: explorerGridView.cellHeight - 8
                    radius: 8
                    color: gridCardMouse.containsMouse ? "#1A2234" : "#131824"
                    border.color: gridCardMouse.containsMouse ? getItemColor(modelData) : "#20283A"
                    border.width: 1

                    scale: gridCardMouse.pressed ? 0.96 : (gridCardMouse.containsMouse ? 1.02 : 1.0)
                    Behavior on scale { NumberAnimation { duration: 140 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: getItemIcon(modelData)
                                font.pixelSize: 22
                            }
                            Item { Layout.fillWidth: true }
                            Rectangle {
                                implicitHeight: 18
                                implicitWidth: sizeText.implicitWidth + 10
                                radius: 4
                                color: modelData.is_dir ? "#0D1322" : "#0B0E17"
                                border.color: modelData.is_dir ? (modelData.size >= 0 ? "#38BDF8" : "#25334D") : "transparent"
                                border.width: modelData.is_dir ? 1 : 0
                                Text {
                                    id: sizeText
                                    anchors.centerIn: parent
                                    text: formatFolderSize(modelData)
                                    font.pixelSize: 9
                                    font.weight: modelData.is_dir ? 600 : Font.Normal
                                    color: modelData.is_dir ? (modelData.size >= 0 ? "#38BDF8" : "#94A3B8") : "#94A3B8"
                                }
                            }
                        }

                        Text {
                            text: modelData.name || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                            elide: Text.ElideMiddle
                            maximumLineCount: 2
                            wrapMode: Text.WrapAnywhere
                            Layout.fillWidth: true
                        }

                        Text {
                            text: formatFolderSubtitle(modelData)
                            font.pixelSize: 9
                            color: modelData.is_dir ? (modelData.size >= 0 ? "#38BDF8" : "#818CF8") : "#64748B"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    MouseArea {
                        id: gridCardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onDoubleClicked: {
                            if (modelData.is_dir) {
                                navigateTo(modelData.path)
                            } else {
                                var cat = getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    openLightbox(modelData)
                                } else if (root.bridge && root.bridge.openPathInSystem) {
                                    root.bridge.openPathInSystem(modelData.path)
                                }
                            }
                        }
                        onClicked: {
                            if (modelData.is_dir) {
                                navigateTo(modelData.path)
                            } else {
                                var cat = getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    openLightbox(modelData)
                                }
                            }
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 350
                        ToolTip.text: {
                            var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                            if (modelData.is_dir) {
                                tip += "\n" + root.formatFolderSubtitle(modelData)
                                tip += "\n• Click or Double-click to open folder"
                            } else {
                                tip += "\nSize: " + root.formatBytes(modelData.size) + "\nModified: " + root.formatDate(modelData.mtime)
                                var cat = root.getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    tip += "\n• Click or Double-click to preview in Lightbox"
                                } else {
                                    tip += "\n• Double-click to open in default app"
                                }
                            }
                            return tip
                        }
                    }
                }
            }

            // LIST VIEW
            ListView {
                id: explorerListView
                visible: root.viewMode === "list"
                anchors.fill: parent
                anchors.margins: 6
                spacing: 2
                model: root.filteredItems
                clip: true

                delegate: Rectangle {
                    width: explorerListView.width
                    height: 32
                    radius: 5
                    color: listRowMouse.containsMouse ? "#1B2336" : (index % 2 === 0 ? "#111622" : "#0E121B")
                    border.color: listRowMouse.containsMouse ? "#38BDF8" : "transparent"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10

                        Text {
                            text: getItemIcon(modelData)
                            font.pixelSize: 14
                        }

                        Text {
                            text: modelData.name || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#38BDF8" : "#E2E8F0"
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }

                        // Files / Child count column
                        Text {
                            text: {
                                if (modelData.is_dir) {
                                    if (modelData.file_count >= 0) {
                                        var cnt = modelData.file_count + (modelData.file_count === 1 ? " file" : " files")
                                        if (modelData.folder_count > 0) {
                                            cnt += " (" + modelData.folder_count + " dirs)"
                                        }
                                        return cnt
                                    }
                                    return modelData.child_count + (modelData.child_count === 1 ? " item" : " items")
                                }
                                return modelData.ext ? modelData.ext.toUpperCase() : "FILE"
                            }
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            font.weight: modelData.is_dir ? 600 : Font.Normal
                            color: modelData.is_dir ? "#A78BFA" : "#64748B"
                            Layout.preferredWidth: 110
                            horizontalAlignment: Text.AlignRight
                        }

                        // Size column
                        Text {
                            text: formatFolderSize(modelData)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            font.weight: (modelData.is_dir && modelData.size >= 0) ? 600 : Font.Normal
                            color: modelData.is_dir ? (modelData.size >= 0 ? "#38BDF8" : "#818CF8") : "#94A3B8"
                            Layout.preferredWidth: 90
                            horizontalAlignment: Text.AlignRight
                        }

                        // Date Modified column
                        Text {
                            text: formatDate(modelData.mtime)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#64748B"
                            Layout.preferredWidth: 120
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    MouseArea {
                        id: listRowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onDoubleClicked: {
                            if (modelData.is_dir) {
                                navigateTo(modelData.path)
                            } else {
                                var cat = getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    openLightbox(modelData)
                                } else if (root.bridge && root.bridge.openPathInSystem) {
                                    root.bridge.openPathInSystem(modelData.path)
                                }
                            }
                        }
                        onClicked: {
                            if (modelData.is_dir) {
                                navigateTo(modelData.path)
                            } else {
                                var cat = getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    openLightbox(modelData)
                                }
                            }
                        }
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 350
                        ToolTip.text: {
                            var tip = (modelData.is_dir ? "📁 " : "📄 ") + (modelData.name || "")
                            if (modelData.is_dir) {
                                tip += "\n" + root.formatFolderSubtitle(modelData)
                                tip += "\n• Click or Double-click to open folder"
                            } else {
                                tip += "\nSize: " + root.formatBytes(modelData.size) + "\nModified: " + root.formatDate(modelData.mtime)
                                var cat = root.getCategory(modelData.ext)
                                if (cat === "image" || cat === "video" || cat === "audio") {
                                    tip += "\n• Click or Double-click to preview in Lightbox"
                                } else {
                                    tip += "\n• Double-click to open in default app"
                                }
                            }
                            return tip
                        }
                    }
                }
            }
        }

        // 6. BOTTOM TELEMETRY / STATUS BAR
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: 6
            color: "#0F121B"
            border.color: "#1E2536"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 12

                Text {
                    text: root.filteredItems.length + " of " + root.rawItems.length + " items"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#94A3B8"
                }

                Rectangle { width: 1; height: 12; color: "#2B354C" }

                Text {
                    text: "⚡ Zero-Lag Virtualized Engine — On-Demand Traversal"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#38BDF8"
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: root.currentPath
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: 400
                }
            }
        }
    }

    // ── Feature Modals ──────────────────────────────────────────────────────
    MediaLightboxModal {
        id: lightboxModal
        bridge: root.bridge
    }

    BatchRenameModal {
        id: batchRenameModal
        bridge: root.bridge
        onRenamed: navigateTo(root.currentPath)
    }

    GalleryCleanerModal {
        id: galleryCleanerModal
        bridge: root.bridge
        onCleaned: navigateTo(root.currentPath)
        onOrganized: navigateTo(root.currentPath)
    }
}
