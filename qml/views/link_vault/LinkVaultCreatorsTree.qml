import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── 3. Tree View of Creators > Posts > Links ───────────────────────────
Item {
    id: creatorsTree
    required property var view
    readonly property bool isScrolling: creatorFlickable.isScrolling
    Layout.fillWidth: true
    Layout.fillHeight: true

    opacity: creatorsTree.view.entranceStage >= 3 ? 1.0 : 0.0
    transform: Translate {
        y: creatorsTree.view.entranceStage >= 3 ? 0 : 20
        Behavior on y {
            SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
        }
    }
    Behavior on opacity { NumberAnimation { duration: 180 } }

    // Empty State Graphic
    Rectangle {
        anchors.centerIn: parent
        visible: !creatorsTree.view.vaultModel || creatorsTree.view.vaultModel.count === 0
        width: Math.min(parent.width - 40, 380)
        height: 200
        color: "#141720"
        radius: 10
        border.color: "#1E2430"
        border.width: 1

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 8

            Text { text: "🔗"; font.pixelSize: 32; Layout.alignment: Qt.AlignHCenter }
            Text {
                text: creatorsTree.view.tr("vault_empty_title", "Link Vault is Empty")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 15
                font.weight: Font.Bold
                color: "#F8FAFC"
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                text: creatorsTree.view.tr("vault_empty_desc", "When you scrape creators or posts, all cloud links (Mega, Drive, Pixeldrain, etc.) and passwords are automatically saved here permanently.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: Math.min(parent.parent.width - 40, 320)
            }
        }
    }

    // High-Performance Momentum Scrollable List of Creators (SettingsView scroll tech)
    // Only the creator cards on screen are built (one card per creator froze big vaults)
    SmoothListView {
        id: creatorFlickable
        anchors.fill: parent
        visible: !!creatorsTree.view.vaultModel && creatorsTree.view.vaultModel.count > 0
        spacing: 10
        cacheBuffer: 800
        currentIndex: -1
        highlightFollowsCurrentItem: false
        bottomMargin: 24
        model: creatorsTree.view.vaultModel

                delegate: Rectangle {
                    id: creatorCard
                    width: creatorFlickable.width - (creatorFlickable.verticalScrollBar && creatorFlickable.verticalScrollBar.visible ? 10 : 0)
                    implicitHeight: creatorCol.implicitHeight + 20
            radius: 8
            color: creatorHover.hovered ? "#181D2A" : "#141720"
            border.color: isExpanded ? "#38BDF8" : (creatorHover.hovered ? "#334155" : "#1E2430")
            border.width: 1

            readonly property var creatorItem: modelData
            readonly property bool isExpanded: !!creatorsTree.view.expandedCreators[creatorItem.creator_key]

            transform: Translate {
                y: creatorHover.hovered && !creatorsTree.view.isScrolling ? -2.5 : 0
                Behavior on y {
                    SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                }
            }
            Behavior on color { ColorAnimation { duration: 140 } }
            Behavior on border.color { ColorAnimation { duration: 140 } }

            HoverHandler { id: creatorHover }

            ColumnLayout {
                id: creatorCol
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                // ── Level 1: Creator Header Row ────────────────────────
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        id: expandBtn
                        width: 24
                        height: 24
                        radius: 4
                        color: expMouse.containsMouse ? "#334155" : "#1E2430"
                        // Use NumberAnimation instead of SpringAnimation to avoid
                        // restarting the animation from 0 every time the delegate is reused
                        scale: expMouse.pressed ? 0.88 : (expMouse.containsMouse ? 1.1 : 1.0)
                        Behavior on scale {
                            NumberAnimation { duration: 110; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                        }
                        Behavior on color { ColorAnimation { duration: 110 } }
                        Text {
                            anchors.centerIn: parent
                            text: creatorCard.isExpanded ? "▼" : "▶"
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                        MouseArea {
                            id: expMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: creatorsTree.view.toggleCreator(creatorItem.creator_key)
                        }
                    }

                    // Service Badge
                    Rectangle {
                        height: 20
                        implicitWidth: serviceText.implicitWidth + 14
                        radius: 4
                        color: creatorsTree.view.serviceColor(creatorItem.service)
                        Text {
                            id: serviceText
                            anchors.left: parent.left
                            anchors.leftMargin: 7
                            anchors.verticalCenter: parent.verticalCenter
                            text: (creatorItem.service || "").toUpperCase()
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                    }

                    // Creator Name
                    Text {
                        text: creatorItem.creator_name || "Unknown"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // User ID Pill
                    Text {
                        text: "#" + creatorItem.user_id
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    // Post Count Badge
                    Rectangle {
                        height: 20
                        implicitWidth: postCountText.implicitWidth + 16
                        radius: 10
                        color: "#1E293B"
                        border.color: "#334155"
                        border.width: 1
                        Text {
                            id: postCountText
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: creatorItem.post_count + " " + creatorsTree.view.tr("vault_posts_badge", "Posts")
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                    }

                    // Link Count Badge
                    Rectangle {
                        height: 20
                        implicitWidth: linkCountText.implicitWidth + 16
                        radius: 10
                        color: "#0C4A6E"
                        border.color: "#0284C7"
                        border.width: 1
                        Text {
                            id: linkCountText
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: creatorItem.link_count + " " + creatorsTree.view.tr("vault_links_badge", "Links")
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            color: "#38BDF8"
                        }
                    }

                    // Copy Creator Links Button
                    Rectangle {
                        width: 24
                        height: 24
                        radius: 4
                        color: copyCreatorMouse.containsMouse ? "#1E293B" : "transparent"
                        border.color: copyCreatorMouse.containsMouse ? "#38BDF8" : "transparent"
                        border.width: 1
                        scale: copyCreatorMouse.pressed ? 0.86 : (copyCreatorMouse.containsMouse ? 1.12 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                        Text {
                            anchors.centerIn: parent
                            text: "📋"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            id: copyCreatorMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: creatorsTree.view.tr("tip_copy_creator_links", "Copy all links for this artist to clipboard")
                            onClicked: {
                                if (creatorsTree.view.bridge) {
                                    var count = creatorsTree.view.bridge.copyVaultLinks(creatorItem.creator_key)
                                    creatorsTree.view.showToast(creatorsTree.view.tr("toast_links_copied", "Copied to clipboard: ") + count + " " + creatorsTree.view.tr("vault_links_pill", "Links"))
                                }
                            }
                        }
                    }

                    // Delete Creator Button
                    Rectangle {
                        width: 24
                        height: 24
                        radius: 4
                        color: delCreatorMouse.containsMouse ? "#3B181E" : "transparent"
                        scale: delCreatorMouse.pressed ? 0.86 : (delCreatorMouse.containsMouse ? 1.12 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                        Text {
                            anchors.centerIn: parent
                            text: "🗑️"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            id: delCreatorMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: creatorsTree.view.tr("tip_delete_creator", "Delete this artist and all their harvested links")
                            onClicked: {
                                if (creatorsTree.view.bridge) creatorsTree.view.bridge.deleteVaultCreator(creatorItem.creator_key)
                            }
                        }
                    }
                }

                // ── Level 2: Posts List (Visible when Creator is expanded) ────
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: creatorCard.isExpanded
                    spacing: 8
                    Layout.leftMargin: 16

                    Repeater {
                        model: creatorCard.isExpanded ? creatorItem.posts : null

                        delegate: Rectangle {
                            id: postBox
                            Layout.fillWidth: true
                            implicitHeight: postCol.implicitHeight + 14
                            color: "#0F1219"
                            radius: 6
                            border.color: "#1E2430"
                            border.width: 1

                            readonly property var postItem: modelData
                            readonly property bool isTextExpanded: !!creatorsTree.view.expandedPostTexts[postItem.post_id]

                            ColumnLayout {
                                id: postCol
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 6

                                // Post Header
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text { text: "📝"; font.pixelSize: 12 }
                                    Text {
                                        text: postItem.title || "Untitled Post"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        font.weight: 600
                                        color: "#E2E8F0"
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    // Date pill
                                    Text {
                                        visible: postItem.published ? true : false
                                        text: (postItem.published || "").substring(0, 10)
                                        font.pixelSize: 10
                                        color: "#64748B"
                                    }

                                    // Toggle Full Text Drawer Button
                                    Rectangle {
                                        height: 22
                                        implicitWidth: txtBtnText.implicitWidth + 16
                                        radius: 4
                                        color: txtBtnMouse.containsMouse ? "#1E293B" : "#141720"
                                        border.color: "#334155"
                                        border.width: 1
                                        scale: txtBtnMouse.pressed ? 0.90 : (txtBtnMouse.containsMouse ? 1.05 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                        Text {
                                            id: txtBtnText
                                            anchors.centerIn: parent
                                            text: postBox.isTextExpanded ? creatorsTree.view.tr("vault_hide_text", "Hide Text") : creatorsTree.view.tr("vault_view_text", "View Text")
                                            font.pixelSize: 9
                                            color: "#94A3B8"
                                        }
                                        MouseArea {
                                            id: txtBtnMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: creatorsTree.view.togglePostText(postItem.post_id)
                                        }
                                    }

                                    // Delete Post Button
                                    Rectangle {
                                        width: 22
                                        height: 22
                                        radius: 4
                                        color: delPostMouse.containsMouse ? "#3B181E" : "transparent"
                                        scale: delPostMouse.pressed ? 0.86 : (delPostMouse.containsMouse ? 1.12 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                        Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 10; color: "#EF4444" }
                                        MouseArea {
                                            id: delPostMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: creatorsTree.view.tr("tip_delete_post", "Delete this post and its links from vault")
                                            onClicked: {
                                                if (creatorsTree.view.bridge) creatorsTree.view.bridge.deleteVaultPost(postItem.post_id)
                                            }
                                        }
                                    }
                                }

                                // Full Uncapped Text Preview Drawer
                                Rectangle {
                                    Layout.fillWidth: true
                                    visible: postBox.isTextExpanded
                                    implicitHeight: fullTextArea.implicitHeight + 16
                                    color: "#080A0F"
                                    radius: 4
                                    border.color: "#1E2430"
                                    border.width: 1

                                    TextEdit {
                                        id: fullTextArea
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        text: creatorsTree.view.cleanHtml(postItem.full_text)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 12
                                        color: "#CBD5E1"
                                        selectionColor: "#0284C7"
                                        selectedTextColor: "#FFFFFF"
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: TextEdit.Wrap
                                        TextBarContextArea {}
                                    }
                                }

                                // ── Level 3: Links Rows ────────────────────────────────
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Layout.leftMargin: 8

                                    Repeater {
                                        model: creatorCard.isExpanded ? postItem.links : null

                                        delegate: Rectangle {
                                            id: linkRowRect
                                            Layout.fillWidth: true
                                            implicitHeight: Math.max(34, linkInnerRow.implicitHeight + 8)
                                            color: linkHover.hovered ? "#141A26" : "#0D1017"
                                            radius: 4
                                            border.color: linkHover.hovered ? "#38BDF8" : "#1E2430"
                                            border.width: 1

                                            readonly property var linkItem: modelData

                                            transform: Translate {
                                                y: linkHover.hovered && !creatorsTree.view.isScrolling ? -1.5 : 0
                                                Behavior on y {
                                                     SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                                }
                                            }
                                            Behavior on border.color { ColorAnimation { duration: 120 } }
                                            Behavior on color { ColorAnimation { duration: 120 } }

                                            HoverHandler { id: linkHover }

                                            RowLayout {
                                                id: linkInnerRow
                                                anchors.fill: parent
                                                anchors.leftMargin: 8
                                                anchors.rightMargin: 8
                                                spacing: 8

                                                // Host Platform Badge
                                                Rectangle {
                                                    height: 20
                                                    implicitWidth: hostText.implicitWidth + 14
                                                    radius: 4
                                                    color: creatorsTree.view.platformColor(linkItem.platform)
                                                    Text {
                                                        id: hostText
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 7
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: (linkItem.platform || "URL").toUpperCase()
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                        color: "#FFFFFF"
                                                    }
                                                }

                                                // Health Status Badge Pill
                                                Rectangle {
                                                    id: healthPillRect
                                                    height: 20
                                                    implicitWidth: healthDot.width + healthText.implicitWidth + 19
                                                    radius: 4
                                                    color: "#141720"
                                                    border.color: creatorsTree.view.healthColor(linkItem.health)
                                                    border.width: 1

                                                    Rectangle {
                                                        id: healthDot
                                                        width: 6; height: 6; radius: 3
                                                        color: creatorsTree.view.healthColor(linkItem.health)
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 7
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                    Text {
                                                        id: healthText
                                                        anchors.left: healthDot.right
                                                        anchors.leftMargin: 4
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: creatorsTree.view.healthLabel(linkItem.health)
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                        color: creatorsTree.view.healthColor(linkItem.health)
                                                    }
                                                }

                                                // URL text
                                                Text {
                                                    text: linkItem.url || ""
                                                    font.family: "Segoe UI, sans-serif"
                                                    font.pixelSize: 11
                                                    color: "#38BDF8"
                                                    elide: Text.ElideMiddle
                                                    Layout.fillWidth: true
                                                }

                                                // Password Pills
                                                Flow {
                                                    spacing: 4
                                                    Repeater {
                                                        model: creatorCard.isExpanded ? (linkItem.passwords || []) : null

                                                        delegate: Rectangle {
                                                            id: pwPill
                                                            height: 22
                                                            implicitWidth: pwInnerRow.implicitWidth + 14
                                                            radius: 4
                                                            color: pwMouse.containsMouse ? "#2E1065" : "#1E1B4B"
                                                            border.color: "#818CF8"
                                                            border.width: 1

                                                            scale: pwMouse.pressed ? 0.90 : (pwMouse.containsMouse ? 1.08 : 1.0)
                                                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }

                                                            Row {
                                                                id: pwInnerRow
                                                                anchors.centerIn: parent
                                                                spacing: 4
                                                                Text { text: "🔑"; font.pixelSize: 9 }
                                                                Text {
                                                                    id: pwText
                                                                    text: modelData
                                                                    font.family: "Segoe UI, sans-serif"
                                                                    font.pixelSize: 10
                                                                    font.weight: Font.Bold
                                                                    color: "#E0E7FF"
                                                                }
                                                            }

                                                            MouseArea {
                                                                id: pwMouse
                                                                anchors.fill: parent
                                                                hoverEnabled: true
                                                                cursorShape: Qt.PointingHandCursor
                                                                ToolTip.visible: containsMouse
                                                                ToolTip.delay: 200
                                                                ToolTip.text: creatorsTree.view.tr("tip_copy_pw", "Click to copy password: ") + modelData
                                                                onClicked: {
                                                                    creatorsTree.view.copyText(modelData)
                                                                    creatorsTree.view.showToast(creatorsTree.view.tr("toast_pw_copied", "Password copied: ") + modelData)
                                                                }
                                                                onDoubleClicked: {
                                                                    creatorsTree.view.openEditPasswordModal(linkItem.id, linkItem.url, (linkItem.passwords || []).join(", "))
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                // Edit / Add Password Button
                                                Rectangle {
                                                    height: 22
                                                    width: 22
                                                    radius: 4
                                                    color: editPwMouse.containsMouse ? "#334155" : "#141720"
                                                    border.color: editPwMouse.containsMouse ? "#38BDF8" : "#283042"
                                                    border.width: 1
                                                    scale: editPwMouse.pressed ? 0.88 : (editPwMouse.containsMouse ? 1.10 : 1.0)
                                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✏️"
                                                        font.pixelSize: 10
                                                    }

                                                    MouseArea {
                                                        id: editPwMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 200
                                                        ToolTip.text: (linkItem.passwords && linkItem.passwords.length > 0) ? creatorsTree.view.tr("tip_edit_pw", "Edit passwords for this link") : creatorsTree.view.tr("tip_add_pw", "Add password for this link")
                                                        onClicked: {
                                                            creatorsTree.view.openEditPasswordModal(linkItem.id, linkItem.url, (linkItem.passwords || []).join(", "))
                                                        }
                                                    }
                                                }

                                                // Password Source Indicator Pill
                                                Rectangle {
                                                    visible: linkItem.password_source && linkItem.password_source !== "post"
                                                    height: 18
                                                    implicitWidth: srcText.implicitWidth + 10
                                                    radius: 3
                                                    color: "#1E293B"
                                                    border.color: "#334155"
                                                    border.width: 1
                                                    Text {
                                                        id: srcText
                                                        anchors.left: parent.left
                                                        anchors.leftMargin: 5
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: linkItem.password_source === "proximity" ? "📍 Near" : "🔗 Cross"
                                                        font.pixelSize: 8
                                                        color: "#94A3B8"
                                                    }
                                                }

                                                // Open URL in Browser Button
                                                Rectangle {
                                                    width: 24; height: 24; radius: 4
                                                    color: openBtnMouse.containsMouse ? "#1E293B" : "transparent"
                                                    scale: openBtnMouse.pressed ? 0.86 : (openBtnMouse.containsMouse ? 1.12 : 1.0)
                                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                    Text { anchors.centerIn: parent; text: "🌐"; font.pixelSize: 11 }
                                                    MouseArea {
                                                        id: openBtnMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 200
                                                        ToolTip.text: creatorsTree.view.tr("tip_open_browser", "Open in Web Browser")
                                                        onClicked: Qt.openUrlExternally(linkItem.url)
                                                    }
                                                }

                                                // Copy URL Button
                                                Rectangle {
                                                    width: 24; height: 24; radius: 4
                                                    color: copyBtnMouse.containsMouse ? "#1E293B" : "transparent"
                                                    scale: copyBtnMouse.pressed ? 0.86 : (copyBtnMouse.containsMouse ? 1.12 : 1.0)
                                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                    Text { anchors.centerIn: parent; text: "📋"; font.pixelSize: 11 }
                                                    MouseArea {
                                                        id: copyBtnMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 200
                                                        ToolTip.text: creatorsTree.view.tr("tip_copy_link", "Copy link URL")
                                                        onClicked: {
                                                            creatorsTree.view.copyText(linkItem.url)
                                                            creatorsTree.view.showToast(creatorsTree.view.tr("toast_link_copied", "URL copied to clipboard!"))
                                                        }
                                                    }
                                                }

                                                // Delete Link Button
                                                Rectangle {
                                                    width: 24; height: 24; radius: 4
                                                    color: delLinkMouse.containsMouse ? "#3B181E" : "transparent"
                                                    scale: delLinkMouse.pressed ? 0.86 : (delLinkMouse.containsMouse ? 1.12 : 1.0)
                                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                                    Text { anchors.centerIn: parent; text: "✖"; font.pixelSize: 10; color: "#EF4444" }
                                                    MouseArea {
                                                        id: delLinkMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        ToolTip.visible: containsMouse
                                                        ToolTip.delay: 200
                                                        ToolTip.text: creatorsTree.view.tr("tip_delete_link", "Delete link from vault")
                                                        onClicked: {
                                                            if (creatorsTree.view.bridge) creatorsTree.view.bridge.deleteVaultLink(linkItem.id)
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
