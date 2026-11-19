import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Collapsible Local AI Vision & LLM Model Pack Download Drawer.
Rectangle {
    id: modelsDrawer

    required property var modal
    Layout.fillWidth: true
    Layout.preferredHeight: modal.showModelsDrawer ? 132 : 0
    visible: Layout.preferredHeight > 0.5
    clip: true
    radius: 10
    color: "#111622"
    border.color: "#312E81"
    border.width: 1

    Behavior on Layout.preferredHeight {
        SpringAnimation { spring: 4.5; damping: 0.38; mass: 1.15 }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "⚡ Universal Local AI Vision & LLM Packs (Optional — Heuristic Vision Engine works immediately without downloads)"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Bold
                color: "#C4B5FD"
                Layout.fillWidth: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Repeater {
                model: modal.vsBridge ? modal.vsBridge.visualModelsStatus : []

                delegate: Rectangle {
                    readonly property var mdl: modelData || ({})
                    readonly property bool isReady: !!mdl.is_ready
                    readonly property bool isDownloading: mdl.status === "downloading"

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 8
                    color: "#0D111A"
                    border.color: isReady ? "#10B981" : (isDownloading ? "#38BDF8" : "#1E293B")
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: mdl.name || mdl.key || ""
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: (mdl.size_mb || 0) + " MB"
                                font.family: "Consolas, monospace"
                                font.pixelSize: 10
                                color: "#64748B"
                            }
                        }

                        Text {
                            text: mdl.description || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            // Download progress bar when downloading
                            Rectangle {
                                visible: isDownloading
                                Layout.fillWidth: true
                                Layout.preferredHeight: 6
                                radius: 3
                                color: "#1E293B"
                                Rectangle {
                                    height: parent.height
                                    radius: 3
                                    color: "#38BDF8"
                                    width: parent.width * Math.min(1.0, (mdl.percent || 0) / 100.0)
                                    Behavior on width {
                                        SpringAnimation { spring: 4.5; damping: 0.40; mass: 0.8 }
                                    }
                                }
                            }

                            Item { visible: !isDownloading; Layout.fillWidth: true }

                            Rectangle {
                                Layout.preferredHeight: 22
                                implicitWidth: mdlBtnTxt.implicitWidth + 12
                                radius: 5
                                color: isReady ? "#064E3B" : (isDownloading ? "#7F1D1D" : "#1E3A8A")
                                border.color: isReady ? "#10B981" : (isDownloading ? "#F87171" : "#38BDF8")
                                border.width: 1
                                Text {
                                    id: mdlBtnTxt
                                    anchors.centerIn: parent
                                    text: isReady ? "✔ Ready" : (isDownloading ? ("Cancel (" + Math.round(mdl.percent || 0) + "%)") : "⬇ Download")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#FFFFFF"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    enabled: !isReady
                                    cursorShape: isReady ? Qt.ArrowCursor : Qt.PointingHandCursor
                                    onClicked: {
                                        if (!modal.vsBridge) return
                                        if (isDownloading) {
                                            modal.vsBridge.cancelVisualModelDownload(mdl.key)
                                        } else {
                                            modal.vsBridge.downloadVisualModel(mdl.key)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

