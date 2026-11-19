import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: statusBar
    required property var view
    Layout.fillWidth: true
    implicitHeight: 28
    radius: 6
    color: "#0F121B"
    border.color: "#1E2536"
    border.width: 1

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 12

        // Left: Counts of folders and files
        Row {
            spacing: 8
            Layout.alignment: Qt.AlignVCenter
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            clip: true

            // Folders count
            Row {
                spacing: 4
                Text { text: "📁"; font.pixelSize: 11 }
                Text {
                    text: statusBar.view.folderCount + (statusBar.view.folderCount === 1 ? " folder" : " folders")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#38BDF8"
                }
            }

            Text { text: "•"; font.pixelSize: 10; color: "#475569" }

            // Files count + total file size
            Row {
                spacing: 4
                Text { text: "📄"; font.pixelSize: 11 }
                Text {
                    text: {
                        var txt = statusBar.view.fileCount + (statusBar.view.fileCount === 1 ? " file" : " files")
                        if (statusBar.view.currentFolderFilesSize > 0) {
                            txt += " (" + statusBar.view.formatBytes(statusBar.view.currentFolderFilesSize) + ")"
                        }
                        return txt
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                }
            }

            // Filtered count (if user searched or picked a category)
            Text {
                visible: !statusBar.view.recursiveActive && statusBar.view.shownItemCount !== statusBar.view.rawItems.length
                text: statusBar.view.compact ? ("(" + statusBar.view.shownItemCount + "/" + statusBar.view.rawItems.length + ")") : ("— showing " + statusBar.view.shownItemCount + " of " + statusBar.view.rawItems.length)
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                color: "#94A3B8"
            }

            // Subfolder search progress
            Text {
                visible: statusBar.view.recursiveActive
                text: "🔎 " + statusBar.view.searchResults.length + (statusBar.view.searchResults.length === 1 ? " match" : " matches") + " in subfolders"
                      + (statusBar.view.searchRunning ? "  (searching… " + statusBar.view.searchScanned + " folders)" : "")
                      + (statusBar.view.searchResults.length >= 5000 ? "  — showing the first 5,000" : "")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 600
                color: "#A78BFA"
            }

            // Folder has more entries than the gallery loads at once
            Text {
                visible: statusBar.view.listingTotal > statusBar.view.rawItems.length
                text: statusBar.view.compact ? ("⚠ " + statusBar.view.rawItems.length.toLocaleString(Qt.locale(), "f", 0) + " of " + statusBar.view.listingTotal.toLocaleString(Qt.locale(), "f", 0) + " shown") : ("⚠ Only the first " + statusBar.view.rawItems.length.toLocaleString(Qt.locale(), "f", 0) + " of " + statusBar.view.listingTotal.toLocaleString(Qt.locale(), "f", 0) + " items are shown")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 600
                color: "#F59E0B"
            }
        }

        Item { Layout.fillWidth: true }

        // A download is running while the download controls are hidden: show it, click to go back
        Rectangle {
            visible: !!statusBar.view.bridge && !!statusBar.view.bridge.isDownloading
            implicitHeight: 20
            implicitWidth: dlChipRow.implicitWidth + 16
            radius: 10
            clip: true
            color: dlChipMouse.containsMouse ? "#1E293B" : "#121a2b"
            border.color: "#38BDF8"
            border.width: 1
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, (statusBar.view.bridge ? statusBar.view.bridge.overallProgress : 0) / 100))
                radius: 10
                color: "#1E3A5F"
                opacity: 0.8
            }
            Row {
                id: dlChipRow
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 5
                Text { text: "⬇"; font.pixelSize: 10; font.weight: 800; color: "#7DD3FC" }
                Text {
                    text: "Downloading " + (statusBar.view.bridge ? statusBar.view.bridge.overallProgress : 0) + "%"
                          + ((statusBar.view.bridge && statusBar.view.bridge.currentSpeed && !statusBar.view.compact) ? "  •  " + statusBar.view.bridge.currentSpeed : "")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                }
            }
            Springy { hover: dlChipMouse.containsMouse; pressed: dlChipMouse.pressed }
            MouseArea {
                id: dlChipMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (typeof appWindow !== "undefined") appWindow.currentTab = 0
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: (statusBar.view.bridge ? statusBar.view.bridge.statusText : "") + "
Click to open the Downloader"
            }
        }

        // Background job: live progress, or "done — view" once it finishes
        Rectangle {
            readonly property bool runningHidden: statusBar.view.archiveModal.ownsJob && !statusBar.view.archiveModal.isOpen
            visible: runningHidden || statusBar.view.archiveModal.unseenResult
            implicitHeight: 20
            implicitWidth: Math.min(bgJobRow.implicitWidth + 16, statusBar.view.compact ? 230 : 380)
            radius: 10
            clip: true
            color: bgJobMouse.containsMouse ? "#1E293B" : "#121a2b"
            border.color: statusBar.view.archiveModal.unseenResult ? ((statusBar.view.archiveModal.result.failed > 0 || statusBar.view.archiveModal.result.cancelled) ? "#F59E0B" : "#34D399") : "#38BDF8"
            border.width: 1

            // Progress fill behind the text
            Rectangle {
                visible: parent.runningHidden
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, statusBar.view.archiveModal.progress / 100))
                radius: 10
                color: "#1E3A5F"
                opacity: 0.8
            }
            Row {
                id: bgJobRow
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text {
                    text: statusBar.view.archiveModal.unseenResult ? ((statusBar.view.archiveModal.result.failed > 0 || statusBar.view.archiveModal.result.cancelled) ? "⚠" : "✔")
                          : (statusBar.view.archiveModal.mode === "compress" ? "📦" : (statusBar.view.archiveModal.mode === "copy" ? "📋" : "📂"))
                    font.pixelSize: 10
                    color: "#CBD5E1"
                }
                Text {
                    text: {
                        if (statusBar.view.archiveModal.unseenResult) return statusBar.view.archiveModal.resultHeadline() + " — view"
                        var t = Math.floor(statusBar.view.archiveModal.progress) + "%"
                        if (statusBar.view.archiveModal.eta >= 0) t += " • " + (statusBar.view.archiveModal.eta < 1.5 ? "almost done" : statusBar.view.archiveModal.formatDuration(statusBar.view.archiveModal.eta) + " left")
                        return (statusBar.view.archiveModal.progressName || statusBar.view.archiveModal.progressStatus) + "  " + t
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                    elide: Text.ElideMiddle
                    width: Math.min(implicitWidth, statusBar.view.compact ? 190 : 340)
                }
            }
            Springy { hover: bgJobMouse.containsMouse; pressed: bgJobMouse.pressed }
            MouseArea {
                id: bgJobMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: statusBar.view.archiveModal.reopen()
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: parent.runningHidden ? (statusBar.view.archiveModal.progressStatus + "\nClick to show the progress window") : "Click to see the details"
            }
        }

        // Media Compression background job: live progress or "done — view"
        Rectangle {
            id: mcBgJobPill
            readonly property var mcItem: statusBar.view.mediaCompressLoader.item
            readonly property bool runningHidden: mcItem && mcItem.stage === "running" && !mcItem.isOpen
            readonly property bool unseenResult: mcItem && mcItem.unseenResult
            visible: runningHidden || unseenResult
            implicitHeight: 20
            implicitWidth: Math.min(mcBgJobRow.implicitWidth + 16, statusBar.view.compact ? 230 : 380)
            radius: 10
            clip: true
            color: mcBgJobMouse.containsMouse ? "#1E293B" : "#121a2b"
            border.color: unseenResult ? ((mcItem && mcItem.failedCount > 0) ? "#F59E0B" : "#34D399") : "#0284C7"
            border.width: 1

            // Progress fill behind the text
            Rectangle {
                visible: mcBgJobPill.runningHidden
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, (mcBgJobPill.mcItem ? mcBgJobPill.mcItem.progress : 0) / 100))
                radius: 10
                color: "#0F3854"
                opacity: 0.8
            }
            Row {
                id: mcBgJobRow
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text {
                    text: mcBgJobPill.unseenResult ? ((mcBgJobPill.mcItem && mcBgJobPill.mcItem.failedCount > 0) ? "⚠" : "✔") : "🗜"
                    font.pixelSize: 10
                    color: "#CBD5E1"
                }
                Text {
                    text: {
                        var it = mcBgJobPill.mcItem
                        if (mcBgJobPill.unseenResult) {
                            var done = it ? it.doneCount : 0
                            return (done > 0 ? ("Compressed " + done + (done === 1 ? " file" : " files")) : "Nothing compressed") + " — view"
                        }
                        var pct = it ? Math.round(it.progress) : 0
                        var cur = it ? (it.currentName || "Compressing…") : "Compressing…"
                        return cur + "  " + pct + "%"
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: "#E2E8F0"
                    elide: Text.ElideMiddle
                    width: Math.min(implicitWidth, statusBar.view.compact ? 190 : 340)
                }
            }
            Springy { hover: mcBgJobMouse.containsMouse; pressed: mcBgJobMouse.pressed }
            MouseArea {
                id: mcBgJobMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (mcBgJobPill.mcItem) mcBgJobPill.mcItem.reopen()
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: mcBgJobPill.runningHidden ? ((mcBgJobPill.mcItem ? mcBgJobPill.mcItem.currentName : "") + "\nClick to show the compression window") : "Click to view results"
            }
        }

        // Result of the last file operation
        Text {
            visible: opacity > 0.01
            opacity: statusBar.view.toastShown ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
            transform: Translate {
                x: statusBar.view.toastShown ? 0 : 14
                Behavior on x { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
            }
            Layout.maximumWidth: statusBar.view.compact ? 200 : 420
            text: (statusBar.view.toastIsError ? "⚠ " : "✔ ") + statusBar.view.toastText
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 10
            font.weight: 600
            color: statusBar.view.toastIsError ? "#F87171" : "#34D399"
            elide: Text.ElideMiddle
        }
        GalleryActionChip {
            visible: statusBar.view.toastShown && statusBar.view.toastCanUndo && !!statusBar.view.tools && statusBar.view.tools.canUndo
            implicitHeight: 20
            icon: "↶"; label: "Undo"
            tip: statusBar.view.tools ? (statusBar.view.tools.undoLabel + " (Ctrl+Z)") : ""
            onTriggered: statusBar.view.undoLast()
        }

        // Storage breakdown of this folder
        Rectangle {
            visible: !!statusBar.view.tools && !statusBar.view.inFavorites
            implicitHeight: 20
            implicitWidth: storRow.implicitWidth + 14
            radius: 10
            Layout.alignment: Qt.AlignVCenter
            color: storMouse.containsMouse ? "#1E293B" : "#141A28"
            border.color: storMouse.containsMouse ? "#38BDF8" : "#2A364E"
            Row {
                id: storRow
                anchors.centerIn: parent
                spacing: 4
                Text { text: "📊"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Storage"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600; color: "#CBD5E1"; anchors.verticalCenter: parent.verticalCenter }
            }
            Springy { hover: storMouse.containsMouse; pressed: storMouse.pressed }
            MouseArea {
                id: storMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: statusBar.view.openStorage()
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "Storage: see which folders and files take up the most space here"
            }
        }

        // Right: Space on current disk
        Row {
            visible: !!statusBar.view.currentDisk
            spacing: 6
            Layout.alignment: Qt.AlignVCenter

            Text { text: "💽"; font.pixelSize: 11 }

            Text {
                visible: !statusBar.view.veryCompact
                text: {
                    if (!statusBar.view.currentDisk) return ""
                    var dName = statusBar.view.currentDisk.name || ""
                    var sLabel = statusBar.view.currentDisk.space_label || (statusBar.view.currentDisk.free_str ? (statusBar.view.currentDisk.free_str + " free") : "")
                    return dName + (sLabel ? ("  " + sLabel) : "")
                }
                font.family: "Segoe UI, monospace"
                font.pixelSize: 10
                font.weight: 600
                color: (statusBar.view.currentDisk && statusBar.view.currentDisk.percent_free < 10) ? "#F87171" : "#38BDF8"
            }

            // Mini disk usage bar
            Rectangle {
                visible: !!statusBar.view.currentDisk && statusBar.view.currentDisk.total_bytes > 0
                width: 44
                height: 6
                radius: 3
                color: "#1E2536"
                anchors.verticalCenter: parent.verticalCenter

                Rectangle {
                    height: parent.height
                    width: Math.min(parent.width, parent.width * Math.max(0.02, 1.0 - ((statusBar.view.currentDisk ? statusBar.view.currentDisk.percent_free : 0) / 100.0)))
                    radius: 3
                    color: (statusBar.view.currentDisk && statusBar.view.currentDisk.percent_free < 10) ? "#EF4444" : ((statusBar.view.currentDisk && statusBar.view.currentDisk.percent_free < 20) ? "#F59E0B" : "#38BDF8")
                }
            }
        }
    }

    // Hover tooltip on the entire status bar (underneath, so buttons keep their own hover)
    MouseArea {
        anchors.fill: parent
        z: -1
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: {
            var tip = "Current Directory:\n" + statusBar.view.currentPath
            tip += "\n• Folders: " + statusBar.view.folderCount
            tip += "\n• Files: " + statusBar.view.fileCount + (statusBar.view.currentFolderFilesSize > 0 ? (" (" + statusBar.view.formatBytes(statusBar.view.currentFolderFilesSize) + ")") : "")
            if (statusBar.view.listingTotal > statusBar.view.rawItems.length) {
                tip += "\n• This folder holds " + statusBar.view.listingTotal + " items; only the first " + statusBar.view.rawItems.length + " are loaded to keep the gallery responsive. Counts and sizes cover the loaded items only."
            }
            if (statusBar.view.currentDisk) {
                tip += "\n• Disk " + statusBar.view.currentDisk.name + ": " + (statusBar.view.currentDisk.free_str || "") + " free of " + (statusBar.view.currentDisk.total_str || "")
            }
            return tip
        }
    }
}
