import QtQuick
import QtQuick.Controls
import "ScrollPhysics.js" as ScrollPhysics

ListView {
    id: listRoot

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    readonly property real contentRatio: ScrollPhysics.listContentRatio(contentHeight, count, 65.0, height)

    flickDeceleration: ScrollPhysics.flickDecel(contentRatio)
    maximumFlickVelocity: ScrollPhysics.maxFlickVel(contentRatio)

    property real targetContentY: contentY
    readonly property bool isScrolling: moving || flicking
    property alias verticalScrollBar: vScrollBar
    property real _lastWheelTime: 0
    property real _wheelMomentum: 1.0
    property real _scrollStreak: 0
    property int _lastWheelDir: 0
    // A page around the list that scrolls on once the list is at its top / bottom (optional)
    property Flickable chainTo: null

    ScrollBar.vertical: ScrollBar {
        id: vScrollBar
        active: listRoot.moving || listRoot.flicking || vScrollHover.hovered
        policy: ScrollBar.AsNeeded
        width: 7
        HoverHandler { id: vScrollHover }

        contentItem: Rectangle {
            implicitWidth: 7
            radius: 3.5
            color: vScrollBar.pressed ? "#38BDF8" : (vScrollBar.hovered ? "#0EA5E9" : (vScrollBar.active ? "#38BDF8" : "#64748B"))
            opacity: vScrollBar.active ? 0.85 : (listRoot.contentHeight > listRoot.height ? 0.35 : 0.0)
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Behavior on color { ColorAnimation { duration: 150 } }
        }

        background: Rectangle {
            implicitWidth: 7
            radius: 3.5
            color: "#0F172A"
            opacity: listRoot.contentHeight > listRoot.height ? 0.25 : 0.0
            Behavior on opacity { NumberAnimation { duration: 180 } }
        }
    }

    WheelHandler {
        id: wheelHandler
        target: null
        acceptedDevices: PointerDevice.Mouse
        onWheel: function(event) {
            var delta = event.angleDelta.y
            if (delta === 0) return

            var page = listRoot.chainTo
            if (page && page.contentHeight > page.height
                    && ((delta > 0 && listRoot.atYBeginning) || (delta < 0 && listRoot.atYEnd))) {
                if (ScrollPhysics.applyWheelFlick(page, delta)) {
                    event.accepted = true
                }
                return
            }

            if (ScrollPhysics.applyWheelFlick(listRoot, delta)) {
                event.accepted = true
            }
        }
    }
}
