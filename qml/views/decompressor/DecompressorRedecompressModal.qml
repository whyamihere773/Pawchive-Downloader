import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ═══════════════════════════════════════════════════════════════════════════
// ── 🔄 REDECOMPRESS CONFIRMATION MODAL ───────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
// ── Redecompress confirm modal with spring-physics animation ─────────────
Rectangle {
    id: redecompressModalBackdrop
    required property var view
    anchors.fill: parent
    visible: opacity > 0
    opacity: redecompressModalBackdrop.view.showRedecompressModal ? 1.0 : 0.0
    color: "#B3000000"
    z: 998

    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
    }

    MouseArea { anchors.fill: parent }

    Rectangle {
        id: redecompressCard
        anchors.centerIn: parent
        width: Math.min(460, parent.width - 40)
        implicitHeight: redecompressCol.implicitHeight + 36
        radius: 14
        color: "#0F172A"
        border.color: "#D97706"
        border.width: 1

        // Slightly heavier feel — amber modal has more visual weight
        scale: redecompressModalBackdrop.view.showRedecompressModal ? 1.0 : 0.80
        opacity: redecompressModalBackdrop.view.showRedecompressModal ? 1.0 : 0.0
        transformOrigin: Item.Center

        Behavior on scale {
            SpringAnimation {
                spring: 4.8
                damping: 0.48
                mass: 1.7
                epsilon: 0.001
            }
        }
        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
        }
        ColumnLayout {
            id: redecompressCol
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16

            // Header
            RowLayout {
                spacing: 12
                Text { text: "🔄"; font.pixelSize: 22 }
                ColumnLayout {
                    spacing: 3
                    Layout.fillWidth: true
                    Text {
                        text: redecompressModalBackdrop.view.tr("modal_redecompress_title", "Already Extracted")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#FBB040"
                    }
                    Text {
                        text: redecompressModalBackdrop.view.tr("modal_redecompress_desc", "The selected archives have already been extracted. Do you want to re-extract them and overwrite the existing files?")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // Info badge
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: redecompressInfoCol.implicitHeight + 18
                radius: 8
                color: "#1C1200"
                border.color: "#78350F"
                border.width: 1

                ColumnLayout {
                    id: redecompressInfoCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    spacing: 4

                    Text {
                        text: redecompressModalBackdrop.view.redecompressAlreadyDoneCount + " " +
                              (redecompressModalBackdrop.view.redecompressAlreadyDoneCount === 1
                               ? redecompressModalBackdrop.view.tr("modal_redecompress_archive_singular", "archive already has extracted files on disk.")
                               : redecompressModalBackdrop.view.tr("modal_redecompress_archive_plural", "archives already have extracted files on disk."))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: "#FBB040"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "⚠️ " + redecompressModalBackdrop.view.tr("modal_redecompress_overwrite_warn", "Existing files in the output folder will be overwritten.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#F87171"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                // Cancel
                Rectangle {
                    height: 32
                    implicitWidth: redecompressCancelTxt.implicitWidth + 24
                    radius: 6
                    color: redecompressCancelMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: "#475569"
                    border.width: 1

                    Text {
                        id: redecompressCancelTxt
                        anchors.centerIn: parent
                        text: redecompressModalBackdrop.view.tr("dialog_cancel", "Cancel")
                        font.pixelSize: 12
                        color: "#E2E8F0"
                    }
                    MouseArea {
                        id: redecompressCancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: redecompressModalBackdrop.view.showRedecompressModal = false
                    }
                }

                // Re-extract button
                Rectangle {
                    height: 32
                    implicitWidth: redecompressProceedTxt.implicitWidth + 24
                    radius: 6
                    color: redecompressProceedMouse.containsMouse ? "#B45309" : "#D97706"
                    border.color: "#FBB040"
                    border.width: 1

                    Text {
                        id: redecompressProceedTxt
                        anchors.centerIn: parent
                        text: "🔄 " + redecompressModalBackdrop.view.tr("modal_redecompress_proceed", "Re-extract & Overwrite")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: redecompressProceedMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            redecompressModalBackdrop.view.showRedecompressModal = false;
                            if (redecompressModalBackdrop.view.decompressor) redecompressModalBackdrop.view.decompressor.confirmRedecompress();
                        }
                    }
                }
            }
        }
    }
}
