import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Live rename preview table header and virtualized ListView.
ColumnLayout {
    id: previewTable

    required property var modal

    Layout.fillWidth: true
    Layout.fillHeight: true
    spacing: 12

    // Preview Table Header
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 26
        radius: 4
        color: "#161D2B"
        border.color: "#222C3E"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 8
            Text { text: "Original Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
            Text { text: "➔"; font.pixelSize: 10; color: "#64748B"; Layout.preferredWidth: 20; horizontalAlignment: Text.AlignHCenter }
            Text { text: "New Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
            Text { text: "Status"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight }
        }
    }

    // Preview Table List
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        radius: 6
        color: "#0A0D15"
        border.color: "#1E273A"
        border.width: 1
        clip: true

        ListView {
            id: previewListView
            anchors.fill: parent
            anchors.margins: 4
            spacing: 2
            model: modal.previewPlan
            clip: true

            delegate: Rectangle {
                width: previewListView.width
                height: 28
                radius: 4
                color: index % 2 === 0 ? "#111623" : "#0D111C"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 8

                    Text {
                        text: modelData.old_name
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 10
                        color: "#CBD5E1"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "➔"
                        font.pixelSize: 10
                        color: "#64748B"
                        Layout.preferredWidth: 20
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        text: modelData.new_name
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 10
                        font.weight: 600
                        color: modelData.status === "ready" ? "#38BDF8" : (modelData.status === "collision" ? "#EF4444" : "#94A3B8")
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    // Move badge
                    Rectangle {
                        visible: modelData.is_move === true
                        implicitHeight: 18
                        implicitWidth: moveBadgeTxt.implicitWidth + 8
                        radius: 4
                        color: "#064E3B"
                        border.color: "#10B981"
                        border.width: 1
                        Layout.preferredWidth: implicitWidth

                        Text {
                            id: moveBadgeTxt
                            anchors.centerIn: parent
                            text: "MOVE"
                            font.pixelSize: 8
                            font.weight: 700
                            color: "#6EE7B7"
                        }
                    }

                    Rectangle {
                        implicitHeight: 18
                        implicitWidth: statusTxt.implicitWidth + 10
                        radius: 4
                        color: modelData.status === "ready" ? "#064E3B" : (modelData.status === "collision" ? "#450A0A" : "#1E273A")
                        border.color: modelData.status === "ready" ? "#10B981" : (modelData.status === "collision" ? "#EF4444" : "#475569")
                        border.width: 1
                        Layout.preferredWidth: implicitWidth

                        Text {
                            id: statusTxt
                            anchors.centerIn: parent
                            text: modelData.status === "ready" ? "READY" : (modelData.status === "collision" ? "COLLISION" : "UNCHANGED")
                            font.pixelSize: 8
                            font.weight: 700
                            color: modelData.status === "ready" ? "#34D399" : (modelData.status === "collision" ? "#F87171" : "#94A3B8")
                        }
                    }
                }

                // ToolTip on hover for row
                ToolTip.visible: itemMouse.containsMouse
                ToolTip.delay: 350
                ToolTip.text: {
                    var tip = "Original: " + modelData.old_path + "\n➔ Target: " + modelData.new_path
                    if (modelData.error) {
                        tip += "\n⚠️ " + modelData.error
                    } else if (modelData.is_move) {
                        tip += "\n📦 Move to destination folder"
                    } else if (modelData.status === "ready") {
                        tip += "\n✅ Ready to rename"
                    } else if (modelData.status === "unchanged") {
                        tip += "\nℹ️ Filename is unchanged"
                    }
                    return tip
                }

                MouseArea {
                    id: itemMouse
                    anchors.fill: parent
                    hoverEnabled: true
                }
            }
        }
    }

}
