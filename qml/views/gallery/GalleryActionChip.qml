import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: chip
    property string icon: ""
    property string label: ""
    property string tip: ""
    property bool danger: false
    property bool compact: false   // icon-only (label moves to the tooltip)
    signal triggered()
    implicitHeight: 24
    implicitWidth: chipRow.implicitWidth + (compact ? 12 : 14)
    radius: 5
    color: chipMouse.containsMouse ? (danger ? "#3A1620" : "#1E293B") : "#141720"
    border.color: chipMouse.containsMouse ? (danger ? "#EF4444" : "#38BDF8") : "#2E384D"
    border.width: 1
    Row {
        id: chipRow
        anchors.centerIn: parent
        spacing: 4
        Text {
            text: chip.icon
            font.pixelSize: 13          // symbol glyphs (⊞ ⋯ ⧉) read too small at text size
            anchors.verticalCenter: parent.verticalCenter
            visible: chip.icon.length > 0
            color: chip.danger ? "#F87171" : "#CBD5E1"
        }
        Text {
            text: chip.label
            anchors.verticalCenter: parent.verticalCenter
            visible: !(chip.compact && chip.icon.length > 0)
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            font.weight: 600
            color: chip.danger ? "#F87171" : "#E2E8F0"
        }
    }
    Springy { hover: chipMouse.containsMouse; pressed: chipMouse.pressed }
    MouseArea {
        id: chipMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: chip.triggered()
        ToolTip.visible: containsMouse && (chip.tip.length > 0 || chip.compact)
        ToolTip.delay: 300
        ToolTip.text: (chip.compact && chip.icon.length > 0) ? (chip.label + (chip.tip ? "
" + chip.tip : "")) : chip.tip
    }
}
