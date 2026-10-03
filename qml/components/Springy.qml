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

    // Weight from area: a 26px icon button ≈ 0.55, a 160px card ≈ 2.2 (clamped)
    readonly property real autoMass: target ? Math.max(0.45, Math.min(2.4, Math.sqrt(Math.max(1, target.width * target.height)) / 48)) : 1.0
    property real mass: autoMass
    property real hoverScale: 1.0 + 0.055 / Math.max(1.0, mass * 1.4)
    property real pressScale: 1.0 - 0.07 / Math.max(1.0, mass)

    property real springValue: pressed ? pressScale : (hover ? hoverScale : 1.0)
    Behavior on springValue {
        SpringAnimation { spring: 5.0; damping: 0.26; mass: sp.mass; epsilon: 0.0004 }
    }

    Binding {
        target: sp.target
        property: "scale"
        value: sp.springValue
        when: !!sp.target
        restoreMode: Binding.RestoreNone
    }
}
