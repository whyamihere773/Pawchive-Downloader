import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Rectangle {
    id: cloudModalRoot

    property var bridge: null
    property bool isOpen: false

    visible: opacity > 0
    anchors.fill: parent
    color: "#CC0B0D12" // Semi-transparent overlay backdrop
    z: 1000

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
    }

    // Prevent clicks from falling through
    MouseArea {
        anchors.fill: parent
        onClicked: {}
    }

    // Local model for harvested links
    ListModel {
        id: cloudLinksModel

        function populate(searchQuery) {
            clear()
            if (!cloudModalRoot.bridge) return
            var list = cloudModalRoot.bridge.getHarvestedLinks()
            var q = (searchQuery || "").toLowerCase().trim()

            for (var i = 0; i < list.length; i++) {
                var item = list[i]
                var title = item.title || "Untitled Post"
                var url = item.url || ""
                var platform = (item.platform || "other").toLowerCase()
                var creator = item.creator || ""

                if (q.length > 0) {
                    if (title.toLowerCase().indexOf(q) === -1 &&
                        url.toLowerCase().indexOf(q) === -1 &&
                        platform.toLowerCase().indexOf(q) === -1 &&
                        creator.toLowerCase().indexOf(q) === -1) {
                        continue
                    }
                }

                cloudLinksModel.append({
                    title: title,
                    url: url,
                    platform: platform,
                    creator: creator,
                    isSelected: true
                })
            }
        }

        function getSelectedList() {
            var res = []
            for (var i = 0; i < count; i++) {
                var item = get(i)
                if (item.isSelected) {
                    res.push({
                        title: item.title,
                        url: item.url,
                        platform: item.platform,
                        creator: item.creator
                    })
                }
            }
            return res
        }

        function countSelected() {
            var c = 0
            for (var i = 0; i < count; i++) {
                if (get(i).isSelected) c++
            }
            return c
        }

        function selectAll(val) {
            for (var i = 0; i < count; i++) {
                setProperty(i, "isSelected", val)
            }
        }
    }

    onIsOpenChanged: {
        if (isOpen) {
            searchField.text = ""
            cloudLinksModel.populate("")
        }
    }

    // Centered Dialog Window with Newtonian Spring Entrance
    Rectangle {
        id: dialogBox
        width: Math.min(cloudModalRoot.width - 40, 760)
        height: Math.min(cloudModalRoot.height - 40, 580)
        anchors.centerIn: parent
        radius: 10
        color: "#131722"
        border.color: "#2A3346"
        border.width: 1

        scale: cloudModalRoot.isOpen ? 1.0 : 0.88
        transformOrigin: Item.Center

        Behavior on scale {
            NumberAnimation {
                duration: cloudModalRoot.isOpen ? 340 : 200
                easing.type: cloudModalRoot.isOpen ? Easing.OutBack : Easing.InCubic
                easing.overshoot: 1.4
            }
        }

        // Top Accent Line
        Rectangle {
            width: parent.width - 2
            height: 2
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            radius: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#2DD4BF" }
                GradientStop { position: 0.5; color: "#38BDF8" }
                GradientStop { position: 1.0; color: "#A855F7" }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // Header Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "☁️"
                    font.pixelSize: 20
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Download Harvested Cloud Links"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: "#F8FAFC"
                    }

                    Text {
                        text: "Download files and folders from Mega.nz, Google Drive, Dropbox, and GoFile."
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                // Close Button
                Rectangle {
                    width: 28; height: 28; radius: 6
                    color: closeMouse.containsMouse ? "#2A3346" : "transparent"
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 12
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: cloudModalRoot.isOpen = false
                    }
                }
            }

            // Search Bar & Selection Tools
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Search Input
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: 6
                    color: "#0F1219"
                    border.color: searchField.activeFocus ? "#38BDF8" : "#242C3D"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text { text: "🔍"; font.pixelSize: 11 }

                        TextInput {
                            id: searchField
                            Layout.fillWidth: true
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F1F5F9"
                            selectByMouse: true
                            verticalAlignment: Text.AlignVCenter

                            Text {
                                text: "Search by title, URL, or platform (Mega, Drive, etc.)..."
                                color: "#64748B"
                                font.pixelSize: 12
                                visible: !searchField.text && !searchField.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            onTextChanged: cloudLinksModel.populate(text)
                        }
                    }
                }

                // Select All
                StyledButton {
                    text: "Select All"
                    height: 32
                    onClicked: cloudLinksModel.selectAll(true)
                }

                // Deselect All
                StyledButton {
                    text: "Deselect All"
                    height: 32
                    onClicked: cloudLinksModel.selectAll(false)
                }
            }

            // Links List View
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: "#0B0E14"
                border.color: "#1E2638"
                border.width: 1
                clip: true

                ListView {
                    id: linksList
                    anchors.fill: parent
                    anchors.margins: 4
                    model: cloudLinksModel
                    spacing: 4
                    boundsBehavior: Flickable.StopAtBounds

                    ScrollBar.vertical: ScrollBar {
                        width: 8
                        policy: ScrollBar.AsNeeded
                    }

                    delegate: Rectangle {
                        width: linksList.width - 8
                        height: 52
                        radius: 6
                        color: model.isSelected ? "#161D2B" : (delegateMouse.containsMouse ? "#111622" : "#0E121A")
                        border.color: model.isSelected ? "#2A3A54" : (delegateMouse.containsMouse ? "#1F283B" : "transparent")
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 100 } }

                        MouseArea {
                            id: delegateMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                cloudLinksModel.setProperty(index, "isSelected", !model.isSelected)
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            // Checkbox
                            Rectangle {
                                width: 18; height: 18; radius: 4
                                color: model.isSelected ? "#2DD4BF" : "transparent"
                                border.color: model.isSelected ? "#2DD4BF" : "#475569"
                                border.width: 1.5

                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    font.bold: true
                                    font.pixelSize: 11
                                    color: "#0F172A"
                                    visible: model.isSelected
                                }
                            }

                            // Platform Badge
                            Rectangle {
                                Layout.preferredWidth: 68
                                Layout.preferredHeight: 22
                                radius: 4
                                color: {
                                    var p = (model.platform || "").toLowerCase()
                                    if (p === "mega") return "#3A1215"
                                    if (p === "gdrive" || p === "google drive") return "#112642"
                                    if (p === "dropbox") return "#0C2E42"
                                    if (p === "gofile") return "#0F3325"
                                    return "#1F2430"
                                }
                                border.color: {
                                    var p = (model.platform || "").toLowerCase()
                                    if (p === "mega") return "#EF4444"
                                    if (p === "gdrive" || p === "google drive") return "#3B82F6"
                                    if (p === "dropbox") return "#0EA5E9"
                                    if (p === "gofile") return "#10B981"
                                    return "#64748B"
                                }
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: (model.platform || "OTHER").toUpperCase()
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: {
                                        var p = (model.platform || "").toLowerCase()
                                        if (p === "mega") return "#FCA5A5"
                                        if (p === "gdrive" || p === "google drive") return "#93C5FD"
                                        if (p === "dropbox") return "#7DD3FC"
                                        if (p === "gofile") return "#6EE7B7"
                                        return "#CBD5E1"
                                    }
                                }
                            }

                            // Title & URL
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    Layout.fillWidth: true
                                    text: model.title
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: "#F1F5F9"
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.url
                                    font.family: "Consolas, Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                    elide: Text.ElideMiddle
                                }
                            }
                        }
                    }
                }

                // Empty State
                Text {
                    anchors.centerIn: parent
                    text: "No external cloud links found matching search."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#64748B"
                    visible: cloudLinksModel.count === 0
                }
            }

            // Footer Action Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "Selected: " + cloudLinksModel.countSelected() + " / " + cloudLinksModel.count + " link(s)"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#94A3B8"
                }

                Item { Layout.fillWidth: true }

                // Cancel Button
                StyledButton {
                    text: "Cancel"
                    height: 34
                    onClicked: cloudModalRoot.isOpen = false
                }

                // Download Selected Button
                Rectangle {
                    id: downloadSelectedBtn
                    Layout.preferredWidth: 170
                    Layout.preferredHeight: 34
                    radius: 7
                    property bool hasSelection: cloudLinksModel.countSelected() > 0
                    color: !hasSelection ? "#1A202C" : (dlMouse.pressed ? "#0D766E" : (dlMouse.containsMouse ? "#14B8A6" : "#2DD4BF"))
                    border.color: !hasSelection ? "#2D3748" : "#2DD4BF"
                    border.width: 1
                    opacity: hasSelection ? 1.0 : 0.5

                    scale: dlMouse.pressed && hasSelection ? 0.95 : (dlMouse.containsMouse && hasSelection ? 1.03 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⬇"; font.pixelSize: 12 }
                        Text {
                            text: "Download (" + cloudLinksModel.countSelected() + ")"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: "#0F172A"
                        }
                    }

                    MouseArea {
                        id: dlMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: downloadSelectedBtn.hasSelection ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: downloadSelectedBtn.hasSelection
                        onClicked: {
                            var sel = cloudLinksModel.getSelectedList()
                            if (sel.length > 0 && cloudModalRoot.bridge) {
                                cloudModalRoot.bridge.startCloudDownloads(sel, "")
                                cloudModalRoot.isOpen = false
                            }
                        }
                    }
                }
            }
        }
    }
}
