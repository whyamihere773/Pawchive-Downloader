import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Add Artist Modal Dialog (Responsive, scrollable & perfectly contained) ──
Item {
    id: addArtistModal
    required property var view

    function clearInputs() {
        addUrlInput.text = ""
        addFolderInput.text = ""
    }

    function setError(msg) {
        addErrorText.text = msg
    }
    anchors.fill: parent
    z: 9999
    visible: addArtistModal.view.showAddDialog
    opacity: visible ? 1.0 : 0.0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B0030712"

        MouseArea {
            anchors.fill: parent
            onClicked: {
                addErrorText.text = ""
                addArtistModal.view.showAddDialog = false
            }
        }
    }

    // Modal Card — Explicit width and height with responsive limits
    Rectangle {
        id: addArtistCard
        width: Math.min(500, Math.max(280, addArtistModal.view.width - 32))
        height: Math.min(addArtistModal.view.height - 40, modalContentCol.implicitHeight + 44)
        anchors.centerIn: parent
        radius: 12
        color: "#0D111E"
        border.color: "#2D3748"
        border.width: 1
        clip: true
        scale: addArtistModal.view.showAddDialog ? 1.0 : 0.94
        Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }

        // Subtle glowing top accent line
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 2
            radius: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: "#8B5CF6" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // Scrollable contents to ensure it shrinks and scrolls on any window height
        SmoothFlickable {
            id: modalFlickable
            anchors.fill: parent
            anchors.margins: 18
            contentWidth: width
            contentHeight: modalContentCol.implicitHeight
            clip: true

            ColumnLayout {
                id: modalContentCol
                width: modalFlickable.width
                spacing: 13

                // Header
                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: "➕ " + addArtistModal.view.tr("watchlist_add_title", "Add Artist to Watchlist")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#E2E8F0"
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "✕"
                        font.pixelSize: 14
                        color: closeAddMouse.containsMouse ? "#E2E8F0" : "#64748B"
                        MouseArea {
                            id: closeAddMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                addErrorText.text = ""
                                addArtistModal.view.showAddDialog = false
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: addArtistModal.view.tr("watchlist_add_desc", "Track an artist to automatically check for future posts without downloading their full past catalog.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    lineHeight: 1.4
                }

                // URL Input Label
                Text {
                    text: addArtistModal.view.tr("watchlist_add_url_label", "Artist URL (Pawchive / cum.st):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                }

                // URL Input Box
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: 6
                    color: addUrlInput.activeFocus ? "#0B0D12" : "#080B14"
                    border.color: addUrlInput.activeFocus ? "#8B5CF6" : (addUrlBoxMouse.containsMouse ? "#475569" : "#242C40")
                    border.width: addUrlInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: addUrlBoxMouse
                        target: addUrlInput
                        focusOnLeftClick: true
                    }

                    TextInput {
                        id: addUrlInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#E2E8F0"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        clip: true
                        selectByMouse: true
                        TextBarContextArea {}

                        Text {
                            text: "https://kemono.cr/patreon/user/12345678"
                            font: parent.font
                            color: "#475569"
                            visible: !addUrlInput.text && !addUrlInput.activeFocus
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                        }
                    }
                }

                // Download Folder Label
                Text {
                    text: addArtistModal.view.tr("watchlist_add_folder_label", "Download Folder (Optional):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                }

                // Download Folder Input Box + Browse
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 36
                        radius: 6
                        color: addFolderInput.activeFocus ? "#0B0D12" : "#080B14"
                        border.color: addFolderInput.activeFocus ? "#8B5CF6" : (addFolderBoxMouse.containsMouse ? "#475569" : "#242C40")
                        border.width: addFolderInput.activeFocus ? 1.5 : 1

                        TextBarContextArea {
                            id: addFolderBoxMouse
                            target: addFolderInput
                            focusOnLeftClick: true
                        }

                        TextInput {
                            id: addFolderInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#E2E8F0"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            clip: true
                            selectByMouse: true
                            TextBarContextArea {}

                            Text {
                                text: addArtistModal.view.tr("watchlist_add_folder_ph", "Leave empty for default download folder")
                                font: parent.font
                                color: "#475569"
                                visible: !addFolderInput.text && !addFolderInput.activeFocus
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Rectangle {
                        width: 78
                        height: 36
                        radius: 6
                        color: addBrowseMouse.containsMouse ? "#1E293B" : "#111827"
                        border.color: "#334155"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: "\uD83D\uDCC2 Browse"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#E2E8F0"
                        }

                        MouseArea {
                            id: addBrowseMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (!addArtistModal.view.bridge) return
                                var picked = addArtistModal.view.bridge.selectExistingDirectory(addFolderInput.text)
                                if (picked) addFolderInput.text = picked
                            }
                        }
                    }
                }

                // Error text if any
                Text {
                    id: addErrorText
                    Layout.fillWidth: true
                    text: ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#F87171"
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                }

                // Spacing before buttons
                Item { Layout.preferredHeight: 4 }

                // Action buttons — responsive, shrink and fill width together with modal
                RowLayout {
                    Layout.fillWidth: true
                    width: parent.width
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.minimumWidth: 80
                        height: 34
                        radius: 6
                        color: cancelAddMouse.containsMouse ? "#1E2536" : "#131826"
                        border.color: "#2E3A52"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 16
                            horizontalAlignment: Text.AlignHCenter
                            text: addArtistModal.view.tr("common_cancel", "Cancel")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#94A3B8"
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            id: cancelAddMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                addErrorText.text = ""
                                addArtistModal.view.showAddDialog = false
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        Layout.minimumWidth: 100
                        height: 34
                        radius: 6
                        color: confirmAddMouse.containsMouse ? "#6D28D9" : "#5B21B6"
                        border.color: "#7C3AED"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 16
                            horizontalAlignment: Text.AlignHCenter
                            text: addArtistModal.view._addRequest !== "" ? addArtistModal.view.tr("watchlist_adding", "Adding…") : addArtistModal.view.tr("watchlist_add_confirm", "Add to Watchlist")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            id: confirmAddMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            enabled: addArtistModal.view._addRequest === ""
                            onClicked: {
                                var url = addUrlInput.text.trim()
                                if (!url) {
                                    addErrorText.text = addArtistModal.view.tr("watchlist_error_no_url", "Please enter an artist URL")
                                    return
                                }
                                addErrorText.text = ""
                                if (!addArtistModal.view.bridge) return
                                // Looked up in the background: the window used to freeze meanwhile
                                addArtistModal.view._addRequest = "watchlist-add-" + Date.now()
                                addArtistModal.view.bridge.addArtistToWatchlistAsync(addArtistModal.view._addRequest, url, addFolderInput.text.trim())
                            }
                        }
                    }
                }
            }
        }
    }
}
