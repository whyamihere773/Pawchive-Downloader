import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string title: ""
    property string iconText: ""
    default property alias content: contentContainer.data

    color: "#181B22"
    border.color: "#282E3D"
    border.width: 1
    radius: 10

    implicitHeight: mainCol.implicitHeight + 28

    Behavior on border.color {
        ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
    }
    Behavior on color {
        ColorAnimation { duration: 200; easing.type: Easing.OutCubic }
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
            }

            Text {
                text: root.title
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: "#CBD5E1"
                Layout.fillWidth: true
            }
        }

        // Content Area
        Item {
            id: contentContainer
            Layout.fillWidth: true
            implicitHeight: {
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
