import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var bridge: null
    signal startRequested()
    signal queueRequested()
    signal settingsRequested()

    color: "#12151C"
    border.color: "#242A38"
    border.width: 1
    implicitHeight: 52

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        // Browser navigation controls
        Row {
            spacing: 4
            Layout.alignment: Qt.AlignVCenter

            Rectangle {
                width: 28; height: 28; radius: 6
                color: bBack.containsMouse ? "#222733" : "transparent"
                scale: bBack.pressed ? 0.88 : (bBack.containsMouse ? 1.12 : 1.0)
                transformOrigin: Item.Center

                Behavior on scale {
                    NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                }
                Behavior on color { ColorAnimation { duration: 120 } }

                Text { anchors.centerIn: parent; text: "◀"; font.pixelSize: 11; color: "#94A3B8" }
                MouseArea {
                    id: bBack
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: "Navigate back"
                }
            }

            Rectangle {
                width: 28; height: 28; radius: 6
                color: bFwd.containsMouse ? "#222733" : "transparent"
                scale: bFwd.pressed ? 0.88 : (bFwd.containsMouse ? 1.12 : 1.0)
                transformOrigin: Item.Center

                Behavior on scale {
                    NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
                }
                Behavior on color { ColorAnimation { duration: 120 } }

                Text { anchors.centerIn: parent; text: "▶"; font.pixelSize: 11; color: "#64748B" }
                MouseArea { id: bFwd; anchors.fill: parent; hoverEnabled: true }
            }

            Rectangle {
                width: 28; height: 28; radius: 6
                color: bReload.containsMouse ? "#222733" : "transparent"
                scale: bReload.pressed ? 0.88 : (bReload.containsMouse ? 1.15 : 1.0)
                transformOrigin: Item.Center

                Behavior on scale {
                    NumberAnimation { duration: 160; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
                }
                Behavior on color { ColorAnimation { duration: 120 } }

                Text {
                    anchors.centerIn: parent
                    text: root.bridge && root.bridge.isDownloading ? "⏹" : "↻"
                    font.pixelSize: 12
                    color: root.bridge && root.bridge.isDownloading ? "#EF4444" : "#38BDF8"
                }
                MouseArea {
                    id: bReload
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                    ToolTip.text: root.bridge && root.bridge.isDownloading ? "Cancel active download" : "Refresh & Start download"
                    onClicked: {
                        if (root.bridge && root.bridge.isDownloading) {
                            root.bridge.cancelDownload()
                        } else if (root.bridge) {
                            root.bridge.startDownload()
                        }
                    }
                }
            }
        }

        // Browser Omnibox Address Bar
        Rectangle {
            Layout.fillWidth: true
            height: 36
            radius: 8
            color: urlInput.activeFocus ? "#0B0D12" : "#171A23"
            border.color: urlInput.activeFocus ? "#38BDF8" : (urlMouse.containsMouse ? "#475569" : "#2E3547")
            border.width: urlInput.activeFocus ? 1.5 : 1

            Behavior on border.color { ColorAnimation { duration: 150 } }

            MouseArea {
                id: urlMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.IBeamCursor
                onClicked: urlInput.forceActiveFocus()
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 8
                spacing: 8

                // Security / Domain Lock Icon
                Text {
                    text: "🔒"
                    font.pixelSize: 12
                    Layout.alignment: Qt.AlignVCenter
                }

                // Domain Tag Badge (Auto-adapts to fit the full provider name in RowLayout)
                Rectangle {
                    implicitWidth: domainText.implicitWidth + 20
                    implicitHeight: 22
                    Layout.preferredWidth: domainText.implicitWidth + 20
                    Layout.preferredHeight: 22
                    Layout.alignment: Qt.AlignVCenter
                    radius: 5
                    color: "#1E2430"
                    border.color: "#2D3748"
                    border.width: 1
                    visible: domainText.text.length > 0

                    Text {
                        id: domainText
                        anchors.centerIn: parent
                        text: {
                            var u = (root.bridge ? root.bridge.currentUrl : "").toLowerCase()
                            if (!u || u.trim().length === 0) return "API URL"
                            if (u.indexOf("cum.st") >= 0 || u.indexOf("cum.") >= 0) return "cum.st"
                            if (u.indexOf("pawchive") >= 0) return "pawchive.pw"
                            if (u.indexOf("kemono") >= 0) return "kemono.su"
                            if (u.indexOf("coomer") >= 0) return "coomer.su"
                            if (u.indexOf("bunkr") >= 0) return "bunkr.is"
                            if (u.indexOf("erome") >= 0) return "erome.com"
                            if (u.indexOf("nhentai") >= 0) return "nhentai.net"
                            if (u.indexOf("saint2") >= 0) return "saint2.su"
                            
                            // Fallback: extract domain from hostname if present
                            try {
                                var clean = u.replace(/^(?:https?:\/\/)?(?:www\.)?/i, "").split('/')[0]
                                if (clean.length > 0) return clean
                            } catch(e) {}
                            return "API URL"
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: "#38BDF8"
                    }
                }

                TextInput {
                    id: urlInput
                    Layout.fillWidth: true
                    text: root.bridge ? root.bridge.currentUrl : ""
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    color: "#F1F5F9"
                    clip: true
                    selectByMouse: true
                    onTextChanged: {
                        if (root.bridge && root.bridge.currentUrl !== text) {
                            root.bridge.currentUrl = text
                        }
                    }
                    onAccepted: root.startRequested()
                }

                // Clear button
                Rectangle {
                    width: 18; height: 18; radius: 9
                    color: clearBtnArea.containsMouse ? "#374151" : "#1F2430"
                    visible: urlInput.text.length > 0
                    Text { anchors.centerIn: parent; text: "×"; font.bold: true; font.pixelSize: 12; color: "#94A3B8" }
                    MouseArea {
                        id: clearBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 400
                        ToolTip.text: "Clear address bar"
                        onClicked: urlInput.text = ""
                    }
                }
            }
        }

        // Page Range Controls (Blank by default = all pages)
        Rectangle {
            height: 34
            implicitWidth: pageRow.implicitWidth + 16
            radius: 8
            color: "#151821"
            border.color: (pStartInput.activeFocus || pEndInput.activeFocus) ? "#38BDF8" : "#282E3D"
            border.width: 1

            Behavior on border.color { ColorAnimation { duration: 150 } }

            RowLayout {
                id: pageRow
                anchors.centerIn: parent
                spacing: 6

                Text {
                    text: "📄 Pages:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: "#94A3B8"
                }

                // Start Page input
                Rectangle {
                    id: pStartBox
                    width: 38
                    height: 24
                    radius: 5
                    color: pStartInput.activeFocus ? "#0B0D12" : "#0E1118"
                    border.color: pStartInput.activeFocus ? "#38BDF8" : "#242A38"
                    border.width: 1

                    ToolTip {
                        text: "Start page number (blank = 1)"
                        visible: pStartMouse.containsMouse
                        delay: 400
                        contentItem: Text {
                            text: "Start page number (blank = 1)"
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                        }
                        background: Rectangle {
                            color: "#181B24"
                            border.color: "#38BDF8"
                            border.width: 1
                            radius: 6
                        }
                    }

                    MouseArea {
                        id: pStartMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.IBeamCursor
                        onClicked: pStartInput.forceActiveFocus()
                    }

                    TextInput {
                        id: pStartInput
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#F1F5F9"
                        text: (root.bridge && root.bridge.pageStart > 1) ? root.bridge.pageStart.toString() : ""
                        validator: IntValidator { bottom: 1; top: 999999 }
                        selectByMouse: true

                        Text {
                            anchors.centerIn: parent
                            text: "1"
                            color: "#64748B"
                            font.pixelSize: 11
                            visible: !pStartInput.text
                        }

                        onTextChanged: {
                            if (!root.bridge) return
                            if (text.trim() === "") {
                                root.bridge.pageStart = 1
                            } else {
                                var val = parseInt(text)
                                if (!isNaN(val)) root.bridge.pageStart = Math.max(1, val)
                            }
                        }
                    }
                }

                Text {
                    text: "→"
                    font.pixelSize: 11
                    color: "#64748B"
                }

                // End Page input
                Rectangle {
                    id: pEndBox
                    width: 44
                    height: 24
                    radius: 5
                    color: pEndInput.activeFocus ? "#0B0D12" : "#0E1118"
                    border.color: pEndInput.activeFocus ? "#38BDF8" : "#242A38"
                    border.width: 1

                    ToolTip {
                        text: "End page number (blank = all pages)"
                        visible: pEndMouse.containsMouse
                        delay: 400
                        contentItem: Text {
                            text: "End page number (blank = all pages)"
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                        }
                        background: Rectangle {
                            color: "#181B24"
                            border.color: "#38BDF8"
                            border.width: 1
                            radius: 6
                        }
                    }

                    MouseArea {
                        id: pEndMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.IBeamCursor
                        onClicked: pEndInput.forceActiveFocus()
                    }

                    TextInput {
                        id: pEndInput
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#F1F5F9"
                        text: (root.bridge && root.bridge.pageEnd < 999999 && root.bridge.pageEnd !== 999) ? root.bridge.pageEnd.toString() : ""
                        validator: IntValidator { bottom: 1; top: 999999 }
                        selectByMouse: true

                        Text {
                            anchors.centerIn: parent
                            text: "All"
                            color: "#64748B"
                            font.pixelSize: 11
                            visible: !pEndInput.text
                        }

                        onTextChanged: {
                            if (!root.bridge) return
                            if (text.trim() === "") {
                                root.bridge.pageEnd = 999999
                            } else {
                                var val = parseInt(text)
                                if (!isNaN(val)) root.bridge.pageEnd = Math.max(1, val)
                            }
                        }
                    }
                }
            }
        }
    }
}

