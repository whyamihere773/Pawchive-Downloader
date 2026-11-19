import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Right-click context menu popup for ConsoleLogView rows.
Popup {
    id: logContextMenu

    required property var consoleView
    property int totalCount: 0
    signal copyTextRequested(string textToCopy, string toastMsg)
    signal filterCategoryRequested(string category)

    width: 256
    padding: 6
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    transformOrigin: Popup.TopLeft

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 120; easing.type: Easing.OutCubic }
        NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 120; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 90; easing.type: Easing.InCubic }
        NumberAnimation { property: "scale"; from: 1.0; to: 0.96; duration: 90; easing.type: Easing.InCubic }
    }

    background: Rectangle {
        color: "#0B0F19"
        border.color: "#232E42"
        border.width: 1.2
        radius: 9

        // Top accent indicator
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            radius: 1
            color: consoleView.contextRowLevel === "ERROR" ? "#EF4444" : (consoleView.contextRowLevel === "WARNING" ? "#F59E0B" : "#38BDF8")
            opacity: 0.7
        }
    }

    contentItem: ColumnLayout {
        spacing: 2

        // Component for modern context menu items
        component ContextMenuItem: Rectangle {
            id: cItem
            Layout.fillWidth: true
            height: 29
            radius: 5

            property string icon: ""
            property string label: ""
            property string shortcut: ""
            property bool danger: false
            property bool active: true
            signal clicked()

            opacity: active ? 1.0 : 0.45
            color: !active ? "transparent" : (cMouse.containsMouse ? (danger ? "#2E151E" : "#162236") : "transparent")
            border.color: !active ? "transparent" : (cMouse.containsMouse ? (danger ? "#7F1D1D" : "#253B5E") : "transparent")
            border.width: 1

            Behavior on color { ColorAnimation { duration: 80 } }
            Behavior on border.color { ColorAnimation { duration: 80 } }

            // Hover indicator bar on left
            Rectangle {
                width: 3
                height: 16
                radius: 1.5
                color: cItem.danger ? "#EF4444" : "#38BDF8"
                anchors.left: parent.left
                anchors.leftMargin: 2
                anchors.verticalCenter: parent.verticalCenter
                visible: cMouse.containsMouse && cItem.active
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 9
                anchors.rightMargin: 8
                spacing: 7

                Text {
                    text: cItem.icon
                    font.pixelSize: 12
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: cItem.label
                    color: cItem.danger ? (cMouse.containsMouse ? "#FCA5A5" : "#F87171") : (cMouse.containsMouse ? "#FFFFFF" : "#E2E8F0")
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    font.family: "Segoe UI, Inter, sans-serif"
                    Layout.alignment: Qt.AlignVCenter
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                Rectangle {
                    visible: !!cItem.shortcut
                    height: 18
                    width: scTxt.implicitWidth + 10
                    radius: 4
                    color: cMouse.containsMouse ? "#1A2234" : "#121824"
                    border.color: cMouse.containsMouse ? "#2C3B56" : "#1F293D"
                    border.width: 1
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        id: scTxt
                        anchors.centerIn: parent
                        text: cItem.shortcut
                        color: cMouse.containsMouse ? "#38BDF8" : "#64748B"
                        font.pixelSize: 9
                        font.family: "Cascadia Code, Consolas, monospace"
                    }
                }
            }

            MouseArea {
                id: cMouse
                anchors.fill: parent
                hoverEnabled: cItem.active
                cursorShape: cItem.active ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    if (cItem.active) {
                        logContextMenu.close()
                        cItem.clicked()
                    }
                }
            }
        }

        // Header Banner with selection badge
        Rectangle {
            Layout.fillWidth: true
            height: 26
            color: "#111726"
            radius: 6
            border.color: "#1A2436"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Row {
                    spacing: 6
                    Layout.alignment: Qt.AlignVCenter
                    Text {
                        text: consoleView.selectedCount > 1 ? "📋" : (consoleView.selectedCount === 1 ? "📄" : "💻")
                        font.pixelSize: 11
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: {
                            if (consoleView.selectedCount > 1) return consoleView.tr("menu_hdr_multi", "Multi-Row Selection")
                            if (consoleView.selectedCount === 1 && consoleView.contextRowLevel) return "Log Entry  ·  " + consoleView.contextRowLevel
                            if (consoleView.selectedCount === 1) return consoleView.tr("menu_hdr_single", "Selected Log Entry")
                            return consoleView.tr("menu_hdr_console", "Console Output")
                        }
                        color: consoleView.contextRowLevel === "ERROR" ? "#F87171" : (consoleView.contextRowLevel === "WARNING" ? "#FBBF24" : "#38BDF8")
                        font.pixelSize: 10
                        font.weight: Font.DemiBold
                        font.family: "Segoe UI, Inter, sans-serif"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    height: 16
                    width: badgeTxt.implicitWidth + 10
                    radius: 8
                    color: "#172338"
                    border.color: "#253B5E"
                    border.width: 1
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        id: badgeTxt
                        anchors.centerIn: parent
                        text: consoleView.selectedCount > 0 ? (consoleView.selectedCount + " " + consoleView.tr("lbl_selected", "selected")) : (logContextMenu.totalCount + " " + consoleView.tr("lbl_total", "total"))
                        color: "#38BDF8"
                        font.pixelSize: 9
                        font.weight: Font.Bold
                        font.family: "Segoe UI, sans-serif"
                    }
                }
            }
        }

        Item { height: 2 }

        // 1. Copy Selected / Copy All
        ContextMenuItem {
            icon: "📋"
            label: consoleView.selectedCount > 0 ? (consoleView.selectedCount > 1 ? consoleView.tr("menu_copy_selected_plural", "Copy %1 Selected Rows").replace("%1", consoleView.selectedCount) : consoleView.tr("menu_copy_selected_one", "Copy Selected Row")) : consoleView.tr("menu_copy_all", "Copy All Logs")
            shortcut: "Ctrl+C"
            onClicked: consoleView.copySelectedLogs()
        }

        // 2. Copy Message Text Only (when 1 row selected)
        ContextMenuItem {
            visible: consoleView.selectedCount === 1
            icon: "💬"
            label: consoleView.tr("menu_copy_message_only", "Copy Message Only")
            shortcut: "Shift+C"
            onClicked: consoleView.copyMessageOnly()
        }

        // 3. Copy All Visible Logs (when multi-row selection active)
        ContextMenuItem {
            visible: consoleView.selectedCount > 0
            icon: "📑"
            label: consoleView.tr("menu_copy_all_logs", "Copy All Logs") + " (" + logContextMenu.totalCount + ")"
            shortcut: "Ctrl+Shift+C"
            onClicked: consoleView.copyAllLogs()
        }

        // Divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#182030"
            Layout.topMargin: 2
            Layout.bottomMargin: 2
        }

        // 4. Select All Rows
        ContextMenuItem {
            icon: "☑️"
            label: consoleView.tr("menu_select_all", "Select All Rows")
            shortcut: "Ctrl+A"
            onClicked: consoleView.selectAllRows()
        }

        // 5. Clear Selection
        ContextMenuItem {
            icon: "✖"
            label: consoleView.tr("menu_clear_selection", "Clear Selection")
            shortcut: "Esc"
            active: consoleView.selectedCount > 0
            onClicked: consoleView.clearSelection()
        }

        // Divider
        Rectangle {
            visible: (!!consoleView.contextRowCategory && consoleView.contextRowCategory !== "general") || true
            Layout.fillWidth: true
            height: 1
            color: "#182030"
            Layout.topMargin: 2
            Layout.bottomMargin: 2
        }

        // 6. Filter by category
        ContextMenuItem {
            visible: !!consoleView.contextRowCategory && consoleView.contextRowCategory !== "general"
            icon: "🔍"
            label: consoleView.tr("menu_filter_category", "Filter by '[cat]'").replace("[cat]", consoleView.contextRowCategory)
            onClicked: logContextMenu.filterCategoryRequested(consoleView.contextRowCategory)
        }

        // 7. Export Logs to File
        ContextMenuItem {
            icon: "💾"
            label: consoleView.tr("menu_export_logs", "Export Logs to File...")
            onClicked: consoleView.exportLogsRequested()
        }

        // 8. Clear Console Logs
        ContextMenuItem {
            icon: "↻"
            danger: true
            label: consoleView.tr("menu_clear_console", "Clear Console Output")
            onClicked: {
                consoleView.clearSelection()
                consoleView.clearLogsRequested()
            }
        }
    }
}

