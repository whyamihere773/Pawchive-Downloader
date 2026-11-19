import QtQuick
import ".."

Rectangle {
    id: box
    property alias text: inner.text
    property alias echoMode: inner.echoMode
    property string placeholder: ""
    property bool error: false
    signal accepted()
    function forceActiveFocus() { inner.forceActiveFocus() }
    function selectAll() { inner.selectAll() }
    implicitHeight: 30
    radius: 6
    color: inner.activeFocus ? "#0B0D12" : "#0D1018"
    border.color: error ? "#EF4444" : (inner.activeFocus ? "#38BDF8" : (innerBoxMouse.containsMouse ? "#475569" : "#252D3E"))
    border.width: inner.activeFocus ? 1.5 : 1

    TextBarContextArea {
        id: innerBoxMouse
        target: inner
        focusOnLeftClick: true
    }

    TextInput {
        id: inner
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        verticalAlignment: TextInput.AlignVCenter
        color: "#F8FAFC"
        selectionColor: "#0284C7"
        selectedTextColor: "#FFFFFF"
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 12
        selectByMouse: true
        clip: true
        onAccepted: box.accepted()
        TextBarContextArea {}
        Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            visible: !inner.text && !inner.activeFocus
            text: box.placeholder
            color: "#475569"
            font.pixelSize: 11
        }
    }
}

