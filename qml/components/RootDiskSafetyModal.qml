import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Root Disk & Operating System Safety Modal ──────────────────────────────
// Foolproof safety barrier preventing accidental cleaning, renames, or deletions
// on the Windows operating system drive root (permanently blocked) or secondary root drives (double confirmation).
Item {
    id: root

    property bool isOpen: false
    property string mode: "blocked" // "blocked" | "warning_stage1" | "warning_stage2"
    property string actionTitle: ""
    property string driveLetter: "C:"
    property string targetPath: ""
    property string safetyMessage: ""
    property var onConfirmCallback: null

    anchors.fill: parent
    z: 99999
    // Fades in / out (weight-based motion); no input while closing
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    function showBlocked(action, drive, path, message) {
        actionTitle = action || "File Operation"
        driveLetter = drive || "C:"
        targetPath = path || ""
        safetyMessage = message || ""
        mode = "blocked"
        onConfirmCallback = null
        isOpen = true
    }

    function showRootWarning(action, drive, path, callback) {
        actionTitle = action || "File Operation"
        driveLetter = drive || "D:"
        targetPath = path || ""
        safetyMessage = ""
        mode = "warning_stage1"
        onConfirmCallback = callback
        isOpen = true
    }

    function close() {
        isOpen = false
        mode = "blocked"
        safetyMessage = ""
        onConfirmCallback = null
    }

    // Semi-transparent dark backdrop
    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: root.isOpen ? 0.92 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea {
            anchors.fill: parent
            // Prevent clicks, hover (card tooltips) and the wheel from passing through
            hoverEnabled: true
            onClicked: {}
            onWheel: (wheel) => wheel.accepted = true
        }
    }

    // Modal Card
    Rectangle {
        // Heavy panel: settles in on a soft spring
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        width: Math.min(540, parent.width - 32)
        height: cardContent.implicitHeight + 48
        anchors.centerIn: parent
        radius: 14
        color: "#101420"
        border.color: root.mode === "blocked" ? "#EF4444" : (root.mode === "warning_stage2" ? "#DC2626" : "#F59E0B")
        border.width: 1.5
        clip: true

        ColumnLayout {
            id: cardContent
            anchors.centerIn: parent
            width: parent.width - 44
            spacing: 16

            // Header Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Rectangle {
                    width: 46
                    height: 46
                    radius: 23
                    color: root.mode === "blocked" ? "#3B1219" : (root.mode === "warning_stage2" ? "#450A0A" : "#38230B")
                    border.color: root.mode === "blocked" ? "#EF4444" : (root.mode === "warning_stage2" ? "#EF4444" : "#F59E0B")
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: root.mode === "blocked" ? "🛡️" : (root.mode === "warning_stage2" ? "🛑" : "⚠️")
                        font.pixelSize: 22
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        text: {
                            if (root.mode === "blocked") return "Operation Permanently Blocked"
                            if (root.mode === "warning_stage1") return "Root Drive Warning (Step 1 of 2)"
                            return "Extreme Danger: Final Confirmation (Step 2 of 2)"
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.weight: 700
                        color: root.mode === "blocked" ? "#FCA5A5" : (root.mode === "warning_stage2" ? "#FCA5A5" : "#FDE68A")
                    }

                    Text {
                        text: {
                            if (root.mode === "blocked") return "Windows Operating System Protection Active"
                            if (root.mode === "warning_stage1") return "High-Risk Storage Location Detected"
                            return "Second Verification Required Before Execution"
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }
            }

            // Path & Action Tag Banner
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                radius: 8
                color: "#161D2E"
                border.color: "#273349"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Text {
                        text: "Action:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: "#64748B"
                    }

                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: actionLabel.implicitWidth + 12
                        radius: 4
                        color: "#1E293B"
                        Text {
                            id: actionLabel
                            anchors.centerIn: parent
                            text: root.actionTitle
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "Target Root:"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 700
                        color: "#64748B"
                    }

                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: driveLabel.implicitWidth + 12
                        radius: 4
                        color: root.mode === "blocked" ? "#450A0A" : "#451A03"
                        border.color: root.mode === "blocked" ? "#DC2626" : "#D97706"
                        border.width: 1
                        Text {
                            id: driveLabel
                            anchors.centerIn: parent
                            text: root.driveLetter ? (root.driveLetter + "\\") : root.targetPath
                            font.family: "Segoe UI, monospace"
                            font.pixelSize: 10
                            font.weight: 700
                            color: root.mode === "blocked" ? "#FCA5A5" : "#FDE68A"
                        }
                    }
                }
            }

            // Detailed Explanation Text Box
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: expText.implicitHeight + 20
                radius: 8
                color: "#0B0E17"
                border.color: "#1A2234"
                border.width: 1

                Text {
                    id: expText
                    anchors.fill: parent
                    anchors.margins: 10
                    wrapMode: Text.Wrap
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    lineHeight: 1.35
                    color: "#CBD5E1"
                    text: {
                        if (root.mode === "blocked") {
                            if (root.safetyMessage && root.safetyMessage.length > 0) {
                                return root.safetyMessage + "\n\nPlease navigate to a safe subfolder (such as your Downloads or Media archive folder) to use this tool."
                            }
                            return "For the stability and safety of your computer, running '" + root.actionTitle + "' directly on the root of your operating system drive (" + root.driveLetter + "\\) or protected system/app folders is permanently forbidden.\n\nPlease navigate to a subfolder (such as your Downloads or Media archive folder) to use this tool."
                        } else if (root.mode === "warning_stage1") {
                            return "You are currently at the root of drive " + root.driveLetter + "\\.\n\nExecuting '" + root.actionTitle + "' directly on a root drive will affect, rename, sort, or scan all files and folders across the entire storage drive!\n\nAre you sure you want to proceed on this root drive?"
                        } else {
                            return "⚠️ FINAL WARNING: You are about to launch '" + root.actionTitle + "' on the root of drive " + root.driveLetter + "\\.\n\nThis is your final confirmation. This operation cannot be easily undone and may move or reorganize thousands of files.\n\nClick 'Confirm & Proceed' only if you are 100% certain."
                        }
                    }
                }
            }

            // Action Buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                // State: Blocked
                Item {
                    visible: root.mode === "blocked"
                    Layout.fillWidth: true
                    implicitHeight: 36

                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: closeBtnMouse.containsMouse ? "#253147" : "#1B2232"
                        border.color: "#384561"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Understood, Close"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                        Springy { hover: closeBtnMouse.containsMouse; pressed: closeBtnMouse.pressed }
                        MouseArea {
                            id: closeBtnMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.close()
                        }
                    }
                }

                // State: Stage 1 Buttons
                RowLayout {
                    visible: root.mode === "warning_stage1"
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 36
                        radius: 6
                        color: cancel1Mouse.containsMouse ? "#253147" : "#1B2232"
                        border.color: "#384561"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Cancel (Recommended)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                        Springy { hover: cancel1Mouse.containsMouse; pressed: cancel1Mouse.pressed }
                        MouseArea {
                            id: cancel1Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.close()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 36
                        radius: 6
                        color: cont1Mouse.containsMouse ? "#D97706" : "#B45309"
                        border.color: "#F59E0B"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Continue to Step 2 →"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 700
                            color: "#FFFFFF"
                        }
                        Springy { hover: cont1Mouse.containsMouse; pressed: cont1Mouse.pressed }
                        MouseArea {
                            id: cont1Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.mode = "warning_stage2"
                        }
                    }
                }

                // State: Stage 2 Buttons (Final Lock)
                RowLayout {
                    visible: root.mode === "warning_stage2"
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 36
                        radius: 6
                        color: abort2Mouse.containsMouse ? "#253147" : "#1B2232"
                        border.color: "#384561"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "Abort & Go Back (Safe)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                        }
                        Springy { hover: abort2Mouse.containsMouse; pressed: abort2Mouse.pressed }
                        MouseArea {
                            id: abort2Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.close()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 36
                        radius: 6
                        color: confirm2Mouse.containsMouse ? "#B91C1C" : "#991B1B"
                        border.color: "#EF4444"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "I Understand Risks, Proceed"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 700
                            color: "#FFFFFF"
                        }
                        Springy { hover: confirm2Mouse.containsMouse; pressed: confirm2Mouse.pressed }
                        MouseArea {
                            id: confirm2Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var cb = root.onConfirmCallback
                                root.close()
                                if (cb) cb()
                            }
                        }
                    }
                }
            }
        }
    }
}
