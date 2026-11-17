import QtQuick

// ── Springy: weight-based hover / press physics for its parent ───────────────
// Drop inside any clickable element:  Springy { hover: m.containsMouse; pressed: m.pressed }
// The parent's scale follows a real spring (stiffness, damping, mass). Mass comes from the
// element's size, so small chips snap back quickly while big cards and panels move with more
// inertia and grow less on hover — like objects with actual weight.
Item {
    id: sp
    width: 0
    height: 0

    property Item target: parent
    property bool hover: false
    property bool pressed: false

    // Weight from area: tiny chips react immediately, larger controls stay understated
    readonly property real autoMass: target ? Math.max(0.35, Math.min(1.0, Math.sqrt(Math.max(1, target.width * target.height)) / 64)) : 0.65
    property real mass: autoMass
    property real hoverScale: 1.0 + 0.035 / Math.max(1.0, mass * 1.3)
    property real pressScale: 1.0 - 0.055 / Math.max(1.0, mass)

    property real springValue: pressed ? pressScale : (hover ? hoverScale : 1.0)
    Behavior on springValue {
        NumberAnimation { duration: 95; easing.type: Easing.OutCubic }
    }

    Binding {
        target: sp.target
        property: "scale"
        value: sp.springValue
        when: !!sp.target
        restoreMode: Binding.RestoreNone
    }
}
