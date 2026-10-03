import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Export Confirmation Modal
// Shown after exporting the queue state snapshot to allow the user to keep downloads stopped or resume.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string exportedFilePath: ""
    property bool wasDownloading: false

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage      // re-translate when the language changes
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    anchors.fill: parent
    z: 9998
    visible: isOpen

    // ── Semi-transparent backdrop ─────────────────────────────────────────────
    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: "#B0060910"
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
            // Prevent interaction with underlying views
        }
    }

    // ── Modal Card ───────────────────────────────────────────────────────────
    Rectangle {
        id: card
        width: Math.min(520, parent.width - 40)
        height: cardCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        y: root.isOpen ? 0 : -28
        scale: root.isOpen ? 1.0 : 0.88
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on y {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on scale {
            NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
        }
        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        // Ambient glow border
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.color: "#10B98130"
            border.width: 2.5
            z: -1
        }

        ColumnLayout {
            id: cardCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 24
                leftMargin: 24
                rightMargin: 24
            }
            spacing: 16

            // ── Header ────────────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 42
                    height: 42
                    radius: 21
                    color: "#064E3B"
                    border.color: "#10B981"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: "💾"
                        font.pixelSize: 20
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        text: root.tr("export_modal_title", "Queue State Exported Successfully")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }

                    Text {
                        text: root.tr("export_modal_subtitle", "Your download progress and batches have been safely backed up.")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }
                }
            }

            // ── File Path Box ─────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: filePathCol.implicitHeight + 16
                radius: 8
                color: "#1A202C"
                border.color: "#2D3748"
                border.width: 1

                ColumnLayout {
                    id: filePathCol
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: 8
                    }
                    spacing: 4

                    Text {
                        text: root.tr("export_saved_to", "Backup File Location:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#64748B"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.exportedFilePath
                        font.family: "Consolas, 'Cascadia Code', monospace"
                        font.pixelSize: 11
                        color: "#38BDF8"
                        elide: Text.ElideMiddle
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            // ── Notice Box ────────────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                visible: root.wasDownloading
                height: noticeText.implicitHeight + 18
                radius: 8
                color: "#2D2615"
                border.color: "#F59E0B"
                border.width: 1

                Text {
                    id: noticeText
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: 9
                    }
                    text: root.tr("export_pause_notice", "⚠️ Downloads were auto-paused to flush disk buffers and guarantee 0% data corruption. What would you like to do with active downloads now?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#FDE68A"
                    wrapMode: Text.WordWrap
                }
            }

            // ── Action Buttons ────────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // Keep Stopped / Exit Ready button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    radius: 8
                    color: stopMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: "#475569"
                    border.width: 1

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🛑"; font.pixelSize: 13 }
                        Text {
                            text: root.tr("btn_keep_stopped", "Keep Stopped (Exit Ready)")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: "#F1F5F9"
                        }
                    }

                    MouseArea {
                        id: stopMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.isOpen = false
                            if (root.bridge) root.bridge.stopAfterExport()
                        }
                    }
                }

                // Resume / Done button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    radius: 8
                    color: resumeMouse.containsMouse ? "#059669" : "#10B981"

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: root.wasDownloading ? "▶" : "✓"; font.pixelSize: 13; color: "#FFFFFF" }
                        Text {
                            text: root.wasDownloading ? root.tr("btn_resume_downloads", "Resume Downloading") : root.tr("btn_close", "Close")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                    }

                    MouseArea {
                        id: resumeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.isOpen = false
                            if (root.wasDownloading && root.bridge) {
                                root.bridge.resumeAfterExport()
                            }
                        }
                    }
                }
            }
        }
    }
}
