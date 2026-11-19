import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ═══════════════════════════════════════════════════════════════════════════
// ── 🗜 COMPRESSION REVIEW: KEEP OR REMOVE THE ORIGINALS ──────────────────
// ═══════════════════════════════════════════════════════════════════════════
Rectangle {
    id: compressReviewBackdrop
    required property var view
    objectName: "compressReviewModal"
    anchors.fill: parent
    visible: opacity > 0
    opacity: compressReviewBackdrop.view.showCompressReview ? 1.0 : 0.0
    color: "#B3000000"
    z: 998

    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
    }

    MouseArea { anchors.fill: parent }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 40)
        implicitHeight: compressReviewCol.implicitHeight + 36
        radius: 14
        color: "#0F172A"
        border.color: "#0284C7"
        border.width: 1
        scale: compressReviewBackdrop.view.showCompressReview ? 1.0 : 0.80
        opacity: compressReviewBackdrop.view.showCompressReview ? 1.0 : 0.0
        transformOrigin: Item.Center

        Behavior on scale {
            SpringAnimation { spring: 4.8; damping: 0.48; mass: 1.7; epsilon: 0.001 }
        }
        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
        }

        ColumnLayout {
            id: compressReviewCol
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16

            RowLayout {
                spacing: 12
                Text { text: "🗜"; font.pixelSize: 22 }
                ColumnLayout {
                    spacing: 3
                    Layout.fillWidth: true
                    Text {
                        text: compressReviewBackdrop.view.tr("compress_review_title", "Compression finished")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#7DD3FC"
                    }
                    Text {
                        text: compressReviewBackdrop.view.tr("compress_review_desc", "The compressed copies are saved next to the originals. Do you want to move the originals to the Recycle Bin?")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: compressReviewInfo.implicitHeight + 18
                radius: 8
                color: "#0B1A2B"
                border.color: "#164E63"
                border.width: 1

                ColumnLayout {
                    id: compressReviewInfo
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    spacing: 4

                    Text {
                        text: compressReviewBackdrop.view.tr("compress_review_count", "%1 file(s) compressed: %2 → %3 (%4% smaller)")
                              .replace("%1", compressReviewBackdrop.view.compressedCount)
                              .replace("%2", compressReviewBackdrop.view.formatBytes(compressReviewBackdrop.view.compressedBefore))
                              .replace("%3", compressReviewBackdrop.view.formatBytes(compressReviewBackdrop.view.compressedAfter))
                              .replace("%4", compressReviewBackdrop.view.compressedBefore > 0 ? Math.round((1 - compressReviewBackdrop.view.compressedAfter / compressReviewBackdrop.view.compressedBefore) * 100) : 0)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: "#E0F2FE"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: compressReviewBackdrop.view.compressFailed > 0
                        text: "⚠️ " + compressReviewBackdrop.view.tr("compress_review_failed", "%1 file(s) couldn't be compressed and were left as they were (see the log).").replace("%1", compressReviewBackdrop.view.compressFailed)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#FBBF24"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Text {
                        text: compressReviewBackdrop.view.tr("compress_review_note", "Files that wouldn't have been smaller were left alone. Anything moved to the Recycle Bin can be restored from there.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Item { Layout.fillWidth: true }

                StyledButton {
                    objectName: "compress_keep_originals"
                    text: compressReviewBackdrop.view.tr("compress_keep_originals", "Keep originals")
                    variant: "outline"
                    implicitHeight: 32
                    onClicked: {
                        compressReviewBackdrop.view.showCompressReview = false;
                        if (compressReviewBackdrop.view.decompressor) compressReviewBackdrop.view.decompressor.keepCompressedOriginals();
                    }
                }
                StyledButton {
                    objectName: "compress_remove_originals"
                    text: compressReviewBackdrop.view.tr("compress_remove_originals", "Move originals to Recycle Bin")
                    variant: "primary"
                    implicitHeight: 32
                    onClicked: {
                        compressReviewBackdrop.view.showCompressReview = false;
                        if (compressReviewBackdrop.view.decompressor) compressReviewBackdrop.view.decompressor.removeCompressedOriginals();
                    }
                }
            }
        }
    }
}
