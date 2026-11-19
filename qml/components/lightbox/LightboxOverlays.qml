import QtQuick
import QtQuick.Controls
import QtMultimedia
import ".."

// Floating panels, OSD bubble, fullscreen header, shortcuts sheet, and prev/next chevrons.
Item {
    id: overlaysRoot
    required property var modal
    required property var player
    property bool imageReady: false
    property int imageImplicitWidth: 0
    property int imageImplicitHeight: 0

    // Info panel (I)
    Rectangle {
        visible: overlaysRoot.modal.showInfo && !!overlaysRoot.modal.currentItem
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 56
        width: Math.min(300, parent.width * 0.45)
        height: infoCol.implicitHeight + 24
        radius: 10
        color: "#E6111622"
        border.color: "#2E3A52"
        border.width: 1
        z: 5
        MouseArea { anchors.fill: parent }   // don't toggle video playback through the panel
        Column {
            id: infoCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 12
            spacing: 6
            Text { text: "ⓘ  File info"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 12; font.weight: 700; color: "#F8FAFC" }
            Repeater {
                model: {
                    if (!overlaysRoot.modal.currentItem) return []
                    var it = overlaysRoot.modal.currentItem
                    var p = overlaysRoot.modal.itemPath
                    var folder = overlaysRoot.modal.isRemote ? (p.replace(/^https?:\/\//, "").split("/")[0] || "Remote CDN") : p.substring(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")))
                    var rows = [
                        ["Name", it.name],
                        [overlaysRoot.modal.isRemote ? "Source" : "Folder", folder],
                        ["Type", (overlaysRoot.modal.itemExt || "").replace(".", "").toUpperCase() + (overlaysRoot.modal.isImage ? " image" : (overlaysRoot.modal.isVideo ? " video" : (overlaysRoot.modal.isAudio ? " audio" : "")))]
                    ]
                    if (it.size > 0) rows.push(["Size", overlaysRoot.modal.formatBytes(it.size)])
                    if (it.mtime > 0) rows.push(["Modified", overlaysRoot.modal.formatDateTime(it.mtime)])
                    if (overlaysRoot.modal.isImage && overlaysRoot.imageReady) rows.push(["Resolution", overlaysRoot.imageImplicitWidth + " × " + overlaysRoot.imageImplicitHeight + " px"])
                    if (overlaysRoot.modal.isVideo || overlaysRoot.modal.isAudio) {
                        var res = overlaysRoot.player.metaData.value(MediaMetaData.Resolution)
                        if (res && res.width > 0) rows.push(["Resolution", res.width + " × " + res.height + " px"])
                        if (overlaysRoot.player.duration > 0) rows.push(["Length", overlaysRoot.modal.formatClock(overlaysRoot.player.duration, overlaysRoot.player.duration)])
                    }
                    if (overlaysRoot.modal.tools) {
                        rows.push(["Favourite", overlaysRoot.modal.isFav ? "★ yes" : "no"])
                        rows.push(["Rating", overlaysRoot.modal.rating > 0 ? "★★★★★".substring(0, overlaysRoot.modal.rating) : "not rated"])
                    }
                    if (overlaysRoot.modal.postId) rows.push(["Post ID", overlaysRoot.modal.postId])
                    return rows
                }
                delegate: Row {
                    spacing: 8
                    width: infoCol.width
                    Text { text: modelData[0]; width: 72; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; color: "#64748B" }
                    Text {
                        text: modelData[1]
                        width: infoCol.width - 80
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#E2E8F0"
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }
        }
    }

    // Delete confirmation (Enter confirms, Esc cancels)
    Rectangle {
        visible: overlaysRoot.modal.confirmDelete
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
        width: confirmRow.implicitWidth + 28
        height: 46
        radius: 10
        color: "#F21A0F14"
        border.color: "#EF4444"
        border.width: 1
        z: 6
        MouseArea { anchors.fill: parent }
        Row {
            id: confirmRow
            anchors.centerIn: parent
            spacing: 10
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Move \"" + overlaysRoot.modal.itemName + "\" to the Recycle Bin?"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#FECACA"
                elide: Text.ElideMiddle
                width: Math.min(implicitWidth, 420)
            }
            Rectangle {
                width: delText.implicitWidth + 20; height: 28; radius: 6
                color: delMouse.containsMouse ? "#DC2626" : "#B91C1C"
                Text { id: delText; anchors.centerIn: parent; text: "🗑 Move to Recycle Bin"; font.pixelSize: 11; font.weight: 700; color: "#FFFFFF" }
                MouseArea { id: delMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: overlaysRoot.modal.deleteCurrent() }
            }
            Rectangle {
                width: cancelText.implicitWidth + 20; height: 28; radius: 6
                color: cancelMouse.containsMouse ? "#1E293B" : "#141720"
                border.color: "#2E384D"
                Text { id: cancelText; anchors.centerIn: parent; text: "Cancel"; font.pixelSize: 11; font.weight: 700; color: "#E2E8F0" }
                MouseArea { id: cancelMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: overlaysRoot.modal.confirmDelete = false }
            }
        }
    }

    // Short confirmation messages (copied, rated, …)
    Rectangle {
        visible: overlaysRoot.modal.flashText.length > 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 12
        width: flashLabel.implicitWidth + 28
        height: 30
        radius: 15
        color: "#E60F172A"
        border.color: "#38BDF8"
        z: 6
        Text { id: flashLabel; anchors.centerIn: parent; text: overlaysRoot.modal.flashText; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#E0F2FE" }
    }

    // Action bubble ("+5 s", volume, speed, play / pause)
    Rectangle {
        z: 7
        anchors.centerIn: parent
        width: Math.max(76, osdRow.implicitWidth + 32)
        height: 58
        radius: 29
        color: "#D90B0F18"
        border.color: "#334155"
        opacity: overlaysRoot.modal.osdShown ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        scale: overlaysRoot.modal.osdScale
        Row {
            id: osdRow
            anchors.centerIn: parent
            spacing: 8
            Text { text: overlaysRoot.modal.osdIcon; font.family: "Segoe UI Symbol"; font.pixelSize: 22; color: "#F8FAFC"; anchors.verticalCenter: parent.verticalCenter }
            Text { visible: overlaysRoot.modal.osdText.length > 0; text: overlaysRoot.modal.osdText; font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F8FAFC"; anchors.verticalCenter: parent.verticalCenter }
        }
    }

    // Full screen: name + exit along the top, fading with the controls
    Rectangle {
        z: 6
        visible: overlaysRoot.modal.fullscreen && opacity > 0.01
        opacity: overlaysRoot.modal.chromeShown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 220 } }
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 64
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#CC070A10" }
            GradientStop { position: 1.0; color: "#00070A10" }
        }
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.right: fsExit.left
            anchors.rightMargin: 12
            anchors.top: parent.top
            anchors.topMargin: 14
            text: overlaysRoot.modal.itemName + (overlaysRoot.modal.mediaList.length > 1 ? "   ·   " + (overlaysRoot.modal.currentIndex + 1) + " / " + overlaysRoot.modal.mediaList.length : "")
            elide: Text.ElideMiddle
            font.family: "Segoe UI"
            font.pixelSize: 14
            font.weight: 600
            color: "#F1F5F9"
        }
        Rectangle {
            id: fsExit
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.top: parent.top
            anchors.topMargin: 10
            width: fsExitLabel.implicitWidth + 22
            height: 28
            radius: 14
            color: fsExitMouse.containsMouse ? "#33FFFFFF" : "#1AFFFFFF"
            border.color: "#44FFFFFF"
            Text { id: fsExitLabel; anchors.centerIn: parent; text: "🗗  Exit full screen"; font.family: "Segoe UI"; font.pixelSize: 11; font.weight: 600; color: "#F8FAFC" }
            Springy { hover: fsExitMouse.containsMouse; pressed: fsExitMouse.pressed }
            MouseArea { id: fsExitMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: overlaysRoot.modal.setFullscreen(false) }
        }
    }

    // Keyboard shortcut sheet (? or the ⌨ button)
    Rectangle {
        z: 8
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, 520)
        height: Math.min(parent.height - 40, sheetCol.implicitHeight + 32)
        radius: 12
        color: "#F20F1422"
        border.color: "#2A364E"
        visible: overlaysRoot.modal.showShortcuts && opacity > 0.01
        opacity: overlaysRoot.modal.showShortcuts ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
        scale: overlaysRoot.modal.showShortcuts ? 1 : 0.94
        Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        MouseArea { anchors.fill: parent; onClicked: overlaysRoot.modal.showShortcuts = false }
        readonly property var rows: overlaysRoot.modal.isMedia ? [
            ["Space / K", "Play or pause"], ["← / →", "Back / forward 5 seconds"], ["J / L", "Back / forward 10 seconds"],
            ["↑ / ↓", "Volume up / down"], ["M", "Mute"], ["0 – 9", "Jump to 0% … 90%"], ["Home / End", "Start / end"],
            [", / .", "Previous / next frame"], ["< / >", "Slower / faster"], ["F  or double-click", "Full screen"],
            ["Ctrl+← / Ctrl+→", "Previous / next file"], ["Ctrl+D", "Favourite"], ["R / Shift+R", "Rotate"],
            ["I", "File info"], ["Delete", "Delete"], ["Esc", "Exit full screen / close"]
        ] : (overlaysRoot.modal.hasAnimBar ? [
            ["Space / K", "Play or pause"], ["← / →", "Previous / next"], [", / .", "Previous / next frame"],
            ["< / >", "Slower / faster"], ["Home / End", "First / last frame"], ["Scroll", "Zoom in where you point"],
            ["+ / − / 0", "Zoom in / out / fit"], ["Drag", "Move around when zoomed"], ["1 – 5", "Rate"],
            ["F", "Full screen"], ["R / Shift+R", "Rotate"], ["Ctrl+D / Ctrl+C", "Favourite / copy"],
            ["I", "File info"], ["Delete", "Delete"], ["Esc", "Close"]
        ] : [
            ["← / →", "Previous / next"], ["Scroll", "Zoom in where you point"], ["+ / − / 0", "Zoom in / out / fit"],
            ["Drag", "Move around when zoomed"], ["1 – 5", "Rate"], ["Ctrl+D", "Favourite"], ["F", "Full screen"],
            ["R / Shift+R", "Rotate"], ["Ctrl+C", "Copy picture"], ["Space", "Pause an animation"], ["I", "File info"],
            ["Delete", "Delete"], ["Esc", "Close"]
        ])
        Column {
            id: sheetCol
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10
            Text { text: "⌨  Keyboard shortcuts"; font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F8FAFC" }
            Grid {
                columns: 2
                columnSpacing: 18
                rowSpacing: 6
                Repeater {
                    model: parent.parent.parent.rows.length * 2
                    delegate: Text {
                        readonly property var row: sheetCol.parent.rows[Math.floor(index / 2)]
                        text: index % 2 === 0 ? row[0] : row[1]
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        font.weight: index % 2 === 0 ? 700 : 400
                        color: index % 2 === 0 ? "#7DD3FC" : "#CBD5E1"
                    }
                }
            }
            Text { text: "Press ? or Esc to close"; font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B" }
        }
    }

    // Floating Navigation Chevron: PREVIOUS (‹)
    Rectangle {
        width: 44
        height: 72
        radius: 8
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        color: prevChevMouse.containsMouse ? "#28354E" : "#161D2B"
        opacity: (prevChevMouse.containsMouse ? 0.95 : 0.6) * (overlaysRoot.modal.chromeShown ? 1 : 0)
        enabled: overlaysRoot.modal.chromeShown
        Behavior on opacity { NumberAnimation { duration: 200 } }
        border.color: prevChevMouse.containsMouse ? "#38BDF8" : "#243044"
        border.width: 1
        visible: overlaysRoot.modal.mediaList.length > 1

        Text {
            anchors.centerIn: parent
            text: "‹"
            font.pixelSize: 32
            font.weight: 300
            color: "#FFFFFF"
        }

        Springy { hover: prevChevMouse.containsMouse; pressed: prevChevMouse.pressed }
        MouseArea {
            id: prevChevMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: overlaysRoot.modal.prevItem()
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: overlaysRoot.modal.isMedia ? "Previous file (Ctrl+← or Page Up)" : "Previous file (←)"
        }
    }

    // Floating Navigation Chevron: NEXT (›)
    Rectangle {
        width: 44
        height: 72
        radius: 8
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        color: nextChevMouse.containsMouse ? "#28354E" : "#161D2B"
        opacity: (nextChevMouse.containsMouse ? 0.95 : 0.6) * (overlaysRoot.modal.chromeShown ? 1 : 0)
        enabled: overlaysRoot.modal.chromeShown
        Behavior on opacity { NumberAnimation { duration: 200 } }
        border.color: nextChevMouse.containsMouse ? "#38BDF8" : "#243044"
        border.width: 1
        visible: overlaysRoot.modal.mediaList.length > 1

        Text {
            anchors.centerIn: parent
            text: "›"
            font.pixelSize: 32
            font.weight: 300
            color: "#FFFFFF"
        }

        Springy { hover: nextChevMouse.containsMouse; pressed: nextChevMouse.pressed }
        MouseArea {
            id: nextChevMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: overlaysRoot.modal.nextItem()
            ToolTip.visible: containsMouse
            ToolTip.delay: 250
            ToolTip.text: overlaysRoot.modal.isMedia ? "Next file (Ctrl+→ or Page Down)" : "Next file (→)"
        }
    }
}
