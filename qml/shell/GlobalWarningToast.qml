import QtQuick

// ── Global session-discard warning toast ──────────────────────────────────
// Shown briefly (amber) when a new download URL auto-discards a leftover
// interrupted session, or to notify about required authentication.
Item {
    id: discardWarningToast
    anchors.bottom: parent.bottom
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottomMargin: 32
    width: discardToastText.implicitWidth + 52
    height: 44
    z: 10000
    visible: opacity > 0
    opacity: 0

    property var actionCallback: null

    function show(oldArtist) {
        actionCallback = null
        var msg = oldArtist && oldArtist !== "previous"
            ? "⚠️  Previous session (" + oldArtist + ") discarded — starting fresh"
            : "⚠️  Previous interrupted session discarded — starting fresh"
        discardToastText.text = msg
        opacity = 1.0
        discardToastTimer.restart()
    }

    function showMessage(msg, callback) {
        actionCallback = callback || null
        discardToastText.text = msg
        opacity = 1.0
        discardToastTimer.restart()
    }

    Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

    Timer {
        id: discardToastTimer
        interval: 5500
        onTriggered: discardWarningToast.opacity = 0
    }

    Rectangle {
        anchors.fill: parent
        radius: 22
        color: "#2A1A00"
        border.color: "#F59E0B"
        border.width: 1.5

        MouseArea {
            anchors.fill: parent
            cursorShape: discardWarningToast.actionCallback ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: {
                if (discardWarningToast.actionCallback) {
                    var cb = discardWarningToast.actionCallback
                    discardWarningToast.actionCallback = null
                    cb()
                }
                discardWarningToast.opacity = 0
            }
        }

        Text {
            id: discardToastText
            anchors.centerIn: parent
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            font.weight: Font.DemiBold
            color: "#FCD34D"
        }
    }
}
