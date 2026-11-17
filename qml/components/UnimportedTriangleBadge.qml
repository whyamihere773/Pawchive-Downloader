import QtQuick
import QtQuick.Controls

/**
 * Amber warning-triangle indicator matching Pawchive's `.state-badge--preview`
 * for posts/creators that exist upstream (previews only) and have not been
 * fully archived/imported yet.
 */
Item {
    id: badgeRoot

    property string tooltipText: "Haven't archived this post yet (previews only)"
    property string badgeColor: "#E6B800"
    property bool showBackground: true

    implicitWidth: 24
    implicitHeight: 24
    width: 24
    height: 24

    Rectangle {
        id: bgPill
        anchors.fill: parent
        radius: 6
        visible: badgeRoot.showBackground
        color: triHover.hovered ? "#F0141923" : "#D80B0E14"
        border.color: triHover.hovered ? "#E6B800" : "#66E6B800"
        border.width: 1
    }

    Canvas {
        id: triCanvas
        anchors.centerIn: parent
        width: Math.max(14, badgeRoot.width - (badgeRoot.showBackground ? 8 : 2))
        height: Math.max(14, badgeRoot.height - (badgeRoot.showBackground ? 8 : 2))
        antialiasing: true
        transform: Translate {
            y: triHover.hovered ? -1.5 : 0
            Behavior on y { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.save()
            ctx.setTransform(1, 0, 0, 1, 0, 0)
            ctx.clearRect(0, 0, width, height)
            var sx = width / 24.0
            var sy = height / 24.0
            ctx.scale(sx, sy)

            ctx.strokeStyle = badgeRoot.badgeColor
            ctx.fillStyle = badgeRoot.badgeColor
            ctx.lineWidth = 2.4
            ctx.lineCap = "round"
            ctx.lineJoin = "round"

            // Triangle outline (matching Lucide / Pawchive .state-badge--preview icon)
            ctx.beginPath()
            ctx.moveTo(12.0, 3.2)
            ctx.lineTo(2.4, 19.6)
            ctx.quadraticCurveTo(1.7, 20.8, 3.1, 20.8)
            ctx.lineTo(20.9, 20.8)
            ctx.quadraticCurveTo(22.3, 20.8, 21.6, 19.6)
            ctx.closePath()
            ctx.stroke()

            // Exclamation stem
            ctx.beginPath()
            ctx.moveTo(12.0, 9.2)
            ctx.lineTo(12.0, 13.8)
            ctx.stroke()

            // Exclamation dot
            ctx.beginPath()
            ctx.arc(12.0, 17.2, 1.15, 0, Math.PI * 2)
            ctx.fill()
            ctx.restore()
        }
    }

    HoverHandler {
        id: triHover
    }

    ToolTip.visible: badgeRoot.visible && triHover.hovered
    ToolTip.delay: 200
    ToolTip.text: badgeRoot.tooltipText
}
