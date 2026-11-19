import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Row 2.5: Download folder(s) & Multi-Drive Overflow Locations
ColumnLayout {
    id: foldersSec
    required property var card
    required property var view
    width: parent.width
    spacing: 4

    // Multi-drive header banner (only when 2+ locations are detected)
    RowLayout {
        Layout.fillWidth: true
        visible: foldersSec.card.artistDownloadDirs.length > 1
        spacing: 6

        Rectangle {
            implicitHeight: 18
            implicitWidth: multiDriveText.implicitWidth + 14
            radius: 9
            color: "#0F243A"
            border.color: "#0284C7"
            border.width: 1
            RowLayout {
                anchors.centerIn: parent
                spacing: 4
                Text { text: "💾"; font.pixelSize: 9 }
                Text {
                    id: multiDriveText
                    text: foldersSec.view.tr("watchlist_multidrive_locations", "Multi-Drive Spanned") + " (" + foldersSec.card.artistDownloadDirs.length + " " + foldersSec.view.tr("watchlist_locations", "locations") + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 9
                    font.bold: true
                    color: "#38BDF8"
                }
            }
        }

        Item { Layout.fillWidth: true }

        // Add Location Button
        Rectangle {
            implicitHeight: 18
            implicitWidth: addLocRow.implicitWidth + 12
            radius: 9
            color: addLocMouse.containsMouse ? "#1E293B" : "#0F172A"
            border.color: addLocMouse.containsMouse ? "#38BDF8" : "#334155"
            border.width: 1
            RowLayout {
                id: addLocRow
                anchors.centerIn: parent
                spacing: 3
                Text { text: "+"; font.pixelSize: 11; font.bold: true; color: "#38BDF8" }
                Text {
                    text: foldersSec.view.tr("watchlist_add_location", "Add Drive/Folder")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 9
                    font.bold: true
                    color: "#94A3B8"
                }
            }
            MouseArea {
                id: addLocMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: foldersSec.view.tr("watchlist_add_location_tip", "Link another storage drive or folder for this artist")
                onClicked: {
                    if (foldersSec.view.bridge) foldersSec.view.bridge.browseAndAddArtistDownloadDir(foldersSec.card.artistUserId, foldersSec.card.artistService)
                }
            }
        }
    }

    // Single path layout (when only 1 path exists)
    RowLayout {
        Layout.fillWidth: true
        visible: foldersSec.card.artistDownloadDirs.length <= 1
        spacing: 6

        Rectangle {
            Layout.fillWidth: true
            height: 24
            radius: 5
            color: singlePathMouse.containsMouse ? "#111A2B" : "#0A0F1A"
            border.color: singlePathMouse.containsMouse ? "#38BDF8" : "#1C2436"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 6

                Text { text: "📁"; font.pixelSize: 11 }
                Text {
                    text: foldersSec.card.artistDownloadDir || foldersSec.view.tr("watchlist_no_folder", "Default download folder")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: singlePathMouse.containsMouse ? "#38BDF8" : (foldersSec.card.artistDownloadDir ? "#94A3B8" : "#4B5563")
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            MouseArea {
                id: singlePathMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: foldersSec.view.tr("watchlist_open_folder_tip", "Click to open folder in File Explorer\n") + (foldersSec.card.artistDownloadDir || "Default download folder")
                onClicked: {
                    if (foldersSec.view.bridge) foldersSec.view.bridge.openFolder(foldersSec.card.artistDownloadDir)
                }
            }
        }

        // Browse button (📂)
        Rectangle {
            height: 24
            width: 28
            radius: 5
            color: browseSingleMouse.containsMouse ? "#1E293B" : "#0F172A"
            border.color: browseSingleMouse.containsMouse ? "#64748B" : "#334155"
            border.width: 1

            Text {
                anchors.centerIn: parent
                text: "📂"
                font.pixelSize: 11
            }
            MouseArea {
                id: browseSingleMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: foldersSec.view.tr("watchlist_browse_tip", "Change download folder for this artist")
                onClicked: {
                    if (foldersSec.view.bridge) foldersSec.view.bridge.browseWatchlistDownloadDir(foldersSec.card.artistUserId, foldersSec.card.artistService)
                }
            }
        }

        // Show this folder in the Gallery tab
        Rectangle {
            height: 24
            width: 28
            radius: 5
            color: gallerySingleMouse.containsMouse ? "#1E293B" : "#0F172A"
            border.color: gallerySingleMouse.containsMouse ? "#38BDF8" : "#334155"
            border.width: 1
            Text { anchors.centerIn: parent; text: "🖼"; font.pixelSize: 11 }
            MouseArea {
                id: gallerySingleMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: foldersSec.view.tr("watchlist_show_gallery_tip", "Show this folder in the Gallery")
                onClicked: if (foldersSec.view.bridge) foldersSec.view.bridge.showInGallery(foldersSec.card.artistDownloadDir || foldersSec.view.bridge.getDownloadDir())
            }
        }

        // Add Path button (links a second drive/folder to this artist)
        Rectangle {
            height: 24
            implicitWidth: addPathRow.implicitWidth + 12
            radius: 5
            color: addPathMouse.containsMouse ? "#0C1F38" : "#080E1A"
            border.color: addPathMouse.containsMouse ? "#38BDF8" : "#1E3A52"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 120 } }
            Behavior on border.color { ColorAnimation { duration: 120 } }
            scale: addPathMouse.pressed ? 0.93 : (addPathMouse.containsMouse ? 1.04 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }

            Row {
                id: addPathRow
                anchors.centerIn: parent
                spacing: 4
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "+"
                    font.pixelSize: 13
                    font.bold: true
                    color: addPathMouse.containsMouse ? "#38BDF8" : "#0EA5E9"
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: foldersSec.view.tr("watchlist_add_path_btn", "Add Path")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    font.weight: 600
                    color: addPathMouse.containsMouse ? "#7DD3FC" : "#475569"
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            MouseArea {
                id: addPathMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: foldersSec.view.tr("watchlist_add_path_tip", "Link another folder or drive as an additional location for this artist")
                onClicked: {
                    if (foldersSec.view.bridge) foldersSec.view.bridge.browseAndAddArtistDownloadDir(foldersSec.card.artistUserId, foldersSec.card.artistService)
                }
            }
        }
    }

    // Multi-path list (when 2+ paths exist)
    Repeater {
        model: foldersSec.card.artistDownloadDirs.length > 1 ? foldersSec.card.artistDownloadDirs : []
        delegate: RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Rectangle {
                Layout.fillWidth: true
                height: 24
                radius: 5
                color: multiPathMouse.containsMouse ? "#111A2B" : "#0A0F1A"
                border.color: multiPathMouse.containsMouse ? "#38BDF8" : (index === 0 ? "#1E293B" : "#1C2436")
                border.width: 1

                Behavior on color { ColorAnimation { duration: 120 } }
                Behavior on border.color { ColorAnimation { duration: 120 } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 6

                    Text { text: "📁"; font.pixelSize: 11 }
                    Text {
                        text: modelData
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: multiPathMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    id: multiPathMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: foldersSec.view.tr("watchlist_open_folder_tip", "Click to open folder in File Explorer\n") + modelData
                    onClicked: {
                        if (foldersSec.view.bridge) foldersSec.view.bridge.openFolder(modelData)
                    }
                }
            }

            // Show this folder in the Gallery tab
            Rectangle {
                height: 24
                width: 28
                radius: 5
                color: galleryMultiMouse.containsMouse ? "#1E293B" : "#0F172A"
                border.color: galleryMultiMouse.containsMouse ? "#38BDF8" : "#334155"
                border.width: 1
                Text { anchors.centerIn: parent; text: "🖼"; font.pixelSize: 11 }
                MouseArea {
                    id: galleryMultiMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: foldersSec.view.tr("watchlist_show_gallery_tip", "Show this folder in the Gallery")
                    onClicked: if (foldersSec.view.bridge) foldersSec.view.bridge.showInGallery(modelData)
                }
            }

            // Remove path button (✕)
            Rectangle {
                height: 24
                width: 24
                radius: 5
                color: removePathMouse.containsMouse ? "#3F1018" : "#1A0F14"
                border.color: removePathMouse.containsMouse ? "#EF4444" : "#4A1A24"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    font.pixelSize: 10
                    font.bold: true
                    color: removePathMouse.containsMouse ? "#FCA5A5" : "#F87171"
                }
                MouseArea {
                    id: removePathMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: foldersSec.view.tr("watchlist_remove_path_tip", "Remove this location from artist (e.g. if files were combined)")
                    onClicked: {
                        if (foldersSec.view.bridge) foldersSec.view.bridge.removeArtistDownloadDir(foldersSec.card.artistUserId, foldersSec.card.artistService, modelData)
                    }
                }
            }
        }
    }
}
