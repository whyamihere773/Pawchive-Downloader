import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Popup {
    id: newPostsModal
    required property var view
    anchors.centerIn: Overlay.overlay
    width: Math.min(720, Math.max(460, newPostsModal.view.width * 0.68))
    height: Math.min(600, Math.max(380, newPostsModal.view.height * 0.72))
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        radius: 12
        color: "#0F1420"
        border.color: "#38BDF8"
        border.width: 1.5
    }

    contentItem: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: "🔎 Newer Posts Check — " + (newPostsModal.view.selectedCreator ? (newPostsModal.view.selectedCreator.name || "Creator") : "Creator")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 15
                font.weight: Font.Bold
                color: "#F8FAFC"
                elide: Text.ElideRight
            }
            Rectangle {
                visible: !!(newPostsModal.view.bBridge && newPostsModal.view.selectedCreator && !newPostsModal.view.bBridge.isCheckingNewPosts)
                Layout.preferredHeight: 30
                implicitWidth: findSiteTxt.implicitWidth + 16
                radius: 7
                color: findSiteMouse.containsMouse ? "#1E293B" : "#151C2B"
                border.color: "#38BDF8"
                border.width: 1
                Springy { hover: findSiteMouse.containsMouse; pressed: findSiteMouse.pressed }
                Text {
                    id: findSiteTxt
                    anchors.centerIn: parent
                    text: "🔎 Switch Site"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#38BDF8"
                }
                MouseArea {
                    id: findSiteMouse
                    objectName: "searchSitesBtnMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (newPostsModal.view.bBridge && newPostsModal.view.selectedCreator) {
                            newPostsModal.view.bBridge.searchCreatorAcrossSites(newPostsModal.view.selectedCreator)
                        }
                    }
                }
            }
            Rectangle {
                visible: !!(newPostsModal.view.bBridge && newPostsModal.view.bBridge.newPostsCount > 0)
                Layout.preferredHeight: 30
                implicitWidth: dlAllNewTxt.implicitWidth + 18
                radius: 7
                color: dlAllNewMouse.containsMouse ? "#10B981" : "#059669"
                Springy { hover: dlAllNewMouse.containsMouse; pressed: dlAllNewMouse.pressed }
                Text {
                    id: dlAllNewTxt
                    anchors.centerIn: parent
                    text: "⬇ Download All (" + ((newPostsModal.view.bBridge ? newPostsModal.view.bBridge.newPostsCount : 0)) + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }
                MouseArea {
                    id: dlAllNewMouse
                    objectName: "downloadAllNewPostsMouse"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (newPostsModal.view.bBridge) {
                            var nList = newPostsModal.view.bBridge.newPostsList || []
                            var items = []
                            var selC = newPostsModal.view.selectedCreator || ({})
                            for (var i = 0; i < nList.length; i++) {
                                var np = nList[i]
                                if (np && np.url) {
                                    items.push({
                                        url: String(np.url),
                                        title: String(np.title || ("Post #" + (np.post_id || ""))),
                                        creator_name: String(np.creator_name || selC.name || selC.creator_name || ""),
                                        creator_id: String(np.creator_id || selC.creator_id || selC.id || ""),
                                        service: String(np.service || selC.service || ""),
                                        service_label: String(np.service_label || selC.service_label || np.service || ""),
                                        item_type: "post"
                                    })
                                }
                            }
                            if (items.length > 0) {
                                newPostsModal.close()
                                newPostsModal.view.openDownloadModalForItems(items, "Download " + items.length + " Newer Post(s)", true, "new_posts")
                            }
                        }
                    }
                }
            }
            Rectangle {
                width: 28; height: 28; radius: 6; color: "#1E293B"
                Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8" }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: newPostsModal.close() }
            }
        }

        Text {
            Layout.fillWidth: true
            text: (newPostsModal.view.bBridge && newPostsModal.view.bBridge.newPostsStatusText) ? newPostsModal.view.bBridge.newPostsStatusText : "Comparing remote posts with your downloaded archive and local folders…"
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            color: (newPostsModal.view.bBridge && newPostsModal.view.bBridge.isCheckingNewPosts) ? "#38BDF8" : "#94A3B8"
            wrapMode: Text.WordWrap
        }

        SmoothListView {
            id: newPostsListView
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            visible: !!(newPostsModal.view.bBridge && newPostsModal.view.bBridge.newPostsCount > 0)
            model: newPostsModal.view.bBridge ? newPostsModal.view.bBridge.newPostsList : []

            delegate: Rectangle {
                readonly property var npItem: modelData || ({})
                width: newPostsListView.width - 8
                height: 68
                radius: 8
                color: npHover.hovered ? "#162033" : "#111827"
                border.color: npHover.hovered ? "#38BDF8" : "#1E293B"
                border.width: 1
                HoverHandler { id: npHover }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    Rectangle {
                        Layout.preferredWidth: 52
                        Layout.preferredHeight: 52
                        radius: 6
                        color: "#090C12"
                        clip: true
                        Image {
                            anchors.fill: parent
                            asynchronous: true
                            fillMode: Image.PreserveAspectCrop
                            source: newPostsModal.view.browserThumbUrl(npItem.thumbnail_url, npItem.provider_id || newPostsModal.view.activeProvider)
                            sourceSize: Qt.size(110, 110)
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 3
                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: (npItem.is_dm ? "💬 DM  •  " : "") + (npItem.title || ("Post #" + (npItem.post_id || "")))
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: npItem.is_dm ? "#E9D5FF" : "#F1F5F9"
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: (npItem.published_at || "No date") + "  •  " + Number(npItem.file_count || 0) + " file(s)"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            elide: Text.ElideRight
                        }
                    }

                    Rectangle {
                        Layout.preferredHeight: 28
                        implicitWidth: npViewTxt.implicitWidth + 14
                        radius: 6
                        color: npViewMouse.containsMouse ? "#1E293B" : "#151C2B"
                        border.color: "#38BDF8"
                        border.width: 1
                        Text {
                            id: npViewTxt
                            anchors.centerIn: parent
                            text: "🔍 Open"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#38BDF8"
                        }
                        MouseArea {
                            id: npViewMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (newPostsModal.view.bBridge) {
                                    newPostsModal.close()
                                    newPostsModal.view.bBridge.openPostDetail(npItem)
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.preferredHeight: 28
                        implicitWidth: npDlTxt.implicitWidth + 14
                        radius: 6
                        color: npDlMouse.containsMouse ? "#10B981" : "#059669"
                        Text {
                            id: npDlTxt
                            anchors.centerIn: parent
                            text: "🚀 Download"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: npDlMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (newPostsModal.view.bBridge && npItem.url) {
                                    var selC = newPostsModal.view.selectedCreator || ({})
                                    newPostsModal.close()
                                    newPostsModal.view.openDownloadModalForItems([{
                                        url: String(npItem.url),
                                        title: String(npItem.title || ("Post #" + (npItem.post_id || ""))),
                                        creator_name: String(npItem.creator_name || selC.name || selC.creator_name || ""),
                                        creator_id: String(npItem.creator_id || selC.creator_id || selC.id || ""),
                                        service: String(npItem.service || selC.service || ""),
                                        service_label: String(npItem.service_label || selC.service_label || npItem.service || ""),
                                        item_type: "post"
                                    }], "Download: " + String(npItem.title || "Post"), true, "new_posts")
                                }
                            }
                        }
                    }
                }
            }
        }

        // Cross-Site Match Picker (when an unlinked local folder matched multiple profiles across sites, or user clicked Switch Site)
        SmoothListView {
            id: creatorMatchesListView
            objectName: "creatorMatchesListView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            visible: !!(newPostsModal.view.bBridge && newPostsModal.view.bBridge.creatorSearchMatchCount > 0 && newPostsModal.view.bBridge.newPostsCount === 0 && !newPostsModal.view.bBridge.isCheckingNewPosts)
            model: newPostsModal.view.bBridge ? newPostsModal.view.bBridge.creatorSearchMatches : []

            delegate: Rectangle {
                readonly property var mItem: modelData || ({})
                width: creatorMatchesListView.width - 8
                height: 64
                radius: 8
                color: mHover.hovered ? "#162033" : "#111827"
                border.color: mHover.hovered ? "#38BDF8" : "#1E293B"
                border.width: 1
                HoverHandler { id: mHover }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10

                    Rectangle {
                        Layout.preferredHeight: 26
                        implicitWidth: mSiteTxt.implicitWidth + 14
                        radius: 6
                        color: "#0F172A"
                        border.color: "#334155"
                        border.width: 1
                        Text {
                            id: mSiteTxt
                            anchors.centerIn: parent
                            text: (mItem.provider_icon ? (mItem.provider_icon + " ") : "") + (mItem.provider_name || mItem.provider_id || "Site")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#38BDF8"
                        }
                    }

                    Rectangle {
                        Layout.preferredHeight: 24
                        implicitWidth: mSvcTxt.implicitWidth + 12
                        radius: 5
                        color: "#1E293B"
                        Text {
                            id: mSvcTxt
                            anchors.centerIn: parent
                            text: mItem.service_label || mItem.service || "Creator"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#E2E8F0"
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: mItem.name || mItem.creator_id || "Creator"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "id: " + (mItem.creator_id || "")
                                  + (Number(mItem.post_count || 0) > 0 ? ("  •  " + Number(mItem.post_count || 0) + " posts") : "")
                                  + (Number(mItem.dm_count || 0) > 0 ? ("  •  💬 " + Number(mItem.dm_count || 0) + " DMs") : "")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#94A3B8"
                            elide: Text.ElideRight
                        }
                    }

                    Rectangle {
                        Layout.preferredHeight: 30
                        implicitWidth: selMatchTxt.implicitWidth + 18
                        radius: 6
                        color: selMatchMouse.containsMouse ? "#10B981" : "#059669"
                        Springy { hover: selMatchMouse.containsMouse; pressed: selMatchMouse.pressed }
                        Text {
                            id: selMatchTxt
                            anchors.centerIn: parent
                            text: "✓ Select & Check"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: selMatchMouse
                            objectName: "selectCreatorMatchMouse"
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (newPostsModal.view.bBridge) {
                                    newPostsModal.view.bBridge.selectCreatorMatchAndCheck(mItem)
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !(newPostsModal.view.bBridge && (newPostsModal.view.bBridge.newPostsCount > 0 || (newPostsModal.view.bBridge.creatorSearchMatchCount > 0 && !newPostsModal.view.bBridge.isCheckingNewPosts)))
            radius: 8
            color: "#0B0F19"
            border.color: "#1E293B"
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 6
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: (newPostsModal.view.bBridge && newPostsModal.view.bBridge.isCheckingNewPosts)
                          ? "⌛"
                          : ((newPostsModal.view.bBridge && String(newPostsModal.view.bBridge.newPostsStatusText || "").toLowerCase().indexOf("could not") >= 0) ? "🔎" : "✅")
                    font.pixelSize: 28
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    width: 460
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: (newPostsModal.view.bBridge && newPostsModal.view.bBridge.isCheckingNewPosts)
                          ? "Searching sites / checking creator posts online…"
                          : ((newPostsModal.view.bBridge && newPostsModal.view.bBridge.newPostsStatusText) ? newPostsModal.view.bBridge.newPostsStatusText : "All recent posts appear to be downloaded.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#CBD5E1"
                }
            }
        }
    }
}
