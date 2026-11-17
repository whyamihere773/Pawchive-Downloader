import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Prompt shown when settings change while a download batch is active or queued.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string scope: "global" // "global" | "creator"
    property string targetUserId: ""
    property string targetService: ""
    property string scopeLabel: ""
    property string diffSummary: ""
    property bool requiresScan: false
    property bool confirmRedownload: false

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    function openWithPayload(scopeArg, payload) {
        var p = payload || {}
        root.scope = String(p.scope || scopeArg || "global")
        root.targetUserId = String(p.targetUserId || "")
        root.targetService = String(p.targetService || "")
        root.scopeLabel = String(p.scopeLabel || (root.scope === "creator" ? "Watchlist creator" : "Active download queue"))
        root.diffSummary = String(p.summary || "Download settings updated.")
        root.requiresScan = Boolean(p.requiresScan)
        root.confirmRedownload = false
        root.isOpen = true
    }

    function close() {
        root.confirmRedownload = false
        root.isOpen = false
    }

    anchors.fill: parent
    z: 9998
    visible: isOpen
    focus: isOpen

    Keys.onEscapePressed: {
        if (root.confirmRedownload) {
            root.confirmRedownload = false
        } else {
            root.close()
        }
    }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B0060910"
        opacity: root.isOpen ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                if (!root.confirmRedownload) root.close()
            }
        }
    }

    // Modal Card
    Rectangle {
        id: card
        width: Math.min(600, parent.width - 40)
        implicitHeight: Math.min(cardCol.implicitHeight + 44, parent.height - 40)
        anchors.centerIn: parent
        radius: 14
        color: "#131722"
        border.color: root.confirmRedownload ? "#EF4444" : "#2D3748"
        border.width: 1.5

        MouseArea {
            anchors.fill: parent
        }

        ColumnLayout {
            id: cardCol
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                topMargin: 22
                leftMargin: 22
                rightMargin: 22
            }
            spacing: 14

            // Header Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    width: 42
                    height: 42
                    radius: 21
                    color: "#1E293B"
                    border.color: root.confirmRedownload ? "#EF4444" : "#38BDF8"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: root.confirmRedownload ? "⚠️" : "⚙️"
                        font.pixelSize: 20
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: root.confirmRedownload
                            ? root.tr("title_confirm_redownload_mid", "Confirm Delete & Re-download")
                            : root.tr("title_mid_download_settings", "Active Download Settings Changed")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 16
                        font.bold: true
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: root.scopeLabel
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        color: "#94A3B8"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                StyledButton {
                    text: "✕"
                    variant: "ghost"
                    implicitWidth: 32
                    implicitHeight: 32
                    onClicked: root.close()
                }
            }

            // Diff Summary Container
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.min(diffText.implicitHeight + 20, 140)
                radius: 8
                color: "#0B0E17"
                border.color: "#1E2638"
                border.width: 1

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 10
                    clip: true

                    Text {
                        id: diffText
                        width: parent.width
                        text: root.diffSummary
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        color: "#CBD5E1"
                        wrapMode: Text.WordWrap
                        lineHeight: 1.35
                    }
                }
            }

            // Tier 4 API Re-scan Notice
            Rectangle {
                visible: root.requiresScan && !root.confirmRedownload
                Layout.fillWidth: true
                implicitHeight: scanNoticeRow.implicitHeight + 16
                radius: 8
                color: "#221B0D"
                border.color: "#D97706"
                border.width: 1

                RowLayout {
                    id: scanNoticeRow
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8

                    Text {
                        text: "🔎"
                        font.pixelSize: 14
                        Layout.alignment: Qt.AlignTop
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.tr("msg_mid_settings_rescan_warn", "Some changed options (such as DMs, comments, favorite filters, or page range) require fetching additional metadata before rebuilding pending items.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#FDE68A"
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // Explanation / Warning section
            Rectangle {
                visible: root.confirmRedownload
                Layout.fillWidth: true
                implicitHeight: redownloadWarnCol.implicitHeight + 18
                radius: 8
                color: "#261016"
                border.color: "#EF4444"
                border.width: 1

                ColumnLayout {
                    id: redownloadWarnCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    Text {
                        Layout.fillWidth: true
                        text: root.tr("msg_mid_redownload_warning_title", "Permanent Deletion Warning")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.bold: true
                        color: "#FCA5A5"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.tr("msg_mid_redownload_warning_desc", "Continuing will cancel active/queued tasks for this scope, permanently DELETE downloaded files and folders on disk for the affected creator(s) along with their download archive history, and re-download everything from scratch with the new settings.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#FECACA"
                        wrapMode: Text.WordWrap
                        lineHeight: 1.35
                    }
                }
            }

            Text {
                visible: !root.confirmRedownload
                Layout.fillWidth: true
                text: root.tr("msg_mid_settings_hint", "Files already finished during this session are kept if you continue; matching .part resume files will be migrated to the new folder/filename layout.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E2638"
            }

            // Primary choice actions
            ColumnLayout {
                visible: !root.confirmRedownload
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    id: midSettingsContinueBtn
                    objectName: "midSettingsContinueBtn"
                    Layout.fillWidth: true
                    implicitHeight: 40
                    text: root.tr("btn_continue_new_settings", "Continue with New Settings")
                    iconText: "▶"
                    variant: "primary"
                    onClicked: {
                        var s = root.scope
                        var uid = root.targetUserId
                        var svc = root.targetService
                        root.close()
                        if (root.bridge) {
                            root.bridge.applyMidDownloadSettings("continue", s, uid, svc)
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    StyledButton {
                        id: midSettingsRedownloadBtn
                        objectName: "midSettingsRedownloadBtn"
                        Layout.fillWidth: true
                        implicitHeight: 38
                        text: root.tr("btn_delete_old_redownload", "Delete Old & Re-download All...")
                        iconText: "🗑"
                        variant: "danger"
                        onClicked: root.confirmRedownload = true
                    }

                    StyledButton {
                        id: midSettingsFutureOnlyBtn
                        objectName: "midSettingsFutureOnlyBtn"
                        Layout.fillWidth: true
                        implicitHeight: 38
                        text: root.tr("btn_keep_running_future_only", "Keep Running (Future Only)")
                        variant: "outline"
                        onClicked: {
                            var s = root.scope
                            var uid = root.targetUserId
                            var svc = root.targetService
                            root.close()
                            if (root.bridge) {
                                root.bridge.applyMidDownloadSettings("future_only", s, uid, svc)
                            }
                        }
                    }
                }
            }

            // Confirm destructive re-download actions
            RowLayout {
                visible: root.confirmRedownload
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    Layout.fillWidth: true
                    implicitHeight: 38
                    text: root.tr("btn_back", "Back")
                    variant: "outline"
                    onClicked: root.confirmRedownload = false
                }

                StyledButton {
                    id: midSettingsConfirmRedownloadBtn
                    objectName: "midSettingsConfirmRedownloadBtn"
                    Layout.fillWidth: true
                    implicitHeight: 38
                    text: root.tr("btn_confirm_delete_redownload", "Delete Old Files & Re-download")
                    iconText: "🗑"
                    variant: "danger"
                    onClicked: {
                        var s = root.scope
                        var uid = root.targetUserId
                        var svc = root.targetService
                        root.close()
                        if (root.bridge) {
                            root.bridge.applyMidDownloadSettings("redownload", s, uid, svc)
                        }
                    }
                }
            }
        }
    }
}
