import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Header bar, search/bulk-selection controls, and creator unimported banner for PostSelectionModal.
ColumnLayout {
    id: headerRoot
    required property var modal
    required property var filesModel
    Layout.fillWidth: true
    Layout.fillHeight: false
    spacing: 12

    function setSearchText(value) {
        searchInput.text = value
    }

    // ── Header Row ───────────────────────────────────────────────
    RowLayout {
        Layout.fillWidth: true
        spacing: 10

        // Back Button (when inspecting a single post)
        Rectangle {
            visible: headerRoot.modal.isInspecting
            height: 32
            implicitWidth: backRow.implicitWidth + 16
            radius: 6
            color: backMouse.containsMouse ? "#1E293B" : "#161D2B"
            border.color: backMouse.containsMouse ? "#38BDF8" : "#2D3748"
            scale: backMouse.pressed ? 0.94 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Row {
                id: backRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "←"; font.pixelSize: 13; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: headerRoot.modal.tr("btn_back_to_posts", "Back to Posts")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#E2E8F0"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: backMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: headerRoot.modal.backToPosts()
            }
        }

        // Back to Favorite Artists Button (when opened from Favorites browser)
        Rectangle {
            visible: !headerRoot.modal.isInspecting && headerRoot.modal.fromFavoritesBrowser
            height: 32
            implicitWidth: backFavRow.implicitWidth + 16
            radius: 6
            color: backFavMouse.containsMouse ? "#2A2008" : "#1A170C"
            border.color: backFavMouse.containsMouse ? "#F59E0B" : "#B45309"
            border.width: 1

            Row {
                id: backFavRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "←"; font.pixelSize: 13; color: "#FCD34D"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: headerRoot.modal.tr("btn_back_to_artists", "Back to Favorite Artists")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#FCD34D"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: backFavMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    headerRoot.modal.closeModal()
                    headerRoot.modal.backToFavoritesRequested()
                }
            }
        }

        Text {
            visible: !headerRoot.modal.isInspecting
            text: "🖼️"
            font.pixelSize: 18
        }

        ColumnLayout {
            spacing: 2
            Layout.fillWidth: true

            RowLayout {
                spacing: 8
                Layout.fillWidth: true

                UnimportedTriangleBadge {
                    id: inspectUnimportedBadge
                    objectName: "postSelectionInspectUnimportedBadge"
                    visible: headerRoot.modal.isInspecting && !!(headerRoot.modal.inspectedPost && headerRoot.modal.inspectedPost.is_unimported)
                    showBackground: false
                    tooltipText: headerRoot.modal.tr("warn_post_unimported", "This post has not been fully imported into Pawchive yet — only a preview thumbnail may be available for images.")
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: headerRoot.modal.isInspecting
                        ? (headerRoot.modal.inspectedPost ? headerRoot.modal.inspectedPost.title : "")
                        : headerRoot.modal.tr("title_post_selector", "Select Posts to Download")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: "#F8FAFC"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                UnimportedTriangleBadge {
                    id: creatorUnimportedBadge
                    objectName: "postSelectionCreatorUnimportedBadge"
                    visible: !headerRoot.modal.isInspecting && (headerRoot.modal.hasUnimportedCreator || headerRoot.modal.unimportedCount > 0)
                    showBackground: false
                    tooltipText: headerRoot.modal.hasUnimportedCreator
                        ? headerRoot.modal.tr("warn_creator_unimported", "This creator has not been imported into Pawchive yet — only preview thumbnails may be available for images.")
                        : headerRoot.modal.tr("warn_posts_unimported_some", "Some posts below have not been fully imported into Pawchive yet.")
                    Layout.alignment: Qt.AlignVCenter
                }

                // Creator name or date badge
                Rectangle {
                    height: 20
                    radius: 4
                    color: "#1E293B"
                    border.color: "#334155"
                    implicitWidth: badgeRowText.implicitWidth + 12

                    Row {
                        id: badgeRowText
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: headerRoot.modal.isInspecting
                                ? ("📅 " + (headerRoot.modal.inspectedPost ? headerRoot.modal.inspectedPost.published : ""))
                                : (headerRoot.modal.creatorName.length > 0 ? headerRoot.modal.creatorName : "Pawchive")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#38BDF8"
                        }
                    }
                }

                // Files in Post Selection Pill (when inspecting)
                Rectangle {
                    visible: headerRoot.modal.isInspecting
                    height: 20
                    radius: 4
                    color: headerRoot.modal.selectedFilesInPost > 0 ? "#0C2A3D" : "#2A181A"
                    border.color: headerRoot.modal.selectedFilesInPost > 0 ? "#0284C7" : "#DC2626"
                    implicitWidth: inspectSelPillText.implicitWidth + 12

                    Text {
                        id: inspectSelPillText
                        anchors.centerIn: parent
                        text: headerRoot.modal.selectedFilesInPost + " / " + headerRoot.filesModel.count + " files selected"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        color: headerRoot.modal.selectedFilesInPost > 0 ? "#38BDF8" : "#F87171"
                    }
                }
            }

            Text {
                text: headerRoot.modal.isInspecting
                    ? headerRoot.modal.tr("label_inspect_files_subtitle", "Inspect attachments and toggle individual files to download.")
                    : headerRoot.modal.tr("post_selector_subtitle", "Choose specific posts to download or filter visually by thumbnail.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#94A3B8"
            }
        }

        // Click Mode Toggle Pill (Preview vs Select)
        Rectangle {
            id: clickModeBtn
            objectName: "postClickModeBtn"
            visible: !headerRoot.modal.isInspecting
            height: 28
            radius: 6
            implicitWidth: clickModeRow.implicitWidth + 16
            color: headerRoot.modal.quickSelectClickMode
                ? (clickModeMouse.containsMouse ? "#075985" : "#0C2A3D")
                : (clickModeMouse.containsMouse ? "#1E293B" : "#161D2B")
            border.color: headerRoot.modal.quickSelectClickMode ? "#0284C7" : (clickModeMouse.containsMouse ? "#475569" : "#2D3748")
            scale: clickModeMouse.pressed ? 0.94 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Row {
                id: clickModeRow
                anchors.centerIn: parent
                spacing: 5
                Text {
                    text: headerRoot.modal.quickSelectClickMode ? "⚡" : "🔍"
                    font.pixelSize: 10
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: headerRoot.modal.quickSelectClickMode ? "Click: Select" : "Click: Preview"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: headerRoot.modal.quickSelectClickMode ? "#38BDF8" : "#CBD5E1"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: clickModeMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: headerRoot.modal.quickSelectClickMode = !headerRoot.modal.quickSelectClickMode
            }

            ToolTip.visible: clickModeMouse.containsMouse
            ToolTip.delay: 400
            ToolTip.text: headerRoot.modal.quickSelectClickMode
                ? "Click toggles selection • Ctrl+Click previews post • Shift+Click selects range"
                : "Click previews post • Ctrl+Click toggles selection • Shift+Click selects range"
        }

        // Re-fetch Posts Button (bypasses cache while preserving saved selections)
        Rectangle {
            id: refetchPostsBtn
            objectName: "refetchPostsBtn"
            visible: !headerRoot.modal.isInspecting && !!headerRoot.modal.bridge && !!headerRoot.modal.bridge.refetchPostsForSelection && !headerRoot.modal.fromFavoritesBrowser
            height: 28
            radius: 6
            implicitWidth: refetchRow.implicitWidth + 16
            color: refetchMouse.containsMouse ? "#1E293B" : "#161D2B"
            border.color: refetchMouse.containsMouse ? "#38BDF8" : "#2D3748"
            scale: refetchMouse.pressed ? 0.94 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Row {
                id: refetchRow
                anchors.centerIn: parent
                spacing: 5
                Text {
                    text: "🔄"
                    font.pixelSize: 10
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: headerRoot.modal.tr("action_refetch", "Re-fetch")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    color: refetchMouse.containsMouse ? "#38BDF8" : "#CBD5E1"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: refetchMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    headerRoot.modal.closeModal()
                    if (headerRoot.modal.bridge && headerRoot.modal.bridge.refetchPostsForSelection) {
                        headerRoot.modal.bridge.refetchPostsForSelection()
                    }
                }
            }

            ToolTip.visible: refetchMouse.containsMouse
            ToolTip.delay: 400
            ToolTip.text: "Re-fetch fresh post list from server (your current selections stay saved)"
        }

        // Close Button ✕
        Rectangle {
            width: 28
            height: 28
            radius: 6
            color: closeMouse.containsMouse ? "#1E293B" : "#161D2B"
            border.color: "#2D3748"
            scale: closeMouse.pressed ? 0.92 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Text {
                anchors.centerIn: parent
                text: "✕"
                font.pixelSize: 11
                color: closeMouse.containsMouse ? "#F87171" : "#94A3B8"
            }

            MouseArea {
                id: closeMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: headerRoot.modal.closeModal()
            }
        }
    }

    // ── Search & Bulk Selection Bar (only when not inspecting) ─────
    RowLayout {
        visible: !headerRoot.modal.isInspecting
        Layout.fillWidth: true
        spacing: 8

        // Search Input Field
        Rectangle {
            Layout.fillWidth: true
            height: 32
            radius: 6
            color: searchInput.activeFocus ? "#0B0D12" : "#0B0E14"
            border.color: searchInput.activeFocus ? "#38BDF8" : (postSearchBoxMouse.containsMouse ? "#475569" : "#1E293B")
            border.width: searchInput.activeFocus ? 1.5 : 1

            TextBarContextArea {
                id: postSearchBoxMouse
                target: searchInput
                focusOnLeftClick: true
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text { text: "🔍"; font.pixelSize: 11; color: "#64748B" }

                TextInput {
                    id: searchInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
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
                        text: headerRoot.modal.tr("placeholder_search_posts", "Search posts by title or date...")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#475569"
                        visible: !searchInput.text && !searchInput.activeFocus
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                    }

                    onTextChanged: {
                        headerRoot.modal.searchFilter = text
                        headerRoot.modal.updateFilteredPosts()
                    }
                }

                Text {
                    visible: searchInput.text.length > 0
                    text: "✕"
                    font.pixelSize: 11
                    color: "#64748B"
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: searchInput.text = ""
                    }
                }
            }
        }

        // Select All Button
        Rectangle {
            Layout.preferredHeight: 32
            Layout.preferredWidth: Math.max(116, selAllRow.implicitWidth + 28)
            radius: 6
            color: selAllMouse.containsMouse ? "#1E293B" : "#161D2B"
            border.color: "#2D3748"
            scale: selAllMouse.pressed ? 0.94 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Row {
                id: selAllRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "✓"; font.pixelSize: 11; color: "#38BDF8"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    id: selAllText
                    text: headerRoot.modal.searchFilter.trim() !== ""
                          ? "Select Filtered"
                          : headerRoot.modal.tr("btn_select_all", "Select All")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: selAllMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: headerRoot.modal.selectAll(true)
            }
        }

        // Deselect All Button
        Rectangle {
            Layout.preferredHeight: 32
            Layout.preferredWidth: Math.max(126, deselAllRow.implicitWidth + 28)
            radius: 6
            color: deselAllMouse.containsMouse ? "#1E293B" : "#161D2B"
            border.color: "#2D3748"
            scale: deselAllMouse.pressed ? 0.94 : 1.0
            Behavior on scale { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0 } }

            Row {
                id: deselAllRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "✕"; font.pixelSize: 11; color: "#94A3B8"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    id: deselAllText
                    text: headerRoot.modal.searchFilter.trim() !== ""
                          ? "Deselect Filtered"
                          : headerRoot.modal.tr("btn_deselect_all", "Deselect All")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            MouseArea {
                id: deselAllMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: headerRoot.modal.selectAll(false)
            }
        }
    }

    // Creator-level / unimported posts warning banner
    Rectangle {
        id: creatorUnimportedBanner
        objectName: "postSelectionCreatorUnimportedBanner"
        visible: !headerRoot.modal.isInspecting && (headerRoot.modal.hasUnimportedCreator || headerRoot.modal.unimportedCount > 0)
        Layout.fillWidth: true
        Layout.leftMargin: 20
        Layout.rightMargin: 20
        Layout.topMargin: 10
        Layout.preferredHeight: visible ? (creatorBannerCol.implicitHeight + 14) : 0
        radius: 8
        color: "#291E0B"
        border.color: "#B45309"
        border.width: 1

        RowLayout {
            id: creatorBannerCol
            anchors {
                left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                leftMargin: 12; rightMargin: 12
            }
            spacing: 10

            UnimportedTriangleBadge {
                showBackground: false
                tooltipText: ""
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                Layout.fillWidth: true
                text: headerRoot.modal.hasUnimportedCreator
                    ? headerRoot.modal.tr("warn_creator_unimported", "This creator has not been imported into Pawchive yet — full-resolution media is only served directly from the origin service when available. Only thumbnails may be previewable.")
                    : headerRoot.modal.tr("warn_posts_unimported_some", "Some posts below are not fully imported into Pawchive yet (marked with ⚠️) — full-resolution media may not be previewable until imported.")
                color: "#FCD34D"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
        }
    }
}
