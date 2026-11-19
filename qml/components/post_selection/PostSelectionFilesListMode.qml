import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// ── 2. List Mode (Compact File Rows with Physical Settling) ──
Item {
            id: listViewWrap
    required property var modal
    required property var filesModel
            width: parent.width
            implicitHeight: Math.max(40, listCol.childrenRect.height)
            opacity: !listViewWrap.modal.visualGalleryMode ? 1.0 : 0.0
            y: !listViewWrap.modal.visualGalleryMode ? 0 : 14
            scale: !listViewWrap.modal.visualGalleryMode ? 1.0 : 0.965
            transformOrigin: Item.Top
            visible: opacity > 0.001

            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }
            Behavior on y {
                SpringAnimation {
                    spring: 3.6
                    damping: 0.38
                    mass: 1.15
                    epsilon: 0.25
                }
            }
            Behavior on scale {
                SpringAnimation {
                    spring: 3.8
                    damping: 0.36
                    mass: 1.10
                    epsilon: 0.005
                }
            }

            ColumnLayout {
                id: listCol
                width: parent.width
                spacing: 6

                Repeater {
            model: listViewWrap.filesModel

            delegate: Item {
                id: listRowItem
                Layout.fillWidth: true
                height: 52

                readonly property var _fMeta: ({
                    "name": model.name || "",
                    "path": model.path || "",
                    "url": model.url || "",
                    "ext": model.ext || "",
                    "media_type": model.media_type || "",
                    "is_loop": !!model.is_loop
                })
                readonly property bool isVideoItem: listViewWrap.modal.isVideoFile(_fMeta)
                readonly property bool isAudioItem: listViewWrap.modal.isAudioFile(_fMeta)
                readonly property bool isGifItem: listViewWrap.modal.isGifFile(_fMeta)
                readonly property bool isArchiveItem: listViewWrap.modal._mediaType(_fMeta) === "archive"
                readonly property bool isViewableItem: listViewWrap.modal.isViewableFile(_fMeta)
                readonly property string kindText: listViewWrap.modal.fileKindLabel(_fMeta)

                // Background rect (hover state driven by fileRowBg)
                Rectangle {
                    id: listRowRect
                    anchors.fill: parent
                    radius: 7
                    color: model.selected ? "#141E2F" : (fileRowHover.containsMouse ? "#0F1520" : "#10141D")
                    border.color: model.selected ? "#38BDF8" : (fileRowHover.containsMouse ? "#334155" : "#1C2433")
                    border.width: model.selected ? 1.5 : 1

                    scale: fileRowHover.pressed ? 0.985 : (fileRowHover.containsMouse ? 1.008 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }

                // Background hover/click (sits behind children via z)
                MouseArea {
                    id: fileRowHover
                    anchors.fill: parent
                    hoverEnabled: true
                    z: 0
                    cursorShape: Qt.PointingHandCursor
                    onClicked: function(mouse) {
                        if (mouse.modifiers & Qt.ShiftModifier) {
                            listViewWrap.modal.toggleFileItem(index, true)
                            return
                        }
                        if (mouse.modifiers & Qt.ControlModifier) {
                            if (listRowItem.isViewableItem) listViewWrap.modal.openLightbox(index)
                            return
                        }
                        listViewWrap.modal.toggleFileItem(index, false)
                    }
                }

                // Content row (z:1 so it sits above the background MouseArea)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 12
                    anchors.topMargin: 0
                    anchors.bottomMargin: 0
                    spacing: 10
                    z: 1

                    // File type icon / thumbnail
                    Rectangle {
                        width: 36
                        height: 36
                        radius: 5
                        color: "#0B0E14"
                        border.color: "#222B3D"
                        clip: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            anchors.centerIn: parent
                            text: listRowItem.isArchiveItem ? "📦"
                                  : (listRowItem.isVideoItem ? "🎬"
                                  : (listRowItem.isAudioItem ? "🎵"
                                  : (listRowItem.isGifItem ? "🎞" : "🖼️")))
                            font.pixelSize: 16
                        }

                        Image {
                            id: listRowThumbImg
                            anchors.fill: parent
                            source: listViewWrap.modal.safeThumbUrl(model.thumbnail, model.provider_id)
                            fillMode: Image.PreserveAspectCrop
                            visible: status === Image.Ready
                            cache: true
                        }

                        Rectangle {
                            visible: listRowItem.isVideoItem && listRowThumbImg.status === Image.Ready
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 2
                            width: 14
                            height: 14
                            radius: 7
                            color: "#CC0A0E17"
                            border.color: "#38BDF8"
                            Text {
                                anchors.centerIn: parent
                                text: "▶"
                                font.pixelSize: 7
                                color: "#38BDF8"
                            }
                        }
                    }

                    // Filename column (fills available width)
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Layout.alignment: Qt.AlignVCenter

                        RowLayout {
                            spacing: 6
                            Layout.fillWidth: true
                            Text {
                                text: model.name || "attachment"
                                font.family: "Segoe UI, monospace, sans-serif"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                color: model.selected ? "#F1F5F9" : "#64748B"
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            // Main file badge
                            Rectangle {
                                visible: !!model.is_main
                                height: 16
                                Layout.preferredWidth: mainFileText2.implicitWidth + 10
                                radius: 3
                                color: "#0F2942"
                                border.color: "#0284C7"
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    id: mainFileText2
                                    anchors.centerIn: parent
                                    text: "MAIN"
                                    font.pixelSize: 8
                                    font.weight: Font.Bold
                                    color: "#38BDF8"
                                }
                            }
                        }

                        Text {
                            text: listRowItem.kindText !== "FILE"
                                  ? ("Format: " + listRowItem.kindText)
                                  : ("File #" + (index + 1))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#475569"
                        }
                    }

                    // View / Play button (z:2 to capture clicks above fileRowHover)
                    Rectangle {
                        id: listViewBtn
                        objectName: "listFileViewBtn"
                        Layout.preferredHeight: 28
                        Layout.preferredWidth: viewBtnRow.implicitWidth + 18
                        radius: 4
                        Layout.alignment: Qt.AlignVCenter
                        z: 2

                        color: !listRowItem.isViewableItem
                               ? "#141A26"
                               : (viewBtnMouse.containsMouse ? "#1E4A72" : "#141A26")
                        border.color: !listRowItem.isViewableItem
                                      ? "#222B3D"
                                      : (viewBtnMouse.containsMouse ? "#38BDF8" : "#2D3748")

                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Row {
                            id: viewBtnRow
                            anchors.centerIn: parent
                            spacing: 4
                            Text {
                                text: (listRowItem.isVideoItem || listRowItem.isAudioItem) ? "▶"
                                      : (listRowItem.isViewableItem ? "🔍" : "📦")
                                font.pixelSize: 10
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: (listRowItem.isVideoItem || listRowItem.isAudioItem) ? "Play"
                                      : (listRowItem.isViewableItem ? "View" : "Archive")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: 600
                                color: !listRowItem.isViewableItem
                                       ? "#64748B"
                                       : (viewBtnMouse.containsMouse ? "#38BDF8"
                                          : ((listRowItem.isVideoItem || listRowItem.isAudioItem) ? "#38BDF8" : "#94A3B8"))
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: viewBtnMouse
                            objectName: "listFileViewMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: listRowItem.isViewableItem ? Qt.PointingHandCursor : Qt.ArrowCursor
                            enabled: listRowItem.isViewableItem
                            // Consume click so it doesn't fall through to fileRowHover
                            onClicked: function(mouse) {
                                mouse.accepted = true
                                listViewWrap.modal.openLightbox(index)
                            }
                        }
                    }

                    // Checkbox (z:2)
                    Rectangle {
                        width: 24
                        height: 24
                        radius: 5
                        color: model.selected ? "#38BDF8" : "#1A2234"
                        border.color: model.selected ? "#38BDF8" : "#334155"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter
                        z: 2

                        scale: model.selected ? 1.0 : 0.88
                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 1.0 } }
                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: "✓"
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            color: "#0A0E17"
                            visible: model.selected
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: function(mouse) {
                                mouse.accepted = true
                                listViewWrap.modal.toggleFileItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                            }
                        }
                    }
                }
            }
        }
    }
}
