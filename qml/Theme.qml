pragma Singleton
import QtQuick

QtObject {
    // Surface & Background Colors
    readonly property color bgBase: "#0F1117"
    readonly property color bgSurface: "#181B22"
    readonly property color bgCard: "#202530"
    readonly property color bgCardHover: "#282E3C"
    readonly property color bgInput: "#13161C"
    readonly property color bgHeader: "#151820"
    readonly property color bgConsole: "#0B0D12"

    // Borders & Dividers
    readonly property color borderSubtle: "#2A303F"
    readonly property color borderActive: "#38BDF8"
    readonly property color borderHover: "#475569"

    // Accents & State Colors
    readonly property color primary: "#38BDF8"
    readonly property color primaryHover: "#0EA5E9"
    readonly property color primaryGlow: "#1E3A5F"
    readonly property color secondary: "#818CF8"
    readonly property color success: "#10B981"
    readonly property color successHover: "#059669"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
    readonly property color dangerHover: "#DC2626"
    readonly property color purple: "#A855F7"

    // Typography Colors
    readonly property color textPrimary: "#F8FAFC"
    readonly property color textSecondary: "#94A3B8"
    readonly property color textMuted: "#64748B"
    readonly property color textCode: "#38BDF8"

    // Dimensions & Geometry
    readonly property int radiusSm: 4
    readonly property int radiusMd: 8
    readonly property int radiusLg: 12
    readonly property int radiusXl: 16

    // Fonts
    readonly property string fontFamily: "Segoe UI, Inter, Roboto, sans-serif"
    readonly property string fontMono: "Cascadia Code, Consolas, Fira Code, monospace"
    readonly property int fontSizeSm: 11
    readonly property int fontSizeMd: 13
    readonly property int fontSizeLg: 15
    readonly property int fontSizeXl: 18

    // Newtonian Physics Animation Tokens (Tuned for physical inertia & elasticity)
    readonly property int animMicro: 120       // For icons, checkmarks, tiny badges
    readonly property int animFast: 180        // For button presses, pill toggles
    readonly property int animNormal: 260      // For list items, cards, dropdowns
    readonly property int animSmooth: 360      // For panels, drawers, view switches
    readonly property int animHeavy: 480       // For full modals and backdrop overlays

    // Physical Springs & Overshoot
    readonly property real buttonHoverScale: 1.025
    readonly property real buttonPressScale: 0.945
    readonly property real cardHoverScale: 1.008
    readonly property real pillHoverScale: 1.04
    readonly property real pillPressScale: 0.93
}
