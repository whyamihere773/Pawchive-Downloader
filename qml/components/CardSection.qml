import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string iconText: ""
    property bool interactive: true
    property real entranceOffsetY: 0
    property real entranceOpacity: 1.0

    default property alias content: contentContainer.data

    color: (cardHover.hovered && root.interactive) ? "#1B1F2A" : "#181B22"
    border.color: (cardHover.hovered && root.interactive) ? "#38BDF8" : "#282E3D"
    border.width: 1
    radius: 10
    opacity: root.entranceOpacity

    implicitHeight: mainCol.implicitHeight + 28

    HoverHandler {
        id: cardHover
        enabled: root.interactive
    }

    transform: Translate {
        y: ((cardHover.hovered && root.interactive) ? -2.0 : 0.0) + root.entranceOffsetY
        Behavior on y {
            SpringAnimation {
                spring: 4.0
                damping: 0.38
                mass: 1.0
                epsilon: 0.25
            }
        }
    }

    Behavior on border.color {
        ColorAnimation { duration: 180; easing.type: Easing.OutCubic }
    }
    Behavior on color {
        ColorAnimation { duration: 180; easing.type: Easing.OutCubic }
    }
    Behavior on opacity {
        NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        id: mainCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 14
        spacing: 12

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: root.title.length > 0

            Text {
                text: root.iconText
                visible: root.iconText.length > 0
                font.pixelSize: 14
                color: "#38BDF8"

                scale: (cardHover.hovered && root.interactive) ? 1.12 : 1.0
                Behavior on scale {
                    SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 }
                }
            }

            Text {
                text: root.title
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: (cardHover.hovered && root.interactive) ? "#F1F5F9" : "#CBD5E1"
                Layout.fillWidth: true

                Behavior on color {
                    ColorAnimation { duration: 160 }
                }
            }
        }

        // Content Area with fast-path layout to prevent scroll sluggishness
        Item {
            id: contentContainer
            Layout.fillWidth: true
            implicitHeight: {
                if (children.length === 1) {
                    var single = children[0];
                    if (single.implicitHeight !== undefined && single.implicitHeight > 0) return single.implicitHeight;
                    if (single.height !== undefined && single.height > 0) return single.height;
                }
                var maxH = 0;
                for (var i = 0; i < children.length; ++i) {
                    var c = children[i];
                    var h = (c.implicitHeight && c.implicitHeight > 0) ? c.implicitHeight : ((c.height && c.height > 0) ? c.height : 0);
                    if (h > maxH) maxH = h;
                }
                return Math.max(maxH, childrenRect.height);
            }
        }
    }
}
