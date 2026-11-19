import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

// Audio preview card, buffering pill, and error state overlays for MediaLightboxModal.
Item {
    id: statesRoot
    required property var modal
    required property var player
    property int imageStatus: Image.Null
    property int imageImplicitWidth: 0

    // Audio Preview (Vinyl / Card aesthetic)
    Item {
        visible: statesRoot.modal.isAudio
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
                            text: statesRoot.modal.itemName
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 14
                            font.weight: 700
                            color: "#F8FAFC"
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                        Text {
                            text: statesRoot.modal.currentItem ? statesRoot.modal.formatBytes(statesRoot.modal.currentItem.size) : ""
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Text {
                    text: statesRoot.modal.formatClock(statesRoot.player.position, statesRoot.player.duration) + " / " + statesRoot.modal.formatClock(statesRoot.player.duration, statesRoot.player.duration)
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 11
                    color: "#10B981"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

    // Streaming / buffering status pill (remote pictures & online videos/audio)
    Rectangle {
        visible: statesRoot.modal.remoteLoading || (statesRoot.modal.isImage && statesRoot.imageStatus === Image.Loading) || (statesRoot.modal.isMedia && (statesRoot.player.mediaStatus === MediaPlayer.LoadingMedia || statesRoot.player.mediaStatus === MediaPlayer.BufferingMedia || statesRoot.player.mediaStatus === MediaPlayer.StalledMedia))
        anchors.centerIn: parent
        width: bufRow.implicitWidth + 28
        height: 40
        radius: 20
        color: "#E60B0F18"
        border.color: "#38BDF8"
        border.width: 1
        z: 5

        Row {
            id: bufRow
            anchors.centerIn: parent
            spacing: 10
            BusyIndicator {
                width: 20
                height: 20
                running: parent.visible
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: statesRoot.modal.isMedia ? "Buffering stream…" : "Loading media…"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#E0F2FE"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // A video / audio file the player can't open
    Column {
        anchors.centerIn: parent
        spacing: 8
        z: 4
        visible: (statesRoot.modal.isVideo || statesRoot.modal.isAudio) && statesRoot.player.error !== MediaPlayer.NoError
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: statesRoot.modal.isVideo ? "🎬" : "🎵"; font.pixelSize: 40; opacity: 0.5 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "This " + (statesRoot.modal.isVideo ? "video" : "audio file") + " can't be played here."
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 13
            color: "#94A3B8"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: statesRoot.player.errorString + (statesRoot.modal.hideExternalActions ? "" : "  •  Try \"Open Externally\"")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#64748B"
        }
        Rectangle {
            visible: statesRoot.modal.isRemote
            anchors.horizontalCenter: parent.horizontalCenter
            width: retryMediaTxt.implicitWidth + 24
            height: 28
            radius: 6
            color: "#1E293B"
            border.color: "#38BDF8"
            Text { id: retryMediaTxt; anchors.centerIn: parent; text: "↻ Retry Stream"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#7DD3FC" }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: statesRoot.modal.loadCurrentItem() }
        }
    }

    // Shown when a picture fails to load remotely or can't be decoded at all
    Column {
        anchors.centerIn: parent
        spacing: 8
        z: 4
        visible: statesRoot.modal.isImage && (statesRoot.modal.remoteError.length > 0 || (statesRoot.imageStatus === Image.Ready && statesRoot.imageImplicitWidth <= 1))
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🖼️"; font.pixelSize: 40; opacity: 0.5 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: statesRoot.modal.remoteError.length > 0 ? ("Couldn't load image (" + statesRoot.modal.remoteError + ")") : "This picture can't be displayed (unknown or damaged format)."
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 13
            color: "#94A3B8"
        }
        Text {
            visible: !statesRoot.modal.hideExternalActions && statesRoot.modal.remoteError.length === 0
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Try \"Open Externally\" to use another app."
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#64748B"
        }
        Rectangle {
            visible: statesRoot.modal.isRemote
            anchors.horizontalCenter: parent.horizontalCenter
            width: retryImgTxt.implicitWidth + 24
            height: 28
            radius: 6
            color: "#1E293B"
            border.color: "#38BDF8"
            Text { id: retryImgTxt; anchors.centerIn: parent; text: "↻ Retry"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#7DD3FC" }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: statesRoot.modal.loadCurrentItem() }
        }
    }
}
