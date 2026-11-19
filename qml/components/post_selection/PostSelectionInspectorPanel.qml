import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// 2. Detail Inspector Panel (When inspecting a single post)
Rectangle {
    id: detailPanel
    required property var modal
    required property var filesModel
    anchors.fill: parent
    radius: 8
    color: "#0B0E14"
    border.color: "#1E293B"
    clip: true
    visible: detailPanel.modal.isInspecting
    opacity: detailPanel.modal.isInspecting ? 1.0 : 0.0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    Flickable {
        id: inspectorFlickable
        objectName: "postSelectionInspectorFlickable"
        anchors.fill: parent
        anchors.margins: 14
        contentWidth: width
        contentHeight: detailCol.implicitHeight + 30
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        property real _targetY: 0
        property real _lastWheelTime: 0
        property real _wheelMomentum: 1.0
        property real _scrollStreak: 0
        property int _lastWheelDir: 0

        onMovingChanged: {
            if (moving) {
                inspectorWheelAnim.stop()
                _targetY = contentY
            }
        }

        NumberAnimation {
            id: inspectorWheelAnim
            target: inspectorFlickable
            property: "contentY"
            duration: 170
            easing.type: Easing.OutQuad
        }

        WheelHandler {
            target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: function(event) {
                detailPanel.modal._handleWheelScroll(inspectorFlickable, inspectorWheelAnim, event, 2.8)
            }
        }

        ScrollBar.vertical: ScrollBar {
            id: inspectorScrollBar
            active: inspectorFlickable.moving || inspectorFlickable.flicking || inspectorWheelAnim.running || inspectorScrollHover.hovered
            policy: ScrollBar.AsNeeded
            width: 7
            HoverHandler { id: inspectorScrollHover }
            contentItem: Rectangle {
                implicitWidth: 7
                radius: 3
                color: inspectorScrollBar.pressed ? "#38BDF8" : (inspectorScrollBar.hovered ? "#0EA5E9" : (inspectorScrollBar.active ? "#38BDF8" : "#64748B"))
                opacity: inspectorScrollBar.active ? 0.85 : (inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.35 : 0.0)
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on color { ColorAnimation { duration: 150 } }
            }
            background: Rectangle {
                implicitWidth: 7
                radius: 3
                color: "#0F172A"
                opacity: inspectorFlickable.contentHeight > inspectorFlickable.height ? 0.25 : 0.0
                Behavior on opacity { NumberAnimation { duration: 180 } }
            }
        }

        ColumnLayout {
            id: detailCol
            width: parent.width
            spacing: 14

            // Unimported post warning banner
            Rectangle {
                id: postUnimportedBanner
                objectName: "postSelectionUnimportedBanner"
                visible: !!(detailPanel.modal.inspectedPost && detailPanel.modal.inspectedPost.is_unimported)
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? (postUnimpRow.implicitHeight + 16) : 0
                radius: 8
                color: "#291E0B"
                border.color: "#B45309"
                border.width: 1

                RowLayout {
                    id: postUnimpRow
                    anchors {
                        left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                        leftMargin: 12; rightMargin: 12
                    }
                    spacing: 10

                    UnimportedTriangleBadge {
                        showBackground: false
                        tooltipText: ""
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        Layout.fillWidth: true
                        text: detailPanel.modal.tr("warn_post_unimported", "This post has not been fully imported into Pawchive yet — only a preview thumbnail may be available for images.")
                        color: "#FCD34D"
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // Description & Content Card (if available)
            Rectangle {
                visible: detailPanel.modal.inspectedPost && detailPanel.modal.inspectedPost.content && detailPanel.modal.inspectedPost.content.length > 0
                Layout.fillWidth: true
                implicitHeight: descCol.implicitHeight + 20
                radius: 8
                color: "#10141D"
                border.color: "#1E293B"
                border.width: 1

                ColumnLayout {
                    id: descCol
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "📝"; font.pixelSize: 12 }
                        Text {
                            text: detailPanel.modal.tr("label_post_description", "Post Description & Notes")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#94A3B8"
                            Layout.fillWidth: true
                        }
                    }

                    TextEdit {
                        Layout.fillWidth: true
                        text: detailPanel.modal.inspectedPost ? detailPanel.modal.inspectedPost.content : ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#E2E8F0"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        wrapMode: TextEdit.Wrap
                        readOnly: true
                        selectByMouse: true
                        TextBarContextArea {}
                    }
                }
            }

            // Attached Media & Files Header + Action Buttons + View Mode Switcher
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text { text: "📎"; font.pixelSize: 13 }
                Text {
                    text: detailPanel.modal.tr("label_attached_files", "Attached Media & Files") + " (" + detailPanel.filesModel.count + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: "#F1F5F9"
                    Layout.fillWidth: true
                }

                // Which file is #1 (same setting as "File order in posts" in the Downloader tab)
                StyledComboBox {
                    implicitHeight: 28
                    implicitWidth: 140
                    model: [
                        { text: detailPanel.modal.tr("file_order_posted", "As posted"), value: "posted" },
                        { text: detailPanel.modal.tr("file_order_reversed", "Reversed"), value: "reversed" },
                        { text: detailPanel.modal.tr("file_order_name", "By file name"), value: "name" }
                    ]
                    value: detailPanel.modal.bridge ? detailPanel.modal.bridge.fileOrder : "posted"
                    tooltip: detailPanel.modal.tr("tip_file_order_modal", "Order of the files: #1 is downloaded first and numbered first. This is the \"File order in posts\" setting from the Downloader tab.")
                    onValuePicked: function(v) { if (detailPanel.modal.bridge) detailPanel.modal.bridge.fileOrder = v }
                }

                // View Switcher: Gallery Mode vs List Mode (Physical Newtonian Spring Slider)
                Rectangle {
                    id: viewSwitchContainer
                    height: 28
                    width: 68
                    radius: 6
                    color: "#161D2B"
                    border.color: "#2D3748"

                    // Sliding Physical Indicator Pill (Newtonian spring glide)
                    Rectangle {
                        id: viewSwitchIndicator
                        y: 3
                        x: detailPanel.modal.visualGalleryMode ? 3 : 35
                        width: 30
                        height: 22
                        radius: 4
                        color: "#0284C7"
                        scale: (gridSwitchMouse.pressed || listSwitchMouse.pressed) ? 0.91 : 1.0

                        Behavior on x {
                            SpringAnimation {
                                spring: 4.8
                                damping: 0.40
                                mass: 1.05
                                epsilon: 0.2
                            }
                        }
                        Behavior on scale {
                            SpringAnimation {
                                spring: 4.5
                                damping: 0.35
                                mass: 1.0
                            }
                        }
                    }

                    Row {
                        anchors.fill: parent
                        anchors.margins: 3
                        spacing: 2

                        // Grid Mode Option
                        Item {
                            width: 30
                            height: 22
                            Text {
                                anchors.centerIn: parent
                                text: "🖼️"
                                font.pixelSize: 11
                                scale: detailPanel.modal.visualGalleryMode ? 1.08 : 0.95
                                opacity: detailPanel.modal.visualGalleryMode ? 1.0 : 0.65
                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                            }
                            MouseArea {
                                id: gridSwitchMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: detailPanel.modal.visualGalleryMode = true
                            }
                        }

                        // List Mode Option
                        Item {
                            width: 30
                            height: 22
                            Text {
                                anchors.centerIn: parent
                                text: "📋"
                                font.pixelSize: 11
                                scale: !detailPanel.modal.visualGalleryMode ? 1.08 : 0.95
                                opacity: !detailPanel.modal.visualGalleryMode ? 1.0 : 0.65
                                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.35; mass: 1.0 } }
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                            }
                            MouseArea {
                                id: listSwitchMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: detailPanel.modal.visualGalleryMode = false
                            }
                        }
                    }
                }

                // Select All Files
                Rectangle {
                    Layout.preferredHeight: 30
                    Layout.preferredWidth: Math.max(108, selAllFilesRow.implicitWidth + 26)
                    radius: 6
                    color: selAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: selAllFilesMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: selAllFilesRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: selAllFilesText
                            text: detailPanel.modal.tr("btn_select_all", "Select All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: selAllFilesMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: detailPanel.modal.selectAllFilesInPost(true)
                    }
                }

                // Deselect All Files
                Rectangle {
                    Layout.preferredHeight: 30
                    Layout.preferredWidth: Math.max(118, deselAllFilesRow.implicitWidth + 26)
                    radius: 6
                    color: deselAllFilesMouse.containsMouse ? "#1E293B" : "#161D2B"
                    border.color: "#2D3748"
                    scale: deselAllFilesMouse.pressed ? 0.94 : 1.0
                    Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

                    Row {
                        id: deselAllFilesRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            id: deselAllFilesText
                            text: detailPanel.modal.tr("btn_deselect_all", "Deselect All")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: deselAllFilesMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: detailPanel.modal.selectAllFilesInPost(false)
                    }
                }
            }

            // ── View Mode Container with Newtonian Weight-Based Transitions ──
            Item {
                id: viewModeContainer
                Layout.fillWidth: true
                implicitHeight: detailPanel.modal.visualGalleryMode ? galleryViewWrap.implicitHeight : listViewWrap.implicitHeight

                Behavior on implicitHeight {
                    NumberAnimation {
                        duration: 280
                        easing.type: Easing.OutCubic
                    }
                }

                // ── 1. Visual Gallery Mode (Responsive Grid with Physical Weight) ──
                Item {
                    id: galleryViewWrap
                    width: parent.width
                    implicitHeight: Math.max(40, galleryFlow.childrenRect.height)
                    opacity: detailPanel.modal.visualGalleryMode ? 1.0 : 0.0
                    y: detailPanel.modal.visualGalleryMode ? 0 : -14
                    scale: detailPanel.modal.visualGalleryMode ? 1.0 : 0.965
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

                    Flow {
                        id: galleryFlow
                        width: parent.width
                        spacing: 10

                        Repeater {
                    model: detailPanel.filesModel

                    delegate: Rectangle {
                        id: galTile
                        width: 175
                        height: 185
                        radius: 8
                        color: model.selected ? "#141E2F" : "#10141D"
                        border.color: model.selected ? "#38BDF8" : (galMouse.containsMouse ? "#334155" : "#1C2433")
                        border.width: model.selected ? 1.5 : 1

                        readonly property var _fMeta: ({
                            "name": model.name || "",
                            "path": model.path || "",
                            "url": model.url || "",
                            "ext": model.ext || "",
                            "media_type": model.media_type || "",
                            "is_loop": !!model.is_loop
                        })
                        readonly property bool isVideoItem: detailPanel.modal.isVideoFile(_fMeta)
                        readonly property bool isAudioItem: detailPanel.modal.isAudioFile(_fMeta)
                        readonly property bool isGifItem: detailPanel.modal.isGifFile(_fMeta)
                        readonly property bool isArchiveItem: detailPanel.modal._mediaType(_fMeta) === "archive"
                        readonly property bool isViewableItem: detailPanel.modal.isViewableFile(_fMeta)
                        readonly property string kindText: detailPanel.modal.fileKindLabel(_fMeta)

                        scale: galMouse.pressed ? 0.96 : (galMouse.containsMouse ? 1.03 : 1.0)
                        transformOrigin: Item.Center
                        Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.35; mass: 1.0 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        // Background click area (z:0, behind everything) - toggles selection (Ctrl+click previews)
                        MouseArea {
                            id: galMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            z: 0
                            cursorShape: Qt.PointingHandCursor
                            onClicked: function(mouse) {
                                if (mouse.modifiers & Qt.ShiftModifier) {
                                    detailPanel.modal.toggleFileItem(index, true)
                                    return
                                }
                                if (mouse.modifiers & Qt.ControlModifier) {
                                    if (galTile.isViewableItem) detailPanel.modal.openLightbox(index)
                                    return
                                }
                                detailPanel.modal.toggleFileItem(index, false)
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 0
                            z: 1

                            // Large Image / Media Preview
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 7
                                color: "#080B11"
                                clip: true

                                // Media icon fallback
                                Rectangle {
                                    anchors.fill: parent
                                    color: "#0D111A"
                                    visible: galThumb.status !== Image.Ready
                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 4
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: galTile.isArchiveItem ? "📦"
                                                  : (galTile.isVideoItem ? "🎬"
                                                  : (galTile.isAudioItem ? "🎵"
                                                  : (galTile.isGifItem ? "🎞" : "🖼️")))
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: "File #" + (index + 1)
                                            font.pixelSize: 9
                                            color: "#64748B"
                                        }
                                    }
                                }

                                Image {
                                    id: galThumb
                                    anchors.fill: parent
                                    source: detailPanel.modal.safeThumbUrl(model.previewUrl || model.thumbnail, model.provider_id)
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                    opacity: status === Image.Ready ? 1.0 : 0.0
                                    Behavior on opacity { NumberAnimation { duration: 180 } }
                                }

                                // Play overlay indicator for videos/audio when thumbnail is visible
                                Rectangle {
                                    visible: (galTile.isVideoItem || galTile.isAudioItem) && galThumb.status === Image.Ready
                                    anchors.centerIn: parent
                                    width: 36
                                    height: 36
                                    radius: 18
                                    color: "#B30A0E17"
                                    border.color: "#38BDF8"
                                    border.width: 1.5
                                    z: 2
                                    Text {
                                        anchors.centerIn: parent
                                        anchors.horizontalCenterOffset: 1
                                        text: "▶"
                                        font.pixelSize: 13
                                        color: "#F8FAFC"
                                    }
                                }

                                // Top-Left Format Pill
                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.margins: 5
                                    height: 18
                                    implicitWidth: galFormatText.implicitWidth + 8
                                    radius: 3
                                    color: galTile.isGifItem ? "#CC1E1B4B"
                                           : (galTile.isVideoItem ? "#CC0C2A3D"
                                           : (galTile.isAudioItem ? "#CC042F2E" : "#CC080C14"))
                                    border.color: galTile.isGifItem ? "#818CF8"
                                                  : (galTile.isVideoItem ? "#38BDF8"
                                                  : (galTile.isAudioItem ? "#2DD4BF" : "#334155"))

                                    Text {
                                        id: galFormatText
                                        anchors.centerIn: parent
                                        text: galTile.kindText
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: galTile.isGifItem ? "#A5B4FC"
                                               : (galTile.isVideoItem ? "#38BDF8"
                                               : (galTile.isAudioItem ? "#5EEAD4" : "#E2E8F0"))
                                    }
                                }

                                // Top-Right Checkbox (Direct Toggle, z:3)
                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.right: parent.right
                                    anchors.margins: 5
                                    width: 24
                                    height: 24
                                    radius: 5
                                    z: 3
                                    color: model.selected ? "#38BDF8" : "#99080C14"
                                    border.color: model.selected ? "#38BDF8" : "#475569"
                                    border.width: 1

                                    scale: model.selected ? 1.0 : 0.92
                                    Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }

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
                                            detailPanel.modal.toggleFileItem(index, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                        }
                                    }
                                }

                                // Hover Zoom / Play / Expand Badge (bottom-right, clickable for Lightbox)
                                Rectangle {
                                    id: expandBadgeRect
                                    objectName: "expandBadgeRect"
                                    anchors.bottom: parent.bottom
                                    anchors.right: parent.right
                                    anchors.margins: 5
                                    height: 22
                                    implicitWidth: expandPillText.implicitWidth + 12
                                    radius: 4

                                    color: !galTile.isViewableItem
                                           ? "#1E293B"
                                           : (expandMouse.containsMouse ? "#0284C7"
                                              : ((galTile.isVideoItem || galTile.isAudioItem) ? "#CC0C2A3D" : "#B30A121F"))
                                    border.color: !galTile.isViewableItem
                                                  ? "#334155"
                                                  : (expandMouse.containsMouse ? "#38BDF8"
                                                     : ((galTile.isVideoItem || galTile.isAudioItem) ? "#0284C7" : "#334155"))
                                    border.width: 1
                                    opacity: (galMouse.containsMouse || expandMouse.containsMouse) ? 1.0 : 0.78
                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                    Behavior on color { ColorAnimation { duration: 100 } }
                                    z: 3

                                    Row {
                                        id: expandPillText
                                        anchors.centerIn: parent
                                        spacing: 3
                                        Text {
                                            text: (galTile.isVideoItem || galTile.isAudioItem) ? "▶"
                                                  : (galTile.isViewableItem ? "🔍" : "📦")
                                            font.pixelSize: 9
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                        Text {
                                            objectName: "expandBadgeLabel"
                                            text: (galTile.isVideoItem || galTile.isAudioItem) ? "Play"
                                                  : (galTile.isViewableItem ? "Preview" : "File")
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: !galTile.isViewableItem
                                                   ? "#94A3B8"
                                                   : (expandMouse.containsMouse ? "#FFFFFF"
                                                      : ((galTile.isVideoItem || galTile.isAudioItem) ? "#38BDF8" : "#CBD5E1"))
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }

                                    MouseArea {
                                        id: expandMouse
                                        objectName: "expandBadgeMouse"
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: galTile.isViewableItem ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        enabled: galTile.isViewableItem
                                        onClicked: function(mouse) {
                                            mouse.accepted = true
                                            detailPanel.modal.openLightbox(index)
                                        }
                                    }
                                }
                            }

                            // Filename & Details Bar
                            Rectangle {
                                Layout.fillWidth: true
                                height: 38
                                color: "transparent"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 1

                                    RowLayout {
                                        spacing: 4
                                        Text {
                                            text: model.name || "attachment"
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                            color: model.selected ? "#F1F5F9" : "#64748B"
                                            elide: Text.ElideMiddle
                                            Layout.fillWidth: true
                                        }

                                        Rectangle {
                                            visible: !!model.is_main
                                            height: 14
                                            implicitWidth: galMainText.implicitWidth + 6
                                            radius: 2
                                            color: "#0F2942"
                                            border.color: "#0284C7"
                                            Text {
                                                id: galMainText
                                                anchors.centerIn: parent
                                                text: "MAIN"
                                                font.pixelSize: 7
                                                font.weight: Font.Bold
                                                color: "#38BDF8"
                                            }
                                        }
                                    }

                                    Text {
                                        text: "#" + (index + 1)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        color: "#475569"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

                PostSelectionFilesListMode {
                    id: listViewWrap
                    modal: detailPanel.modal
                    filesModel: detailPanel.filesModel
                }
        }
    }
}
            }
