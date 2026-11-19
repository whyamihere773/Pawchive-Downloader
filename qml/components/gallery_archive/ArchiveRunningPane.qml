import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Live progress, shimmer bar, and throughput telemetry pane for GalleryArchiveModal.
ColumnLayout {
    id: runningPane

    required property var modal
    Layout.fillWidth: true
    spacing: 8
    visible: modal.stage === "running"

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Text {
            Layout.fillWidth: true
            text: modal.progressStatus
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#CBD5E1"
            elide: Text.ElideMiddle
        }
        Text {
            visible: modal.itemCount > 1
            text: (modal.itemIndex + 1) + " of " + modal.itemCount
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            font.weight: 600
            color: "#94A3B8"
        }
    }

    // Progress bar with a moving shimmer, so it visibly keeps working
    // even while 7-Zip is between percentage updates.
    Rectangle {
        id: track
        Layout.fillWidth: true
        implicitHeight: 10
        radius: 5
        color: "#1E2536"
        clip: true
        Rectangle {
            id: fill
            width: track.width * Math.max(0.02, Math.min(1, modal.progress / 100))
            height: parent.height
            radius: 5
            color: modal.mode === "compress" ? "#A78BFA" : (modal.mode === "copy" ? "#34D399" : "#38BDF8")
            Behavior on width { NumberAnimation { duration: 250 } }
        }
        Rectangle {
            id: shimmer
            width: 60
            height: parent.height
            opacity: 0.55
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#00FFFFFF" }
                GradientStop { position: 0.5; color: "#AAFFFFFF" }
                GradientStop { position: 1.0; color: "#00FFFFFF" }
            }
            NumberAnimation on x {
                running: modal.stage === "running"
                loops: Animation.Infinite
                from: -60
                to: Math.max(track.width, 60)
                duration: 1400
            }
        }
    }

    // 45%  •  128 MB of 400 MB  •  23.4 MB/s  •  about 12s left        0:34
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        Text {
            text: Math.floor(modal.progress) + "%"
            font.family: "Segoe UI, monospace"
            font.pixelSize: 12
            font.weight: 700
            color: "#F8FAFC"
        }
        Text {
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: {
                var parts = []
                if (modal.totalBytes > 0) parts.push(modal.formatBytes(modal.doneBytes) + " of " + modal.formatBytes(modal.totalBytes))
                if (modal.speed > 0) parts.push(modal.formatBytes(modal.speed) + "/s")
                if (modal.eta >= 0) parts.push(modal.eta < 1.5 ? "almost done" : ("about " + modal.formatDuration(modal.eta) + " left"))
                else if (modal.elapsedSec >= 1) parts.push("estimating time…")
                return parts.length ? "•  " + parts.join("  •  ") : ""
            }
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
        }
        Text {
            text: "⏱ " + modal.formatClock(modal.elapsedSec)
            font.family: "Segoe UI, monospace"
            font.pixelSize: 11
            color: "#64748B"
            ToolTip.visible: clockMouse.containsMouse
            ToolTip.delay: 300
            ToolTip.text: "Time elapsed"
            MouseArea { id: clockMouse; anchors.fill: parent; hoverEnabled: true }
        }
    }

    Text {
        Layout.fillWidth: true
        text: "You can keep browsing: \"Run in background\" (or Esc) hides this window and shows the progress in the status bar."
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        color: "#475569"
        wrapMode: Text.WordWrap
    }

    Text {
        Layout.fillWidth: true
        visible: modal.looksQuiet
        text: "Still working… 7-Zip reports progress in steps, so big files can sit on one number for a while."
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        color: "#F59E0B"
        wrapMode: Text.WordWrap
    }
}

