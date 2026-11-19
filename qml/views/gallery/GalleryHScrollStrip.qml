import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: strip
    default property alias content: flick.flickableData
    property real contentWidth: 0
    property color arrowColor: "#141824"
    readonly property bool overflowing: contentWidth > width + 1
    readonly property real maxX: Math.max(0, flick.contentWidth - flick.width)
    clip: true

    function scrollBy(dx) {
        scrollAnim.stop()
        scrollAnim.to = Math.max(0, Math.min(strip.maxX, flick.contentX + dx))
        scrollAnim.start()
    }
    function scrollToEnd() {
        scrollAnim.stop()
        flick.contentX = strip.maxX
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.leftMargin: strip.overflowing ? 20 : 0
        anchors.rightMargin: strip.overflowing ? 20 : 0
        contentWidth: strip.contentWidth
        contentHeight: height
        flickableDirection: Flickable.HorizontalFlick
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        NumberAnimation { id: scrollAnim; target: flick; property: "contentX"; duration: 180; easing.type: Easing.OutCubic }
    }

    // Vertical wheel (or touchpad swipe) scrolls the strip sideways
    WheelHandler {
        target: null
        enabled: strip.overflowing
        onWheel: (event) => {
            var d = event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
            scrollAnim.stop()
            flick.contentX = Math.max(0, Math.min(strip.maxX, flick.contentX - d * 0.6))
        }
    }

    Rectangle {
        visible: strip.overflowing
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 18; height: Math.min(22, strip.height); radius: 4
        color: leftArrowMouse.containsMouse && flick.contentX > 0 ? "#1E293B" : strip.arrowColor
        opacity: flick.contentX > 0 ? 1.0 : 0.35
        Text { anchors.centerIn: parent; text: "‹"; font.pixelSize: 14; font.weight: 700; color: "#CBD5E1" }
        Springy { hover: leftArrowMouse.containsMouse; pressed: leftArrowMouse.pressed }
        MouseArea {
            id: leftArrowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: flick.contentX > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: strip.scrollBy(-flick.width * 0.7)
        }
    }
    Rectangle {
        visible: strip.overflowing
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 18; height: Math.min(22, strip.height); radius: 4
        color: rightArrowMouse.containsMouse && flick.contentX < strip.maxX - 1 ? "#1E293B" : strip.arrowColor
        opacity: flick.contentX < strip.maxX - 1 ? 1.0 : 0.35
        Text { anchors.centerIn: parent; text: "›"; font.pixelSize: 14; font.weight: 700; color: "#CBD5E1" }
        Springy { hover: rightArrowMouse.containsMouse; pressed: rightArrowMouse.pressed }
        MouseArea {
            id: rightArrowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: flick.contentX < strip.maxX - 1 ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: strip.scrollBy(flick.width * 0.7)
        }
    }
}
