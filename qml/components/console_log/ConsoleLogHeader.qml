import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Progress Log header toolbar (level pills, cloud/export/status-only/copy/reset actions).
RowLayout {
    id: headerRow

    required property var consoleView
    Layout.fillWidth: true
    spacing: consoleView.isVeryNarrow ? 4 : (consoleView.isCompact ? 6 : 8)

    // Title & Icon
    Row {
        spacing: consoleView.isVeryNarrow ? 0 : 6
        Layout.alignment: Qt.AlignVCenter
        Text {
            text: "💻"
            font.pixelSize: 13
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: consoleView.tr("title_progress_log", "Progress Log")
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 12
            font.weight: 600
            color: "#F1F5F9"
            visible: !consoleView.isVeryNarrow
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    Item { Layout.fillWidth: true }

    // Level filters (Highlights active level)
    Row {
        spacing: consoleView.isVeryNarrow ? 2 : 4
        Layout.alignment: Qt.AlignVCenter
        Repeater {
            model: ["ALL", "INFO", "WARN", "ERR"]
            delegate: Rectangle {
                id: filterPill
                implicitHeight: 22
                implicitWidth: consoleView.isVeryNarrow ? 28 : Math.max(42, filterText.implicitWidth + 14)
                width: implicitWidth
                height: 22
                radius: 4
                property bool selected: consoleView.activeLevel === modelData

                color: selected ? "#38BDF8" : (mArea.containsMouse ? "#2A303F" : "#1A1E29")
                border.color: selected ? "#38BDF8" : "#2E3547"
                border.width: 1

                Behavior on implicitWidth { NumberAnimation { duration: 120 } }
                Behavior on color { ColorAnimation { duration: 100 } }
                Behavior on border.color { ColorAnimation { duration: 100 } }

                Text {
                    id: filterText
                    anchors.centerIn: parent
                    text: consoleView.isVeryNarrow && modelData === "INFO" ? "INF" : (consoleView.isVeryNarrow && modelData === "WARN" ? "WRN" : modelData)
                    font.pixelSize: consoleView.isVeryNarrow ? 8 : 9
                    font.weight: Font.Bold
                    color: selected ? "#0F172A" : "#94A3B8"
                }

                MouseArea {
                    id: mArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: modelData === "ALL" ? consoleView.tr("tip_log_all", "Show all log messages") : (modelData === "INFO" ? consoleView.tr("tip_log_info", "Filter by Info level") : (modelData === "WARN" ? consoleView.tr("tip_log_warn", "Filter by Warnings") : consoleView.tr("tip_log_err", "Filter by Errors")))
                    onClicked: {
                        consoleView.activeLevel = modelData
                        var lvl = modelData === "WARN" ? "WARNING" : (modelData === "ERR" ? "ERROR" : modelData)
                        if (consoleView.logModel) consoleView.logModel.setFilterLevel(lvl)
                    }
                }
            }
        }
    }

    // Download links button (Cloud Download)
    Rectangle {
        id: dlBtn
        implicitHeight: 24
        implicitWidth: consoleView.isCompact ? 28 : Math.max(120, dlText.implicitWidth + 38)
        Layout.preferredHeight: 24
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: implicitWidth
        radius: 5
        clip: true
        color: dlLinkMouse.containsMouse ? "#113832" : "#0A2521"
        border.color: "#2DD4BF"
        border.width: 1
        Layout.alignment: Qt.AlignVCenter

        Behavior on implicitWidth { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 5
            Text { text: "☁️"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: dlText
                text: consoleView.tr("btn_download_links", "Download Links")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 10
                color: "#2DD4BF"
                font.weight: 600
                visible: !consoleView.isCompact
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: dlLinkMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: consoleView.tr("tip_download_links", "Open dialog to download harvested links via Mega.nz, Google Drive, Dropbox, or GoFile")
            onClicked: consoleView.downloadLinksRequested()
        }
    }

    // Export links button
    Rectangle {
        id: exBtn
        implicitHeight: 24
        implicitWidth: consoleView.isCompact ? 28 : Math.max(106, exText.implicitWidth + 38)
        Layout.preferredHeight: 24
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: implicitWidth
        radius: 5
        clip: true
        color: exLinkMouse.containsMouse ? "#1E2D2A" : "#13211E"
        border.color: "#10B981"
        border.width: 1
        Layout.alignment: Qt.AlignVCenter

        Behavior on implicitWidth { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 5
            Text { text: "🔗"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: exText
                text: consoleView.tr("btn_export_links", "Export Links")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 10
                color: "#34D399"
                font.weight: Font.Medium
                visible: !consoleView.isCompact
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: exLinkMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: consoleView.tr("tip_export_links", "Extract and export all external cloud links to a text file")
            onClicked: consoleView.exportLinksRequested()
        }
    }

    // Eye Button: Status / Summary mode toggle (Filters out individual file names)
    Rectangle {
        implicitHeight: 24
        implicitWidth: 28
        Layout.preferredHeight: 24
        Layout.preferredWidth: 28
        Layout.minimumWidth: 28
        radius: 5
        color: consoleView.statusOnlyMode ? "#1E2A3A" : (eyeMouse.containsMouse ? "#222734" : "#1A1E29")
        border.color: consoleView.statusOnlyMode ? "#38BDF8" : "#2E3547"
        border.width: 1
        Layout.alignment: Qt.AlignVCenter

        Behavior on color { ColorAnimation { duration: 100 } }
        Behavior on border.color { ColorAnimation { duration: 100 } }

        Text {
            anchors.centerIn: parent
            text: consoleView.statusOnlyMode ? "🙈" : "👁"
            font.pixelSize: 12
            color: consoleView.statusOnlyMode ? "#38BDF8" : "#64748B"
        }

        MouseArea {
            id: eyeMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: consoleView.statusOnlyMode ? consoleView.tr("tip_status_only_active", "Status-Only mode active (click to show all file details)") : consoleView.tr("tip_status_only", "Click to hide individual file names and show status only")
            onClicked: {
                consoleView.statusOnlyMode = !consoleView.statusOnlyMode
                if (consoleView.logModel) consoleView.logModel.setStatusOnly(consoleView.statusOnlyMode)
            }
        }
    }

    // Copy Logs button (Copies selected rows, or all visible logs if none selected)
    Rectangle {
        id: copyBtn
        implicitHeight: 24
        implicitWidth: consoleView.isCompact ? 28 : (consoleView.selectedCount > 0 ? Math.max(90, copyText.implicitWidth + 36) : Math.max(80, copyText.implicitWidth + 36))
        Layout.preferredHeight: 24
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: implicitWidth
        radius: 5
        clip: true
        color: copyMouse.containsMouse ? "#1E3A5F" : (consoleView.selectedCount > 0 ? "#172A45" : "#131C2E")
        border.color: consoleView.selectedCount > 0 ? "#38BDF8" : "#2563EB"
        border.width: 1
        Layout.alignment: Qt.AlignVCenter

        Behavior on implicitWidth { NumberAnimation { duration: 120 } }
        Behavior on color { ColorAnimation { duration: 100 } }
        Behavior on border.color { ColorAnimation { duration: 100 } }

        Row {
            anchors.centerIn: parent
            spacing: 4
            Text { text: "📋"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: copyText
                text: consoleView.selectedCount > 0 ? consoleView.tr("btn_copy_selected", "Copy (%1)").replace("%1", consoleView.selectedCount) : consoleView.tr("btn_copy_all", "Copy All")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 10
                color: "#38BDF8"
                font.weight: 600
                visible: !consoleView.isCompact
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: copyMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: consoleView.selectedCount > 0 ? consoleView.tr("tip_copy_selected", "Copy %1 selected log row(s) to clipboard (Ctrl+C)").replace("%1", consoleView.selectedCount) : consoleView.tr("tip_copy_all", "Copy all visible console logs to clipboard (Ctrl+C)")
            onClicked: consoleView.copySelectedLogs()
        }
    }

    // Reset/Clear button
    Rectangle {
        id: resetBtn
        implicitHeight: 24
        implicitWidth: consoleView.isCompact ? 28 : Math.max(70, resetText.implicitWidth + 32)
        Layout.preferredHeight: 24
        Layout.preferredWidth: implicitWidth
        Layout.minimumWidth: implicitWidth
        radius: 5
        clip: true
        color: resetMouse.containsMouse ? "#2C1D24" : "#1F161C"
        border.color: "#EF4444"
        border.width: 1
        Layout.alignment: Qt.AlignVCenter

        Behavior on implicitWidth { NumberAnimation { duration: 120 } }

        Row {
            anchors.centerIn: parent
            spacing: 4
            Text { text: "↻"; font.pixelSize: 11; color: "#F87171"; anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: resetText
                text: consoleView.tr("btn_reset", "Reset")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 10
                color: "#F87171"
                font.weight: Font.Medium
                visible: !consoleView.isCompact
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        MouseArea {
            id: resetMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            ToolTip.visible: containsMouse
            ToolTip.delay: 300
            ToolTip.text: consoleView.tr("tip_reset_logs", "Clear all progress console logs")
            onClicked: {
                consoleView.clearSelection()
                consoleView.clearLogsRequested()
            }
        }
    }
}

