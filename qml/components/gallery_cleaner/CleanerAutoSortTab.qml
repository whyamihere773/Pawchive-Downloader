import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Tab 3: Auto-Sort Hierarchies & Flatten/Undo controls.
Item {
    id: autoSortTab

    required property var modal
    visible: modal.activeTab === "sort"
    Layout.fillWidth: true
    Layout.fillHeight: true

    Flickable {
        anchors.fill: parent
        contentHeight: sortColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: sortColumn
            width: parent.width
            spacing: 8

            Text {
                text: "Choose how to automatically organize loose files in this folder into clean subfolders:"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#E2E8F0"
            }

            // Mode 1: By Type
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                radius: 8
                color: modal.sortMode === "type" ? "#1B2A40" : "#111622"
                border.color: modal.sortMode === "type" ? "#38BDF8" : "#232F45"
                border.width: 1

                Text {
                    id: sortIcon1
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "🖼️"
                    font.pixelSize: 18
                }

                Rectangle {
                    id: sortCircle1
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 18; height: 18; radius: 9
                    color: modal.sortMode === "type" ? "#38BDF8" : "transparent"
                    border.color: "#38BDF8"; border.width: 1.5
                }

                ColumnLayout {
                    anchors.left: sortIcon1.right
                    anchors.leftMargin: 10
                    anchors.right: sortCircle1.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1
                    Text { text: "Sort by File Type"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                    Text { text: "Groups into Images/, Videos/, Audio/, Archives/, Documents/, and Other/"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.sortMode = "type"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Sort by File Type\nAutomatically creates Images/, Videos/, Audio/, Archives/, and Documents/ folders and sorts loose files into them."
                }
            }

            // Mode 2: By Date
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                radius: 8
                color: modal.sortMode === "date" ? "#1B2A40" : "#111622"
                border.color: modal.sortMode === "date" ? "#38BDF8" : "#232F45"
                border.width: 1

                Text {
                    id: sortIcon2
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "📅"
                    font.pixelSize: 18
                }

                Rectangle {
                    id: sortCircle2
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 18; height: 18; radius: 9
                    color: modal.sortMode === "date" ? "#38BDF8" : "transparent"
                    border.color: "#38BDF8"; border.width: 1.5
                }

                ColumnLayout {
                    anchors.left: sortIcon2.right
                    anchors.leftMargin: 10
                    anchors.right: sortCircle2.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1
                    Text { text: "Sort by Date Modified"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                    Text { text: "Groups files into YYYY-MM/ subfolders based on file modification timestamps"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.sortMode = "date"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Sort by Date Modified\nGroups files into YYYY-MM subfolders (e.g. 2026-09/, 2026-10/) based on file modification timestamps."
                }
            }

            // Mode 3: By Extension
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                radius: 8
                color: modal.sortMode === "extension" ? "#1B2A40" : "#111622"
                border.color: modal.sortMode === "extension" ? "#38BDF8" : "#232F45"
                border.width: 1

                Text {
                    id: sortIcon3
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "🏷️"
                    font.pixelSize: 18
                }

                Rectangle {
                    id: sortCircle3
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 18; height: 18; radius: 9
                    color: modal.sortMode === "extension" ? "#38BDF8" : "transparent"
                    border.color: "#38BDF8"; border.width: 1.5
                }

                ColumnLayout {
                    anchors.left: sortIcon3.right
                    anchors.leftMargin: 10
                    anchors.right: sortCircle3.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1
                    Text { text: "Sort by Extension"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                    Text { text: "Groups files into PNG/, JPG/, MP4/, etc. based on file extension"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.sortMode = "extension"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Sort by Extension\nGroups files into subfolders named after their extension (e.g. PNG/, JPG/, MP4/, ZIP/)."
                }
            }

            // Option 4: Dump / Flatten Everything into Single Folder
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 48
                radius: 8
                color: modal.sortMode === "flatten" ? "#1B2234" : "#0F1420"
                border.color: modal.sortMode === "flatten" ? "#F59E0B" : "#212B3D"
                border.width: 1

                Text {
                    id: sortIcon4
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    text: "📦"
                    font.pixelSize: 18
                }

                Rectangle {
                    id: sortCircle4
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 18; height: 18; radius: 9
                    color: modal.sortMode === "flatten" ? "#F59E0B" : "transparent"
                    border.color: "#F59E0B"; border.width: 1.5
                }

                ColumnLayout {
                    anchors.left: sortIcon4.right
                    anchors.leftMargin: 10
                    anchors.right: sortCircle4.left
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1
                    Text { text: "Dump Everything into Single Folder (Flatten)"; font.bold: true; font.pixelSize: 11; color: "#F8FAFC" }
                    Text { text: "Extracts all files from subfolders into this main folder and cleans up empty folders"; font.pixelSize: 10; color: "#94A3B8"; elide: Text.ElideRight; Layout.fillWidth: true }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.sortMode = "flatten"
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Dump Everything into Single Folder\nMoves all files nested in any subfolder directly into this main folder. Automatically appends (1), (2) to duplicate names and cleans up empty subfolders."
                }
            }

            // Recursive Subfolders Option (relevant for categorization modes)
            Rectangle {
                visible: modal.sortMode !== "flatten"
                Layout.fillWidth: true
                implicitHeight: 38
                radius: 8
                color: modal.sortRecursive ? "#16253B" : "#0F1420"
                border.color: modal.sortRecursive ? "#38BDF8" : "#212B3D"
                border.width: 1

                Rectangle {
                    id: recCheckbox
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    width: 16
                    height: 16
                    radius: 4
                    color: modal.sortRecursive ? "#38BDF8" : "transparent"
                    border.color: modal.sortRecursive ? "#38BDF8" : "#475569"
                    border.width: 1.5

                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#0F172A"
                        visible: modal.sortRecursive
                    }
                }

                ColumnLayout {
                    anchors.left: recCheckbox.right
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1

                    Text {
                        text: "Apply recursively to all post subfolders"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#F8FAFC"
                    }
                    Text {
                        text: "Sorts attachments inside each individual post folder (e.g. Creator/[Post 1]/Images/, Creator/[Post 2]/Videos/)"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 9
                        color: "#94A3B8"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.sortRecursive = !modal.sortRecursive
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Recursive Subfolder Sorting\nWhen enabled, iterates through all post subfolders and categorizes loose attachments into Images/, Videos/, etc. inside each post folder."
                }
            }

            // Spacing before organize action
            Item { Layout.preferredHeight: 4 }

            // Organize Button
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                radius: 6
                color: modal.isPathBlocked ? "#1E2433" : (modal.sortMode === "flatten" ? (orgBtnMouse.containsMouse ? "#D97706" : "#B45309") : (orgBtnMouse.containsMouse ? "#059669" : "#047857"))
                border.color: modal.isPathBlocked ? "#2D3748" : (modal.sortMode === "flatten" ? "#F59E0B" : "#10B981")
                border.width: 1
                opacity: modal.isPathBlocked ? 0.35 : 1.0

                Text {
                    anchors.centerIn: parent
                    text: modal.isPathBlocked ? "Organizing Disabled on System Root" : (modal.isSorting ? "Working…" : (modal.sortMode === "flatten" ? "Dump & Flatten All Files Now" : "Organize Folder Now"))
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 700
                    color: "#FFFFFF"
                }
                Springy { hover: orgBtnMouse.containsMouse; pressed: orgBtnMouse.pressed }
                MouseArea {
                    id: orgBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: modal.isPathBlocked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                    onClicked: {
                        if (!modal.isPathBlocked) {
                            modal.executeAutoSort()
                        }
                    }
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: modal.isPathBlocked ?
                        ("Action Blocked: Cannot execute Auto-Sort on Windows system drive root (" + (modal.pathSafety ? modal.pathSafety.drive_letter : "C:") + "\\)") :
                        (modal.sortMode === "flatten" ?
                            "Dump & Flatten All Files Now\nMoves all files from subfolders into this main folder and removes empty subfolders." :
                            ("Organize Folder Now\nMove loose files in this folder into clean subfolders using the '" + (modal.sortMode === "type" ? "File Type" : (modal.sortMode === "date" ? "Date Modified" : "Extension")) + "' strategy." + (modal.sortRecursive ? " (Recursive: enabled)" : "")))
                }
            }

            // Sort Result Feedback
            Text {
                visible: modal.sortResultMsg.length > 0
                text: modal.sortResultMsg
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#10B981"
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }

            // Undo the last Flatten of this folder
            Rectangle {
                visible: modal.canUndoFlatten
                Layout.alignment: Qt.AlignHCenter
                implicitHeight: 28
                implicitWidth: undoFlattenLabel.implicitWidth + 28
                radius: 6
                color: undoFlattenMouse.containsMouse ? "#1E273A" : "transparent"
                border.color: "#F59E0B"
                border.width: 1
                opacity: modal.isSorting ? 0.5 : 1.0
                Text {
                    id: undoFlattenLabel
                    anchors.centerIn: parent
                    text: "Undo flatten"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#FCD34D"
                }
                MouseArea {
                    id: undoFlattenMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.undoFlatten()
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: "Move the files of the last flatten back into the folders they came from."
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
