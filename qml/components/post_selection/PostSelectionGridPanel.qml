import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// 1. Grid of Post Cards (When not inspecting)
Rectangle {
    id: gridPanel
    required property var modal
    required property var postsModel
    anchors.fill: parent
    radius: 8
    color: "#0B0E14"
    border.color: "#1E293B"
    clip: true
    visible: !gridPanel.modal.isInspecting
    opacity: gridPanel.modal.isInspecting ? 0.0 : 1.0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    GridView {
        id: postsGrid
        anchors.fill: parent
        anchors.margins: 10
        clip: true
        model: gridPanel.postsModel

        readonly property int colCount: Math.max(1, Math.floor(width / 220))
        cellWidth: Math.floor(width / colCount)
        cellHeight: 224
        boundsBehavior: Flickable.StopAtBounds

        property real _targetY: 0
        property real _lastWheelTime: 0
        property real _wheelMomentum: 1.0
        property real _scrollStreak: 0
        property int _lastWheelDir: 0

        NumberAnimation {
            id: postsGridWheelAnim
            target: postsGrid
            property: "contentY"
            duration: 170
            easing.type: Easing.OutQuad
        }

        WheelHandler {
            target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) {
                gridPanel.modal._handleWheelScroll(postsGrid, postsGridWheelAnim, event, 3.0)
            }
        }

        ScrollBar.vertical: ScrollBar {
            id: postsGridScrollBar
            active: postsGrid.moving || postsGrid.flicking || postsGridScrollHover.hovered
            policy: ScrollBar.AsNeeded
            width: 7
            HoverHandler { id: postsGridScrollHover }
            contentItem: Rectangle {
                implicitWidth: 7
                radius: 3
                color: postsGridScrollBar.pressed ? "#38BDF8" : (postsGridScrollBar.hovered ? "#0EA5E9" : (postsGridScrollBar.active ? "#38BDF8" : "#64748B"))
                opacity: postsGridScrollBar.active ? 0.85 : (postsGrid.contentHeight > postsGrid.height ? 0.35 : 0.0)
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on color { ColorAnimation { duration: 150 } }
            }
            background: Rectangle {
                implicitWidth: 7
                radius: 3
                color: "#0F172A"
                opacity: postsGrid.contentHeight > postsGrid.height ? 0.25 : 0.0
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }
        }

        delegate: Item {
            width: postsGrid.cellWidth
            height: postsGrid.cellHeight

            Rectangle {
                id: postCard
                anchors.fill: parent
                anchors.margins: 6
                radius: 8
                color: model.selected ? "#141E2F" : "#10141D"
                border.color: model.selected ? "#38BDF8" : (cardMouse.containsMouse ? "#334155" : "#1C2433")
                border.width: model.selected ? 1.5 : 1

                scale: cardMouse.pressed ? 0.96 : (cardMouse.containsMouse ? 1.02 : 1.0)
                transformOrigin: Item.Center
                Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }
                Behavior on color { ColorAnimation { duration: 140 } }
                Behavior on border.color { ColorAnimation { duration: 140 } }

                // Card Click: Preview or Toggle according to mode (Ctrl inverts, Shift toggles range)
                MouseArea {
                    id: cardMouse
                    objectName: "postCardMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: function(mouse) {
                        if (mouse.modifiers & Qt.ShiftModifier) {
                            gridPanel.modal.toggleItem(index, true)
                            return
                        }
                        var hasCtrl = (mouse.modifiers & Qt.ControlModifier) !== 0
                        var shouldToggle = gridPanel.modal.quickSelectClickMode ? !hasCtrl : hasCtrl
                        if (shouldToggle) {
                            gridPanel.modal.toggleItem(index, false)
                        } else {
                            gridPanel.modal.inspectPost(model.id)
                        }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Thumbnail Container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: "#080B11"
                        radius: 7
                        clip: true

                        // Fallback icon
                        Rectangle {
                            anchors.fill: parent
                            color: "#0E131E"
                            visible: postThumb.status !== Image.Ready
                            Column {
                                anchors.centerIn: parent
                                spacing: 4
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: model.hasVideo ? "🎬" : (model.hasGif ? "🎞" : "🖼️")
                                    font.pixelSize: 22
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: (model.fileCount || 0) + " files"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#475569"
                                }
                            }
                        }

                        Image {
                            id: postThumb
                            anchors.fill: parent
                            source: gridPanel.modal.safeThumbUrl(model.thumbnail, model.provider_id)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            opacity: status === Image.Ready ? 1.0 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 180 } }
                        }

                        // Gradient shadow at bottom of image
                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 28
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "transparent" }
                                GradientStop { position: 1.0; color: "#99000000" }
                            }
                        }

                        // Bottom-left media kind pill for video / GIF posts
                        Rectangle {
                            visible: !!model.hasVideo || !!model.hasGif
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.margins: 6
                            height: 18
                            implicitWidth: postMediaKindTxt.implicitWidth + 10
                            radius: 4
                            color: model.hasVideo ? "#CC0C2A3D" : "#CC1E1B4B"
                            border.color: model.hasVideo ? "#38BDF8" : "#818CF8"
                            border.width: 1
                            z: 2

                            Text {
                                id: postMediaKindTxt
                                anchors.centerIn: parent
                                text: model.hasVideo ? "▶ VIDEO" : "🎞 GIF"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                color: model.hasVideo ? "#38BDF8" : "#A5B4FC"
                            }
                        }

                        // Unimported warning badge (top-right, beside checkbox)
                        UnimportedTriangleBadge {
                            objectName: "postSelectionUnimportedBadge"
                            visible: !!model.is_unimported
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.topMargin: 6
                            anchors.rightMargin: 38
                            z: 3
                            showBackground: true
                            tooltipText: gridPanel.modal.tr("warn_post_unimported_short", "Not imported into Pawchive yet — full-resolution media may not be available.")
                        }

                        // Selected Files / Total Files Count Badge (top-left)
                        Rectangle {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.margins: 6
                            height: 20
                            implicitWidth: fileBadgeText.implicitWidth + 10
                            radius: 4
                            color: {
                                var selF = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                var totF = model.fileCount || 0
                                if (selF === totF && totF > 0) return "#CC0A2338"
                                if (selF > 0) return "#CC341D09"
                                return "#CC0A0E17"
                            }
                            border.color: {
                                var selF2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                var totF2 = model.fileCount || 0
                                if (selF2 === totF2 && totF2 > 0) return "#0284C7"
                                if (selF2 > 0) return "#D97706"
                                return "#2D3748"
                            }

                            Row {
                                id: fileBadgeText
                                anchors.centerIn: parent
                                spacing: 3
                                Text { text: "📎"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: {
                                        var s = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                        var t = model.fileCount || 0
                                        return s + " / " + t + " files"
                                    }
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: {
                                        var s2 = model.selectedFileCount !== undefined ? model.selectedFileCount : (model.selected ? model.fileCount : 0)
                                        var t2 = model.fileCount || 0
                                        if (s2 === t2 && t2 > 0) return "#38BDF8"
                                        if (s2 > 0) return "#FBBF24"
                                        return "#94A3B8"
                                    }
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        // Selection checkbox badge (top-right) with Newtonian bounce
                        Rectangle {
                            id: checkBadge
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.margins: 6
                            width: 26
                            height: 26
                            radius: 6
                            color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#1A3A58" : "#990A0E17")
                            border.color: model.selected ? "#38BDF8" : (checkMouse.containsMouse ? "#38BDF8" : "#475569")
                            border.width: 1.5

                            scale: model.selected ? 1.0 : (checkMouse.containsMouse ? 1.0 : 0.9)
                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }
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
                                id: checkMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: (model.selected ? "Deselect post" : "Select post") + "\nShift+click to select a range"
                                onClicked: function(mouse) {
                                    mouse.accepted = true
                                    gridPanel.modal.toggleItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                }
                            }
                        }

                        // Inspect hover badge (bottom-right of thumbnail)
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.right: parent.right
                            anchors.margins: 6
                            height: 20
                            implicitWidth: inspectPillText.implicitWidth + 10
                            radius: 4
                            color: cardMouse.containsMouse ? "#0284C7" : "#B30F172A"
                            border.color: "#38BDF8"
                            visible: cardMouse.containsMouse || (model.fileCount > 1)

                            Row {
                                id: inspectPillText
                                anchors.centerIn: parent
                                spacing: 3
                                Text { text: "🔍"; font.pixelSize: 9; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: gridPanel.modal.tr("btn_inspect_card", "Inspect")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#FFFFFF"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }

                    // Card Footer (Title & Published Date)
                    Rectangle {
                        Layout.fillWidth: true
                        height: 52
                        color: "transparent"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 2

                            Text {
                                text: model.title || "Untitled"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: model.selected ? "#F1F5F9" : "#94A3B8"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                spacing: 4
                                Text { text: "📅"; font.pixelSize: 9; color: "#64748B" }
                                Text {
                                    text: model.published || "Unknown"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Empty state indicator
    Column {
        anchors.centerIn: parent
        spacing: 8
        visible: gridPanel.postsModel.count === 0

        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "🔍"; font.pixelSize: 28 }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: gridPanel.modal.tr("no_matching_posts", "No posts match your search.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 13
            color: "#64748B"
        }
    }
}
