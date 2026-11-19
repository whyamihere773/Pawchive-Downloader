import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Phase 2: Archive Rebuild live progress, throughput badges, and telemetry micro-cards.
ColumnLayout {
    id: progressPane

    required property var modal
    required property real cardWidth

    Layout.fillWidth: true
    spacing: 14
    visible: modal.isRunning || modal.isFinished

    // Status Banner Line
    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Text {
            text: modal.isFinished
                  ? (modal.finishStatus === "cancelled" ? modal.tr("rebuild_status_cancelled", "Rebuild Stopped") : modal.tr("rebuild_status_complete", "Archive Rebuild Complete"))
                  : (modal.isPaused
                     ? modal.tr("rebuild_status_paused", "Rebuild Paused")
                     : (modal.progressData.phase === "discovering"
                        ? ((modal.progressData.total_files || 0) > 0
                           ? modal.tr("rebuild_status_discovering_count", "Discovering files across directories… (%1 found)").replace("%1", modal.progressData.total_files)
                           : modal.tr("rebuild_status_discovering", "Discovering files across directories..."))
                        : modal.tr("rebuild_status_indexing", "Scanning and cataloging files...")))
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 13
            font.weight: 600
            color: modal.isFinished
                   ? (modal.finishStatus === "cancelled" ? "#FBBF24" : "#34D399")
                   : (modal.isPaused ? "#FBBF24" : "#38BDF8")
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        // Speed Badge
        Rectangle {
            implicitHeight: 22
            implicitWidth: speedRow.implicitWidth + 12
            radius: 6
            color: "#0B0E14"
            border.color: "#1E293B"
            border.width: 1
            visible: modal.isRunning && modal.progressData.files_per_sec > 0

            RowLayout {
                id: speedRow
                anchors.centerIn: parent
                spacing: 5

                Text {
                    text: "⚡ " + (modal.progressData.files_per_sec || 0) + " files/s (" + (modal.progressData.mb_per_sec || 0) + " MB/s)"
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#38BDF8"
                }
            }
        }

        // Elapsed Time Badge
        Rectangle {
            implicitHeight: 22
            implicitWidth: elapsedRow.implicitWidth + 12
            radius: 6
            color: "#0B0E14"
            border.color: "#1E293B"
            border.width: 1

            RowLayout {
                id: elapsedRow
                anchors.centerIn: parent
                spacing: 4

                Text {
                    text: "⏱️ " + (modal.progressData.elapsed_seconds || 0) + "s"
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
            }
        }
    }

    // Sleek Animated Progress Bar
    Rectangle {
        id: modalProgressTrack
        Layout.fillWidth: true
        height: 14
        radius: 7
        color: "#0B0E14"
        border.color: "#1E293B"
        border.width: 1
        clip: true

        readonly property bool isDiscovering: modal.isRunning && !modal.isPaused && modal.progressData.phase === "discovering"

        Rectangle {
            visible: !modalProgressTrack.isDiscovering
            height: parent.height
            width: Math.max(8, parent.width * (Math.min(100, Math.max(0, modal.progressData.percentage || 0)) / 100.0))
            radius: 7

            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: modal.isFinished ? (modal.finishStatus === "cancelled" ? "#D97706" : "#10B981") : "#0284C7" }
                GradientStop { position: 1.0; color: modal.isFinished ? (modal.finishStatus === "cancelled" ? "#FBBF24" : "#34D399") : "#38BDF8" }
            }

            Behavior on width {
                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }

        Rectangle {
            id: modalShimmer
            visible: modalProgressTrack.isDiscovering
            width: Math.max(64, parent.width * 0.28)
            height: parent.height
            radius: 7
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: "#38BDF8" }
                GradientStop { position: 1.0; color: "transparent" }
            }
            SequentialAnimation on x {
                running: modal.isOpen && modalProgressTrack.isDiscovering
                loops: Animation.Infinite
                NumberAnimation { from: -modalShimmer.width; to: modalProgressTrack.width; duration: 1200; easing.type: Easing.InOutSine }
            }
        }
    }

    // Current File Marquee
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        visible: modal.isRunning && Boolean(modal.progressData.current_file)

        Text {
            text: "📄"
            font.pixelSize: 11
        }

        Text {
            text: modal.progressData.current_path || modal.progressData.current_file || ""
            font.family: "Consolas, monospace"
            font.pixelSize: 11
            color: "#64748B"
            Layout.fillWidth: true
            elide: Text.ElideMiddle
        }
    }

    // Telemetry Micro-Cards Grid
    GridLayout {
        Layout.fillWidth: true
        columns: progressPane.cardWidth < 500 ? 2 : 4
        rowSpacing: 8
        columnSpacing: 8

        // Stat 1: Files Processed / Total
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            radius: 8
            color: "#0D111A"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 2

                Text {
                    text: (modal.progressData.processed_files || 0) + " / " + (modal.progressData.total_files || 0)
                    font.family: "Consolas, monospace"
                    font.pixelSize: 13
                    font.weight: 700
                    color: "#F8FAFC"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: modal.tr("rebuild_stat_files", "Files Scanned")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        // Stat 2: Added to Archive
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            radius: 8
            color: "#0D111A"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 2

                Text {
                    text: "+" + (modal.progressData.added_count || 0)
                    font.family: "Consolas, monospace"
                    font.pixelSize: 13
                    font.weight: 700
                    color: "#34D399"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: modal.tr("rebuild_stat_added", "Added")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        // Stat 3: Skipped (Existing)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            radius: 8
            color: "#0D111A"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 2

                Text {
                    text: (modal.progressData.skipped_count || 0).toString()
                    font.family: "Consolas, monospace"
                    font.pixelSize: 13
                    font.weight: 700
                    color: "#FBBF24"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: modal.tr("rebuild_stat_skipped", "Skipped")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }

        // Stat 4: Errors
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 52
            radius: 8
            color: "#0D111A"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 2

                Text {
                    text: (modal.progressData.error_count || 0).toString()
                    font.family: "Consolas, monospace"
                    font.pixelSize: 13
                    font.weight: 700
                    color: (modal.progressData.error_count > 0) ? "#F87171" : "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
                Text {
                    text: modal.tr("rebuild_stat_errors", "Errors")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

    // Discovered Entities Line
    RowLayout {
        Layout.fillWidth: true
        spacing: 12

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: 6
            color: "#0B0E14"
            border.color: "#1E293B"
            border.width: 1

            RowLayout {
                anchors.centerIn: parent
                spacing: 6

                Text {
                    text: "🎨 " + modal.tr("rebuild_stat_creators", "Creators Found") + ":"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
                Text {
                    text: (modal.progressData.total_creators || 0).toString()
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#38BDF8"
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            radius: 6
            color: "#0B0E14"
            border.color: "#1E293B"
            border.width: 1

            RowLayout {
                anchors.centerIn: parent
                spacing: 6

                Text {
                    text: "📦 " + modal.tr("rebuild_stat_posts", "Posts Found") + ":"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
                Text {
                    text: (modal.progressData.total_posts || 0).toString()
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    font.weight: 700
                    color: "#A78BFA"
                }
            }
        }
    }
}
