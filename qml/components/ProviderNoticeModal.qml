import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Switched-off site notice ────────────────────────────────────────────────
// Shown when a Kemono or Coomer link is used while those sites are turned off.
// Points to Pawchive (same links) or cum.st.
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string message: ""
    property string alternativeUrl: ""
    property string context: "link"      // "link" | "watchlist"
    property int kemonoWatchlistCount: 0

    signal useAlternative(string url)

    anchors.fill: parent
    z: 99990
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

    function show(msg, altUrl, ctx) {
        message = msg || ""
        alternativeUrl = altUrl || ""
        context = ctx || "link"
        kemonoWatchlistCount = (bridge && bridge.kemonoWatchlistCount) ? bridge.kemonoWatchlistCount() : 0
        isOpen = true
    }

    function close() { isOpen = false }

    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: root.isOpen ? 0.85 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.close()
            onWheel: (wheel) => wheel.accepted = true
        }
    }

    Rectangle {
        width: Math.min(500, parent.width - 32)
        height: content.implicitHeight + 40
        anchors.centerIn: parent
        radius: 10
        color: "#181B22"
        border.color: "#282E3D"
        border.width: 1
        scale: root.isOpen ? 1.0 : 0.96
        Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        // Swallow clicks on the card itself
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: content
            anchors.centerIn: parent
            width: parent.width - 40
            spacing: 14

            Text {
                text: "This site is turned off"
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 15
                font.weight: 700
                color: "#F8FAFC"
            }

            Text {
                Layout.fillWidth: true
                text: root.message
                wrapMode: Text.Wrap
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                lineHeight: 1.25
                color: "#94A3B8"
            }

            Rectangle {
                visible: root.alternativeUrl.length > 0
                Layout.fillWidth: true
                implicitHeight: altText.implicitHeight + 14
                radius: 6
                color: "#13161C"
                border.color: "#2A303F"
                border.width: 1
                Text {
                    id: altText
                    anchors.fill: parent
                    anchors.margins: 7
                    text: root.alternativeUrl
                    elide: Text.ElideMiddle
                    verticalAlignment: Text.AlignVCenter
                    font.family: "Cascadia Code, Consolas, monospace"
                    font.pixelSize: 11
                    color: "#38BDF8"
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 2
                spacing: 8

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: "Close"
                    variant: "ghost"
                    onClicked: root.close()
                }

                StyledButton {
                    visible: root.context === "watchlist" && root.kemonoWatchlistCount > 0
                    text: "Move " + root.kemonoWatchlistCount + " Kemono artist" + (root.kemonoWatchlistCount === 1 ? "" : "s") + " to Pawchive"
                    variant: "primary"
                    tooltip: "Pawchive uses the same creator IDs, so your Watchlist keeps working."
                    onClicked: {
                        if (root.bridge && root.bridge.switchWatchlistToPawchive) root.bridge.switchWatchlistToPawchive()
                        root.close()
                    }
                }

                StyledButton {
                    visible: root.alternativeUrl.length > 0
                    text: "Use the Pawchive link"
                    variant: "primary"
                    onClicked: {
                        root.useAlternative(root.alternativeUrl)
                        root.close()
                    }
                }
            }
        }
    }
}
