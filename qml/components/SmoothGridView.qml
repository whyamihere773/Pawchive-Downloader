import QtQuick
import QtQuick.Controls
import "ScrollPhysics.js" as ScrollPhysics

GridView {
    id: gridRoot

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    readonly property real contentRatio: ScrollPhysics.gridContentRatio(
        contentHeight, count, cellWidth, cellHeight, width, height
    )

    flickDeceleration: ScrollPhysics.flickDecel(contentRatio)
    maximumFlickVelocity: ScrollPhysics.maxFlickVel(contentRatio)

    readonly property bool isScrolling: moving || flicking
    property alias verticalScrollBar: vScrollBar
    property real _lastWheelTime: 0
    property real _wheelMomentum: 1.0
    property real _scrollStreak: 0
    property int _lastWheelDir: 0

    ScrollBar.vertical: ScrollBar {
        id: vScrollBar
        active: gridRoot.moving || gridRoot.flicking || vScrollHover.hovered
        policy: ScrollBar.AsNeeded
        width: 7
        HoverHandler { id: vScrollHover }

        contentItem: Rectangle {
            implicitWidth: 7
            radius: 3.5
            color: vScrollBar.pressed ? "#38BDF8" : (vScrollBar.hovered ? "#0EA5E9" : (vScrollBar.active ? "#38BDF8" : "#64748B"))
            opacity: vScrollBar.active ? 0.85 : (gridRoot.contentHeight > gridRoot.height ? 0.35 : 0.0)
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Behavior on color { ColorAnimation { duration: 150 } }
        }

        background: Rectangle {
            implicitWidth: 7
            radius: 3.5
            color: "#0F172A"
            opacity: gridRoot.contentHeight > gridRoot.height ? 0.25 : 0.0
            Behavior on opacity { NumberAnimation { duration: 180 } }
        }
    }

    WheelHandler {
        id: wheelHandler
        target: null
        acceptedDevices: PointerDevice.Mouse
        onWheel: function(event) {
            if (ScrollPhysics.applyWheelFlick(gridRoot, event.angleDelta.y)) {
                event.accepted = true
            }
        }
    }
}
