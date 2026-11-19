import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab3Content
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    visible: subTab3Content.view.currentSubTab === 3
    Layout.fillWidth: true
    spacing: 12

// Character & Franchise Recognition Engine (Master Database vs Auto-Learning)
CardSection {
    Layout.fillWidth: true
    interactive: !subTab3Content.view.isScrolling
    title: tr("section_known_engine", "Character & Franchise Recognition (Known Engine)")
    iconText: "🏷️"
    entranceOffsetY: subTab3Content.view.tabEntranceOffsetY
    entranceOpacity: subTab3Content.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 10

        Text {
            text: tr("desc_known_engine", "Choose how the engine identifies characters and structures folders (Franchise ➔ Character):")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            wrapMode: Text.WordWrap
        }

        Flow {
            width: parent.width
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            FilterCheckbox {
                label: tr("mode_hybrid", "Master DB + Auto-Learn (Hybrid)")
                iconText: "✨"
                activeColor: "#38BDF8"
                tooltip: tr("mode_hybrid_tip", "Combines the comprehensive 100k+ game & anime database with automatic learning of new tags into Known.txt (Recommended)")
                checked: subTab3Content.view.bridge ? (subTab3Content.view.bridge.knownRecognitionMode === "hybrid" || subTab3Content.view.bridge.knownRecognitionMode === "") : true
                onClicked: if (subTab3Content.view.bridge) subTab3Content.view.bridge.knownRecognitionMode = "hybrid"
            }

            FilterCheckbox {
                label: tr("mode_database_only", "Master Database Only")
                iconText: "📚"
                activeColor: "#818CF8"
                tooltip: tr("mode_database_only_tip", "Only matches against the curated 100k+ video game/anime database (prevents modifying Known.txt)")
                checked: subTab3Content.view.bridge ? subTab3Content.view.bridge.knownRecognitionMode === "database_only" : false
                onClicked: if (subTab3Content.view.bridge) subTab3Content.view.bridge.knownRecognitionMode = "database_only"
            }

            FilterCheckbox {
                label: tr("mode_learning_only", "Custom Known.txt Only")
                iconText: "📝"
                activeColor: "#34D399"
                tooltip: tr("mode_learning_only_tip", "Only uses your custom Known.txt and learns new character tags as downloads run")
                checked: subTab3Content.view.bridge ? subTab3Content.view.bridge.knownRecognitionMode === "learning_only" : false
                onClicked: if (subTab3Content.view.bridge) subTab3Content.view.bridge.knownRecognitionMode = "learning_only"
            }
        }

        Text {
            text: tr("note_known_structure", "ℹ️ When 'Separate folders by Known' is enabled, downloads will automatically sort into: 'Franchise Name / Character Name / Post Folder'.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#64748B"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        // AI-Assisted Recognition & Archive Reasoning Sub-Card
        Rectangle {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: aiCol.implicitHeight + 28
            radius: 8
            color: "#141A26"
            border.color: aiBoxHover.hovered ? "#38BDF8" : "#233147"
            border.width: 1
            clip: true

            HoverHandler { id: aiBoxHover }

            transform: Translate {
                y: aiBoxHover.hovered ? -1.5 : 0
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                }
            }

            Behavior on border.color { ColorAnimation { duration: 160 } }

            ColumnLayout {
                id: aiCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 12

                // Header Row: Title, Hardware Badge, Switch
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Text {
                        text: "🧠"
                        font.pixelSize: 15
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: tr("opt_ai_recognition_title", "AI Semantic Assistant & Archive Reasoning")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#F1F5F9"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        elide: Text.ElideRight
                    }

                    // Hardware Acceleration Badge
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: hwBadgeText.implicitWidth + 12
                        radius: 10
                        color: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#064E3B" : "#1E293B"
                        border.color: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#10B981" : "#475569"
                        border.width: 1

                        Text {
                            id: hwBadgeText
                            anchors.centerIn: parent
                            text: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? ("⚡ " + subTab3Content.view.bridge.aiHardwareBadge) : ("💻 " + (subTab3Content.view.bridge ? subTab3Content.view.bridge.aiHardwareBadge : "CPU"))
                            font.pixelSize: 9
                            font.weight: 600
                            color: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiHardwareBadge.indexOf("GPU") !== -1) ? "#34D399" : "#94A3B8"
                        }
                    }

                    StyledSwitch {
                        checked: subTab3Content.view.bridge ? subTab3Content.view.bridge.aiRecognitionEnabled : false
                        accentColor: "#38BDF8"
                        onToggled: function(isChecked) {
                            if (subTab3Content.view.bridge) subTab3Content.view.bridge.aiRecognitionEnabled = isChecked
                        }
                    }
                }

                Text {
                    text: tr("desc_ai_recognition", "Uses vector semantic embeddings and creator archive patterns to identify obscure, unspaced, and misspelled character titles without manual rules. 100% offline, zero-handholding.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                }

                // Collapsible Drawer when enabled
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 12
                    visible: subTab3Content.view.bridge ? subTab3Content.view.bridge.aiRecognitionEnabled : false

                    // Engine Mode Selection: Semantic Matcher Only vs Full Hybrid
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 6

                        Text {
                            text: tr("lbl_ai_engine_mode", "Recognition Engine Mode:")
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
                                label: tr("ai_mode_minilm_only", "Semantic Only (MiniLM • Fast)")
                                iconText: "⚡"
                                activeColor: "#38BDF8"
                                tooltip: tr("ai_mode_minilm_only_tip", "Runs fast vector embeddings only (~127 MB). Instant 1–3 ms inference on CPU with zero LLM RAM overhead. Best for potato PCs and pure speed.")
                                checked: subTab3Content.view.bridge ? (subTab3Content.view.bridge.aiEngineMode === "semantic_only") : false
                                onClicked: if (subTab3Content.view.bridge) subTab3Content.view.bridge.aiEngineMode = "semantic_only"
                            }

                            FilterCheckbox {
                                label: tr("ai_mode_hybrid", "Full Hybrid (MiniLM + Reasoner)")
                                iconText: "🧠"
                                activeColor: "#818CF8"
                                tooltip: tr("ai_mode_hybrid_tip", "Combines MiniLM vector search with offline SLM reasoning. Analyzes creator archive history to deduce obscure, unspaced, and cryptic titles.")
                                checked: subTab3Content.view.bridge ? (subTab3Content.view.bridge.aiEngineMode === "hybrid" || subTab3Content.view.bridge.aiEngineMode === "") : true
                                onClicked: if (subTab3Content.view.bridge) subTab3Content.view.bridge.aiEngineMode = "hybrid"
                            }
                        }

                        Text {
                            text: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiEngineMode === "semantic_only")
                                ? tr("desc_ai_mode_minilm", "⚡ MiniLM-only mode active: Only the Fast Multilingual Matcher is needed. Deep Context Reasoner SLM will be completely bypassed.")
                                : tr("desc_ai_mode_hybrid", "🧠 Full Hybrid mode active: Fast heuristics run first, followed by MiniLM embeddings, and finally Deep Reasoner SLM for ambiguous titles.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: (subTab3Content.view.bridge && subTab3Content.view.bridge.aiEngineMode === "semantic_only") ? "#38BDF8" : "#818CF8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }
                    }

                    // Tier 1 Model Card: Fast Multilingual Semantic Matcher
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        implicitHeight: t1Col.implicitHeight + 24
                        radius: 6
                        color: "#0B111E"
                        border.color: subTab3Content.view.aiT1Status === "downloading" ? "#0284C7" : "#1E293B"
                        border.width: 1
                        clip: true

                        ColumnLayout {
                            id: t1Col
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
                                    text: "⚡"
                                    font.pixelSize: 13
                                }

                                Text {
                                    text: tr("model_t1_title", "Fast Multilingual Matcher (MiniLM INT8 • ~127 MB)")
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
                                    implicitWidth: t1StatusText.implicitWidth + 12
                                    radius: 10
                                    color: subTab3Content.view.aiT1Status === "downloading" ? "#082F49" : (subTab3Content.view.aiT1Status === "error" ? "#450A0A" : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? "#064E3B" : "#1E293B"))
                                    border.color: subTab3Content.view.aiT1Status === "downloading" ? "#0284C7" : (subTab3Content.view.aiT1Status === "error" ? "#EF4444" : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? "#059669" : "#334155"))
                                    border.width: 1

                                    Text {
                                        id: t1StatusText
                                        anchors.centerIn: parent
                                        text: subTab3Content.view.aiT1Status === "downloading" ? (subTab3Content.view.aiT1Percent.toFixed(1) + "%") : (subTab3Content.view.aiT1Status === "error" ? "Error" : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? "Ready" : "Not Downloaded"))
                                        font.pixelSize: 9
                                        font.weight: 600
                                        color: subTab3Content.view.aiT1Status === "downloading" ? "#38BDF8" : (subTab3Content.view.aiT1Status === "error" ? "#F87171" : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? "#34D399" : "#94A3B8"))
                                    }
                                }

                                // Action Button
                                StyledButton {
                                    variant: subTab3Content.view.aiT1Status === "downloading" ? "secondary" : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? "danger" : "primary")
                                    text: subTab3Content.view.aiT1Status === "downloading" ? tr("btn_cancel", "Cancel") : ((subTab3Content.view.bridge && subTab3Content.view.bridge.aiFastSemanticReady) ? tr("btn_remove_model", "Remove") : (subTab3Content.view.aiT1Status === "error" ? tr("btn_retry", "Retry") : tr("btn_download_t1", "Download 127 MB")))
                                    implicitHeight: 26
                                    font.pixelSize: 10
                                    onClicked: {
                                        if (!subTab3Content.view.bridge) return
                                        if (subTab3Content.view.aiT1Status === "downloading") {
                                            subTab3Content.view.bridge.cancelAiModelDownload("fast_semantic")
                                        } else if (subTab3Content.view.bridge.aiFastSemanticReady) {
                                            subTab3Content.view.bridge.deleteAiModel("fast_semantic")
                                        } else {
                                            subTab3Content.view.bridge.startAiModelDownload("fast_semantic")
                                        }
                                    }
                                }
                            }

                            // Dedicated Download Progress Bar
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 4
                                visible: subTab3Content.view.aiT1Status === "downloading"

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0

                                    Text {
                                        text: tr("lbl_downloading_t1", "Downloading model & multilingual tokenizer...")
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: "#38BDF8"
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        text: subTab3Content.view.aiT1Speed
                                        font.family: "Cascadia Code, Consolas, monospace"
                                        font.pixelSize: 10
                                        color: "#A78BFA"
                                        visible: subTab3Content.view.aiT1Speed !== ""
                                    }

                                    Text {
                                        text: subTab3Content.view.aiT1Percent.toFixed(1) + "%"
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
                                        width: Math.max(0, Math.min(parent.width, parent.width * (subTab3Content.view.aiT1Percent / 100.0)))
                                        radius: 3
                                        gradient: Gradient {
                                            orientation: Gradient.Horizontal
                                            GradientStop { position: 0.0; color: "#0284C7" }
                                            GradientStop { position: 1.0; color: "#38BDF8" }
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
                                visible: subTab3Content.view.aiT1Status === "error"

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 6
                                    Text { text: "⚠️"; font.pixelSize: 11 }
                                    Text {
                                        text: subTab3Content.view.aiT1Error !== "" ? subTab3Content.view.aiT1Error : tr("err_download_failed", "Download failed. Please check your internet connection.")
                                        font.pixelSize: 10
                                        color: "#FCA5A5"
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            Text {
                                text: tr("desc_model_t1", "Embeds title tokens into multi-dimensional vectors to recognize anime/game characters across Chinese, Japanese, Korean, Russian, and European languages in 1–3 ms.")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#64748B"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                            }
                        }
                    }

                    SettingsAiTier2Card {
                        view: subTab3Content.view
                    }

                    SettingsAiClipCard {
                        view: subTab3Content.view
                    }

                    // Interactive Testing Sandbox Card
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        implicitHeight: sandboxCol.implicitHeight + 24
                        radius: 6
                        color: "#0B111E"
                        border.color: "#1E293B"
                        border.width: 1
                        clip: true

                        ColumnLayout {
                            id: sandboxCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 6

                                Text {
                                    text: "🧪"
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: tr("sandbox_title", "Live AI Recognition Test Sandbox")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#E2E8F0"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 8

                                StyledTextField {
                                    id: aiTestInput
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    placeholderText: tr("sandbox_placeholder", "Enter a messy title, e.g. 【五等分】水着 4K, 乃木坂, or Nino Nakano...")
                                    onAccepted: testAiBtn.clicked()
                                }

                                StyledButton {
                                    id: testAiBtn
                                    variant: "primary"
                                    text: tr("btn_test_ai", "Test Match")
                                    iconText: "🔍"
                                    implicitHeight: 34
                                    onClicked: {
                                        if (subTab3Content.view.bridge && aiTestInput.text.trim().length > 0) {
                                            var res = subTab3Content.view.bridge.testAiRecognition(aiTestInput.text.trim())
                                            aiResultText.text = "Heuristic: " + res.tier0 + "  |  AI Semantic: " + res.tier1 + "  ➔  Final Folder: " + res.final
                                        }
                                    }
                                }
                            }

                            Text {
                                id: aiResultText
                                text: tr("sandbox_hint", "Type a post title above and click 'Test Match' to preview how Pawchive categorizes it in real time.")
                                font.family: "Consolas, monospace"
                                font.pixelSize: 10
                                color: "#38BDF8"
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                            }
                        }
                    }
                }
            }
        }

    }
}

}
