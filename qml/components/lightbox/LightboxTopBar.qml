import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Top toolbar for MediaLightboxModal (hidden in full screen).
RowLayout {
    id: topBar
    required property var modal
    property bool imageReady: false
    property int imageImplicitWidth: 0
    property int imageImplicitHeight: 0
    visible: !topBar.modal.fullscreen
    Layout.fillWidth: true
    Layout.fillHeight: false
    spacing: 12

    // Close button
    Rectangle {
        width: 32
        height: 32
        radius: 6
        color: closeMouse.containsMouse ? "#EF4444" : "#1A2234"
        border.color: closeMouse.containsMouse ? "#DC2626" : "#2E3A52"
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: "✕"
            font.pixelSize: 13
            font.weight: Font.Bold
            color: "#FFFFFF"
        }

        Springy { hover: closeMouse.containsMouse; pressed: closeMouse.pressed }
        MouseArea {
            id: closeMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: topBar.modal.close()
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Close media viewer (Esc)"
        }
    }

    // Media Info Tag
    Rectangle {
        implicitHeight: 28
        implicitWidth: tagRow.implicitWidth + 16
        radius: 6
        color: "#131926"
        border.color: "#27344D"
        border.width: 1

        Row {
            id: tagRow
            anchors.centerIn: parent
            spacing: 8

            Text {
                readonly property bool isGifTag: !topBar.modal.isVideo && !topBar.modal.isAudio && (topBar.modal.itemExt === ".gif" || !!(topBar.modal.currentItem && topBar.modal.currentItem.is_loop))
                text: topBar.modal.isVideo ? "🎬 VIDEO" : (topBar.modal.isAudio ? "🎵 AUDIO" : (isGifTag ? "🎞 GIF" : "🖼️ IMAGE"))
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 700
                color: topBar.modal.isVideo ? "#8B5CF6" : (topBar.modal.isAudio ? "#10B981" : (isGifTag ? "#C084FC" : "#EC4899"))
            }

            Text {
                text: (topBar.modal.currentIndex + 1) + " / " + topBar.modal.mediaList.length
                font.family: "Segoe UI, monospace"
                font.pixelSize: 10
                color: "#94A3B8"
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Media item " + (topBar.modal.currentIndex + 1) + " of " + topBar.modal.mediaList.length + " in this folder"
        }
    }

    UnimportedTriangleBadge {
        objectName: "lightboxUnimportedBadge"
        visible: !!(topBar.modal.currentItem && topBar.modal.currentItem.is_unimported)
        Layout.preferredWidth: 24
        Layout.preferredHeight: 24
        width: 24
        height: 24
        tooltipText: "Haven't archived this post yet (previews only)"
    }

    // Filename
    Text {
        text: topBar.modal.itemName
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 13
        font.weight: 600
        color: "#F8FAFC"
        elide: Text.ElideMiddle
        Layout.fillWidth: true
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: topBar.modal.itemPath
        }
    }

    // Image Dimensions pill (when viewing image)
    Rectangle {
        visible: topBar.modal.isImage && topBar.imageReady && topBar.imageImplicitWidth > 1
        implicitHeight: 28
        implicitWidth: dimText.implicitWidth + 14
        radius: 6
        color: "#131926"
        border.color: "#27344D"
        border.width: 1

        Text {
            id: dimText
            anchors.centerIn: parent
            text: topBar.imageImplicitWidth + " × " + topBar.imageImplicitHeight
            font.family: "Segoe UI, monospace"
            font.pixelSize: 10
            color: "#38BDF8"
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Image dimensions: " + topBar.imageImplicitWidth + " × " + topBar.imageImplicitHeight + " px"
        }
    }

    // File Size Pill
    Rectangle {
        visible: topBar.modal.currentItem && topBar.modal.currentItem.size > 0
        implicitHeight: 28
        implicitWidth: szText.implicitWidth + 14
        radius: 6
        color: "#131926"
        border.color: "#27344D"
        border.width: 1

        Text {
            id: szText
            anchors.centerIn: parent
            text: topBar.modal.currentItem ? topBar.modal.formatBytes(topBar.modal.currentItem.size) : ""
            font.family: "Segoe UI, monospace"
            font.pixelSize: 10
            color: "#94A3B8"
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "File size on disk: " + (topBar.modal.currentItem ? topBar.modal.formatBytes(topBar.modal.currentItem.size) : "0 B")
        }
    }

    // Image Zoom Controls
    Row {
        visible: topBar.modal.isImage
        spacing: 4

        Rectangle {
            width: 28; height: 28; radius: 5
            color: zoomInMouse.containsMouse ? "#222D42" : "#141A28"
            border.color: "#2A364E"; border.width: 1
            Text { anchors.centerIn: parent; text: "➕"; font.pixelSize: 10; color: "#E2E8F0" }
            Springy { hover: zoomInMouse.containsMouse; pressed: zoomInMouse.pressed }
            MouseArea {
                id: zoomInMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: topBar.modal.zoomStep(1)
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Zoom In (+ or scroll up over the picture)\nCurrent zoom: " + Math.round(topBar.modal.zoomFactor * 100) + "%"
            }
        }
        Rectangle {
            width: 28; height: 28; radius: 5
            color: zoomOutMouse.containsMouse ? "#222D42" : "#141A28"
            border.color: "#2A364E"; border.width: 1
            Text { anchors.centerIn: parent; text: "➖"; font.pixelSize: 10; color: "#E2E8F0" }
            Springy { hover: zoomOutMouse.containsMouse; pressed: zoomOutMouse.pressed }
            MouseArea {
                id: zoomOutMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: topBar.modal.zoomStep(-1)
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Zoom Out (- or scroll down over the picture)\nCurrent zoom: " + Math.round(topBar.modal.zoomFactor * 100) + "%"
            }
        }
        Rectangle {
            width: 28; height: 28; radius: 5
            color: zoomResetMouse.containsMouse ? "#222D42" : "#141A28"
            border.color: "#2A364E"; border.width: 1
            Text { anchors.centerIn: parent; text: "1:1"; font.pixelSize: 10; font.weight: 600; color: "#38BDF8" }
            Springy { hover: zoomResetMouse.containsMouse; pressed: zoomResetMouse.pressed }
            MouseArea {
                id: zoomResetMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: topBar.modal.resetZoom(true)
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "Fit the picture to the window (0 or double-click)"
            }
        }
    }

    // Extras: rotate · copy · favourite · rating · source post · info · delete
    Row {
        spacing: 4
        Layout.alignment: Qt.AlignVCenter

        LightboxIconButton { visible: topBar.modal.isImage || topBar.modal.isVideo; glyph: "⟲"; tip: "Rotate left (Shift+R)"; onClicked: topBar.modal.rotate(-1) }
        LightboxIconButton { visible: topBar.modal.isImage || topBar.modal.isVideo; glyph: "⟳"; tip: "Rotate right (R)"; onClicked: topBar.modal.rotate(1) }
        LightboxIconButton { glyph: "⛶"; tip: "Full screen (F)"; onClicked: topBar.modal.toggleFullscreen() }
        LightboxIconButton { glyph: "⌨"; active: topBar.modal.showShortcuts; tip: "Keyboard shortcuts (?)"; onClicked: topBar.modal.showShortcuts = !topBar.modal.showShortcuts }
        LightboxIconButton { visible: !!topBar.modal.tools && (!topBar.modal.isRemote || !!topBar.modal.resolvedLocalPath); glyph: "⧉"; tip: topBar.modal.isImage ? "Copy picture (Ctrl+C): paste into chats, or as a file in Explorer" : "Copy file (Ctrl+C)"; onClicked: topBar.modal.copyCurrent() }
        LightboxIconButton { visible: !!topBar.modal.tools && !topBar.modal.isRemote; glyph: topBar.modal.isFav ? "★" : "☆"; active: topBar.modal.isFav; activeColor: "#FBBF24"; tip: topBar.modal.isFav ? "Remove from favourites (Ctrl+D)" : "Add to favourites (Ctrl+D)"; onClicked: topBar.modal.toggleFav() }

        // Rating: click a star, click it again to clear (keys 1–5)
        Rectangle {
            visible: !!topBar.modal.tools && !topBar.modal.isRemote
            width: lbStars.implicitWidth + 12
            height: 28
            radius: 5
            color: "#141A28"
            border.color: "#2A364E"
            Row {
                id: lbStars
                anchors.centerIn: parent
                spacing: 1
                Repeater {
                    model: 5
                    delegate: Text {
                        readonly property int n: index + 1
                        text: n <= topBar.modal.rating ? "★" : "☆"
                        font.pixelSize: 14
                        color: n <= topBar.modal.rating ? "#FBBF24" : "#64748B"
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -2
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: topBar.modal.rate(parent.n)
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 400
                            ToolTip.text: "Rate " + parent.n + " (key " + parent.n + ")"
                        }
                    }
                }
            }
        }

        LightboxIconButton { visible: !topBar.modal.hideExternalActions && topBar.modal.sourceUrl.length > 0; glyph: "🌐"; tip: "View the source post in your browser"; onClicked: Qt.openUrlExternally(topBar.modal.sourceUrl) }
        LightboxIconButton { objectName: "lightboxCopyFileLinkBtn"; visible: topBar.modal.itemLinkUrl.length > 0 && (!!topBar.modal.browserBridge || !!topBar.modal.bridge); glyph: "🔗"; tip: "Copy link to this file"; onClicked: topBar.modal.copyLinkText(topBar.modal.itemLinkUrl, "File link") }
        LightboxIconButton { glyph: "ⓘ"; active: topBar.modal.showInfo; tip: "File info (I)"; onClicked: topBar.modal.showInfo = !topBar.modal.showInfo }
        LightboxIconButton { visible: !topBar.modal.isRemote && !!topBar.modal.bridge; glyph: "🗑"; danger: true; tip: "Move to the Recycle Bin (Del)"; onClicked: topBar.modal.confirmDelete = true }
    }

    // Copy Post Link Button (when source post URL differs from current file link)
    Rectangle {
        objectName: "lightboxCopyPostLinkBtn"
        visible: topBar.modal.sourceUrl.length > 0 && topBar.modal.sourceUrl !== topBar.modal.itemLinkUrl && (!!topBar.modal.browserBridge || !!topBar.modal.bridge)
        implicitHeight: 28
        implicitWidth: lbCopyPostRow.implicitWidth + 14
        radius: 6
        color: lbCopyPostMouse.containsMouse ? "#1E273A" : "#141A28"
        border.color: lbCopyPostMouse.containsMouse ? "#38BDF8" : "#2A364E"
        border.width: 1

        Row {
            id: lbCopyPostRow
            anchors.centerIn: parent
            spacing: 5
            Text { text: "🔗"; font.pixelSize: 11; color: "#7DD3FC" }
            Text { text: "Post Link"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#E2E8F0" }
        }
        Springy { hover: lbCopyPostMouse.containsMouse; pressed: lbCopyPostMouse.pressed }
        MouseArea {
            id: lbCopyPostMouse
            objectName: "lightboxCopyPostLinkMouse"
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: topBar.modal.copyLinkText(topBar.modal.sourceUrl, "Post link")
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Copy link to the source post"
        }
    }

    // Selection Toggle Pill (shown when opened from PostSelectionModal)
    Rectangle {
        id: lbSelRect
        objectName: "lbSelRect"
        visible: topBar.modal.selectionMode
        implicitHeight: 28
        implicitWidth: lbSelRow.implicitWidth + 16
        radius: 6
        color: topBar.modal.currentItemSelected ? "#0C2A3D" : "#141A28"
        border.color: topBar.modal.currentItemSelected ? "#38BDF8" : "#475569"
        border.width: 1

        Row {
            id: lbSelRow
            anchors.centerIn: parent
            spacing: 6
            Rectangle {
                width: 14
                height: 14
                radius: 3
                color: topBar.modal.currentItemSelected ? "#38BDF8" : "transparent"
                border.color: topBar.modal.currentItemSelected ? "#38BDF8" : "#64748B"
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    anchors.centerIn: parent
                    text: "✓"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: "#0A0E17"
                    visible: topBar.modal.currentItemSelected
                }
            }
            Text {
                text: topBar.modal.currentItemSelected ? "Selected for Download" : "Excluded from Download"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 600
                color: topBar.modal.currentItemSelected ? "#38BDF8" : "#94A3B8"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Springy { hover: lbSelMouse.containsMouse; pressed: lbSelMouse.pressed }
        MouseArea {
            id: lbSelMouse
            objectName: "lbSelMouse"
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: topBar.modal.selectionToggled()
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: topBar.modal.currentItemSelected
                ? "Exclude this file from download"
                : "Include this file in download"
        }
    }

    // In-App Download button (shown for online/remote Browser items outside selection mode)
    Rectangle {
        visible: topBar.modal.isRemote && !!topBar.modal.browserBridge && !topBar.modal.selectionMode
        implicitHeight: 28
        implicitWidth: dlBtnRow.implicitWidth + 14
        radius: 6
        color: dlBtnMouse.containsMouse ? "#047857" : "#065F46"
        border.color: "#10B981"
        border.width: 1

        Row {
            id: dlBtnRow
            anchors.centerIn: parent
            spacing: 6
            Text { text: "📥"; font.pixelSize: 11; color: "#ECFDF5" }
            Text { text: "Download Post"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#ECFDF5" }
        }
        Springy { hover: dlBtnMouse.containsMouse; pressed: dlBtnMouse.pressed }
        MouseArea {
            id: dlBtnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (topBar.modal.currentItem) topBar.modal.downloadItemRequested(topBar.modal.currentItem)
                if (topBar.modal.browserBridge && topBar.modal.sourceUrl) {
                    topBar.modal.browserBridge.downloadSingleUrl(topBar.modal.sourceUrl, true)
                    topBar.modal.flash("Queued post in Downloader")
                }
            }
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Download this post cleanly via the Pawchive Downloader"
        }
    }

    // Open Externally Button (local files only, hidden when external actions are suppressed)
    Rectangle {
        visible: !topBar.modal.isRemote && !topBar.modal.hideExternalActions
        implicitHeight: 28
        implicitWidth: extRow.implicitWidth + 14
        radius: 6
        color: extMouse.containsMouse ? "#1E273A" : "#141A28"
        border.color: extMouse.containsMouse ? "#38BDF8" : "#2A364E"
        border.width: 1

        Row {
            id: extRow
            anchors.centerIn: parent
            spacing: 6
            Text { text: "↗"; font.pixelSize: 11; color: "#E2E8F0" }
            Text { text: "Open Externally"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#E2E8F0" }
        }
        Springy { hover: extMouse.containsMouse; pressed: extMouse.pressed }
        MouseArea {
            id: extMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (topBar.modal.bridge && topBar.modal.bridge.openPathInSystem) {
                    topBar.modal.bridge.openPathInSystem(topBar.modal.itemPath)
                }
            }
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Open file in your system's default media player / viewer"
        }
    }

    // Reveal in Folder Button (local files only)
    Rectangle {
        visible: !topBar.modal.isRemote
        width: 28; height: 28; radius: 5
        color: folderMouse.containsMouse ? "#1E273A" : "#141A28"
        border.color: folderMouse.containsMouse ? "#38BDF8" : "#2A364E"
        border.width: 1
        Text { anchors.centerIn: parent; text: "📂"; font.pixelSize: 12 }
        Springy { hover: folderMouse.containsMouse; pressed: folderMouse.pressed }
        MouseArea {
            id: folderMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (topBar.modal.bridge && topBar.modal.bridge.openFolder) {
                    var dir = topBar.modal.itemPath.substring(0, Math.max(topBar.modal.itemPath.lastIndexOf("/"), topBar.modal.itemPath.lastIndexOf("\\")))
                    topBar.modal.bridge.openFolder(dir)
                }
            }
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: "Open containing folder in File Explorer / OS manager"
        }
    }
}
