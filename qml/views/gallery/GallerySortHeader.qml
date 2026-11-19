import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: sh
    property string label: ""
    property string sortKeyName: ""
    property bool alignRight: true
    property var gallery: null
    readonly property bool active: !!gallery && gallery.sortKey === sortKeyName
    height: 18
    Text {
        anchors.fill: parent
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: sh.alignRight ? Text.AlignRight : Text.AlignLeft
        text: sh.label + ((sh.active && sh.gallery) ? (sh.gallery.sortAscending ? "  ▲" : "  ▼") : "")
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 9
        font.weight: 700
        color: sh.active ? "#38BDF8" : (shMouse.containsMouse ? "#CBD5E1" : "#64748B")
    }
    MouseArea {
        id: shMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (sh.gallery) sh.gallery.sortBy(sh.sortKeyName)
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: "Sort by " + sh.label.toLowerCase() + (sh.active ? " (click to reverse)" : "")
    }
}
