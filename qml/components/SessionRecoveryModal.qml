import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Session Recovery Modal
// Displays interrupted download sessions with multi-artist and multi-platform breakdown.
// Allows users to cleanly resume or discard.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property var sessionSummary: bridge ? bridge.recoverySummary : null

    function tr(key, fallback) {
        if (!Lang) return fallback !== undefined ? fallback : key
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    anchors.fill: parent
    z: 9999
    visible: isOpen

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B0060910"
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
        }
    }

    // Modal Card
    Rectangle {
        id: card
        width: Math.min(560, parent.width - 40)
        implicitHeight: cardCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 16
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        y: root.isOpen ? 0 : -28
        scale: root.isOpen ? 1.0 : 0.90
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

            // Header Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Rectangle {
                    width: 44
                    height: 44
                    radius: 22
                    color: "#1E293B"
                    border.color: "#34D399"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: "🔄"
                        font.pixelSize: 22
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        text: root.tr("recovery_modal_title", "Unfinished Download Detected")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 17
                        font.bold: true
                        color: "#F1F5F9"
                    }

                    Text {
                        text: root.tr("recovery_modal_subtitle", "Pawchive Downloader was interrupted. Your download progress was saved safely.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            // Separator
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E293B"
            }

            // Overall Progress Summary Box
            Rectangle {
                Layout.fillWidth: true
                height: 64
                radius: 10
                color: "#0B0E14"
                border.color: "#222A3A"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: root.tr("recovery_label_progress", "Saved Progress:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.bold: true
                            color: "#CBD5E1"
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: {
                                var s = root.sessionSummary || (root.bridge ? root.bridge.recoverySummary : null)
                                if (!s) return "0%"
                                var pct = s.percent !== undefined ? s.percent : 0
                                var comp = s.completed_files || 0
                                var tot = s.total_files || 0
                                var dl = s.formatted_downloaded || "0 B"
                                return comp + " / " + tot + " files (" + pct + "%) • " + dl
                            }
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.bold: true
                            color: "#34D399"
                        }
                    }

                    // Progress Bar Track
                    Rectangle {
                        Layout.fillWidth: true
                        height: 8
                        radius: 4
                        color: "#1A2234"

                        Rectangle {
                            height: parent.height
                            radius: 4
                            color: "#34D399"
                            width: {
                                var s = root.sessionSummary || (root.bridge ? root.bridge.recoverySummary : null)
                                var pct = (s && s.percent !== undefined) ? s.percent : 0
                                return Math.max(0, Math.min(parent.width, parent.width * (pct / 100.0)))
                            }
                            Behavior on width {
                                NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                            }
                        }
                    }
                }
            }

            // Artists & Platforms Section Title
            Text {
                text: root.tr("recovery_label_creators", "Creators in Queue:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.bold: true
                color: "#94A3B8"
            }

            // Scrollable Creator List
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.min(180, Math.max(50, artistList.contentHeight + 10))
                radius: 10
                color: "#0D111A"
                border.color: "#1E293B"
                border.width: 1
                clip: true

                SmoothListView {
                    id: artistList
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 6
                    model: {
                        var s = root.sessionSummary || (root.bridge ? root.bridge.recoverySummary : null)
                        return (s && s.artists) ? s.artists : []
                    }

                    delegate: Rectangle {
                        width: artistList.width
                        height: 38
                        radius: 6
                        color: "#151B27"
                        border.color: "#222C3E"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8

                            Text {
                                text: modelData.name || "Unknown Artist"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.bold: true
                                color: "#F1F5F9"
                                elide: Text.ElideRight
                                Layout.preferredWidth: Math.min(180, parent.width * 0.4)
                            }

                            // Platform Tag Pill
                            Rectangle {
                                height: 20
                                width: platText.implicitWidth + 12
                                radius: 10
                                color: "#1E293B"
                                border.color: "#38BDF8"
                                border.width: 1

                                Text {
                                    id: platText
                                    anchors.centerIn: parent
                                    text: modelData.platform || "Kemono"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#38BDF8"
                                }
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: (modelData.completed || 0) + " / " + (modelData.total || 0) + " files"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: (modelData.completed >= modelData.total && modelData.total > 0) ? "#34D399" : "#94A3B8"
                            }
                        }
                    }
                }
            }

            // Timestamp Note
            Text {
                text: {
                    var s = root.sessionSummary || (root.bridge ? root.bridge.recoverySummary : null)
                    var ts = (s && s.saved_at) ? s.saved_at : ""
                    return ts ? (root.tr("recovery_saved_at", "Interrupted checkpoint: ") + ts) : ""
                }
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                visible: text.length > 0
            }

            // Action Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Layout.topMargin: 4

                // Discard Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    radius: 8
                    color: discardMouse.containsMouse ? "#2B1111" : "#1C0D0D"
                    border.color: discardMouse.containsMouse ? "#DC2626" : "#7F1D1D"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🗑"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.tr("action_discard_fresh", "Discard & Start Fresh")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.bold: true
                            color: "#FCA5A5"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: discardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bridge) {
                                root.bridge.discardRecoverySession()
                            }
                            root.isOpen = false
                        }
                    }
                }

                // Resume Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    radius: 8
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: resumeMouse.containsMouse ? "#059669" : "#047857" }
                        GradientStop { position: 1.0; color: resumeMouse.containsMouse ? "#10B981" : "#059669" }
                    }
                    border.color: "#34D399"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "▶"; font.pixelSize: 12; color: "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: root.tr("action_resume_download", "Resume Download")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.bold: true
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: resumeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.bridge) {
                                root.bridge.resumeRecoverySession()
                            }
                            root.isOpen = false
                        }
                    }
                }
            }
        }
    }
}
