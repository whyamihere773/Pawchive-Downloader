import QtQuick
import QtQuick.Controls

Flickable {
    id: flickRoot

    clip: true
    boundsBehavior: Flickable.DragAndOvershootBounds
    boundsMovement: Flickable.FollowBoundsBehavior
    flickableDirection: Flickable.VerticalFlick
    flickDeceleration: 1500
    maximumFlickVelocity: 4500

    property real targetContentY: contentY
    property real lastWheelTime: 0
    property real wheelVelocityFactor: 1.0
    readonly property bool isScrolling: moving || flicking || wheelAnim.running
    property alias verticalScrollBar: vScrollBar

    onMovingChanged: {
        if (moving) {
            wheelAnim.stop()
            targetContentY = contentY
        }
    }

    NumberAnimation {
        id: wheelAnim
        target: flickRoot
        property: "contentY"
        duration: 170
        easing.type: Easing.OutQuad
    }

    ScrollBar.vertical: ScrollBar {
        id: vScrollBar
        active: flickRoot.moving || flickRoot.flicking || wheelAnim.running || vScrollHover.hovered
        policy: ScrollBar.AsNeeded
        width: 8
        onPressedChanged: {
            if (pressed) {
                wheelAnim.stop()
                flickRoot.targetContentY = flickRoot.contentY
            }
        }
        HoverHandler { id: vScrollHover }
    }

    WheelHandler {
        id: wheelHandler
        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) {
            var now = Date.now()
            var dt = now - flickRoot.lastWheelTime
            flickRoot.lastWheelTime = now

            // Accelerate velocity if scrolled rapidly (Newtonian momentum)
            if (dt < 130) {
                flickRoot.wheelVelocityFactor = Math.min(2.8, flickRoot.wheelVelocityFactor + 0.4)
            } else {
                flickRoot.wheelVelocityFactor = 1.0
            }

            var delta = event.angleDelta.y
            if (delta === 0) return

            var baseStep = 120 * flickRoot.wheelVelocityFactor
            var step = (delta / 120.0) * baseStep
            var maxY = Math.max(0, flickRoot.contentHeight - flickRoot.height)

            if (!wheelAnim.running) {
                flickRoot.targetContentY = flickRoot.contentY
            }

            flickRoot.targetContentY = Math.max(0, Math.min(maxY, flickRoot.targetContentY - step))

            wheelAnim.stop()
            wheelAnim.from = flickRoot.contentY
            wheelAnim.to = flickRoot.targetContentY
            wheelAnim.start()
        }
    }
}
