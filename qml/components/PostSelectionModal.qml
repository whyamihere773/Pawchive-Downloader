import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: modalRoot

    property var bridge: null
    property bool isOpen: false
    property string creatorName: ""
    property var allPosts: []
    property var filteredPosts: []
    property string searchFilter: ""
    property int selectedCount: 0
    property int totalFilesCount: 0
    property int totalSelectedFiles: 0

    // Inspector state
    property var inspectedPost: null
    readonly property bool isInspecting: inspectedPost !== null
    property int selectedFilesInPost: 0
    property bool visualGalleryMode: true

    // Lightbox / Visualizer state
    property bool lightboxVisible: false
    property int lightboxIndex: -1
    property var lightboxItem: null

    anchors.fill: parent
    visible: opacity > 0.001
    opacity: isOpen ? 1.0 : 0.0
    z: 9999
    focus: true

    Behavior on opacity {
        NumberAnimation {
            duration: modalRoot.isOpen ? 240 : 180
            easing.type: Easing.OutCubic
        }
    }

    Keys.onEscapePressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.closeLightbox()
            event.accepted = true
        } else if (modalRoot.isInspecting) {
            modalRoot.backToPosts()
            event.accepted = true
        } else if (modalRoot.isOpen) {
            modalRoot.closeModal()
            event.accepted = true
        }
    }

    Keys.onLeftPressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.prevLightboxItem()
            event.accepted = true
        }
    }

    Keys.onRightPressed: function(event) {
        if (modalRoot.lightboxVisible) {
            modalRoot.nextLightboxItem()
            event.accepted = true
        }
    }

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function isImageFile(name, path, url) {
        var str = ((url || "") + " " + (path || "") + " " + (name || "")).toLowerCase()
        if (!str.trim()) return false
        if (str.indexOf(".mp4") !== -1 || str.indexOf(".mkv") !== -1 || str.indexOf(".webm") !== -1 ||
            str.indexOf(".mov") !== -1 || str.indexOf(".avi") !== -1 || str.indexOf(".wmv") !== -1 ||
            str.indexOf(".flv") !== -1 || str.indexOf(".m4v") !== -1 || str.indexOf(".zip") !== -1 ||
            str.indexOf(".rar") !== -1 || str.indexOf(".7z") !== -1 || str.indexOf(".tar") !== -1 ||
            str.indexOf(".gz") !== -1 || str.indexOf(".pdf") !== -1 || str.indexOf(".mp3") !== -1 ||
            str.indexOf(".wav") !== -1 || str.indexOf(".flac") !== -1 || str.indexOf(".ogg") !== -1) {
            return false
        }
        return str.indexOf(".png") !== -1 || str.indexOf(".jpg") !== -1 ||
               str.indexOf(".jpeg") !== -1 || str.indexOf(".webp") !== -1 ||
               str.indexOf(".gif") !== -1 || str.indexOf(".bmp") !== -1 ||
               str.indexOf(".avif") !== -1
    }

    function openModal(posts, creator, totalCount) {
        creatorName = creator || ""
        inspectedPost = null
        lightboxVisible = false
        lightboxIndex = -1
        lightboxItem = null

        var list = []
        if (posts && posts.length) {
            for (var i = 0; i < posts.length; i++) {
                var p = posts[i]
                var filesList = []
                if (p.files && p.files.length) {
                    for (var f = 0; f < p.files.length; f++) {
                        var fileItem = p.files[f]
                        var thumbUrl = fileItem.thumbnail || ""
                        var prevUrl = fileItem.previewUrl || thumbUrl
                        if (prevUrl && prevUrl.indexOf("/thumbnail/data/") === -1 && prevUrl.indexOf("/data/") !== -1) {
                            prevUrl = prevUrl.replace("/data/", "/thumbnail/data/")
                        }
                        if (thumbUrl && thumbUrl.indexOf("/thumbnail/data/") === -1 && thumbUrl.indexOf("/data/") !== -1) {
                            thumbUrl = thumbUrl.replace("/data/", "/thumbnail/data/")
                        }
                        filesList.push({
                            name: fileItem.name || "attachment",
                            path: fileItem.path || "",
                            thumbnail: thumbUrl,
                            previewUrl: prevUrl,
                            is_main: !!fileItem.is_main,
                            selected: fileItem.selected !== undefined ? !!fileItem.selected : true
                        })
                    }
                }
                var totalF = filesList.length || p.fileCount || 0
                var selF = 0
                if (filesList.length > 0) {
                    for (var sf = 0; sf < filesList.length; sf++) {
                        if (filesList[sf].selected) selF++
                    }
                } else {
                    selF = p.selected !== false ? totalF : 0
                }
                var isPostSel = (selF > 0) && (p.selected !== false)
                var pThumb = p.thumbnail || ""
                if (pThumb && pThumb.indexOf("/thumbnail/data/") === -1 && pThumb.indexOf("/data/") !== -1) {
                    pThumb = pThumb.replace("/data/", "/thumbnail/data/")
                }
                list.push({
                    id: p.id || "",
                    title: p.title || "Untitled Post",
                    content: p.content || "",
                    published: p.published || "",
                    thumbnail: pThumb,
                    fileCount: totalF,
                    selectedFileCount: selF,
                    files: filesList,
                    selected: isPostSel
                })
            }
        }
        allPosts = list
        searchFilter = ""
        searchInput.text = ""
        updateFilteredPosts()
        updateTotals()
        isOpen = true
    }

    function closeModal() {
        isOpen = false
        inspectedPost = null
        lightboxVisible = false
    }

    function inspectPost(postId) {
        for (var i = 0; i < allPosts.length; i++) {
            if (allPosts[i].id === postId) {
                inspectedPost = allPosts[i]
                postFilesModel.clear()
                var selInPost = 0
                for (var f = 0; f < allPosts[i].files.length; f++) {
                    var fitem = allPosts[i].files[f]
                    postFilesModel.append(fitem)
                    if (fitem.selected) selInPost++
                }
                selectedFilesInPost = selInPost
                break
            }
        }
    }

    function backToPosts() {
        inspectedPost = null
        lightboxVisible = false
    }

    function updateTotals() {
        var selP = 0
        var totalF = 0
        var selF = 0
        for (var i = 0; i < allPosts.length; i++) {
            var p = allPosts[i]
            var nFiles = (p.files && p.files.length) ? p.files.length : (p.fileCount || 0)
            totalF += nFiles

            var pSelF = 0
            if (p.files && p.files.length) {
                for (var f = 0; f < p.files.length; f++) {
                    if (p.files[f].selected) pSelF++
                }
            } else if (p.selected) {
                pSelF = nFiles
            }

            selF += pSelF
            p.selectedFileCount = pSelF
            p.selected = (pSelF > 0)
            if (p.selected) selP++
        }

        selectedCount = selP
        totalFilesCount = totalF
        totalSelectedFiles = selF

        if (inspectedPost && inspectedPost.files) {
            var curSel = 0
            for (var k = 0; k < inspectedPost.files.length; k++) {
                if (inspectedPost.files[k].selected) curSel++
            }
            selectedFilesInPost = curSel
        }
    }

    function updateFilteredPosts() {
        var query = searchFilter.trim().toLowerCase()
        var out = []
        for (var i = 0; i < allPosts.length; i++) {
            var item = allPosts[i]
            if (!query) {
                out.push(item)
            } else {
                var matchTitle = item.title && item.title.toLowerCase().indexOf(query) !== -1
                var matchDate = item.published && item.published.toLowerCase().indexOf(query) !== -1
                if (matchTitle || matchDate) {
                    out.push(item)
                }
            }
        }
        filteredPosts = out
        postsModel.clear()
        for (var j = 0; j < out.length; j++) {
            postsModel.append(out[j])
        }
        updateTotals()
    }

    function toggleItem(index) {
        if (index < 0 || index >= postsModel.count) return
        var current = postsModel.get(index).selected
        var targetState = !current
        postsModel.setProperty(index, "selected", targetState)

        var id = postsModel.get(index).id
        for (var i = 0; i < allPosts.length; i++) {
            if (allPosts[i].id === id) {
                allPosts[i].selected = targetState
                if (allPosts[i].files) {
                    for (var f = 0; f < allPosts[i].files.length; f++) {
                        allPosts[i].files[f].selected = targetState
                    }
                }
                var newSelF = targetState ? allPosts[i].files.length : 0
                allPosts[i].selectedFileCount = newSelF
                postsModel.setProperty(index, "selectedFileCount", newSelF)
                break
            }
        }
        updateTotals()
    }

    function toggleFileItem(index) {
        if (!inspectedPost || index < 0 || index >= postFilesModel.count) return
        var cur = postFilesModel.get(index).selected
        var nextState = !cur
        postFilesModel.setProperty(index, "selected", nextState)
        if (inspectedPost.files && inspectedPost.files[index]) {
            inspectedPost.files[index].selected = nextState
        }

        var selFiles = 0
        for (var f = 0; f < inspectedPost.files.length; f++) {
            if (inspectedPost.files[f].selected) selFiles++
        }
        inspectedPost.selectedFileCount = selFiles
        inspectedPost.selected = (selFiles > 0)
        selectedFilesInPost = selFiles

        for (var j = 0; j < postsModel.count; j++) {
            if (String(postsModel.get(j).id) === String(inspectedPost.id)) {
                postsModel.setProperty(j, "selected", inspectedPost.selected)
                postsModel.setProperty(j, "selectedFileCount", selFiles)
                break
            }
        }

        // Keep lightbox sync
        if (lightboxVisible && lightboxIndex === index) {
            lightboxItem = null
            lightboxItem = postFilesModel.get(index)
        }

        updateTotals()
    }

    function selectAllFilesInPost(val) {
        if (!inspectedPost) return
        for (var i = 0; i < postFilesModel.count; i++) {
            postFilesModel.setProperty(i, "selected", val)
            if (inspectedPost.files && inspectedPost.files[i]) {
                inspectedPost.files[i].selected = val
            }
        }
        var selFiles = val ? postFilesModel.count : 0
        inspectedPost.selectedFileCount = selFiles
        inspectedPost.selected = (selFiles > 0)
        selectedFilesInPost = selFiles

        for (var j = 0; j < postsModel.count; j++) {
            if (String(postsModel.get(j).id) === String(inspectedPost.id)) {
                postsModel.setProperty(j, "selected", (selFiles > 0))
                postsModel.setProperty(j, "selectedFileCount", selFiles)
                break
            }
        }
        updateTotals()
    }

    function selectAll(val) {
        for (var i = 0; i < allPosts.length; i++) {
            allPosts[i].selected = val
            if (allPosts[i].files) {
                for (var f = 0; f < allPosts[i].files.length; f++) {
                    allPosts[i].files[f].selected = val
                }
                allPosts[i].selectedFileCount = val ? allPosts[i].files.length : 0
            }
        }
        for (var j = 0; j < postsModel.count; j++) {
            postsModel.setProperty(j, "selected", val)
            var curF = postsModel.get(j).fileCount || 0
            postsModel.setProperty(j, "selectedFileCount", val ? curF : 0)
        }
        updateTotals()
    }

    function getSelectedPostIds() {
        var ids = []
        for (var i = 0; i < allPosts.length; i++) {
            if (allPosts[i].selected) {
                ids.push(String(allPosts[i].id))
            }
        }
        return ids
    }

    function getSelectedFilesMap() {
        var map = {}
        for (var i = 0; i < allPosts.length; i++) {
            var p = allPosts[i]
            if (p.selected && p.files && p.files.length) {
                var selectedFilePaths = []
                var allSelected = true
                for (var f = 0; f < p.files.length; f++) {
                    if (p.files[f].selected) {
                        selectedFilePaths.push(p.files[f].path)
                    } else {
                        allSelected = false
                    }
                }
                if (!allSelected) {
                    map[String(p.id)] = selectedFilePaths
                }
            }
        }
        return map
    }

    // ── Lightbox Visualizer Methods ──────────────────────────────
    function openLightbox(index) {
        if (index < 0 || index >= postFilesModel.count) return
        lightboxIndex = index
        lightboxItem = postFilesModel.get(index)
        lightboxVisible = true
    }

    function closeLightbox() {
        lightboxVisible = false
        lightboxIndex = -1
        lightboxItem = null
    }

    function prevLightboxItem() {
        if (!lightboxVisible || postFilesModel.count === 0) return
        var prevIdx = lightboxIndex - 1
        if (prevIdx < 0) prevIdx = postFilesModel.count - 1
        openLightbox(prevIdx)
    }

    function nextLightboxItem() {
        if (!lightboxVisible || postFilesModel.count === 0) return
        var nextIdx = lightboxIndex + 1
        if (nextIdx >= postFilesModel.count) nextIdx = 0
        openLightbox(nextIdx)
    }

    ListModel {
        id: postsModel
    }

    ListModel {
        id: postFilesModel
    }

    // Semi-transparent backdrop overlay
    Rectangle {
        anchors.fill: parent
        color: "#05070B"
        opacity: 0.75

        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (modalRoot.lightboxVisible) modalRoot.closeLightbox()
                else modalRoot.closeModal()
            }
        }

        // Block wheel events from reaching background scrollables
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) { event.accepted = true }
        }
    }

    // Centered Dialog Window with Newtonian Spring Entrance
    Rectangle {
        id: dialogBox
        width: Math.min(modalRoot.width - 40, 1040)
        height: Math.min(modalRoot.height - 40, 720)
        anchors.centerIn: parent
        radius: 12
        color: "#0F131C"
        border.color: "#222B3D"
        border.width: 1

        scale: modalRoot.isOpen ? 1.0 : 0.88
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation {
                duration: modalRoot.isOpen ? 340 : 200
                easing.type: modalRoot.isOpen ? Easing.OutBack : Easing.InCubic
                easing.overshoot: 1.3
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ── Header Row ───────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Back Button (when inspecting a single post)
                Rectangle {
                    visible: modalRoot.isInspecting
                    height: 32
                    implicitWidth: backRow.implicitWidth + 16
                    radius: 6
                    color: backMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: backMouse.containsMouse ? "#38BDF8" : "#2D3748"
                    scale: backMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: backRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "←"; font.pixelSize: 13; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_back_to_posts", "Back to Posts")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: backMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.backToPosts()
                    }
                }

                Text {
                    visible: !modalRoot.isInspecting
                    text: "🖼️"
                    font.pixelSize: 18
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    RowLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        Text {
                            text: modalRoot.isInspecting
                                ? (modalRoot.inspectedPost ? modalRoot.inspectedPost.title : "")
                                : modalRoot.tr("title_post_selector", "Select Posts to Download")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        // Creator name or date badge
                        Rectangle {
                            height: 20
                            radius: 4
                            color: "#1E293B"
                            border.color: "#334155"
                            implicitWidth: badgeRowText.implicitWidth + 12

                            Row {
                                id: badgeRowText
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    text: modalRoot.isInspecting
                                        ? ("📅 " + (modalRoot.inspectedPost ? modalRoot.inspectedPost.published : ""))
                                        : (modalRoot.creatorName.length > 0 ? modalRoot.creatorName : "Pawchive")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: 600
                                    color: "#38BDF8"
                                }
                            }
                        }

                        // Files in Post Selection Pill (when inspecting)
                        Rectangle {
                            visible: modalRoot.isInspecting
                            height: 20
                            radius: 4
                            color: modalRoot.selectedFilesInPost > 0 ? "#0C2A3D" : "#2A181A"
                            border.color: modalRoot.selectedFilesInPost > 0 ? "#0284C7" : "#DC2626"
                            implicitWidth: inspectSelPillText.implicitWidth + 12

                            Text {
                                id: inspectSelPillText
                                anchors.centerIn: parent
                                text: modalRoot.selectedFilesInPost + " / " + postFilesModel.count + " files selected"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: modalRoot.selectedFilesInPost > 0 ? "#38BDF8" : "#F87171"
                            }
                        }
                    }

                    Text {
                        text: modalRoot.isInspecting
                            ? modalRoot.tr("label_inspect_files_subtitle", "Inspect attachments and toggle individual files to download.")
                            : modalRoot.tr("post_selector_subtitle", "Choose specific posts to download or filter visually by thumbnail.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                // Close Button ✕
                Rectangle {
                    width: 28
                    height: 28
                    radius: 6
                    color: closeMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: closeMouse.pressed ? 0.92 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 11
                        color: closeMouse.containsMouse ? "#F87171" : "#94A3B8"
                    }

                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeModal()
                    }
                }
            }

            // ── Search & Bulk Selection Bar (only when not inspecting) ─────
            RowLayout {
                visible: !modalRoot.isInspecting
                Layout.fillWidth: true
                spacing: 8

                // Search Input Field
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: 6
                    color: "#0B0E14"
                    border.color: searchInput.activeFocus ? "#38BDF8" : "#1E293B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text { text: "🔍"; font.pixelSize: 11; color: "#64748B" }

                        TextInput {
                            id: searchInput
                            Layout.fillWidth: true
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#E2E8F0"
                            clip: true
                            selectByMouse: true

                            Text {
                                text: modalRoot.tr("placeholder_search_posts", "Search posts by title or date...")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#475569"
                                visible: !searchInput.text && !searchInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            onTextChanged: {
                                modalRoot.searchFilter = text
                                modalRoot.updateFilteredPosts()
                            }
                        }

                        Text {
                            visible: searchInput.text.length > 0
                            text: "✕"
                            font.pixelSize: 11
                            color: "#64748B"
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: searchInput.text = ""
                            }
                        }
                    }
                }

                // Select All Button
                Rectangle {
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: Math.max(116, selAllRow.implicitWidth + 28)
                    radius: 6
                    color: selAllMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: selAllMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: selAllRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: selAllText
                            text: modalRoot.tr("btn_select_all", "Select All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: selAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.selectAll(true)
                    }
                }

                // Deselect All Button
                Rectangle {
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: Math.max(126, deselAllRow.implicitWidth + 28)
                    radius: 6
                    color: deselAllMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: deselAllMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: deselAllRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: deselAllText
                            text: modalRoot.tr("btn_deselect_all", "Deselect All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: deselAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.selectAll(false)
                    }
                }
            }

            // ── Main Content Area (Swap between Grid and Inspector View) ──
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                // 1. Grid of Post Cards (When not inspecting)
                Rectangle {
                    id: gridPanel
                    anchors.fill: parent
                    radius: 8
                    color: "#0B0E14"
                    border.color: "#1E293B"
                    clip: true
                    visible: !modalRoot.isInspecting
                    opacity: modalRoot.isInspecting ? 0.0 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    GridView {
                        id: postsGrid
                        anchors.fill: parent
                        anchors.margins: 10
                        clip: true
                        model: postsModel

                        readonly property int colCount: Math.max(1, Math.floor(width / 215))
                        cellWidth: Math.floor(width / colCount)
                        cellHeight: 210
                        boundsBehavior: Flickable.StopAtBounds

                        property real _targetY: 0
                        property real _lastWheelTime: 0
                        property real _wheelVelocity: 1.0

                        NumberAnimation {
                            id: postsGridWheelAnim
                            target: postsGrid
                            property: "contentY"
                            duration: 170
                            easing.type: Easing.OutQuad
                        }

                        WheelHandler {
                            target: null
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: function(event) {
                                var now = Date.now()
                                var dt = now - postsGrid._lastWheelTime
                                postsGrid._lastWheelTime = now
                                if (dt < 130) postsGrid._wheelVelocity = Math.min(2.8, postsGrid._wheelVelocity + 0.4)
                                else postsGrid._wheelVelocity = 1.0
                                var delta = event.angleDelta.y
                                if (delta === 0) return
                                var step = (delta / 120.0) * 120 * postsGrid._wheelVelocity
                                var maxY = Math.max(0, postsGrid.contentHeight - postsGrid.height)
                                if (!postsGridWheelAnim.running) postsGrid._targetY = postsGrid.contentY
                                postsGrid._targetY = Math.max(0, Math.min(maxY, postsGrid._targetY - step))
                                postsGridWheelAnim.stop()
                                postsGridWheelAnim.from = postsGrid.contentY
                                postsGridWheelAnim.to = postsGrid._targetY
                                postsGridWheelAnim.start()
                                event.accepted = true
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            id: postsGridScrollBar
                            active: postsGrid.moving || postsGrid.flicking || postsGridScrollHover.hovered
                            policy: ScrollBar.AsNeeded
                            width: 7
                            HoverHandler { id: postsGridScrollHover }
                            contentItem: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: postsGridScrollBar.pressed ? "#38BDF8" : (postsGridScrollBar.hovered ? "#0EA5E9" : (postsGridScrollBar.active ? "#38BDF8" : "#64748B"))
                                opacity: postsGridScrollBar.active ? 0.85 : (postsGrid.contentHeight > postsGrid.height ? 0.35 : 0.0)
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                            background: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: "#0F172A"
                                opacity: postsGrid.contentHeight > postsGrid.height ? 0.25 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                            }
                        }

                        delegate: Item {
                            width: postsGrid.cellWidth
                            height: postsGrid.cellHeight

                            Rectangle {
                                id: postCard
                                anchors.fill: parent
                                anchors.margins: 6
                                radius: 8
                                color: model.selected ? "#141E2F" : "#10141D"
                                border.color: model.selected ? "#38BDF8" : (cardMouse.containsMouse ? "#334155" : "#1C2433")
                                border.width: model.selected ? 1.5 : 1

                                scale: cardMouse.pressed ? 0.96 : (cardMouse.containsMouse ? 1.02 : 1.0)
                                transformOrigin: Item.Center
                                Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }
                                Behavior on color { ColorAnimation { duration: 140 } }
                                Behavior on border.color { ColorAnimation { duration: 140 } }

                                // Card Click: Inspects the post (FIRST child = behind ColumnLayout)
                                MouseArea {
                                    id: cardMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: modalRoot.inspectPost(model.id)
                                }

                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 0

                                    // Thumbnail Container
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        color: "#080B11"
                                        radius: 7
                                        clip: true

                                        // Fallback icon
                                        Rectangle {
                                            anchors.fill: parent
                                            color: "#0E131E"
                                            visible: postThumb.status !== Image.Ready
                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 4
                                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🖼️"; font.pixelSize: 22 }
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: (model.fileCount || 0) + " files"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#475569"
                                                }
                                            }
                                        }

                                        Image {
                                            id: postThumb
                                            anchors.fill: parent
                                            source: (modalRoot.isImageFile(model.title, "", model.thumbnail) ? (model.thumbnail || "") : "")
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            cache: true
                                            opacity: status === Image.Ready ? 1.0 : 0.0
                                            Behavior on opacity { NumberAnimation { duration: 180 } }
                                        }

                                        // Gradient shadow at bottom of image
                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.bottom: parent.bottom
                                            height: 28
                                            gradient: Gradient {
                                                GradientStop { position: 0.0; color: "transparent" }
                                                GradientStop { position: 1.0; color: "#99000000" }
                                            }
                                        }

                                        // Selected Files / Total Files Count Badge (top-left)
                                        Rectangle {
                                            anchors.top: parent.top
                                            anchors.left: parent.left
                                            anchors.margins: 6
                                            height: 20
                                            implicitWidth: fileBadgeText.implicitWidth + 10
                                            radius: 4
                                            color: {
                                                var selF = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                var totF = model.fileCount || 0
                                                if (selF === totF && totF > 0) return "#CC0A2338"
                                                if (selF > 0) return "#CC341D09"
                                                return "#CC0A0E17"
                                            }
                                            border.color: {
                                                var selF2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                var totF2 = model.fileCount || 0
                                                if (selF2 === totF2 && totF2 > 0) return "#0284C7"
                                                if (selF2 > 0) return "#D97706"
                                                return "#2D3748"
                                            }

                                            Row {
                                                id: fileBadgeText
                                                anchors.centerIn: parent
                                                spacing: 3
                                                Text { text: "📎"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Text {
                                                    text: {
                                                        var s = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                        var t = model.fileCount || 0
                                                        return s + " / " + t + " files"
                                                    }
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: {
                                                        var s2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                                        var t2 = model.fileCount || 0
                                                        if (s2 === t2 && t2 > 0) return "#38BDF8"
                                                        if (s2 > 0) return "#FBBF24"
                                                        return "#94A3B8"
                                                    }
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                            }
                                        }

                                        // Selection checkbox badge (top-right) with Newtonian bounce
                                        Rectangle {
                                            id: checkBadge
                                            anchors.top: parent.top
                                            anchors.right: parent.right
                                            anchors.margins: 6
                                            width: 26
                                            height: 26
                                            radius: 6
                                            color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#1A3A58" : "#990A0E17")
                                            border.color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#38BDF8" : "#475569")
                                            border.width: 1.5

                                            scale: model.selected ? 1.0 : (checkMouse.containsMouse ? 1.0 : 0.9)
                                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
                                            Behavior on color { ColorAnimation { duration: 100 } }
                                            Behavior on border.color { ColorAnimation { duration: 100 } }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                font.pixelSize: 13
                                                font.weight: Font.Bold
                                                color: "#0A0E17"
                                                visible: model.selected
                                            }

                                            MouseArea {
                                                id: checkMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: function(mouse) {
                                                    mouse.accepted = true
                                                    modalRoot.toggleItem(index)
                                                }
                                            }
                                        }

                                        // Inspect hover badge (bottom-right of thumbnail)
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            anchors.right: parent.right
                                            anchors.margins: 6
                                            height: 20
                                            implicitWidth: inspectPillText.implicitWidth + 10
                                            radius: 4
                                            color: cardMouse.containsMouse ? "#0284C7" : "#B30F172A"
                                            border.color: "#38BDF8"
                                            visible: cardMouse.containsMouse || (model.fileCount > 1)

                                            Row {
                                                id: inspectPillText
                                                anchors.centerIn: parent
                                                spacing: 3
                                                Text { text: "🔍"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                                Text {
                                                    text: modalRoot.tr("btn_inspect_card", "Inspect")
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 9
                                                    font.weight: Font.Bold
                                                    color: "#FFFFFF"
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                            }
                                        }
                                    }

                                    // Card Footer (Title & Published Date)
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 52
                                        color: "transparent"

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 6
                                            spacing: 2

                                            Text {
                                                text: model.title || "Untitled"
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                                color: model.selected ? "#F1F5F9" : "#94A3B8"
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            RowLayout {
                                                spacing: 4
                                                Text { text: "📅"; font.pixelSize: 9; color: "#64748B" }
                                                Text {
                                                    text: model.published || "Unknown"
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#64748B"
                                                    Layout.fillWidth: true
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Empty state indicator
                    Column {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: postsModel.count === 0

                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🔍"; font.pixelSize: 28 }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modalRoot.tr("no_matching_posts", "No posts match your search.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 13
                            color: "#64748B"
                        }
                    }
                }

                // 2. Detail Inspector Panel (When inspecting a single post)
                Rectangle {
                    id: detailPanel
                    anchors.fill: parent
                    radius: 8
                    color: "#0B0E14"
                    border.color: "#1E293B"
                    clip: true
                    visible: modalRoot.isInspecting
                    opacity: modalRoot.isInspecting ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    Flickable {
                        id: inspectorFlickable
                        anchors.fill: parent
                        anchors.margins: 14
                        contentWidth: width
                        contentHeight: detailCol.implicitHeight + 30
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        property real _targetY: 0
                        property real _lastWheelTime: 0
                        property real _wheelVelocity: 1.0

                        onMovingChanged: {
                            if (moving) {
                                inspectorWheelAnim.stop()
                                _targetY = contentY
                            }
                        }

                        NumberAnimation {
                            id: inspectorWheelAnim
                            target: inspectorFlickable
                            property: "contentY"
                            duration: 170
                            easing.type: Easing.OutQuad
                        }

                        WheelHandler {
                            target: null
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: function(event) {
                                var now = Date.now()
                                var dt = now - inspectorFlickable._lastWheelTime
                                inspectorFlickable._lastWheelTime = now
                                if (dt < 130) inspectorFlickable._wheelVelocity = Math.min(2.8, inspectorFlickable._wheelVelocity + 0.4)
                                else inspectorFlickable._wheelVelocity = 1.0
                                var delta = event.angleDelta.y
                                if (delta === 0) return
                                var step = (delta / 120.0) * 120 * inspectorFlickable._wheelVelocity
                                var maxY = Math.max(0, inspectorFlickable.contentHeight - inspectorFlickable.height)
                                if (!inspectorWheelAnim.running) inspectorFlickable._targetY = inspectorFlickable.contentY
                                inspectorFlickable._targetY = Math.max(0, Math.min(maxY, inspectorFlickable._targetY - step))
                                inspectorWheelAnim.stop()
                                inspectorWheelAnim.from = inspectorFlickable.contentY
                                inspectorWheelAnim.to = inspectorFlickable._targetY
                                inspectorWheelAnim.start()
                                event.accepted = true
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            id: inspectorScrollBar
                            active: inspectorFlickable.moving || inspectorFlickable.flicking || inspectorWheelAnim.running || inspectorScrollHover.hovered
                            policy: ScrollBar.AsNeeded
                            width: 7
                            HoverHandler { id: inspectorScrollHover }
                            contentItem: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: inspectorScrollBar.pressed ? "#38BDF8" : (inspectorScrollBar.hovered ? "#0EA5E9" : (inspectorScrollBar.active ? "#38BDF8" : "#64748B"))
                                opacity: inspectorScrollBar.active ? 0.85 : (inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.35 : 0.0)
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
                            background: Rectangle {
                                implicitWidth: 7
                                radius: 3
                                color: "#0F172A"
                                opacity: inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.25 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 180 } }
                            }
                        }

                        ColumnLayout {
                            id: detailCol
                            width: parent.width
                            spacing: 14

                            // Description & Content Card (if available)
                            Rectangle {
                                visible: modalRoot.inspectedPost && modalRoot.inspectedPost.content && modalRoot.inspectedPost.content.length > 0
                                Layout.fillWidth: true
                                implicitHeight: descCol.implicitHeight + 20
                                radius: 8
                                color: "#10141D"
                                border.color: "#1E293B"
                                border.width: 1

                                ColumnLayout {
                                    id: descCol
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 6

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: "📝"; font.pixelSize: 12 }
                                        Text {
                                            text: modalRoot.tr("label_post_description", "Post Description & Notes")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                            color: "#94A3B8"
                                            Layout.fillWidth: true
                                        }
                                    }

                                    TextEdit {
                                        Layout.fillWidth: true
                                        text: modalRoot.inspectedPost ? modalRoot.inspectedPost.content : ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        color: "#E2E8F0"
                                        wrapMode: TextEdit.Wrap
                                        readOnly: true
                                        selectByMouse: true
                                    }
                                }
                            }

                            // Attached Media & Files Header + Action Buttons + View Mode Switcher
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text { text: "📎"; font.pixelSize: 13 }
                                Text {
                                    text: modalRoot.tr("label_attached_files", "Attached Media & Files") + " (" + postFilesModel.count + ")"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.Bold
                                    color: "#F1F5F9"
                                    Layout.fillWidth: true
                                }

                                // View Switcher: Gallery Mode vs List Mode (Physical Newtonian Spring Slider)
                                Rectangle {
                                    id: viewSwitchContainer
                                    height: 28
                                    width: 68
                                    radius: 6
                                    color: "#161D2B"
                                    border.color: "#2D3748"

                                    // Sliding Physical Indicator Pill (Newtonian spring glide)
                                    Rectangle {
                                        id: viewSwitchIndicator
                                        y: 3
                                        x: modalRoot.visualGalleryMode ? 3 : 35
                                        width: 30
                                        height: 22
                                        radius: 4
                                        color: "#0284C7"
                                        scale: (gridSwitchMouse.pressed || listSwitchMouse.pressed) ? 0.91 : 1.0

                                        Behavior on x {
                                            SpringAnimation {
                                                spring: 4.8
                                                damping: 0.40
                                                mass: 1.05
                                                epsilon: 0.2
                                            }
                                        }
                                        Behavior on scale {
                                            SpringAnimation {
                                                spring: 4.5
                                                damping: 0.35
                                                mass: 1.0
                                            }
                                        }
                                    }

                                    Row {
                                        anchors.fill: parent
                                        anchors.margins: 3
                                        spacing: 2

                                        // Grid Mode Option
                                        Item {
                                            width: 30
                                            height: 22
                                            Text {
                                                anchors.centerIn: parent
                                                text: "🖼️"
                                                font.pixelSize: 11
                                                scale: modalRoot.visualGalleryMode ? 1.08 : 0.95
                                                opacity: modalRoot.visualGalleryMode ? 1.0 : 0.65
                                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                            }
                                            MouseArea {
                                                id: gridSwitchMouse
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: modalRoot.visualGalleryMode = true
                                            }
                                        }

                                        // List Mode Option
                                        Item {
                                            width: 30
                                            height: 22
                                            Text {
                                                anchors.centerIn: parent
                                                text: "📋"
                                                font.pixelSize: 11
                                                scale: !modalRoot.visualGalleryMode ? 1.08 : 0.95
                                                opacity: !modalRoot.visualGalleryMode ? 1.0 : 0.65
                                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                            }
                                            MouseArea {
                                                id: listSwitchMouse
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: modalRoot.visualGalleryMode = false
                                            }
                                        }
                                    }
                                }

                                // Select All Files
                                Rectangle {
                                    Layout.preferredHeight: 30
                                    Layout.preferredWidth: Math.max(108, selAllFilesRow.implicitWidth + 26)
                                    radius: 6
                                    color: selAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                                    border.color: "#2D3748"
                                    scale: selAllFilesMouse.pressed ? 0.94 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                                    Row {
                                        id: selAllFilesRow
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                                        Text {
                                            id: selAllFilesText
                                            text: modalRoot.tr("btn_select_all", "Select All")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#CBD5E1"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    MouseArea {
                                        id: selAllFilesMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: modalRoot.selectAllFilesInPost(true)
                                    }
                                }

                                // Deselect All Files
                                Rectangle {
                                    Layout.preferredHeight: 30
                                    Layout.preferredWidth: Math.max(118, deselAllFilesRow.implicitWidth + 26)
                                    radius: 6
                                    color: deselAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                                    border.color: "#2D3748"
                                    scale: deselAllFilesMouse.pressed ? 0.94 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                                    Row {
                                        id: deselAllFilesRow
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                                        Text {
                                            id: deselAllFilesText
                                            text: modalRoot.tr("btn_deselect_all", "Deselect All")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: 600
                                            color: "#CBD5E1"
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                    MouseArea {
                                        id: deselAllFilesMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: modalRoot.selectAllFilesInPost(false)
                                    }
                                }
                            }

                            // ── View Mode Container with Newtonian Weight-Based Transitions ──
                            Item {
                                id: viewModeContainer
                                Layout.fillWidth: true
                                implicitHeight: modalRoot.visualGalleryMode ? galleryViewWrap.implicitHeight : listViewWrap.implicitHeight

                                Behavior on implicitHeight {
                                    NumberAnimation {
                                        duration: 280
                                        easing.type: Easing.OutCubic
                                    }
                                }

                                // ── 1. Visual Gallery Mode (Responsive Grid with Physical Weight) ──
                                Item {
                                    id: galleryViewWrap
                                    width: parent.width
                                    implicitHeight: Math.max(40, galleryFlow.childrenRect.height)
                                    opacity: modalRoot.visualGalleryMode ? 1.0 : 0.0
                                    y: modalRoot.visualGalleryMode ? 0 : -14
                                    scale: modalRoot.visualGalleryMode ? 1.0 : 0.965
                                    transformOrigin: Item.Top
                                    visible: opacity > 0.001

                                    Behavior on opacity {
                                        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                    }
                                    Behavior on y {
                                        SpringAnimation {
                                            spring: 3.6
                                            damping: 0.38
                                            mass: 1.15
                                            epsilon: 0.25
                                        }
                                    }
                                    Behavior on scale {
                                        SpringAnimation {
                                            spring: 3.8
                                            damping: 0.36
                                            mass: 1.10
                                            epsilon: 0.005
                                        }
                                    }

                                    Flow {
                                        id: galleryFlow
                                        width: parent.width
                                        spacing: 10

                                        Repeater {
                                    model: postFilesModel

                                    delegate: Rectangle {
                                        width: 175
                                        height: 185
                                        radius: 8
                                        color: model.selected ? "#141E2F" : "#10141D"
                                        border.color: model.selected ? "#38BDF8" : (galMouse.containsMouse ? "#334155" : "#1C2433")
                                        border.width: model.selected ? 1.5 : 1

                                        scale: galMouse.pressed ? 0.96 : (galMouse.containsMouse ? 1.03 : 1.0)
                                        transformOrigin: Item.Center
                                        Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                        // Background click area (z:0, behind everything) - toggles selection
                                        MouseArea {
                                            id: galMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            z: 0
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: modalRoot.toggleFileItem(index)
                                        }

                                        ColumnLayout {
                                            anchors.fill: parent
                                            spacing: 0
                                            z: 1

                                            // Large Image / Media Preview
                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                radius: 7
                                                color: "#080B11"
                                                clip: true

                                                // Media icon fallback
                                                Rectangle {
                                                    anchors.fill: parent
                                                    color: "#0D111A"
                                                    visible: galThumb.status !== Image.Ready
                                                    Column {
                                                        anchors.centerIn: parent
                                                        spacing: 4
                                                        Text {
                                                            anchors.horizontalCenter: parent.horizontalCenter
                                                            text: {
                                                                var fn = (model.name || "").toLowerCase()
                                                                if (fn.endsWith(".zip") || fn.endsWith(".rar") || fn.endsWith(".7z")) return "📦"
                                                                if (fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov")) return "🎥"
                                                                if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".flac") || fn.endsWith(".m4a")) return "🎵"
                                                                return "🖼️"
                                                            }
                                                            font.pixelSize: 28
                                                        }
                                                        Text {
                                                            anchors.horizontalCenter: parent.horizontalCenter
                                                            text: "File #" + (index + 1)
                                                            font.pixelSize: 9
                                                            color: "#64748B"
                                                        }
                                                    }
                                                }

                                                Image {
                                                    id: galThumb
                                                    anchors.fill: parent
                                                    source: (modalRoot.isImageFile(model.name, model.path, model.previewUrl || model.thumbnail) ? (model.previewUrl || model.thumbnail || "") : "")
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    cache: true
                                                    opacity: status === Image.Ready ? 1.0 : 0.0
                                                    Behavior on opacity { NumberAnimation { duration: 180 } }
                                                }

                                                // Top-Left Format Pill
                                                Rectangle {
                                                    anchors.top: parent.top
                                                    anchors.left: parent.left
                                                    anchors.margins: 5
                                                    height: 18
                                                    implicitWidth: galFormatText.implicitWidth + 8
                                                    radius: 3
                                                    color: "#CC080C14"
                                                    border.color: "#334155"

                                                    Text {
                                                        id: galFormatText
                                                        anchors.centerIn: parent
                                                        text: {
                                                            var parts = (model.name || model.path || "").split(".")
                                                            return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE"
                                                        }
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                        color: "#E2E8F0"
                                                    }
                                                }

                                                // Top-Right Checkbox (Direct Toggle, z:3)
                                                Rectangle {
                                                    anchors.top: parent.top
                                                    anchors.right: parent.right
                                                    anchors.margins: 5
                                                    width: 24
                                                    height: 24
                                                    radius: 5
                                                    z: 3
                                                    color: model.selected ? "#38BDF8" : "#99080C14"
                                                    border.color: model.selected ? "#38BDF8" : "#475569"
                                                    border.width: 1

                                                    scale: model.selected ? 1.0 : 0.92
                                                    Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✓"
                                                        font.pixelSize: 13
                                                        font.weight: Font.Bold
                                                        color: "#0A0E17"
                                                        visible: model.selected
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: function(mouse) {
                                                            mouse.accepted = true
                                                            modalRoot.toggleFileItem(index)
                                                        }
                                                    }
                                                }

                                                // Hover Zoom / Expand Badge (bottom-right, clickable for Lightbox)
                                                Rectangle {
                                                    id: expandBadgeRect
                                                    objectName: "expandBadgeRect"
                                                    anchors.bottom: parent.bottom
                                                    anchors.right: parent.right
                                                    anchors.margins: 5
                                                    height: 22
                                                    implicitWidth: expandPillText.implicitWidth + 12
                                                    radius: 4

                                                    // Detect if this file is a video
                                                    readonly property bool isVideo: {
                                                        var fn = (model.name || "").toLowerCase()
                                                        return fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov") || fn.endsWith(".avi") || fn.endsWith(".m4v")
                                                    }

                                                    color: isVideo ? "#1A0F00" : (expandMouse.containsMouse ? "#0284C7" : "#B30A121F")
                                                    border.color: isVideo ? "#92400E" : (expandMouse.containsMouse ? "#38BDF8" : "#334155")
                                                    border.width: 1
                                                    opacity: (galMouse.containsMouse || expandMouse.containsMouse) ? 1.0 : 0.72
                                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                                    Behavior on color { ColorAnimation { duration: 100 } }
                                                    z: 3

                                                    Row {
                                                        id: expandPillText
                                                        anchors.centerIn: parent
                                                        spacing: 3
                                                        Text {
                                                            text: expandBadgeRect.isVideo ? "⚠️" : "🔍"
                                                            font.pixelSize: 9
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }
                                                        Text {
                                                            text: expandBadgeRect.isVideo ? "No Preview" : "Preview"
                                                            font.family: "Segoe UI, sans-serif"
                                                            font.pixelSize: 9
                                                            font.weight: Font.Bold
                                                            color: expandBadgeRect.isVideo ? "#F59E0B" : (expandMouse.containsMouse ? "#FFFFFF" : "#CBD5E1")
                                                            anchors.verticalCenter: parent.verticalCenter
                                                        }
                                                    }

                                                    MouseArea {
                                                        id: expandMouse
                                                        objectName: "expandBadgeMouse"
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: expandBadgeRect.isVideo ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                        enabled: !expandBadgeRect.isVideo
                                                        onClicked: function(mouse) {
                                                            mouse.accepted = true
                                                            modalRoot.openLightbox(index)
                                                        }
                                                    }
                                                }
                                            }

                                            // Filename & Details Bar
                                            Rectangle {
                                                Layout.fillWidth: true
                                                height: 38
                                                color: "transparent"

                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 6
                                                    spacing: 1

                                                    RowLayout {
                                                        spacing: 4
                                                        Text {
                                                            text: model.name || "attachment"
                                                            font.family: "Segoe UI, sans-serif"
                                                            font.pixelSize: 10
                                                            font.weight: Font.DemiBold
                                                            color: model.selected ? "#F1F5F9" : "#64748B"
                                                            elide: Text.ElideMiddle
                                                            Layout.fillWidth: true
                                                        }

                                                        Rectangle {
                                                            visible: !!model.is_main
                                                            height: 14
                                                            implicitWidth: galMainText.implicitWidth + 6
                                                            radius: 2
                                                            color: "#0F2942"
                                                            border.color: "#0284C7"
                                                            Text {
                                                                id: galMainText
                                                                anchors.centerIn: parent
                                                                text: "MAIN"
                                                                font.pixelSize: 7
                                                                font.weight: Font.Bold
                                                                color: "#38BDF8"
                                                            }
                                                        }
                                                    }

                                                    Text {
                                                        text: "#" + (index + 1)
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 9
                                                        color: "#475569"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── 2. List Mode (Compact File Rows with Physical Settling) ──
                        Item {
                                    id: listViewWrap
                                    width: parent.width
                                    implicitHeight: Math.max(40, listCol.childrenRect.height)
                                    opacity: !modalRoot.visualGalleryMode ? 1.0 : 0.0
                                    y: !modalRoot.visualGalleryMode ? 0 : 14
                                    scale: !modalRoot.visualGalleryMode ? 1.0 : 0.965
                                    transformOrigin: Item.Top
                                    visible: opacity > 0.001

                                    Behavior on opacity {
                                        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                                    }
                                    Behavior on y {
                                        SpringAnimation {
                                            spring: 3.6
                                            damping: 0.38
                                            mass: 1.15
                                            epsilon: 0.25
                                        }
                                    }
                                    Behavior on scale {
                                        SpringAnimation {
                                            spring: 3.8
                                            damping: 0.36
                                            mass: 1.10
                                            epsilon: 0.005
                                        }
                                    }

                                    ColumnLayout {
                                        id: listCol
                                        width: parent.width
                                        spacing: 6

                                        Repeater {
                                    model: postFilesModel

                                    delegate: Item {
                                        Layout.fillWidth: true
                                        height: 52

                                        // Background rect (hover state driven by fileRowBg)
                                        Rectangle {
                                            id: listRowRect
                                            anchors.fill: parent
                                            radius: 7
                                            color: model.selected ? "#141E2F" : (fileRowHover.containsMouse ? "#0F1520" : "#10141D")
                                            border.color: model.selected ? "#38BDF8" : (fileRowHover.containsMouse ? "#334155" : "#1C2433")
                                            border.width: model.selected ? 1.5 : 1

                                            scale: fileRowHover.pressed ? 0.985 : (fileRowHover.containsMouse ? 1.008 : 1.0)
                                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
                                            Behavior on color { ColorAnimation { duration: 120 } }
                                            Behavior on border.color { ColorAnimation { duration: 120 } }
                                        }

                                        // Background hover/click (sits behind children via z)
                                        MouseArea {
                                            id: fileRowHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            z: 0
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: modalRoot.toggleFileItem(index)
                                        }

                                        // Content row (z:1 so it sits above the background MouseArea)
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 10
                                            anchors.rightMargin: 12
                                            anchors.topMargin: 0
                                            anchors.bottomMargin: 0
                                            spacing: 10
                                            z: 1

                                            // File type icon / thumbnail
                                            Rectangle {
                                                width: 36
                                                height: 36
                                                radius: 5
                                                color: "#0B0E14"
                                                border.color: "#222B3D"
                                                clip: true
                                                Layout.alignment: Qt.AlignVCenter

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: {
                                                        var fn = (model.name || "").toLowerCase()
                                                        if (fn.endsWith(".zip") || fn.endsWith(".rar") || fn.endsWith(".7z")) return "📦"
                                                        if (fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov")) return "🎥"
                                                        if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".flac") || fn.endsWith(".m4a")) return "🎵"
                                                        return "🖼️"
                                                    }
                                                    font.pixelSize: 16
                                                }

                                                Image {
                                                    anchors.fill: parent
                                                    source: (modalRoot.isImageFile(model.name, model.path, model.thumbnail) ? (model.thumbnail || "") : "")
                                                    fillMode: Image.PreserveAspectCrop
                                                    visible: status === Image.Ready
                                                    cache: true
                                                }
                                            }

                                            // Filename column (fills available width)
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 3
                                                Layout.alignment: Qt.AlignVCenter

                                                RowLayout {
                                                    spacing: 6
                                                    Layout.fillWidth: true
                                                    Text {
                                                        text: model.name || "attachment"
                                                        font.family: "Segoe UI, monospace, sans-serif"
                                                        font.pixelSize: 12
                                                        font.weight: Font.DemiBold
                                                        color: model.selected ? "#F1F5F9" : "#64748B"
                                                        elide: Text.ElideMiddle
                                                        Layout.fillWidth: true
                                                    }

                                                    // Main file badge
                                                    Rectangle {
                                                        visible: !!model.is_main
                                                        height: 16
                                                        Layout.preferredWidth: mainFileText2.implicitWidth + 10
                                                        radius: 3
                                                        color: "#0F2942"
                                                        border.color: "#0284C7"
                                                        Layout.alignment: Qt.AlignVCenter
                                                        Text {
                                                            id: mainFileText2
                                                            anchors.centerIn: parent
                                                            text: "MAIN"
                                                            font.pixelSize: 8
                                                            font.weight: Font.Bold
                                                            color: "#38BDF8"
                                                        }
                                                    }
                                                }

                                                Text {
                                                    text: {
                                                        var parts = (model.path || "").split(".")
                                                        var ext = parts.length > 1 ? ("." + parts[parts.length - 1].toUpperCase()) : ""
                                                        return ext ? ("Format: " + ext) : "File #" + (index + 1)
                                                    }
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 10
                                                    color: "#475569"
                                                }
                                            }

                                            // View button (z:2 to capture clicks above fileRowHover)
                                            Rectangle {
                                                Layout.preferredHeight: 28
                                                Layout.preferredWidth: viewBtnRow.implicitWidth + 18
                                                radius: 4
                                                Layout.alignment: Qt.AlignVCenter
                                                z: 2

                                                // Detect if this file is a video
                                                readonly property bool isVideoFile: {
                                                    var fn = (model.name || "").toLowerCase()
                                                    return fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov") || fn.endsWith(".avi") || fn.endsWith(".m4v")
                                                }

                                                color: isVideoFile ? "#1A0F00" : (viewBtnMouse.containsMouse ? "#1E4A72" : "#141A26")
                                                border.color: isVideoFile ? "#92400E" : (viewBtnMouse.containsMouse ? "#38BDF8" : "#2D3748")

                                                Behavior on color { ColorAnimation { duration: 100 } }
                                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                                Row {
                                                    id: viewBtnRow
                                                    anchors.centerIn: parent
                                                    spacing: 4
                                                    Text {
                                                        text: parent.parent.isVideoFile ? "⚠️" : "🔍"
                                                        font.pixelSize: 10
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                    Text {
                                                        text: parent.parent.isVideoFile ? "No Preview" : "View"
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 10
                                                        font.weight: 600
                                                        color: parent.parent.isVideoFile ? "#F59E0B" : (viewBtnMouse.containsMouse ? "#38BDF8" : "#94A3B8")
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                }

                                                MouseArea {
                                                    id: viewBtnMouse
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: parent.isVideoFile ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                    enabled: !parent.isVideoFile
                                                    // Consume click so it doesn't fall through to fileRowHover
                                                    onClicked: function(mouse) {
                                                        mouse.accepted = true
                                                        modalRoot.openLightbox(index)
                                                    }
                                                }
                                            }

                                            // Checkbox (z:2)
                                            Rectangle {
                                                width: 24
                                                height: 24
                                                radius: 5
                                                color: model.selected ? "#38BDF8" : "#1A2234"
                                                border.color: model.selected ? "#38BDF8" : "#334155"
                                                border.width: 1
                                                Layout.alignment: Qt.AlignVCenter
                                                z: 2

                                                scale: model.selected ? 1.0 : 0.88
                                                Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 1.0 } }
                                                Behavior on color { ColorAnimation { duration: 100 } }
                                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    font.pixelSize: 13
                                                    font.weight: Font.Bold
                                                    color: "#0A0E17"
                                                    visible: model.selected
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: function(mouse) {
                                                        mouse.accepted = true
                                                        modalRoot.toggleFileItem(index)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        }
                    }
                }
            }

            } // ── end Main Content Area Item ──────────────────────────

            // ── Footer Row ───────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Comprehensive Selection Counter Pill (Files + Posts)
                Rectangle {
                    height: 30
                    implicitWidth: selCounterRow.implicitWidth + 20
                    radius: 6
                    color: "#161D2B"
                    border.color: "#2D3748"

                    Row {
                        id: selCounterRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: modalRoot.tr("label_selected_counter", "Selected:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Files Count
                        Text {
                            text: modalRoot.totalSelectedFiles + " / " + modalRoot.totalFilesCount + " files"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: modalRoot.totalSelectedFiles > 0 ? "#38BDF8" : "#EF4444"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Divider
                        Text {
                            text: "•"
                            font.pixelSize: 10
                            color: "#475569"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Posts Count
                        Text {
                            text: modalRoot.selectedCount + " / " + modalRoot.allPosts.length + " posts"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Cancel / Close Button
                Rectangle {
                    height: 34
                    implicitWidth: cancelText.implicitWidth + 20
                    radius: 7
                    color: cancelMouse.containsMouse ? "#1E293B" : "transparent"
                    border.color: cancelMouse.containsMouse ? "#334155" : "transparent"
                    scale: cancelMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Text {
                        id: cancelText
                        anchors.centerIn: parent
                        text: modalRoot.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeModal()
                    }
                }

                // Add to Queue Selected Button
                Rectangle {
                    height: 34
                    implicitWidth: queueSelRow.implicitWidth + 24
                    radius: 7
                    color: queueSelMouse.containsMouse ? "#1E293B" : "#141A26"
                    border.color: "#2D3748"
                    border.width: 1
                    scale: queueSelMouse.pressed ? 0.94 : (queueSelMouse.containsMouse ? 1.02 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: queueSelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "➕"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_queue_selected", "Queue Selected") + " (" + modalRoot.totalSelectedFiles + " files)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: queueSelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: modalRoot.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: modalRoot.totalSelectedFiles > 0
                        opacity: modalRoot.totalSelectedFiles > 0 ? 1.0 : 0.5
                        onClicked: {
                            var ids = modalRoot.getSelectedPostIds()
                            var filesMap = modalRoot.getSelectedFilesMap()
                            if (modalRoot.bridge) {
                                modalRoot.bridge.startDownloadSelectedPosts(ids, false, filesMap)
                            }
                            modalRoot.closeModal()
                        }
                    }
                }

                // Download Selected Button
                Rectangle {
                    height: 34
                    implicitWidth: dlSelRow.implicitWidth + 28
                    radius: 7
                    color: dlSelMouse.containsMouse ? "#0284C7" : "#0369A1"
                    border.color: "#38BDF8"
                    border.width: 1
                    scale: dlSelMouse.pressed ? 0.94 : (dlSelMouse.containsMouse ? 1.03 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: dlSelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⚡"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modalRoot.tr("btn_download_selected", "Download Selected") + " (" + modalRoot.totalSelectedFiles + " files)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: dlSelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: modalRoot.totalSelectedFiles > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: modalRoot.totalSelectedFiles > 0
                        opacity: modalRoot.totalSelectedFiles > 0 ? 1.0 : 0.5
                        onClicked: {
                            var ids = modalRoot.getSelectedPostIds()
                            var filesMap = modalRoot.getSelectedFilesMap()
                            if (modalRoot.bridge) {
                                modalRoot.bridge.startDownloadSelectedPosts(ids, true, filesMap)
                            }
                            modalRoot.closeModal()
                        }
                    }
                }
            }
        }
    }

    // ── Fullscreen Lightbox Visualizer Overlay ─────────────────────
    Rectangle {
        id: lightboxOverlay
        anchors.fill: parent
        color: "#070A12"
        visible: modalRoot.lightboxVisible
        opacity: modalRoot.lightboxVisible ? 1.0 : 0.0
        z: 10000

        Behavior on opacity { NumberAnimation { duration: 200 } }

        MouseArea {
            anchors.fill: parent
            onClicked: modalRoot.closeLightbox()
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            // Lightbox Top Navigation Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    height: 32
                    implicitWidth: lbBackRow.implicitWidth + 16
                    radius: 6
                    color: lbBackMouse.containsMouse ? "#1E293B" : "#141A26"
                    border.color: "#2D3748"

                    Row {
                        id: lbBackRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Close Preview (Esc)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: lbBackMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.closeLightbox()
                    }
                }

                // File Name and Index
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        text: modalRoot.lightboxItem ? (modalRoot.lightboxItem.name || "Attachment") : ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    Text {
                        text: (modalRoot.lightboxIndex + 1) + " of " + postFilesModel.count + " files"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                }

                // Interactive Selection Checkbox in Lightbox
                Rectangle {
                    id: lbSelRect
                    objectName: "lbSelRect"
                    height: 32
                    implicitWidth: lbSelRow.implicitWidth + 18
                    radius: 6
                    readonly property bool isCurrentSelected: (modalRoot.lightboxIndex >= 0 && modalRoot.lightboxIndex < postFilesModel.count)
                                                              ? !!postFilesModel.get(modalRoot.lightboxIndex).selected : false
                    color: isCurrentSelected ? "#0C2A3D" : "#1A2234"
                    border.color: isCurrentSelected ? "#38BDF8" : "#475569"

                    Row {
                        id: lbSelRow
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            width: 16
                            height: 16
                            radius: 3
                            color: lbSelRect.isCurrentSelected ? "#38BDF8" : "transparent"
                            border.color: lbSelRect.isCurrentSelected ? "#38BDF8" : "#64748B"
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                anchors.centerIn: parent
                                text: "✓"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#0A0E17"
                                visible: lbSelRect.isCurrentSelected
                            }
                        }
                        Text {
                            text: lbSelRect.isCurrentSelected ? "Selected for Download" : "Excluded from Download"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: lbSelRect.isCurrentSelected ? "#38BDF8" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: lbSelMouse
                        objectName: "lbSelMouse"
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.toggleFileItem(modalRoot.lightboxIndex)
                    }
                }
            }

            // Lightbox Main Preview Viewport with Next/Prev Arrows
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Prev Arrow
                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 44
                    height: 44
                    radius: 22
                    color: prevMouse.containsMouse ? "#334155" : "#B31E293B"
                    border.color: "#475569"
                    z: 10

                    Text {
                        anchors.centerIn: parent
                        text: "←"
                        font.pixelSize: 18
                        color: "#F8FAFC"
                    }

                    MouseArea {
                        id: prevMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.prevLightboxItem()
                    }
                }

                // Next Arrow
                Rectangle {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 44
                    height: 44
                    radius: 22
                    color: nextMouse.containsMouse ? "#334155" : "#B31E293B"
                    border.color: "#475569"
                    z: 10

                    Text {
                        anchors.centerIn: parent
                        text: "→"
                        font.pixelSize: 18
                        color: "#F8FAFC"
                    }

                    MouseArea {
                        id: nextMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modalRoot.nextLightboxItem()
                    }
                }

                // Image Container
                Item {
                    anchors.fill: parent
                    anchors.leftMargin: 60
                    anchors.rightMargin: 60

                    Image {
                        id: lbImage
                        anchors.fill: parent
                        source: (modalRoot.lightboxItem && modalRoot.isImageFile(modalRoot.lightboxItem.name, modalRoot.lightboxItem.path, modalRoot.lightboxItem.previewUrl || modalRoot.lightboxItem.thumbnail))
                                ? (modalRoot.lightboxItem.previewUrl || modalRoot.lightboxItem.thumbnail || "")
                                : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: true
                        opacity: status === Image.Ready ? 1.0 : 0.0
                        Behavior on opacity { NumberAnimation { duration: 180 } }
                    }

                    // Fallback for non-images or while loading
                    Column {
                        anchors.centerIn: parent
                        spacing: 10
                        visible: lbImage.status !== Image.Ready

                        readonly property bool lbIsVideo: {
                            var fn = modalRoot.lightboxItem ? (modalRoot.lightboxItem.name || "").toLowerCase() : ""
                            return fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov") || fn.endsWith(".avi") || fn.endsWith(".m4v")
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: {
                                var fn = modalRoot.lightboxItem ? (modalRoot.lightboxItem.name || "").toLowerCase() : ""
                                if (fn.endsWith(".zip") || fn.endsWith(".rar") || fn.endsWith(".7z")) return "📦"
                                if (fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov") || fn.endsWith(".avi") || fn.endsWith(".m4v")) return "🎥"
                                if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".flac") || fn.endsWith(".m4a")) return "🎵"
                                return "🖼️"
                            }
                            font.pixelSize: 48
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: {
                                var fn = modalRoot.lightboxItem ? (modalRoot.lightboxItem.name || "").toLowerCase() : ""
                                if (fn.endsWith(".zip") || fn.endsWith(".rar") || fn.endsWith(".7z")) return "Archive File"
                                if (fn.endsWith(".mp4") || fn.endsWith(".mkv") || fn.endsWith(".webm") || fn.endsWith(".mov") || fn.endsWith(".avi") || fn.endsWith(".m4v")) return "Video File"
                                if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".flac") || fn.endsWith(".m4a")) return "Audio Track"
                                return "Loading Preview..."
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 18
                            font.weight: Font.Bold
                            color: "#CBD5E1"
                        }

                        // Video-specific warning banner
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: parent.lbIsVideo
                            height: 32
                            width: videoWarnRow.implicitWidth + 24
                            radius: 6
                            color: "#2D1A00"
                            border.color: "#92400E"
                            border.width: 1

                            Row {
                                id: videoWarnRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: "⚠️"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: "Videos cannot be previewed — they will be downloaded to your disk."
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#F59E0B"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modalRoot.lightboxItem ? (modalRoot.lightboxItem.name || "") : ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                        }
                    }
                }
            }
        }
    }
}
