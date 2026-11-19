import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: clipCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    implicitHeight: clipCol.implicitHeight + 24
    radius: 6
    color: "#0B111E"
    border.color: clipCard.view.aiClipStatus === "downloading" ? "#10B981" : "#1E293B"
    border.width: 1
    clip: true

    readonly property bool isClipReady: clipCard.view.aiClipStatus === "ready"

    ColumnLayout {
        id: clipCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            Text {
                text: "🎨"
                font.pixelSize: 13
            }

            Text {
                text: tr("model_clip_title", "Gallery Visual Sorter Vision Encoder (CLIP ViT-B/32 INT8 • ~88 MB)")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#E2E8F0"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
            }

            // Status Pill
            Rectangle {
                implicitHeight: 20
                implicitWidth: clipStatusText.implicitWidth + 12
                radius: 10
                color: clipCard.view.aiClipStatus === "downloading" ? "#064E3B" : (clipCard.view.aiClipStatus === "error" ? "#450A0A" : (clipCard.isClipReady ? "#064E3B" : "#1E293B"))
                border.color: clipCard.view.aiClipStatus === "downloading" ? "#10B981" : (clipCard.view.aiClipStatus === "error" ? "#EF4444" : (clipCard.isClipReady ? "#059669" : "#334155"))
                border.width: 1

                Text {
                    id: clipStatusText
                    anchors.centerIn: parent
                    text: clipCard.view.aiClipStatus === "downloading" ? (clipCard.view.aiClipPercent.toFixed(1) + "%") : (clipCard.view.aiClipStatus === "error" ? "Error" : (clipCard.isClipReady ? "Ready" : "Not Downloaded"))
                    font.pixelSize: 9
                    font.weight: 600
                    color: clipCard.view.aiClipStatus === "downloading" ? "#34D399" : (clipCard.view.aiClipStatus === "error" ? "#F87171" : (clipCard.isClipReady ? "#34D399" : "#94A3B8"))
                }
            }

            // Action Button
            StyledButton {
                variant: clipCard.view.aiClipStatus === "downloading" ? "secondary" : (clipCard.isClipReady ? "danger" : "primary")
                text: clipCard.view.aiClipStatus === "downloading" ? tr("btn_cancel", "Cancel") : (clipCard.isClipReady ? tr("btn_remove_model", "Remove") : (clipCard.view.aiClipStatus === "error" ? tr("btn_retry", "Retry") : tr("btn_download_clip", "Download 88 MB")))
                implicitHeight: 26
                font.pixelSize: 10
                onClicked: {
                    if (!clipCard.view.bridge) return
                    if (clipCard.view.aiClipStatus === "downloading") {
                        clipCard.view.bridge.cancelAiModelDownload("visual_clip_vit")
                    } else if (clipCard.isClipReady) {
                        clipCard.view.bridge.deleteAiModel("visual_clip_vit")
                        clipCard.view.syncAiModelStatuses()
                    } else {
                        clipCard.view.bridge.startAiModelDownload("visual_clip_vit")
                    }
                }
            }
        }

        // Download Progress Bar
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 4
            visible: clipCard.view.aiClipStatus === "downloading"

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0

                Text {
                    text: tr("lbl_downloading_clip", "Downloading quantized ONNX vision weights...")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#34D399"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                }

                Text {
                    text: clipCard.view.aiClipSpeed
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    color: "#A78BFA"
                    visible: clipCard.view.aiClipSpeed !== ""
                }

                Text {
                    text: clipCard.view.aiClipPercent.toFixed(1) + "%"
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#E2E8F0"
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                height: 6
                radius: 3
                color: "#161E2E"
                border.color: "#1E293B"
                border.width: 1
                clip: true

                Rectangle {
                    height: parent.height
                    width: Math.max(0, Math.min(parent.width, parent.width * (clipCard.view.aiClipPercent / 100.0)))
                    radius: 3
                    color: "#10B981"
                    Behavior on width {
                        NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
                    }
                }
            }
        }

        Text {
            text: tr("desc_model_clip", "Powers the Gallery Visual Sorter with DirectML / CPU neural vision embeddings for visual style, aesthetic clustering, and natural-language custom sorting.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            color: "#64748B"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
    }
}
