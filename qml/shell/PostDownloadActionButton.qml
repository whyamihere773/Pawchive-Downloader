import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── When Done (Post-Download Action) Selector ───────────────
Rectangle {
    id: postActionBtn
    required property var window
    property string currentAction: appBridge ? appBridge.postDownloadAction : "none"

    function getActionLabel(act) {
        if (act === "close_app") return postActionBtn.window.tr("post_action_close", "Close App")
        if (act === "sleep") return postActionBtn.window.tr("post_action_sleep_short", "Sleep")
        if (act === "hibernate") return postActionBtn.window.tr("post_action_hibernate_short", "Hibernate (-F)")
        if (act === "shutdown") return postActionBtn.window.tr("post_action_shutdown_short", "Shut Down (-F)")
        if (act === "restart") return postActionBtn.window.tr("post_action_restart_short", "Restart (-F)")
        return postActionBtn.window.tr("post_action_none_short", "Do Nothing")
    }

    function getOptionLabel(actId) {
        if (actId === "close_app") return postActionBtn.window.tr("post_action_close", "Close App")
        if (actId === "sleep") return postActionBtn.window.tr("post_action_sleep", "Sleep System")
        if (actId === "hibernate") return postActionBtn.window.tr("post_action_hibernate", "Hibernate (-F Force)")
        if (actId === "shutdown") return postActionBtn.window.tr("post_action_shutdown", "Shut Down (-F Force)")
        if (actId === "restart") return postActionBtn.window.tr("post_action_restart", "Restart (-F Force)")
        return postActionBtn.window.tr("post_action_none", "Do Nothing (Default)")
    }

    function getOptionDesc(actId) {
        if (actId === "close_app") return postActionBtn.window.tr("post_action_close_desc", "Exit Pawchive Downloader")
        if (actId === "sleep") return postActionBtn.window.tr("post_action_sleep_desc", "Suspend / sleep computer")
        if (actId === "hibernate") return postActionBtn.window.tr("post_action_hibernate_desc", "Force save to disk and power down")
        if (actId === "shutdown") return postActionBtn.window.tr("post_action_shutdown_desc", "Force close apps & turn off (10s buffer)")
        if (actId === "restart") return postActionBtn.window.tr("post_action_restart_desc", "Force close apps & reboot computer")
        return postActionBtn.window.tr("post_action_none_desc", "Keep app & system running")
    }

    function getActionIcon(act) {
        if (act === "close_app") return "🚪"
        if (act === "sleep") return "🌙"
        if (act === "hibernate") return "💤"
        if (act === "shutdown") return "🔌"
        if (act === "restart") return "🔄"
        return "⏸️"
    }

    function getActionColor(act) {
        if (act === "close_app") return "#38BDF8"
        if (act === "sleep") return "#A78BFA"
        if (act === "hibernate") return "#818CF8"
        if (act === "shutdown") return "#F43F5E"
        if (act === "restart") return "#F59E0B"
        return "#64748B"
    }

    function getActionBorderColor(act) {
        if (act === "close_app") return "#0284C7"
        if (act === "sleep") return "#7C3AED"
        if (act === "hibernate") return "#4F46E5"
        if (act === "shutdown") return "#E11D48"
        if (act === "restart") return "#D97706"
        return "#2E3A56"
    }

    function getActionBg(act, hovered) {
        if (act === "close_app") return hovered ? "#0E2A3E" : "#0A1D2B"
        if (act === "sleep") return hovered ? "#241E3A" : "#191528"
        if (act === "hibernate") return hovered ? "#22203A" : "#171628"
        if (act === "shutdown") return hovered ? "#361014" : "#260B0E"
        if (act === "restart") return hovered ? "#35220A" : "#241707"
        return hovered ? "#181B28" : "#111420"
    }

    Layout.preferredWidth: postActionRow.implicitWidth + 24
    Layout.preferredHeight: 34
    radius: 7
    color: getActionBg(currentAction, postActionMouse.containsMouse)
    border.color: getActionBorderColor(currentAction)
    border.width: currentAction !== "none" ? 1.5 : 1

    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }

    Row {
        id: postActionRow
        anchors.centerIn: parent
        spacing: 6

        Text {
            text: postActionBtn.getActionIcon(postActionBtn.currentAction)
            font.pixelSize: 11
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: postActionBtn.window.tr("action_when_done", "When Done: %1").replace("%1", postActionBtn.getActionLabel(postActionBtn.currentAction))
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            font.weight: postActionBtn.currentAction !== "none" ? 600 : Font.Normal
            color: postActionBtn.getActionColor(postActionBtn.currentAction)
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: postActionPopup.opened ? "▴" : "▾"
            font.pixelSize: 10
            color: postActionBtn.getActionColor(postActionBtn.currentAction)
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: postActionMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        ToolTip.visible: containsMouse && !postActionPopup.opened
        ToolTip.delay: 300
        ToolTip.text: postActionBtn.window.tr("tip_when_done", "Choose what action to execute when downloads finish (resets to 'Do Nothing' after execution)")
        onClicked: {
            if (postActionPopup.opened) {
                postActionPopup.close()
            } else {
                postActionPopup.open()
            }
        }
    }

    // Dropdown Menu for selecting post-download action (opens downwards)
    Popup {
        id: postActionPopup
        y: postActionBtn.height + 6
        x: 0
        width: 256
        padding: 8
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#111420"
            border.color: "#2E3A56"
            border.width: 1
            radius: 8
        }

        contentItem: ColumnLayout {
            spacing: 4

            Text {
                text: postActionBtn.window.tr("post_action_header", "ACTION WHEN COMPLETED")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: Font.Bold
                color: "#64748B"
                Layout.leftMargin: 6
                Layout.topMargin: 2
                Layout.bottomMargin: 2
            }

            ListModel {
                id: postActionOptionsModel
                ListElement { actionId: "none"; actionIcon: "⏸️"; actionColor: "#94A3B8" }
                ListElement { actionId: "close_app"; actionIcon: "🚪"; actionColor: "#38BDF8" }
                ListElement { actionId: "sleep"; actionIcon: "🌙"; actionColor: "#A78BFA" }
                ListElement { actionId: "hibernate"; actionIcon: "💤"; actionColor: "#818CF8" }
                ListElement { actionId: "shutdown"; actionIcon: "🔌"; actionColor: "#F43F5E" }
                ListElement { actionId: "restart"; actionIcon: "🔄"; actionColor: "#F59E0B" }
            }

            Repeater {
                model: postActionOptionsModel
                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: 6
                    property bool isCurrent: (appBridge ? appBridge.postDownloadAction : "none") === model.actionId
                    color: optMouse.containsMouse ? "#1E2436" : (isCurrent ? "#161B2E" : "transparent")
                    border.color: isCurrent ? model.actionColor : "transparent"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 8

                        Text {
                            text: model.actionIcon
                            font.pixelSize: 13
                            Layout.alignment: Qt.AlignVCenter
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                text: postActionBtn.getOptionLabel(model.actionId)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: isCurrent ? 600 : Font.Normal
                                color: isCurrent ? model.actionColor : "#E2E8F0"
                            }
                            Text {
                                text: postActionBtn.getOptionDesc(model.actionId)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 9
                                color: "#64748B"
                            }
                        }

                        Text {
                            text: "✔"
                            font.pixelSize: 11
                            color: model.actionColor
                            visible: isCurrent
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }

                    MouseArea {
                        id: optMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (appBridge) {
                                appBridge.postDownloadAction = model.actionId
                            }
                            postActionPopup.close()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E293B"
                Layout.topMargin: 2
                Layout.bottomMargin: 2
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 6
                Layout.rightMargin: 6
                Layout.bottomMargin: 2
                spacing: 4
                Text {
                    text: "ℹ️"
                    font.pixelSize: 10
                }
                Text {
                    text: postActionBtn.window.tr("post_action_footer", "Automatically resets to 'Do Nothing' after each task.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 9
                    color: "#64748B"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
