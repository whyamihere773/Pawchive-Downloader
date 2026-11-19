import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Download Options overlay dialog for single artist or batch favorite sync.
Rectangle {
    id: downloadOptionsOverlay

    required property var modal
    property alias startPageInput: startPageInput
    property alias endPageInput: endPageInput
    property alias locInput: locInput
    anchors.fill: parent
    color: Qt.rgba(0, 0, 0, 0.70)
    visible: modal.downloadDialogVisible
    z: 1000

    MouseArea {
        anchors.fill: parent
        // Absorb clicks so clicking backdrop inside the dialog doesn't close accidentally
    }

    Rectangle {
        id: downloadOptionsCard
        width: Math.min(560, modal.width - 32)
        height: Math.min(530, modal.height - 32)
        anchors.centerIn: parent
        radius: 12
        color: "#111827"
        border.color: "#374151"
        border.width: 1
        clip: true

        // Glowing amber accent border
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: 13
            color: "transparent"
            border.color: Qt.rgba(245/255, 158/255, 11/255, 0.3)
            border.width: 1
            z: -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            // Header row
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "⬇️"
                    font.pixelSize: 20
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: modal.downloadDialogIsBatch
                              ? modal.tr("title_dl_all_favorites", "Sync All Favorite Artists")
                              : (modal.tr("title_dl_artist", "Download Artist") + " — " + modal.downloadDialogArtistName)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#F8FAFC"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: modal.downloadDialogIsBatch
                              ? modal.tr("hint_dl_all_favorites", "Select page range and destination folder for all favorited creators.")
                              : ((modal.downloadDialogService ? modal.downloadDialogService.toUpperCase() + " • " : "") + "ID: " + modal.downloadDialogArtistId)
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                // Dialog Close ✕
                Rectangle {
                    width: 28; height: 28; radius: 6
                    color: dlCloseMouse.containsMouse ? "#374151" : "#1F2937"
                    Text { anchors.centerIn: parent; text: "✕"; font.bold: true; font.pixelSize: 12; color: "#94A3B8" }
                    MouseArea {
                        id: dlCloseMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.downloadDialogVisible = false
                    }
                }
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1F2937"
            }

            // Update Status Callout Box
            Rectangle {
                Layout.fillWidth: true
                radius: 7
                color: modal.downloadDialogIsBatch
                       ? "#1A2234"
                       : (modal.downloadDialogNewPostCount > 0 ? "#2E1E05" : (modal.downloadDialogLastPostDate ? "#064E3B" : "#1A2234"))
                border.color: modal.downloadDialogIsBatch
                       ? "#2E3B56"
                       : (modal.downloadDialogNewPostCount > 0 ? "#F59E0B" : (modal.downloadDialogLastPostDate ? "#10B981" : "#2E3B56"))
                border.width: 1
                implicitHeight: statusCalloutRow.implicitHeight + 14

                RowLayout {
                    id: statusCalloutRow
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Text {
                        text: modal.downloadDialogIsBatch
                              ? (modal.totalNewPosts > 0 ? "🔔" : "ℹ️")
                              : (modal.downloadDialogNewPostCount > 0 ? "🔔" : (modal.downloadDialogLastPostDate ? "✓" : "✦"))
                        font.pixelSize: 14
                    }

                    Text {
                        Layout.fillWidth: true
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: modal.downloadDialogIsBatch
                               ? (modal.totalNewPosts > 0 ? "#FCD34D" : "#94A3B8")
                               : (modal.downloadDialogNewPostCount > 0 ? "#FCD34D" : (modal.downloadDialogLastPostDate ? "#A7F3D0" : "#94A3B8"))
                        wrapMode: Text.WordWrap
                        text: {
                            if (modal.downloadDialogIsBatch) {
                                if (modal.totalNewPosts > 0) {
                                    return modal.totalNewPosts + " total new post" + (modal.totalNewPosts > 1 ? "s" : "") + " detected across your favorite creators. Incremental sync will download only missing posts."
                                }
                                return modal.tr("msg_batch_sync_desc", "Incremental sync will check all favorited creators and download new posts published since their last sync.")
                            } else if (modal.downloadDialogNewPostCount > 0) {
                                return modal.downloadDialogNewPostCount + " new post" + (modal.downloadDialogNewPostCount > 1 ? "s" : "") + " available since last download (" + (modal.downloadDialogLastPostDate || "previous sync") + ")."
                            } else if (modal.downloadDialogLastPostDate) {
                                return "Artist is up to date with last download (" + modal.downloadDialogLastPostDate + "). Downloading again will check for any newly added files."
                            } else {
                                return "First-time download for this creator. All posts will be downloaded."
                            }
                        }
                    }
                }
            }

            // Page Range Configuration
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: modal.tr("lbl_page_range", "Page Range")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#E2E8F0"
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    // Start Page
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: modal.tr("lbl_start_page", "Start Page:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            radius: 6
                            color: startPageInput.activeFocus ? "#111827" : "#1F2937"
                            border.color: startPageInput.activeFocus ? "#F59E0B" : (startPageBoxMouse.containsMouse ? "#475569" : "#374151")
                            border.width: startPageInput.activeFocus ? 1.5 : 1

                            TextBarContextArea {
                                id: startPageBoxMouse
                                target: startPageInput
                                focusOnLeftClick: true
                            }

                            TextInput {
                                id: startPageInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#F8FAFC"
                                selectionColor: "#0284C7"
                                selectedTextColor: "#FFFFFF"
                                clip: true
                                selectByMouse: true
                                text: modal.downloadDialogStartPage
                                validator: IntValidator { bottom: 1; top: 99999 }
                                onTextChanged: modal.downloadDialogStartPage = text
                                TextBarContextArea {}
                            }
                        }
                    }

                    // End Page
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            text: modal.tr("lbl_end_page", "End Page (optional):")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: 34
                            radius: 6
                            color: endPageInput.activeFocus ? "#111827" : "#1F2937"
                            border.color: endPageInput.activeFocus ? "#F59E0B" : (endPageBoxMouse.containsMouse ? "#475569" : "#374151")
                            border.width: endPageInput.activeFocus ? 1.5 : 1

                            TextBarContextArea {
                                id: endPageBoxMouse
                                target: endPageInput
                                focusOnLeftClick: true
                            }

                            TextInput {
                                id: endPageInput
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                verticalAlignment: TextInput.AlignVCenter
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#F8FAFC"
                                selectionColor: "#0284C7"
                                selectedTextColor: "#FFFFFF"
                                clip: true
                                selectByMouse: true
                                text: modal.downloadDialogEndPage
                                validator: IntValidator { bottom: 1; top: 99999 }
                                onTextChanged: modal.downloadDialogEndPage = text
                                TextBarContextArea {}

                                Text {
                                    text: modal.tr("ph_all_pages", "All pages (blank)")
                                    font: parent.font
                                    color: "#64748B"
                                    visible: !parent.text && !parent.activeFocus
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                Text {
                    text: modal.tr("hint_page_range", "Leave End Page blank to check all pages until already-downloaded posts are reached.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                }
            }

            // Download Location Configuration
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: modal.tr("lbl_download_location", "Download Folder")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: 600
                    color: "#E2E8F0"
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 34
                        radius: 6
                        color: locInput.activeFocus ? "#111827" : "#1F2937"
                        border.color: locInput.activeFocus ? "#F59E0B" : (locBoxMouse.containsMouse ? "#475569" : "#374151")
                        border.width: locInput.activeFocus ? 1.5 : 1

                        TextBarContextArea {
                            id: locBoxMouse
                            target: locInput
                            focusOnLeftClick: true
                        }

                        TextInput {
                            id: locInput
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F8FAFC"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            clip: true
                            selectByMouse: true
                            text: modal.downloadDialogLocation
                            onTextChanged: modal.downloadDialogLocation = text
                            TextBarContextArea {}

                            Text {
                                text: modal.tr("ph_default_location", "Default downloads folder")
                                font: parent.font
                                color: "#64748B"
                                visible: !parent.text && !parent.activeFocus
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                            }
                        }
                    }

                    // Browse Button
                    Rectangle {
                        Layout.preferredWidth: browseBtnText.implicitWidth + 24
                        height: 34
                        radius: 6
                        color: browseLocMouse.containsMouse ? "#374151" : "#1F2937"
                        border.color: "#4B5563"
                        border.width: 1

                        Row {
                            id: browseBtnText
                            anchors.centerIn: parent
                            spacing: 5
                            Text { text: "📁"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: modal.tr("btn_browse", "Browse…")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: "#E2E8F0"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: browseLocMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modal.browseDownloadFolder()
                        }
                    }
                }
            }

            // Location Destination Structure Explanation Box
            Rectangle {
                Layout.fillWidth: true
                radius: 7
                color: "#162032"
                border.color: "#28354E"
                border.width: 1
                implicitHeight: folderExplCol.implicitHeight + 14

                ColumnLayout {
                    id: folderExplCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 4

                    RowLayout {
                        spacing: 6
                        Text { text: modal.downloadDialogIsBatch ? "📁" : "📂"; font.pixelSize: 11 }
                        Text {
                            text: modal.downloadDialogIsBatch
                                  ? modal.tr("lbl_batch_destination_header", "Where will artists be saved?")
                                  : modal.tr("lbl_single_destination_header", "Artist Save Destination:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: "#38BDF8"
                        }
                    }

                    Text {
                        text: modal.downloadDialogIsBatch
                              ? modal.tr("msg_batch_destination_expl", "Each artist will download into their own subfolder inside this directory:")
                              : modal.tr("msg_single_destination_expl", "Files for this creator will be saved directly into:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#CBD5E1"
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        text: {
                            var base = modal.downloadDialogLocation || "Downloads"
                            if (modal.downloadDialogIsBatch) {
                                return base + "/<Artist Name> [<Service>]/"
                            } else {
                                return base
                            }
                        }
                        font.family: "Consolas, 'Courier New', monospace"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#FCD34D"
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                    }

                    Text {
                        visible: modal.downloadDialogIsBatch
                        text: modal.tr("hint_existing_watchlist_folders", "💡 Existing Watchlist artists with custom folder locations will continue using their assigned folders.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Actions Bottom Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Item { Layout.fillWidth: true }

                // Cancel Button
                Rectangle {
                    implicitWidth: cancelBtnText.implicitWidth + 24
                    implicitHeight: 34
                    radius: 6
                    color: cancelDlMouse.containsMouse ? "#374151" : "#1F2937"
                    border.color: "#4B5563"
                    border.width: 1

                    Text {
                        id: cancelBtnText
                        anchors.centerIn: parent
                        text: modal.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: cancelDlMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.downloadDialogVisible = false
                    }
                }

                // Start Download Confirm Button
                Rectangle {
                    implicitWidth: startDlBtnRow.implicitWidth + 26
                    implicitHeight: 34
                    radius: 6
                    color: startDlMouse.containsMouse ? "#D97706" : "#B45309"
                    border.color: "#F59E0B"
                    border.width: 1

                    Row {
                        id: startDlBtnRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "⬇️"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: modal.downloadDialogIsBatch
                                  ? modal.tr("btn_start_sync_all", "Start Sync All")
                                  : modal.tr("btn_start_download", "Start Download")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: 700
                            color: "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: startDlMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.confirmDownload()
                    }
                }
            }
        }
    }
}

