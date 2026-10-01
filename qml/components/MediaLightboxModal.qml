import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

// ── Media Lightbox Modal ───────────────────────────────────────────────────
// High-performance inline previews for Images, animated GIFs, Videos, and Audio.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property var mediaList: []
    property int currentIndex: 0

    readonly property var currentItem: (mediaList && currentIndex >= 0 && currentIndex < mediaList.length) ? mediaList[currentIndex] : null
    readonly property string itemPath: currentItem ? (currentItem.path || "") : ""
    readonly property string itemName: currentItem ? (currentItem.name || "") : ""
    readonly property string itemExt: currentItem ? ((currentItem.ext || "").toLowerCase()) : ""
    readonly property bool isImage: [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"].indexOf(itemExt) >= 0
    readonly property bool isVideo: [".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v"].indexOf(itemExt) >= 0
    readonly property bool isAudio: [".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"].indexOf(itemExt) >= 0

    property real zoomFactor: 1.0
    property bool isLooping: false

    anchors.fill: parent
    z: 9999
    visible: isOpen

    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return "0 B"
        var k = 1024
        var sizes = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(k))
        if (i < 0) i = 0
        if (i >= sizes.length) i = sizes.length - 1
        return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
    }

    function formatTime(ms) {
        if (!ms || ms <= 0) return "00:00"
        var totalSec = Math.floor(ms / 1000)
        var min = Math.floor(totalSec / 60)
        var sec = totalSec % 60
        var sMin = min < 10 ? "0" + min : "" + min
        var sSec = sec < 10 ? "0" + sec : "" + sec
        return sMin + ":" + sSec
    }

    function toUrl(path) {
        if (!path) return ""
        if (bridge && bridge.pathToUrl) {
            return bridge.pathToUrl(path)
        }
        var p = path.replace(/\\/g, "/")
        return p.indexOf("file://") === 0 ? p : ("file:///" + p)
    }

    function open(item, allMedia) {
        mediaList = allMedia || []
        var idx = 0
        if (item) {
            for (var i = 0; i < mediaList.length; i++) {
                if (mediaList[i].path === item.path) {
                    idx = i
                    break
                }
            }
        }
        currentIndex = idx
        zoomFactor = 1.0
        isOpen = true
        root.forceActiveFocus()
        loadCurrentItem()
    }

    function close() {
        if (mediaPlayer) {
            mediaPlayer.stop()
        }
        isOpen = false
    }

    function prevItem() {
        if (mediaList.length <= 1) return
        if (currentIndex > 0) currentIndex--
        else currentIndex = mediaList.length - 1
        zoomFactor = 1.0
        loadCurrentItem()
    }

    function nextItem() {
        if (mediaList.length <= 1) return
        if (currentIndex < mediaList.length - 1) currentIndex++
        else currentIndex = 0
        zoomFactor = 1.0
        loadCurrentItem()
    }

    function loadCurrentItem() {
        if (!currentItem) return
        var url = toUrl(itemPath)
        if (isVideo || isAudio) {
            mediaPlayer.source = url
            mediaPlayer.play()
        } else {
            mediaPlayer.stop()
        }
    }

    // Keyboard controls
    Keys.onPressed: function(event) {
        if (!isOpen) return
        if (event.key === Qt.Key_Escape) {
            close()
            event.accepted = true
        } else if (event.key === Qt.Key_Left) {
            prevItem()
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            nextItem()
            event.accepted = true
        } else if (event.key === Qt.Key_Space) {
            if (isVideo || isAudio) {
                if (mediaPlayer.playbackState === MediaPlayer.PlayingState) {
                    mediaPlayer.pause()
                } else {
                    mediaPlayer.play()
                }
            }
            event.accepted = true
        } else if (event.key === Qt.Key_Plus || event.key === Qt.Key_Equal) {
            zoomFactor = Math.min(4.0, zoomFactor + 0.25)
            event.accepted = true
        } else if (event.key === Qt.Key_Minus) {
            zoomFactor = Math.max(0.25, zoomFactor - 0.25)
            event.accepted = true
        } else if (event.key === Qt.Key_0) {
            zoomFactor = 1.0
            event.accepted = true
        }
    }

    // Media Player backend
    AudioOutput {
        id: audioOutput
        volume: 0.85
        muted: false
    }

    MediaPlayer {
        id: mediaPlayer
        audioOutput: audioOutput
        videoOutput: videoOutput
        loops: root.isLooping ? MediaPlayer.Infinite : 1
    }

    // Dark translucent backdrop
    Rectangle {
        anchors.fill: parent
        color: "#080B11"
        opacity: root.isOpen ? 0.96 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {} // consume clicks so underlying view isn't tapped
        }
    }

    // Main Lightbox Container
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        // 1. TOP LIGHTBOX TOOLBAR
        RowLayout {
            Layout.fillWidth: true
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

                MouseArea {
                    id: closeMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.close()
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
                        text: root.isVideo ? "🎬 VIDEO" : (root.isAudio ? "🎵 AUDIO" : "🖼️ IMAGE")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: root.isVideo ? "#8B5CF6" : (root.isAudio ? "#10B981" : "#EC4899")
                    }

                    Text {
                        text: (root.currentIndex + 1) + " / " + root.mediaList.length
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                }
            }

            // Filename
            Text {
                text: root.itemName
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.weight: 600
                color: "#F8FAFC"
                elide: Text.ElideMiddle
                Layout.fillWidth: true
            }

            // Image Dimensions pill (when viewing image)
            Rectangle {
                visible: root.isImage && imgViewer.status === Image.Ready
                implicitHeight: 28
                implicitWidth: dimText.implicitWidth + 14
                radius: 6
                color: "#131926"
                border.color: "#27344D"
                border.width: 1

                Text {
                    id: dimText
                    anchors.centerIn: parent
                    text: imgViewer.implicitWidth + " × " + imgViewer.implicitHeight
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    color: "#38BDF8"
                }
            }

            // File Size Pill
            Rectangle {
                visible: root.currentItem && root.currentItem.size > 0
                implicitHeight: 28
                implicitWidth: szText.implicitWidth + 14
                radius: 6
                color: "#131926"
                border.color: "#27344D"
                border.width: 1

                Text {
                    id: szText
                    anchors.centerIn: parent
                    text: root.currentItem ? formatBytes(root.currentItem.size) : ""
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 10
                    color: "#94A3B8"
                }
            }

            // Image Zoom Controls
            Row {
                visible: root.isImage
                spacing: 4

                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomInMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "➕"; font.pixelSize: 10; color: "#E2E8F0" }
                    MouseArea {
                        id: zoomInMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.zoomFactor = Math.min(4.0, root.zoomFactor + 0.25)
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomOutMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "➖"; font.pixelSize: 10; color: "#E2E8F0" }
                    MouseArea {
                        id: zoomOutMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.zoomFactor = Math.max(0.25, root.zoomFactor - 0.25)
                    }
                }
                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: zoomResetMouse.containsMouse ? "#222D42" : "#141A28"
                    border.color: "#2A364E"; border.width: 1
                    Text { anchors.centerIn: parent; text: "1:1"; font.pixelSize: 10; font.weight: 600; color: "#38BDF8" }
                    MouseArea {
                        id: zoomResetMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.zoomFactor = 1.0
                    }
                }
            }

            // Open Externally Button
            Rectangle {
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
                MouseArea {
                    id: extMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.openPathInSystem) {
                            root.bridge.openPathInSystem(root.itemPath)
                        }
                    }
                }
            }

            // Reveal in Folder Button
            Rectangle {
                width: 28; height: 28; radius: 5
                color: folderMouse.containsMouse ? "#1E273A" : "#141A28"
                border.color: folderMouse.containsMouse ? "#38BDF8" : "#2A364E"
                border.width: 1
                Text { anchors.centerIn: parent; text: "📂"; font.pixelSize: 12 }
                MouseArea {
                    id: folderMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.bridge && root.bridge.openFolder) {
                            var dir = root.itemPath.substring(0, Math.max(root.itemPath.lastIndexOf("/"), root.itemPath.lastIndexOf("\\")))
                            root.bridge.openFolder(dir)
                        }
                    }
                }
            }
        }

        // 2. MAIN MEDIA DISPLAY AREA WITH CHEVRONS
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Image / GIF Preview with Pan & Zoom
            Flickable {
                id: imageFlickable
                visible: root.isImage
                anchors.fill: parent
                contentWidth: Math.max(parent.width, imgViewer.width * root.zoomFactor)
                contentHeight: Math.max(parent.height, imgViewer.height * root.zoomFactor)
                clip: true

                Image {
                    id: imgViewer
                    anchors.centerIn: parent
                    source: root.isImage ? root.toUrl(root.itemPath) : ""
                    asynchronous: true
                    fillMode: Image.PreserveAspectFit
                    width: parent.width
                    height: parent.height
                    scale: root.zoomFactor

                    Behavior on scale {
                        NumberAnimation { duration: 120 }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onDoubleClicked: {
                            root.zoomFactor = (root.zoomFactor > 1.2 ? 1.0 : 2.0)
                        }
                        onWheel: function(wheel) {
                            if (wheel.angleDelta.y > 0) {
                                root.zoomFactor = Math.min(4.0, root.zoomFactor + 0.2)
                            } else {
                                root.zoomFactor = Math.max(0.25, root.zoomFactor - 0.2)
                            }
                        }
                    }
                }
            }

            // Video Preview
            Item {
                id: videoContainer
                visible: root.isVideo
                anchors.fill: parent

                VideoOutput {
                    id: videoOutput
                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectFit
                }

                // Click video area to toggle play/pause
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (mediaPlayer.playbackState === MediaPlayer.PlayingState) {
                            mediaPlayer.pause()
                        } else {
                            mediaPlayer.play()
                        }
                    }
                }
            }

            // Audio Preview (Vinyl / Card aesthetic)
            Item {
                visible: root.isAudio
                anchors.fill: parent

                Rectangle {
                    width: Math.min(420, parent.width - 40)
                    implicitHeight: 240
                    anchors.centerIn: parent
                    radius: 16
                    color: "#121724"
                    border.color: "#253147"
                    border.width: 1.5

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 16

                        RowLayout {
                            spacing: 16
                            Rectangle {
                                width: 72
                                height: 72
                                radius: 36
                                color: "#0D111A"
                                border.color: "#10B981"
                                border.width: 2

                                Text {
                                    anchors.centerIn: parent
                                    text: "🎵"
                                    font.pixelSize: 32
                                }
                            }

                            ColumnLayout {
                                spacing: 4
                                Layout.fillWidth: true
                                Text {
                                    text: root.itemName
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 14
                                    font.weight: 700
                                    color: "#F8FAFC"
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: root.currentItem ? formatBytes(root.currentItem.size) : ""
                                    font.family: "Segoe UI, monospace"
                                    font.pixelSize: 11
                                    color: "#94A3B8"
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        Text {
                            text: formatTime(mediaPlayer.position) + " / " + formatTime(mediaPlayer.duration)
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 11
                            color: "#10B981"
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
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
                opacity: prevChevMouse.containsMouse ? 0.95 : 0.6
                border.color: prevChevMouse.containsMouse ? "#38BDF8" : "#243044"
                border.width: 1
                visible: root.mediaList.length > 1

                Text {
                    anchors.centerIn: parent
                    text: "‹"
                    font.pixelSize: 32
                    font.weight: 300
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: prevChevMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.prevItem()
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
                opacity: nextChevMouse.containsMouse ? 0.95 : 0.6
                border.color: nextChevMouse.containsMouse ? "#38BDF8" : "#243044"
                border.width: 1
                visible: root.mediaList.length > 1

                Text {
                    anchors.centerIn: parent
                    text: "›"
                    font.pixelSize: 32
                    font.weight: 300
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: nextChevMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.nextItem()
                }
            }
        }

        // 3. MEDIA PLAYBACK CONTROL BAR (for Video and Audio)
        Rectangle {
            visible: root.isVideo || root.isAudio
            Layout.fillWidth: true
            implicitHeight: 46
            radius: 8
            color: "#121724"
            border.color: "#253147"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                // Play / Pause Button
                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    color: playBtnMouse.containsMouse ? "#38BDF8" : "#1F293D"
                    border.color: "#38BDF8"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: (mediaPlayer.playbackState === MediaPlayer.PlayingState) ? "⏸" : "▶"
                        font.pixelSize: 12
                        color: playBtnMouse.containsMouse ? "#0B0E14" : "#F8FAFC"
                    }

                    MouseArea {
                        id: playBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (mediaPlayer.playbackState === MediaPlayer.PlayingState) {
                                mediaPlayer.pause()
                            } else {
                                mediaPlayer.play()
                            }
                        }
                    }
                }

                // Time Elapsed
                Text {
                    text: formatTime(mediaPlayer.position)
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                // Timeline Scrubber Slider
                Slider {
                    id: timeSlider
                    Layout.fillWidth: true
                    from: 0
                    to: Math.max(1, mediaPlayer.duration)
                    value: mediaPlayer.position

                    onMoved: {
                        mediaPlayer.setPosition(value)
                    }
                }

                // Time Total
                Text {
                    text: formatTime(mediaPlayer.duration)
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }

                // Loop Toggle
                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: root.isLooping ? "#223354" : (loopMouse.containsMouse ? "#1A2234" : "transparent")
                    border.color: root.isLooping ? "#38BDF8" : "transparent"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "🔁"
                        font.pixelSize: 11
                    }
                    MouseArea {
                        id: loopMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.isLooping = !root.isLooping
                    }
                }

                // Volume Icon & Slider
                Text {
                    text: audioOutput.muted ? "🔇" : (audioOutput.volume > 0.5 ? "🔊" : "🔉")
                    font.pixelSize: 13
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: audioOutput.muted = !audioOutput.muted
                    }
                }

                Slider {
                    implicitWidth: 80
                    from: 0.0
                    to: 1.0
                    value: audioOutput.volume
                    onMoved: {
                        audioOutput.volume = value
                        if (audioOutput.muted && value > 0) {
                            audioOutput.muted = false
                        }
                    }
                }
            }
        }
    }
}
