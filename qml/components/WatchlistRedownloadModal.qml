import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Confirmation warning modal before deleting all existing downloads and re-downloading a Watchlist creator.
Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 100
    focus: visible

    property var bridge: null
    property string targetUserId: ""
    property string targetService: ""
    property string creatorName: ""
    property string targetDir: ""
    property string deleteFoldersSummary: ""
    property int fileCount: -1
    property string sizeText: ""
    property bool useCustomSettings: false
    property string activeFileType: "all"

    signal openSettingsRequested(string uid, string svc)

    function open(uid, svc) {
        if (!root.bridge) return
        var info = root.bridge.requestRedownloadPreview(uid, svc)
        if (!info || !info.ok) return
        root.targetUserId = String(info.userId || uid)
        root.targetService = String(info.service || svc)
        root.creatorName = String(info.creatorName || uid)
        root.targetDir = String(info.targetDir || "")
        root.deleteFoldersSummary = root.targetDir
        root.useCustomSettings = Boolean(info.useCustomSettings)
        root.activeFileType = String(info.fileType || "all")
        root.fileCount = -1
        root.sizeText = ""
        root.visible = true
    }

    function close() {
        root.visible = false
    }

    Keys.onEscapePressed: root.close()

    Connections {
        target: root.bridge
        function onWatchlistRedownloadPreviewReady(uid, svc, cnt, sz, folderSum) {
            if (!root.visible) return
            if (uid === root.targetUserId && svc === root.targetService) {
                root.fileCount = cnt
                root.sizeText = sz
                root.deleteFoldersSummary = folderSum || root.targetDir
            }
        }
    }

    // Backdrop blocker
    Rectangle {
        anchors.fill: parent
        color: "#B804060A"

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.close()
        }
    }

    // Modal card
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(540, parent.width - 40)
        implicitHeight: modalCol.implicitHeight + 44
        height: Math.min(implicitHeight, parent.height - 40)
        radius: 12
        color: "#111520"
        border.color: "#991B1B"
        border.width: 1.5

        MouseArea {
            anchors.fill: parent
            // Eat clicks inside dialog card
        }

        ColumnLayout {
            id: modalCol
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 34
                    height: 34
                    radius: 8
                    color: "#2A1215"
                    border.color: "#B91C1C"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "\u26A0\uFE0F"
                        font.pixelSize: 16
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        Layout.fillWidth: true
                        text: "Delete & Re-download All?"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: 700
                        color: "#F8FAFC"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.creatorName + "  [" + root.targetService.toUpperCase() + "]"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#C4B5FD"
                        elide: Text.ElideRight
                    }
                }
            }

            // Warning alert banner
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: warnText.implicitHeight + 20
                radius: 8
                color: "#241014"
                border.color: "#7F1D1D"
                border.width: 1

                Text {
                    id: warnText
                    anchors.fill: parent
                    anchors.margins: 10
                    text: "This will permanently delete all existing downloaded files and download archive records for this creator first, then re-download their entire catalog using the current Watchlist settings and destination folder."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#FCA5A5"
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                }
            }

            // Details box
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: detailsCol.implicitHeight + 20
                radius: 8
                color: "#0A0D16"
                border.color: "#1E2638"
                border.width: 1

                ColumnLayout {
                    id: detailsCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: "EXISTING FILES TO DELETE:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 700
                            color: "#94A3B8"
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.fileCount < 0
                                  ? "Counting existing files..."
                                  : (root.fileCount === 0
                                     ? "0 local files found (archive history & cutoff will still be cleared)"
                                     : root.fileCount + " file(s) (" + root.sizeText + ")")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 600
                            color: root.fileCount > 0 ? "#F87171" : "#CBD5E1"
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.deleteFoldersSummary
                            font.family: "Consolas, monospace"
                            font.pixelSize: 10
                            color: "#64748B"
                            wrapMode: Text.WrapAnywhere
                            maximumLineCount: 3
                            elide: Text.ElideMiddle
                            visible: root.deleteFoldersSummary.length > 0
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: "#1E2638"
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: "RE-DOWNLOAD DESTINATION & SETTINGS:"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 700
                            color: "#94A3B8"
                        }
                        Text {
                            Layout.fillWidth: true
                            text: root.targetDir
                            font.family: "Consolas, monospace"
                            font.pixelSize: 11
                            color: "#38BDF8"
                            wrapMode: Text.WrapAnywhere
                        }
                        Text {
                            Layout.fillWidth: true
                            text: (root.useCustomSettings ? "Using Creator's Custom Settings" : "Using Global Watchlist Settings")
                                  + "  •  Files: " + root.activeFileType
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: root.useCustomSettings ? "#A78BFA" : "#94A3B8"
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }

            // Action buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    text: "Edit Settings"
                    iconText: "\u2699"
                    variant: "outline"
                    implicitHeight: 36
                    onClicked: {
                        var uid = root.targetUserId
                        var svc = root.targetService
                        root.close()
                        root.openSettingsRequested(uid, svc)
                    }
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: "Cancel"
                    variant: "outline"
                    implicitHeight: 36
                    onClicked: root.close()
                }

                StyledButton {
                    id: confirmRedownloadBtn
                    objectName: "confirmRedownloadBtn"
                    text: "Delete All & Re-download"
                    variant: "danger"
                    implicitHeight: 36
                    onClicked: {
                        if (root.bridge) {
                            root.bridge.redownloadWatchlistEntry(root.targetUserId, root.targetService, true)
                        }
                        root.close()
                    }
                }
            }
        }
    }
}
