import QtQuick

// Newtonian slide & fade transition container for each tab inside the main StackLayout.
Item {
    required property bool active
    visible: opacity > 0.001
    opacity: active ? 1.0 : 0.0
    y: active ? 0 : 10
    scale: active ? 1.0 : 0.985
    transformOrigin: Item.Center
    Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on y { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
    Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
}
