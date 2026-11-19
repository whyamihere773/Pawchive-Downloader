import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Right Pane: Selected-items reassignment bar and virtualized preview GridView.
Rectangle {
    id: previewPane

    required property var modal
    Layout.fillWidth: true
    Layout.fillHeight: true
    radius: 10
    color: "#101520"
    border.color: "#1E293B"
    border.width: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // Reassign Selected Items Bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: modal.selectedItemCount > 0 ? 40 : 0
            visible: Layout.preferredHeight > 0.5
            clip: true
            radius: 7
            color: "#1E1B4B"
            border.color: "#818CF8"
            border.width: 1

            Behavior on Layout.preferredHeight {
                SpringAnimation { spring: 4.6; damping: 0.38; mass: 1.0 }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                Text {
                    text: modal.selectedItemCount + " selected — Move to bucket:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#E0E7FF"
                }

                Rectangle {
                    Layout.preferredWidth: 190
                    Layout.preferredHeight: 26
                    radius: 5
                    color: targetBktInput.activeFocus ? "#0B0D12" : "#0D111A"
                    border.color: targetBktInput.activeFocus ? "#38BDF8" : (targetBktBoxMouse.containsMouse ? "#818CF8" : "#6366F1")
                    border.width: targetBktInput.activeFocus ? 1.5 : 1
                    TextBarContextArea {
                        id: targetBktBoxMouse
                        target: targetBktInput
                        focusOnLeftClick: true
                    }
                    TextInput {
                        id: targetBktInput
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        clip: true
                        selectByMouse: true
                        TextBarContextArea {}
                        Text {
                            anchors.fill: parent
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            text: "Type new or existing folder…"
                            font.pixelSize: 11
                            color: "#64748B"
                            visible: !targetBktInput.text
                        }
                        onAccepted: {
                            if (text.trim().length > 0) {
                                modal.assignSelectedToBucket(text.trim())
                                text = ""
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredHeight: 26
                    implicitWidth: applyMoveTxt.implicitWidth + 14
                    radius: 5
                    color: "#4F46E5"
                    Text {
                        id: applyMoveTxt
                        anchors.centerIn: parent
                        text: "Assign"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (targetBktInput.text.trim().length > 0) {
                                modal.assignSelectedToBucket(targetBktInput.text.trim())
                                targetBktInput.text = ""
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredHeight: 26
                    implicitWidth: clrSelTxt.implicitWidth + 12
                    radius: 5
                    color: "#1E293B"
                    Text {
                        id: clrSelTxt
                        anchors.centerIn: parent
                        text: "Clear Selection"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.clearSelectedItems()
                    }
                }
            }
        }

        // Virtual Preview GridView
        SmoothGridView {
            id: previewGrid
            Layout.fillWidth: true
            Layout.fillHeight: true
            cellWidth: 196
            cellHeight: 212
            model: modal.vsBridge ? modal.vsBridge.previewItemsModel : null

            delegate: Item {
                width: previewGrid.cellWidth
                height: previewGrid.cellHeight

                readonly property var itm: modelData || ({})
                readonly property string itmKey: itm.key || ""
                readonly property bool isExcluded: !!itm.excluded
                readonly property bool isChecked: !!modal.selectedItemKeys[itmKey]

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 5
                    radius: 9
                    color: isExcluded ? "#090C12" : (isChecked ? "#1E1B4B" : "#0D111A")
                    border.color: isChecked ? "#818CF8" : (isExcluded ? "#334155" : "#1E293B")
                    border.width: isChecked ? 1.5 : 1
                    opacity: isExcluded ? 0.52 : 1.0

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 4
                        z: 1

                        // Thumbnail Box
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 118
                            radius: 6
                            color: "#070A10"
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: modal.thumbUrlForPath(itm.file_path || "")
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }

                            // Confidence Badge (Top-Left)
                            Rectangle {
                                anchors.top: parent.top
                                anchors.left: parent.left
                                anchors.margins: 5
                                height: 18
                                implicitWidth: confTxt.implicitWidth + 10
                                radius: 4
                                color: "#CC0F172A"
                                border.color: "#38BDF8"
                                border.width: 1
                                Text {
                                    id: confTxt
                                    anchors.centerIn: parent
                                    text: (itm.confidence_pct || 85) + "%"
                                    font.family: "Consolas, monospace"
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#38BDF8"
                                }
                            }

                            // Exclude / Skip Toggle (Top-Right)
                            Rectangle {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 5
                                height: 20
                                implicitWidth: exclTxt.implicitWidth + 10
                                radius: 4
                                color: isExcluded ? "#7F1D1D" : "#CC0F172A"
                                border.color: isExcluded ? "#F87171" : "#475569"
                                border.width: 1
                                z: 2
                                Text {
                                    id: exclTxt
                                    anchors.centerIn: parent
                                    text: isExcluded ? "Skipped" : "✔ Keep"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: isExcluded ? "#FECACA" : "#E2E8F0"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (modal.vsBridge) modal.vsBridge.toggleExcludeItem(itmKey)
                                    }
                                }
                            }

                            // Target Bucket Pill (Bottom)
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                height: 20
                                color: "#D90F172A"
                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 6
                                    anchors.rightMargin: 6
                                    verticalAlignment: Text.AlignVCenter
                                    text: "📂 " + (itm.bucket_name || "")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: "#A78BFA"
                                    elide: Text.ElideRight
                                }
                            }
                        }

                        // Filename
                        Text {
                            text: itm.filename || ""
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }

                        // Reason / Dimensions
                        Text {
                            text: (itm.reason || "") + ((itm.width > 0 && itm.height > 0) ? (" • " + itm.width + "×" + itm.height) : "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        z: 0
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.toggleSelectItem(itmKey)
                    }
                }
            }

            // Empty State Overlay
            Column {
                anchors.centerIn: parent
                spacing: 10
                visible: previewGrid.count === 0 && (!modal.vsBridge || !modal.vsBridge.isRunning)

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "🎨"
                    font.pixelSize: 38
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Virtual Sandbox Ready"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#E2E8F0"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Pick a sorting strategy above and click 'Run Virtual Sort'.\nNothing is written or moved on disk until you review the buckets and click Commit."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#64748B"
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
