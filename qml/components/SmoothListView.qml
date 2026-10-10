import QtQuick
import QtQuick.Controls

ListView {
    id: listRoot

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    readonly property real contentRatio: {
        var effectiveH = contentHeight
        if (typeof count === "number" && count > 0) {
            effectiveH = Math.max(effectiveH, count * 65.0)
        }
        return Math.max(1.0, effectiveH / Math.max(1, height))
    }

    // Dynamic deceleration: snappy (6000) on short views, more fluid (4000) on large lists
    flickDeceleration: Math.max(5000, 6000 - Math.min(1000, (contentRatio - 1.0) * 50))
    // Dynamic velocity cap: 2500 on short views, scaling up to 7500 on massive lists
    maximumFlickVelocity: Math.min(5000, 2500 + Math.min(2500, (contentRatio - 1.0) * 100))

    property real targetContentY: contentY
    readonly property bool isScrolling: moving || flicking
    property alias verticalScrollBar: vScrollBar
    property real _lastWheelTime: 0
    property real _wheelMomentum: 1.0
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
                var pv = (delta / 120.0) * 1100
                page.flick(0, Math.max(-page.maximumFlickVelocity, Math.min(page.maximumFlickVelocity, pv)))
                event.accepted = true
                return
            }

            var now = Date.now()
            var dt = now - listRoot._lastWheelTime
            listRoot._lastWheelTime = now

            // Detect rapid wheel spinning and build momentum faster on larger lists
            if (dt < 180) {
                var accelStep = 0.2 + Math.min(0.2, (listRoot.contentRatio - 1.0) * 0.02)
                var maxMomentum = Math.min(2.2, 1.5 + Math.min(0.7, (listRoot.contentRatio - 1.0) * 0.05))
                listRoot._wheelMomentum = Math.min(maxMomentum, listRoot._wheelMomentum + accelStep)
            } else {
                listRoot._wheelMomentum = 1.0
            }

            // Dynamic base notch scale: 1.0x on short views (~120px), scaling up to 2.8x on huge lists
            var sizeScale = Math.min(1.35, 1.0 + Math.log2(Math.max(1.0, listRoot.contentRatio / 1.8)) * 0.12)
            var baseSpeed = 1100 * sizeScale * listRoot._wheelMomentum

            var notchV = (delta / 120.0) * baseSpeed
            var curV = listRoot.flicking ? listRoot.verticalVelocity : 0
            var targetV = 0
            if ((notchV > 0 && curV > 0) || (notchV < 0 && curV < 0)) {
                var carryFactor = Math.min(0.55, 0.35 + Math.min(0.2, (listRoot.contentRatio - 1.0) * 0.02))
                targetV = curV * carryFactor + notchV
            } else {
                targetV = notchV
            }
            targetV = Math.max(-listRoot.maximumFlickVelocity, Math.min(listRoot.maximumFlickVelocity, targetV))
            listRoot.flick(0, targetV)
            event.accepted = true
        }
    }
}
