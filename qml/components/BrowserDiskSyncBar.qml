import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// ── BrowserDiskSyncBar: Newtonian-animated Disk Sync Mode Selector & Homogeneous Auto-Reuse Card ──
Rectangle {
    id: syncBar
    objectName: "browserDiskSyncBar"

    property string diskSyncMode: "all"       // "all" | "missing_or_mismatched" | "missing_only" | "mismatched_only"
    property string homogeneousSummary: ""
    property int onDiskCreatorCount: 0
    property int totalCreatorCount: 0
    signal modeSelected(string newMode)

    readonly property bool isSyncActive: diskSyncMode !== "all"

    Layout.fillWidth: true
    implicitHeight: barCol.implicitHeight + 22
    radius: 9
    color: isSyncActive ? "#0B1B18" : "#121726"
    border.color: isSyncActive ? "#10B981" : "#1E293B"
    border.width: 1

    Behavior on implicitHeight {
        SpringAnimation { spring: 4.2; damping: 0.36; mass: 0.9 }
    }
    Behavior on color { ColorAnimation { duration: 150 } }
    Behavior on border.color { ColorAnimation { duration: 150 } }

    ColumnLayout {
        id: barCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 11
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "DOWNLOAD SCOPE"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Bold
                color: syncBar.isSyncActive ? "#34D399" : "#38BDF8"
            }

            Rectangle {
                visible: syncBar.isSyncActive
                height: 18
                width: homoBadgeTxt.implicitWidth + 12
                radius: 9
                color: "#064E3B"
                border.color: "#10B981"
                border.width: 1
                scale: syncBar.isSyncActive ? 1.0 : 0.85
                Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.32 } }

                Text {
                    id: homoBadgeTxt
                    anchors.centerIn: parent
                    text: "✓ Auto-Reuses Path & Settings"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 9
                    font.bold: true
                    color: "#6EE7B7"
                }
            }

            Item { Layout.fillWidth: true }
        }

        // 4-Option Segmented Pill Row
        Flow {
            id: modePillsFlow
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: [
                    { key: "all",                   icon: "📥", label: "All Posts",            tip: "Download all posts matching your active Downloader settings" },
                    { key: "missing_or_mismatched", icon: "🔄", label: "Missing & Mismatched", tip: "Download only posts not on disk or with missing/mismatched files — automatically reuses the creator's existing folder & layout" },
                    { key: "missing_only",          icon: "🆕", label: "Not on Disk Only",     tip: "Download only posts completely absent from disk — automatically reuses the creator's existing folder & layout" },
                    { key: "mismatched_only",       icon: "🛠️", label: "Mismatched Only",      tip: "Repair only existing on-disk posts whose file count or file sizes don't match online — automatically reuses existing folder & layout" }
                ]

                delegate: Rectangle {
                    readonly property bool active: syncBar.diskSyncMode === modelData.key
                    readonly property bool isSyncPill: modelData.key !== "all"
                    objectName: "diskSyncPill_" + modelData.key
                    height: 30
                    width: pillRow.implicitWidth + 18
                    radius: 7
                    color: active
                           ? (isSyncPill ? "#065F46" : "#182235")
                           : (pillMouse.containsMouse ? "#172033" : "#0B0F19")
                    border.color: active
                                  ? (isSyncPill ? "#34D399" : "#38BDF8")
                                  : (pillMouse.containsMouse ? "#334155" : "#1E293B")
                    border.width: active ? 1.5 : 1

                    Springy { hover: pillMouse.containsMouse; pressed: pillMouse.pressed }

                    Row {
                        id: pillRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: modelData.icon
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: modelData.label
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: active ? Font.Bold : Font.Medium
                            color: active ? "#F8FAFC" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: pillMouse
                        objectName: "diskSyncPillMouse_" + modelData.key
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: modelData.tip
                        onClicked: {
                            if (syncBar.diskSyncMode !== modelData.key) {
                                syncBar.modeSelected(modelData.key)
                            }
                        }
                    }
                }
            }
        }

        // Expandable Homogeneous Explanation Strip
        Rectangle {
            id: homoExplainBox
            Layout.fillWidth: true
            Layout.preferredHeight: syncBar.isSyncActive ? (homoCol.implicitHeight + 14) : 0
            visible: opacity > 0.01
            opacity: syncBar.isSyncActive ? 1.0 : 0.0
            clip: true
            radius: 7
            color: "#071311"
            border.color: "#0F5132"
            border.width: 1

            Behavior on Layout.preferredHeight {
                SpringAnimation { spring: 4.2; damping: 0.36; mass: 0.85 }
            }
            Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

            ColumnLayout {
                id: homoCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 7
                spacing: 3

                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: syncBar.diskSyncMode === "missing_only"
                          ? "Skips all posts already on disk and downloads only missing posts into your existing creator folder structure."
                          : (syncBar.diskSyncMode === "mismatched_only"
                             ? "Repairs only incomplete or size-mismatched posts already on disk (intact files inside those posts are untouched)."
                             : "Downloads posts not on disk and repairs incomplete/mismatched posts while keeping existing folders, naming & sorting 100% homogeneous.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#A7F3D0"
                }

                Text {
                    visible: syncBar.homogeneousSummary.length > 0
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: "⚙️ Reused layout:  " + syncBar.homogeneousSummary
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: "#6EE7B7"
                }
            }
        }
    }
}
