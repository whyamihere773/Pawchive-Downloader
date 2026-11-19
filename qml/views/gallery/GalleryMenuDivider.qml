import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    width: parent ? parent.width : 200
    height: 9
    color: "transparent"
    Rectangle { anchors.centerIn: parent; width: parent.width - 8; height: 1; color: "#232B3D" }
}
