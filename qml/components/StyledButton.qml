import QtQuick
import QtQuick.Controls

Button {
    id: control

    property string variant: "default" // "primary", "success", "danger", "ghost", "outline", "default"
    property string iconText: ""
    property int customRadius: 8
    property string tooltip: ""

    ToolTip {
        text: control.tooltip
        visible: control.tooltip.length > 0 && control.hovered
        delay: 400
        timeout: 5000
        contentItem: Text {
            text: control.tooltip
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 11
            color: "#F1F5F9"
        }
        background: Rectangle {
            color: "#181B24"
            border.color: "#38BDF8"
            border.width: 1
            radius: 6
        }
    }

    font.family: "Segoe UI, Inter, sans-serif"
    font.pixelSize: 12
    font.weight: Font.Medium
    implicitHeight: 34
    implicitWidth: Math.max(90, contentItem.implicitWidth + 24)

    // Fluid Newtonian Spring Scale on Hover & Press
    scale: control.down ? 0.945 : (control.hovered ? 1.025 : 1.0)
    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation {
            duration: control.down ? 110 : 220
            easing.type: control.down ? Easing.OutCubic : Easing.OutBack
            easing.overshoot: 1.4
        }
    }

    contentItem: Row {
        spacing: 6
        anchors.centerIn: parent

        Text {
            text: control.iconText
            visible: control.iconText.length > 0
            font.pixelSize: 13
            anchors.verticalCenter: parent.verticalCenter
            color: control.textColor()

            // Subtle micro-spring bounce on icon
            scale: control.hovered ? 1.1 : 1.0
            Behavior on scale {
                NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
            }
        }

        Text {
            text: control.text
            font: control.font
            color: control.textColor()
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    background: Rectangle {
        implicitWidth: control.implicitWidth
        implicitHeight: control.implicitHeight
        radius: control.customRadius
        color: control.backgroundColor()
        border.color: control.borderColor()
        border.width: 1

        // Soft dynamic glow aura on hover for primary/success/danger buttons
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: control.customRadius + 2
            color: "transparent"
            border.color: control.glowColor()
            border.width: 1.5
            opacity: control.hovered && !control.down ? 0.6 : 0.0
            z: -1

            Behavior on opacity {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }
        }

        Behavior on color {
            ColorAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
        Behavior on border.color {
            ColorAnimation { duration: 160; easing.type: Easing.OutCubic }
        }
    }

    function glowColor() {
        if (variant === "primary") return "#38BDF8"
        if (variant === "success") return "#10B981"
        if (variant === "danger") return "#EF4444"
        return "#475569"
    }

    function backgroundColor() {
        if (!control.enabled) return "#1F232B"

        if (variant === "primary") {
            return control.down ? "#0284C7" : (control.hovered ? "#0EA5E9" : "#38BDF8")
        } else if (variant === "success") {
            return control.down ? "#047857" : (control.hovered ? "#059669" : "#10B981")
        } else if (variant === "danger") {
            return control.down ? "#B91C1C" : (control.hovered ? "#DC2626" : "#EF4444")
        } else if (variant === "ghost") {
            return control.hovered ? "#242B38" : "transparent"
        } else if (variant === "outline") {
            return control.hovered ? "#242B38" : "#181B22"
        }
        // default
        return control.down ? "#1E222A" : (control.hovered ? "#2C3340" : "#222732")
    }

    function borderColor() {
        if (!control.enabled) return "#2A303C"
        if (variant === "primary" && (control.hovered || control.down)) return "#38BDF8"
        if (variant === "outline") return control.hovered ? "#38BDF8" : "#374151"
        if (variant === "ghost") return "transparent"
        return control.hovered ? "#475569" : "#333A48"
    }

    function textColor() {
        if (!control.enabled) return "#64748B"
        if (variant === "primary") return "#0F172A"
        if (variant === "success") return "#FFFFFF"
        if (variant === "danger") return "#FFFFFF"
        if (variant === "ghost" && control.hovered) return "#38BDF8"
        return "#E2E8F0"
    }
}
