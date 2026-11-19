import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ══════════════════════════════════════════════════════════════════════
// ── DISK SPACE PRE-FLIGHT CHECK MODAL ─────────────────────────────────
// ══════════════════════════════════════════════════════════════════════
// ── Disk space modal with spring-physics animation ──────────────────────
Rectangle {
    id: diskModalBackdrop
    required property var view
    anchors.fill: parent
    // Use opacity > 0 as the visibility gate so the fade-out animation
    // completes before the element is removed from the scene.
    visible: opacity > 0
    opacity: diskModalBackdrop.view.showDiskModal ? 1.0 : 0.0
    color: "#B3000000"
    z: 999

    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
    }

    MouseArea {
        anchors.fill: parent
        // Block clicks through
    }

    Rectangle {
        id: diskModalCard
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 40)
        implicitHeight: modalCol.implicitHeight + 36
        radius: 14
        color: "#0F172A"
        border.color: "#334155"
        border.width: 1

        // Spring entrance: weighted mass bounces in from slightly below
        scale: diskModalBackdrop.view.showDiskModal ? 1.0 : 0.82
        opacity: diskModalBackdrop.view.showDiskModal ? 1.0 : 0.0
        transformOrigin: Item.Center

        Behavior on scale {
            SpringAnimation {
                spring: 5.5
                damping: 0.52
                mass: 1.4
                epsilon: 0.001
            }
        }
        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
        }
        ColumnLayout {
            id: modalCol
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            // Modal Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: "💾"; font.pixelSize: 22 }
                ColumnLayout {
                    spacing: 2
                    Text {
                        text: diskModalBackdrop.view.tr("decompressor_disk_title", "Disk Space Pre-Flight Check")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }
                    Text {
                        text: diskModalBackdrop.view.tr("decompressor_disk_subtitle", "Verifying available disk space on target drives before decompressing.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }
            }

            // Drive Check Items
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Repeater {
                    model: diskModalBackdrop.view.diskCheckData
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 58
                        radius: 8
                        color: modelData.isSufficient ? "#0D1F17" : "#2B1111"
                        border.color: modelData.isSufficient ? "#10B981" : "#EF4444"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            Text {
                                text: modelData.isSufficient ? "✅" : "⚠️"
                                font.pixelSize: 18
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                RowLayout {
                                    Text {
                                        text: "Drive " + modelData.drive
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 13
                                        font.weight: 600
                                        color: "#F1F5F9"
                                    }
                                    Text {
                                        text: "(" + modelData.archiveCount + " archives, " + diskModalBackdrop.view.formatBytes(modelData.totalArchiveSize) + ")"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#94A3B8"
                                    }
                                }
                                Text {
                                    text: "Free: " + diskModalBackdrop.view.formatBytes(modelData.freeBytes) +
                                          "  |  Estimated Required: ~" + diskModalBackdrop.view.formatBytes(modelData.estimatedRequired)
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    color: modelData.isSufficient ? "#34D399" : "#FCA5A5"
                                }
                            }
                        }
                    }
                }
            }

            // Modal Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                // Cancel
                Rectangle {
                    height: 32
                    implicitWidth: modalCancelTxt.implicitWidth + 24
                    radius: 6
                    color: modalCancelMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: "#475569"
                    border.width: 1

                    Text {
                        id: modalCancelTxt
                        anchors.centerIn: parent
                        text: diskModalBackdrop.view.tr("dialog_cancel", "Cancel")
                        font.pixelSize: 12
                        color: "#E2E8F0"
                    }

                    MouseArea {
                        id: modalCancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: diskModalBackdrop.view.showDiskModal = false
                    }
                }

                // Proceed
                Rectangle {
                    height: 32
                    implicitWidth: modalProceedTxt.implicitWidth + 24
                    radius: 6
                    color: modalProceedMouse.containsMouse ? "#059669" : "#10B981"
                    border.color: "#34D399"
                    border.width: 1

                    Text {
                        id: modalProceedTxt
                        anchors.centerIn: parent
                        text: diskModalBackdrop.view.tr("decompressor_proceed", "Proceed with Extraction")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        id: modalProceedMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            diskModalBackdrop.view.showDiskModal = false;
                            if (diskModalBackdrop.view.decompressor) diskModalBackdrop.view.decompressor.startDecompression();
                        }
                    }
                }
            }
        }
    }
}
