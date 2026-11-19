import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Left Pane: Virtual Buckets list with cover thumbs, inline rename, and gallery filter.
Rectangle {
    id: bucketsPane

    required property var modal
    Layout.preferredWidth: 310
    Layout.fillHeight: true
    radius: 10
    color: "#101520"
    border.color: "#1E293B"
    border.width: 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "📂 Virtual Buckets (" + (modal.vsBridge ? modal.vsBridge.totalBucketsCount : 0) + ")"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: Font.Bold
                color: "#F8FAFC"
                Layout.fillWidth: true
            }
            Rectangle {
                visible: !!(modal.vsBridge && modal.vsBridge.hasVirtualPlan)
                height: 22
                implicitWidth: allBktTxt.implicitWidth + 12
                radius: 5
                color: (modal.vsBridge && modal.vsBridge.selectedBucketId === "all") ? "#1E3A8A" : "#151C2B"
                border.color: (modal.vsBridge && modal.vsBridge.selectedBucketId === "all") ? "#38BDF8" : "#26324B"
                border.width: 1
                Text {
                    id: allBktTxt
                    anchors.centerIn: parent
                    text: "Show All (" + (modal.vsBridge ? modal.vsBridge.totalPlannedFiles : 0) + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    color: "#E2E8F0"
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (modal.vsBridge) modal.vsBridge.selectBucket("all")
                }
            }
        }

        ListView {
            id: bucketsListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: modal.vsBridge ? modal.vsBridge.bucketsModel : null

            delegate: Rectangle {
                readonly property var bkt: modelData || ({})
                readonly property string bktId: bkt.key || ""
                readonly property bool isSel: (modal.vsBridge ? modal.vsBridge.selectedBucketId : "all") === bktId
                readonly property bool isRenaming: modal.renamingBucketId === bktId

                width: bucketsListView.width
                height: isRenaming ? 86 : 62
                radius: 8
                color: isSel ? "#172554" : (bktMouse.containsMouse ? "#161E2E" : "#0D111A")
                border.color: isSel ? "#38BDF8" : "#1E293B"
                border.width: isSel ? 1.5 : 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        // Cover Thumbnail
                        Rectangle {
                            width: 42
                            height: 42
                            radius: 6
                            color: "#1E293B"
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: modal.thumbUrlForPath(bkt.cover_path || "")
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: bkt.bucket_name || bktId
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Text {
                                text: (bkt.count || 0) + " files • " + modal.formatBytes(bkt.total_bytes || 0)
                                      + ((bkt.excluded_count || 0) > 0 ? (" (" + bkt.excluded_count + " skipped)") : "")
                                font.family: "Consolas, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        // Rename Bucket Button
                        Rectangle {
                            width: 24
                            height: 24
                            radius: 5
                            color: "#151C2B"
                            border.color: "#26324B"
                            border.width: 1
                            z: 2
                            Text {
                                anchors.centerIn: parent
                                text: "✎"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (isRenaming) {
                                        modal.renamingBucketId = ""
                                    } else {
                                        modal.renamingBucketId = bktId
                                        modal.renameBuffer = bkt.bucket_name || ""
                                    }
                                }
                            }
                        }

                        // Filter in Gallery Button
                        Rectangle {
                            width: 24
                            height: 24
                            radius: 5
                            color: "#151C2B"
                            border.color: "#38BDF8"
                            border.width: 1
                            z: 2
                            Text {
                                anchors.centerIn: parent
                                text: "🔍"
                                font.pixelSize: 10
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (modal.vsBridge) modal.vsBridge.applyBucketAsGalleryFilter(bktId)
                                }
                            }
                        }
                    }

                    // Inline Rename Row
                    RowLayout {
                        visible: isRenaming
                        Layout.fillWidth: true
                        spacing: 4
                        z: 3

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 24
                            radius: 4
                            color: "#090D14"
                            border.color: renInput.activeFocus ? "#38BDF8" : "#2563EB"
                            border.width: 1
                            TextBarContextArea {
                                target: renInput
                                focusOnLeftClick: true
                            }
                            TextInput {
                                id: renInput
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                anchors.rightMargin: 6
                                verticalAlignment: TextInput.AlignVCenter
                                text: modal.renameBuffer
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#F8FAFC"
                                selectionColor: "#0284C7"
                                selectedTextColor: "#FFFFFF"
                                clip: true
                                selectByMouse: true
                                TextBarContextArea {}
                                onAccepted: {
                                    if (modal.vsBridge && text.trim().length > 0) {
                                        modal.vsBridge.renameBucket(bktId, text.trim())
                                    }
                                    modal.renamingBucketId = ""
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredHeight: 24
                            implicitWidth: 44
                            radius: 4
                            color: "#059669"
                            Text {
                                anchors.centerIn: parent
                                text: "Save"
                                font.pixelSize: 10
                                font.bold: true
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (modal.vsBridge && renInput.text.trim().length > 0) {
                                        modal.vsBridge.renameBucket(bktId, renInput.text.trim())
                                    }
                                    modal.renamingBucketId = ""
                                }
                            }
                        }
                    }
                }

                MouseArea {
                    id: bktMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    z: 1
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modal.vsBridge) modal.vsBridge.selectBucket(bktId)
                    }
                }
            }
        }
    }
}

