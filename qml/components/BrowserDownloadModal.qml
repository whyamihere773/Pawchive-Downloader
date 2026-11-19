import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// ── BrowserDownloadModal: Destination Picker, Multi-Creator Subfolder Preview & Full Downloader Settings ──
Item {
    id: modalRoot

    property var appBridge: null
    property var browserBridge: null
    property bool isOpen: false
    property int activeTab: 0          // 0 = Destination & Summary, 1 = All Download Settings
    property string mode: "marked"     // "marked" | "single" | "dms" | "new_posts"
    property bool defaultAutoStart: true
    property string modalTitle: "Download Selection"
    property var pendingItems: []
    property string targetDir: ""
    property bool createCreatorFolder: true
    property var folderPreviews: []
    property string errorText: ""

    signal downloadDispatched(var urls, bool autoStart, string folder)

    readonly property int itemCount: pendingItems ? pendingItems.length : 0
    readonly property int distinctCreatorCount: {
        var items = pendingItems || []
        var seen = {}
        var count = 0
        for (var i = 0; i < items.length; i++) {
            var it = items[i]
            if (!it) continue
            var svc = String(it.service || "").toLowerCase().trim()
            var cid = String(it.creator_id || it.creator_name || it.name || "").toLowerCase().trim()
            var key = svc + "|" + (cid || ("item_" + i))
            if (!seen[key]) {
                seen[key] = true
                count++
            }
        }
        return count
    }
    readonly property bool isMultiCreator: distinctCreatorCount > 1
    readonly property bool effectiveCreateCreatorFolder: isMultiCreator ? true : createCreatorFolder

    readonly property string activeSettingsSummary: {
        if (!appBridge) return ""
        var parts = []
        var ft = String(appBridge.fileType || "all")
        if (ft === "all") parts.push("All Files")
        else if (ft === "images") parts.push("Images")
        else if (ft === "videos") parts.push("Videos")
        else if (ft === "archives") parts.push("Archives")
        else if (ft === "audio") parts.push("Audio")
        else if (ft === "links") parts.push("Links Only")
        else parts.push(ft)

        if (appBridge.subfolderPerPost) parts.push("Subfolder per post")
        if (appBridge.downloadThumbnailsOnly) parts.push("Thumbnails only")
        else if (appBridge.fallbackToThumbnails) parts.push("Thumbnail fallback")
        if (appBridge.downloadDms) parts.push("Include DMs")
        if (appBridge.compressWebp) parts.push("WebP")
        parts.push((appBridge.threadsCount || 4) + "T" + (appBridge.threadsLocked ? " Locked" : (appBridge.adaptiveThreading ? " Adaptive" : "")))
        if (appBridge.enableDownloadArchive) parts.push("Archive ON")
        return parts.join("  •  ")
    }

    anchors.fill: parent
    z: 99990
    opacity: isOpen ? 1.0 : 0.0
    visible: opacity > 0.005
    enabled: isOpen
    focus: isOpen

    Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }

    Keys.onEscapePressed: modalRoot.close()

    function refreshFolderPreviews() {
        var dir = (modalRoot.targetDir || "").trim()
        if (!dir) {
            modalRoot.folderPreviews = []
            return
        }
        if (modalRoot.browserBridge && modalRoot.browserBridge.previewDownloadFolders) {
            modalRoot.folderPreviews = modalRoot.browserBridge.previewDownloadFolders(
                dir,
                modalRoot.pendingItems || [],
                modalRoot.effectiveCreateCreatorFolder
            ) || []
        } else {
            modalRoot.folderPreviews = [dir]
        }
    }

    function openForMarked(autoStart) {
        var items = (modalRoot.browserBridge && modalRoot.browserBridge.getMarkedItemsList)
            ? modalRoot.browserBridge.getMarkedItemsList()
            : []
        var downloadable = []
        for (var i = 0; i < items.length; i++) {
            var it = items[i]
            if (it && it.url && String(it.url).trim().length > 0) {
                downloadable.push(it)
            }
        }
        if (downloadable.length === 0) {
            if (modalRoot.browserBridge && modalRoot.browserBridge.toastRequested) {
                modalRoot.browserBridge.toastRequested("No downloadable URLs in your selection cart.", "warning")
            }
            return
        }
        var cCnt = 0
        var pCnt = 0
        for (var j = 0; j < downloadable.length; j++) {
            if (String(downloadable[j].item_type || "") === "post") pCnt++
            else cCnt++
        }
        var titleParts = []
        if (cCnt > 0) titleParts.push(cCnt + (cCnt === 1 ? " Creator" : " Creators"))
        if (pCnt > 0) titleParts.push(pCnt + (pCnt === 1 ? " Post" : " Posts"))
        var heading = "Download Marked (" + (titleParts.length > 0 ? titleParts.join(" & ") : (downloadable.length + " Items")) + ")"
        openForItems(downloadable, heading, autoStart, "marked")
    }

    function openForItems(items, title, autoStart, modeName) {
        var list = []
        for (var i = 0; i < (items || []).length; i++) {
            var it = items[i]
            if (it && it.url && String(it.url).trim().length > 0) {
                list.push(it)
            }
        }
        if (list.length === 0) {
            if (modalRoot.browserBridge && modalRoot.browserBridge.toastRequested) {
                modalRoot.browserBridge.toastRequested("No downloadable URL available for this item.", "warning")
            }
            return
        }
        modalRoot.pendingItems = list
        modalRoot.modalTitle = title || ("Download " + list.length + (list.length === 1 ? " Item" : " Items"))
        modalRoot.defaultAutoStart = (autoStart === undefined) ? true : Boolean(autoStart)
        modalRoot.mode = modeName || "single"
        modalRoot.activeTab = 0
        modalRoot.errorText = ""
        modalRoot.createCreatorFolder = true

        var initialDir = ""
        if (modalRoot.browserBridge && modalRoot.browserBridge.getEffectiveDownloadDir) {
            initialDir = String(modalRoot.browserBridge.getEffectiveDownloadDir() || "").trim()
        } else if (modalRoot.appBridge && modalRoot.appBridge.downloadDir) {
            initialDir = String(modalRoot.appBridge.downloadDir || "").trim()
        }
        modalRoot.targetDir = initialDir
        modalRoot.refreshFolderPreviews()
        modalRoot.isOpen = true
    }

    function close() {
        modalRoot.isOpen = false
    }

    function browseFolder() {
        if (!modalRoot.browserBridge || !modalRoot.browserBridge.browseDownloadDir) return
        var chosen = String(modalRoot.browserBridge.browseDownloadDir(modalRoot.targetDir) || "").trim()
        if (chosen) {
            modalRoot.targetDir = chosen
            modalRoot.errorText = ""
            modalRoot.refreshFolderPreviews()
        }
    }

    function confirmDispatch(autoStart) {
        var cleanDir = (modalRoot.targetDir || "").trim()
        if (!cleanDir) {
            modalRoot.activeTab = 0
            modalRoot.errorText = "Please choose a destination folder before starting."
            return
        }
        var urls = []
        var seen = {}
        for (var i = 0; i < (modalRoot.pendingItems || []).length; i++) {
            var u = String(modalRoot.pendingItems[i].url || "").trim()
            if (u && !seen[u]) {
                seen[u] = true
                urls.push(u)
            }
        }
        if (urls.length === 0) {
            modalRoot.errorText = "No downloadable URLs found."
            return
        }
        if (modalRoot.browserBridge && modalRoot.browserBridge.dispatchBrowserDownload) {
            var dispatched = modalRoot.browserBridge.dispatchBrowserDownload(
                urls,
                cleanDir,
                Boolean(autoStart),
                modalRoot.effectiveCreateCreatorFolder,
                modalRoot.mode === "marked",
                false
            )
            if (dispatched > 0) {
                modalRoot.downloadDispatched(urls, Boolean(autoStart), cleanDir)
                modalRoot.close()
            }
        }
    }

    onTargetDirChanged: if (isOpen) refreshFolderPreviews()
    onCreateCreatorFolderChanged: if (isOpen) refreshFolderPreviews()

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#C4060911"
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onWheel: (wheel) => wheel.accepted = true
            onClicked: modalRoot.close()
        }
    }

    // Centered Modal Dialog
    Rectangle {
        id: dialogCard
        objectName: "browserDownloadModalCard"
        anchors.centerIn: parent
        width: Math.min(modalRoot.activeTab === 1 ? 940 : 720, modalRoot.width - 32)
        height: Math.min(modalRoot.activeTab === 1 ? 760 : 620, modalRoot.height - 32)
        radius: 12
        color: "#0E121D"
        border.color: "#29354D"
        border.width: 1
        scale: modalRoot.isOpen ? 1.0 : 0.95

        Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        MouseArea { anchors.fill: parent }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ── Header Row ──────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "📥"
                    font.pixelSize: 18
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: modalRoot.modalTitle
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        text: modalRoot.isMultiCreator
                              ? ("Saving " + modalRoot.itemCount + " items across " + modalRoot.distinctCreatorCount + " creators — each creator gets its own folder")
                              : ("Choose where to save and adjust any Downloader settings before starting")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        elide: Text.ElideRight
                    }
                }

                // Close Button
                Rectangle {
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    radius: 14
                    color: closeHover.containsMouse ? "#334155" : "#1B2232"
                    Text {
                        anchors.centerIn: parent
                        text: "×"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: closeHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.close()
                    }
                }
            }

            // ── Segmented Tab Switcher (Destination & Summary | All Download Settings) ──
            Rectangle {
                Layout.fillWidth: true
                height: 38
                radius: 8
                color: "#090C14"
                border.color: "#1E293B"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 4

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 6
                        color: modalRoot.activeTab === 0 ? "#182235" : (tab0Mouse.containsMouse ? "#121826" : "transparent")
                        border.color: modalRoot.activeTab === 0 ? "#38BDF8" : "transparent"
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "📁"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: "Destination & Summary"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: modalRoot.activeTab === 0 ? Font.Bold : Font.Medium
                                color: modalRoot.activeTab === 0 ? "#F8FAFC" : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: tab0Mouse
                            objectName: "browserDlModalTabDest"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modalRoot.activeTab = 0
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 6
                        color: modalRoot.activeTab === 1 ? "#182235" : (tab1Mouse.containsMouse ? "#121826" : "transparent")
                        border.color: modalRoot.activeTab === 1 ? "#38BDF8" : "transparent"
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text { text: "⚙️"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: "All Download Settings"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: modalRoot.activeTab === 1 ? Font.Bold : Font.Medium
                                color: modalRoot.activeTab === 1 ? "#F8FAFC" : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                        MouseArea {
                            id: tab1Mouse
                            objectName: "browserDlModalTabSettings"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modalRoot.activeTab = 1
                        }
                    }
                }
            }

            // ── TAB 0: Destination Picker, Multi-Creator Handling & Selection Summary ──
            SmoothFlickable {
                visible: modalRoot.activeTab === 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: destCol.implicitHeight + 8

                ColumnLayout {
                    id: destCol
                    width: parent.width - 6
                    spacing: 12

                    // 1. Download Folder Card
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: folderCardCol.implicitHeight + 24
                        radius: 9
                        color: "#121726"
                        border.color: modalRoot.errorText.length > 0 ? "#EF4444" : (modalRoot.targetDir.trim().length === 0 ? "#F59E0B" : "#1E293B")
                        border.width: 1

                        ColumnLayout {
                            id: folderCardCol
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 9

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: "DESTINATION FOLDER"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    color: "#38BDF8"
                                }

                                Rectangle {
                                    visible: !!(modalRoot.browserBridge && modalRoot.browserBridge.lastDownloadDir && modalRoot.targetDir === modalRoot.browserBridge.lastDownloadDir)
                                    height: 18
                                    width: remTxt.implicitWidth + 12
                                    radius: 9
                                    color: "#0A2A22"
                                    border.color: "#10B981"
                                    border.width: 1
                                    Text {
                                        id: remTxt
                                        anchors.centerIn: parent
                                        text: "✓ Remembered"
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: "#6EE7B7"
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                StyledButton {
                                    visible: !!(modalRoot.appBridge && modalRoot.appBridge.downloadDir && modalRoot.appBridge.downloadDir !== modalRoot.targetDir)
                                    text: "Use Downloader Default"
                                    variant: "ghost"
                                    implicitHeight: 24
                                    onClicked: {
                                        if (modalRoot.appBridge && modalRoot.appBridge.downloadDir) {
                                            modalRoot.targetDir = modalRoot.appBridge.downloadDir
                                            modalRoot.errorText = ""
                                            modalRoot.refreshFolderPreviews()
                                        }
                                    }
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                StyledTextField {
                                    id: dirField
                                    objectName: "browserDlModalDirField"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: modalRoot.targetDir
                                    leadingIcon: "💾"
                                    placeholderText: "Pick a folder where downloads will be saved…"
                                    showClearButton: false
                                    onTextEdited: {
                                        modalRoot.targetDir = text
                                        modalRoot.errorText = ""
                                        modalRoot.refreshFolderPreviews()
                                    }
                                }

                                StyledButton {
                                    objectName: "browserDlModalBrowseBtn"
                                    text: "Browse…"
                                    iconText: "📂"
                                    variant: "primary"
                                    implicitHeight: 36
                                    tooltip: "Pick destination folder (reopens at your last selected folder)"
                                    onClicked: modalRoot.browseFolder()
                                }
                            }

                            Text {
                                visible: modalRoot.targetDir.trim().length === 0
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                text: "⚠️ No folder selected yet. Click Browse to choose where these downloads should go — your choice will be remembered next time."
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#FDE68A"
                            }

                            // Multi-Creator Auto-Subfolder Notice vs Single-Creator Toggle
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: folderModeRow.implicitHeight + 14
                                radius: 7
                                color: modalRoot.isMultiCreator ? "#0A221C" : "#0D121F"
                                border.color: modalRoot.isMultiCreator ? "#10B981" : "#1E293B"
                                border.width: 1

                                RowLayout {
                                    id: folderModeRow
                                    anchors.fill: parent
                                    anchors.margins: 7
                                    spacing: 8

                                    Text {
                                        visible: modalRoot.isMultiCreator
                                        text: "📁"
                                        font.pixelSize: 13
                                    }

                                    Text {
                                        visible: modalRoot.isMultiCreator
                                        Layout.fillWidth: true
                                        wrapMode: Text.Wrap
                                        text: "Multiple creators selected (" + modalRoot.distinctCreatorCount + ") — each creator will automatically get its own subfolder inside the destination folder."
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#A7F3D0"
                                    }

                                    StyledSwitch {
                                        visible: !modalRoot.isMultiCreator
                                        Layout.fillWidth: true
                                        label: "Create a subfolder for this creator"
                                        tooltip: "When ON, saves inside <Destination>/<Creator Name>. Turn OFF to save files directly into the chosen folder."
                                        checked: modalRoot.createCreatorFolder
                                        onToggled: function(val) {
                                            modalRoot.createCreatorFolder = val
                                            modalRoot.refreshFolderPreviews()
                                        }
                                    }
                                }
                            }

                            // Live Resolved Folder Preview
                            Rectangle {
                                visible: modalRoot.folderPreviews && modalRoot.folderPreviews.length > 0
                                Layout.fillWidth: true
                                implicitHeight: prevCol.implicitHeight + 14
                                radius: 6
                                color: "#090D16"
                                border.color: "#1E2638"
                                border.width: 1

                                ColumnLayout {
                                    id: prevCol
                                    anchors.fill: parent
                                    anchors.margins: 7
                                    spacing: 3

                                    Text {
                                        text: modalRoot.folderPreviews.length > 1
                                              ? "FOLDERS TO BE USED (" + modalRoot.folderPreviews.length + "):"
                                              : "RESOLVED SAVE FOLDER:"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: "#64748B"
                                    }

                                    Repeater {
                                        model: Math.min(4, modalRoot.folderPreviews ? modalRoot.folderPreviews.length : 0)
                                        delegate: Text {
                                            Layout.fillWidth: true
                                            text: "↳ " + String(modalRoot.folderPreviews[index] || "")
                                            font.family: "Cascadia Code, Consolas, monospace"
                                            font.pixelSize: 10
                                            color: "#7DD3FC"
                                            elide: Text.ElideMiddle
                                        }
                                    }

                                    Text {
                                        visible: modalRoot.folderPreviews && modalRoot.folderPreviews.length > 4
                                        text: "  + " + (modalRoot.folderPreviews.length - 4) + " more creator folder(s)…"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: "#94A3B8"
                                    }
                                }
                            }
                        }
                    }

                    // 2. Active Downloader Settings Summary Banner (1-Click jump to All Settings)
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: settingsSummaryRow.implicitHeight + 18
                        radius: 9
                        color: "#121726"
                        border.color: "#1E293B"
                        border.width: 1

                        RowLayout {
                            id: settingsSummaryRow
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 3

                                Text {
                                    text: "ACTIVE DOWNLOADER SETTINGS"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#94A3B8"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modalRoot.activeSettingsSummary || "Using Downloader tab settings"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: "#E2E8F0"
                                    wrapMode: Text.Wrap
                                }
                            }

                            StyledButton {
                                text: "Edit All Settings →"
                                iconText: "⚙️"
                                variant: "outline"
                                implicitHeight: 30
                                onClicked: modalRoot.activeTab = 1
                            }
                        }
                    }

                    // 3. Selected Items Preview
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: itemsSecCol.implicitHeight + 20
                        radius: 9
                        color: "#121726"
                        border.color: "#1E293B"
                        border.width: 1

                        ColumnLayout {
                            id: itemsSecCol
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 6

                            Text {
                                text: "ITEMS TO DOWNLOAD (" + modalRoot.itemCount + ")"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#94A3B8"
                            }

                            Repeater {
                                model: Math.min(8, modalRoot.pendingItems ? modalRoot.pendingItems.length : 0)
                                delegate: Rectangle {
                                    readonly property var it: modalRoot.pendingItems[index] || ({})
                                    readonly property bool isPost: String(it.item_type || "") === "post"
                                    Layout.fillWidth: true
                                    height: 30
                                    radius: 6
                                    color: "#0D121F"
                                    border.color: isPost ? "#1E3A5F" : "#4C1D95"
                                    border.width: 1

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        spacing: 8

                                        Text {
                                            text: isPost ? "🖼️" : "👤"
                                            font.pixelSize: 11
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: String(it.title || it.creator_name || it.name || it.url || "")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#F1F5F9"
                                            elide: Text.ElideRight
                                        }

                                        Rectangle {
                                            visible: !!(it.service_label || it.service)
                                            height: 18
                                            width: itSvcTxt.implicitWidth + 10
                                            radius: 4
                                            color: "#1E293B"
                                            Text {
                                                id: itSvcTxt
                                                anchors.centerIn: parent
                                                text: String(it.service_label || it.service || "").toUpperCase()
                                                font.pixelSize: 9
                                                font.bold: true
                                                color: "#38BDF8"
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: modalRoot.itemCount > 8
                                text: "+ " + (modalRoot.itemCount - 8) + " more item(s)…"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                        }
                    }
                }
            }

            // ── TAB 1: Full Embedded Downloader Settings (Lazy-Loaded) ──────
            Rectangle {
                visible: modalRoot.activeTab === 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 9
                color: "#0A0E17"
                border.color: "#1E293B"
                border.width: 1
                clip: true

                Loader {
                    id: embeddedDownloaderSettingsLoader
                    anchors.fill: parent
                    anchors.margins: 8
                    active: modalRoot.isOpen && modalRoot.activeTab === 1
                    source: Qt.resolvedUrl("../views/DownloaderView.qml")
                    onLoaded: {
                        if (item) {
                            item.embeddedInModal = true
                            item.bridge = Qt.binding(function() { return modalRoot.appBridge })
                        }
                    }
                }
            }

            // Inline Error Banner
            Text {
                visible: modalRoot.errorText.length > 0
                Layout.fillWidth: true
                text: "⚠️ " + modalRoot.errorText
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.bold: true
                color: "#FCA5A5"
                wrapMode: Text.Wrap
            }

            // ── Footer Actions ──────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    visible: modalRoot.activeTab === 1 && modalRoot.targetDir.trim().length > 0
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: "📁 " + modalRoot.targetDir
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    color: "#7DD3FC"
                    elide: Text.ElideMiddle
                }

                Item {
                    visible: !(modalRoot.activeTab === 1 && modalRoot.targetDir.trim().length > 0)
                    Layout.fillWidth: true
                }

                StyledButton {
                    text: "Cancel"
                    variant: "ghost"
                    implicitHeight: 34
                    onClicked: modalRoot.close()
                }

                StyledButton {
                    objectName: "browserDlModalQueueBtn"
                    text: "Add to Queue"
                    iconText: "➕"
                    variant: modalRoot.defaultAutoStart ? "outline" : "primary"
                    implicitHeight: 34
                    enabled: modalRoot.targetDir.trim().length > 0
                    onClicked: modalRoot.confirmDispatch(false)
                }

                StyledButton {
                    objectName: "browserDlModalStartBtn"
                    text: "Start Download"
                    iconText: "🚀"
                    variant: modalRoot.defaultAutoStart ? "success" : "outline"
                    implicitHeight: 34
                    enabled: modalRoot.targetDir.trim().length > 0
                    onClicked: modalRoot.confirmDispatch(true)
                }
            }
        }
    }
}

