import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: t2Card
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    implicitHeight: t2Col.implicitHeight + 24
    radius: 6
    color: "#0B111E"
    border.color: currentT2Status === "downloading" ? "#6366F1" : "#1E293B"
    border.width: 1
    clip: true

    readonly property string activeT2Key: (t2Card.view.bridge && t2Card.view.bridge.aiDeepReasonerVariant === "heavy") ? "deep_reasoner_heavy" : "deep_reasoner_light"
    readonly property bool isCurrentT2Ready: (t2Card.view.bridge && t2Card.view.bridge.aiDeepReasonerVariant === "heavy") ? t2Card.view.bridge.aiDeepReasonerHeavyReady : t2Card.view.bridge.aiDeepReasonerLightReady
    readonly property string currentT2Status: activeT2Key === "deep_reasoner_heavy" ? t2Card.view.aiT2HeavyStatus : t2Card.view.aiT2LightStatus
    readonly property real currentT2Percent: activeT2Key === "deep_reasoner_heavy" ? t2Card.view.aiT2HeavyPercent : t2Card.view.aiT2LightPercent
    readonly property string currentT2Speed: activeT2Key === "deep_reasoner_heavy" ? t2Card.view.aiT2HeavySpeed : t2Card.view.aiT2LightSpeed
    readonly property string currentT2Error: activeT2Key === "deep_reasoner_heavy" ? t2Card.view.aiT2HeavyError : t2Card.view.aiT2LightError

    ColumnLayout {
        id: t2Col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 8

        // Optional Notice when in Semantic Matcher Only mode
        Rectangle {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: 26
            radius: 4
            color: "#161E2E"
            border.color: "#1E293B"
            border.width: 1
            visible: t2Card.view.bridge ? (t2Card.view.bridge.aiEngineMode === "semantic_only") : false

            RowLayout {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 6
                Text { text: "💡"; font.pixelSize: 11 }
                Text {
                    text: tr("tip_t2_optional", "Optional in 'Semantic Matcher Only' mode. Deep Context Reasoner SLM is only used when 'Full Hybrid' mode is active.")
                    font.pixelSize: 10
                    color: "#94A3B8"
                    font.italic: true
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            Text {
                text: "🧠"
                font.pixelSize: 13
            }

            Text {
                text: tr("model_t2_title", "Deep Context Reasoner (SLM + Archive)")
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
                implicitWidth: t2StatusText.implicitWidth + 12
                radius: 10
                color: t2Card.currentT2Status === "downloading" ? "#312E81" : (t2Card.currentT2Status === "error" ? "#450A0A" : (t2Card.isCurrentT2Ready ? "#064E3B" : "#1E293B"))
                border.color: t2Card.currentT2Status === "downloading" ? "#6366F1" : (t2Card.currentT2Status === "error" ? "#EF4444" : (t2Card.isCurrentT2Ready ? "#059669" : "#334155"))
                border.width: 1

                Text {
                    id: t2StatusText
                    anchors.centerIn: parent
                    text: t2Card.currentT2Status === "downloading" ? (t2Card.currentT2Percent.toFixed(1) + "%") : (t2Card.currentT2Status === "error" ? "Error" : (t2Card.isCurrentT2Ready ? "Ready" : "Not Downloaded"))
                    font.pixelSize: 9
                    font.weight: 600
                    color: t2Card.currentT2Status === "downloading" ? "#A5B4FC" : (t2Card.currentT2Status === "error" ? "#F87171" : (t2Card.isCurrentT2Ready ? "#34D399" : "#94A3B8"))
                }
            }

            // Action Button
            StyledButton {
                variant: t2Card.currentT2Status === "downloading" ? "secondary" : (t2Card.isCurrentT2Ready ? "danger" : "primary")
                text: t2Card.currentT2Status === "downloading" ? tr("btn_cancel", "Cancel") : (t2Card.isCurrentT2Ready ? tr("btn_remove_model", "Remove") : (t2Card.currentT2Status === "error" ? tr("btn_retry", "Retry") : (t2Card.view.bridge && t2Card.view.bridge.aiDeepReasonerVariant === "heavy" ? tr("btn_download_t2_smart", "Download 1.0 GB") : tr("btn_download_t2_light", "Download 490 MB"))))
                implicitHeight: 26
                font.pixelSize: 10
                onClicked: {
                    if (!t2Card.view.bridge) return
                    var key = t2Card.activeT2Key
                    if (t2Card.currentT2Status === "downloading") {
                        t2Card.view.bridge.cancelAiModelDownload(key)
                    } else if (t2Card.isCurrentT2Ready) {
                        t2Card.view.bridge.deleteAiModel(key)
                    } else {
                        t2Card.view.bridge.startAiModelDownload(key)
                    }
                }
            }
        }

        // Dedicated Download Progress Bar
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 4
            visible: t2Card.currentT2Status === "downloading"

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0

                Text {
                    text: tr("lbl_downloading_t2", "Downloading reasoning SLM weights...")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#818CF8"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                }

                Text {
                    text: t2Card.currentT2Speed
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 10
                    color: "#A78BFA"
                    visible: t2Card.currentT2Speed !== ""
                }

                Text {
                    text: t2Card.currentT2Percent.toFixed(1) + "%"
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
                    width: Math.max(0, Math.min(parent.width, parent.width * (t2Card.currentT2Percent / 100.0)))
                    radius: 3
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#4F46E5" }
                        GradientStop { position: 1.0; color: "#818CF8" }
                    }
                    Behavior on width {
                        NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
                    }
                }
            }
        }

        // Error Notification Banner
        Rectangle {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: 28
            radius: 4
            color: "#450A0A"
            border.color: "#EF4444"
            border.width: 1
            visible: t2Card.currentT2Status === "error"

            RowLayout {
                anchors.fill: parent
                anchors.margins: 6
                spacing: 6
                Text { text: "⚠️"; font.pixelSize: 11 }
                Text {
                    text: t2Card.currentT2Error !== "" ? t2Card.currentT2Error : tr("err_download_failed", "Download failed. Please check your internet connection.")
                    font.pixelSize: 10
                    color: "#FCA5A5"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                }
            }
        }

        // Variant Selector: Light vs Smart
        Text {
            text: tr("lbl_llm_tier", "Model Size:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            font.weight: 600
            color: "#E2E8F0"
        }

        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            FilterCheckbox {
                label: tr("llm_opt_light", "Light (Qwen 0.5B • ~490 MB)")
                iconText: "🪶"
                activeColor: "#34D399"
                tooltip: tr("llm_opt_light_tip", "Potato-friendly 0.5B model. Low memory (~450 MB RAM), quick deductions on CPU.")
                checked: t2Card.view.bridge ? t2Card.view.bridge.aiDeepReasonerVariant === "light" : true
                onClicked: if (t2Card.view.bridge) t2Card.view.bridge.aiDeepReasonerVariant = "light"
            }

            FilterCheckbox {
                label: tr("llm_opt_smart", "Smart (Qwen 1.5B • ~1.04 GB)")
                iconText: "✨"
                activeColor: "#818CF8"
                tooltip: tr("llm_opt_smart_tip", "Higher intelligence and deeper anime & pop culture knowledge. Best for modern GPUs/CPUs.")
                checked: t2Card.view.bridge ? t2Card.view.bridge.aiDeepReasonerVariant === "heavy" : false
                onClicked: if (t2Card.view.bridge) t2Card.view.bridge.aiDeepReasonerVariant = "heavy"
            }
        }

        Text {
            text: tr("desc_model_t2", "Deduces character and series names by cross-referencing subtle post tokens against the creator's historical download patterns from download_archive.db.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            color: "#64748B"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
    }
}
