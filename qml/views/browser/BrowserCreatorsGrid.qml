import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: creatorsGridPane
    required property var view
    required property bool showingPostsGrid
    anchors.fill: parent

    SmoothGridView {
        id: creatorsGrid
        property int markAnchor: -1
        property string markAnchorKey: ""
        property bool markAnchorState: true
        anchors.fill: parent
        visible: !creatorsGridPane.showingPostsGrid
        cellWidth: width > 0 ? Math.min(width, Math.max(270, Math.floor(width / Math.max(1, Math.floor(width / 290))))) : 280
        cellHeight: 176
        cacheBuffer: 640
        model: creatorsGridPane.view.bBridge ? creatorsGridPane.view.bBridge.creatorsModel : null

        delegate: Item {
            width: creatorsGrid.cellWidth
            height: creatorsGrid.cellHeight

            readonly property var cData: model.creator || modelData || ({})
            readonly property bool isMarked: !!cData.is_marked
            readonly property bool onDisk: !!cData.is_on_disk

            Rectangle {
                id: cCard
                anchors.fill: parent
                anchors.margins: 5
                radius: 10
                color: cCardHover.hovered ? "#161E2E" : "#111622"
                border.color: isMarked ? "#A78BFA" : (onDisk ? "#10B981" : (cCardHover.hovered ? "#38BDF8" : "#1E293B"))
                border.width: (isMarked || onDisk) ? 1.5 : 1
                clip: true

                HoverHandler { id: cCardHover }

                ColumnLayout {
                    z: 1
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 7

                    // Top Row: Avatar + Name/Service + Right Action Buttons (strictly bounded, never overflows)
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        Rectangle {
                            Layout.preferredWidth: 44
                            Layout.preferredHeight: 44
                            Layout.minimumWidth: 44
                            Layout.maximumWidth: 44
                            radius: 22
                            color: "#1E293B"
                            border.color: onDisk ? "#10B981" : "#334155"
                            border.width: 1
                            clip: true

                            Text {
                                anchors.centerIn: parent
                                visible: cardAvatarImg.status !== Image.Ready || cardAvatarImg.implicitWidth <= 2
                                text: ((cData.name || cData.creator_name || "?").trim().charAt(0) || "?").toUpperCase()
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 16
                                font.weight: Font.Bold
                                color: "#7DD3FC"
                            }

                            Image {
                                id: cardAvatarImg
                                anchors.fill: parent
                                opacity: (status === Image.Ready && implicitWidth > 2) ? 1.0 : 0.0
                                source: creatorsGridPane.view.browserThumbUrl(cData.avatar_url, cData.provider_id || creatorsGridPane.view.activeProvider)
                                sourceSize: Qt.size(96, 96)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 3

                            Text {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: cData.name || cData.creator_name || "Unknown"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 13
                                font.weight: Font.Bold
                                color: "#F8FAFC"
                                elide: Text.ElideRight
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 5
                                Rectangle {
                                    Layout.preferredHeight: 18
                                    Layout.preferredWidth: Math.min(82, svcBadgeTxt.implicitWidth + 10)
                                    Layout.minimumWidth: 0
                                    clip: true
                                    radius: 4
                                    color: "#1E293B"
                                    Text {
                                        id: svcBadgeTxt
                                        anchors.centerIn: parent
                                        width: Math.min(implicitWidth, parent.width - 6)
                                        horizontalAlignment: Text.AlignHCenter
                                        elide: Text.ElideRight
                                        text: (cData.service_label || cData.service || "").toUpperCase()
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#38BDF8"
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    visible: !!(cData.updated_at)
                                    text: cData.updated_at || ""
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                    elide: Text.ElideRight
                                }
                            }
                        }

                        Row {
                            spacing: 4
                            Layout.alignment: Qt.AlignVCenter
                            z: 3

                            UnimportedTriangleBadge {
                                objectName: "creatorUnimportedBadge"
                                visible: !creatorsGridPane.view.isLocalMode && !!cData.is_unimported
                                anchors.verticalCenter: parent.verticalCenter
                                width: 22
                                height: 22
                                tooltipText: "Previews only (creator not yet imported)"
                            }

                            // Favorite / Unfavorite Creator Button (Online Mode)
                            Rectangle {
                                objectName: "creatorFavBtn"
                                visible: !creatorsGridPane.view.isLocalMode && !!creatorsGridPane.view.activeCaps.supportsFavorites
                                readonly property bool isFav: !!cData.is_favorited
                                width: 28
                                height: 28
                                radius: 7
                                color: isFav ? "#422006" : (creatorFavMouse.containsMouse ? "#1E293B" : "#151C2B")
                                border.color: isFav ? "#F59E0B" : "#334155"
                                border.width: 1
                                Springy { hover: creatorFavMouse.containsMouse; pressed: creatorFavMouse.pressed }

                                Text {
                                    id: creatorFavStarTxt
                                    objectName: "creatorFavStarTxt"
                                    anchors.centerIn: parent
                                    text: parent.isFav ? "★" : "☆"
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    color: parent.isFav ? "#FBBF24" : "#94A3B8"
                                }
                                MouseArea {
                                    id: creatorFavMouse
                                    objectName: "creatorFavMouse"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    preventStealing: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.text: parent.isFav
                                                  ? "Remove from " + creatorsGridPane.view.activeProviderDisplayName + " favorites"
                                                  : "Add to " + creatorsGridPane.view.activeProviderDisplayName + " favorites"
                                    onClicked: {
                                        if (creatorsGridPane.view.bBridge && cData) {
                                            creatorsGridPane.view.bBridge.toggleFavoriteCreator(cData)
                                        }
                                    }
                                }
                            }

                            // Mark / Unmark Creator Button (Online Mode)
                            Rectangle {
                                visible: !creatorsGridPane.view.isLocalMode
                                width: 28
                                height: 28
                                radius: 7
                                color: isMarked ? "#4C1D95" : (mkMouse.containsMouse ? "#1E293B" : "#151C2B")
                                border.color: isMarked ? "#A78BFA" : "#334155"
                                border.width: 1
                                Springy { hover: mkMouse.containsMouse; pressed: mkMouse.pressed }

                                Text {
                                    anchors.centerIn: parent
                                    text: isMarked ? "✔" : "🛒"
                                    font.pixelSize: 11
                                    color: isMarked ? "#DDD6FE" : "#94A3B8"
                                }
                                MouseArea {
                                    id: mkMouse
                                    objectName: "creatorMarkMouse"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: (isMarked ? "Remove creator from Download Cart" : "Mark creator for Download Cart") + "\nShift+click to mark/unmark a range"
                                    onClicked: (mouse) => creatorsGridPane.view.handleRangeMarkClick("creators", creatorsGrid, index, cData, (mouse.modifiers & Qt.ShiftModifier) !== 0)
                                }
                            }
                        }
                    }

                    // Middle Row: Telemetry Chips (Posts / Videos / Images / Disk Size / Drives)
                    Flow {
                        id: cTelemetryFlow
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.maximumHeight: 46
                        clip: true
                        spacing: 5

                        Rectangle {
                            visible: Number(cData.post_count || 0) > 0
                            height: 20
                            width: Math.min(cTelemetryFlow.width, pCntTxt.implicitWidth + 10)
                            clip: true
                            radius: 5
                            color: "#0F172A"
                            Text {
                                id: pCntTxt
                                anchors.centerIn: parent
                                text: "📄 " + Number(cData.post_count || 0) + " posts"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#CBD5E1"
                            }
                        }

                        Rectangle {
                            visible: !creatorsGridPane.view.isLocalMode && Number(cData.video_count || 0) > 0
                            height: 20
                            width: Math.min(cTelemetryFlow.width, vCntTxt.implicitWidth + 10)
                            clip: true
                            radius: 5
                            color: "#0F172A"
                            Text {
                                id: vCntTxt
                                anchors.centerIn: parent
                                text: "🎬 " + Number(cData.video_count || 0)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#38BDF8"
                            }
                        }

                        Rectangle {
                            visible: !creatorsGridPane.view.isLocalMode && Number(cData.image_count || 0) > 0
                            height: 20
                            width: Math.min(cTelemetryFlow.width, iCntTxt.implicitWidth + 10)
                            clip: true
                            radius: 5
                            color: "#0F172A"
                            Text {
                                id: iCntTxt
                                anchors.centerIn: parent
                                text: "🖼️ " + Number(cData.image_count || 0)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#A78BFA"
                            }
                        }

                        Rectangle {
                            visible: !creatorsGridPane.view.isLocalMode && Number(cData.dm_count || 0) > 0
                            height: 20
                            width: Math.min(cTelemetryFlow.width, dmCntTxt.implicitWidth + 10)
                            clip: true
                            radius: 5
                            color: "#2E1065"
                            Text {
                                id: dmCntTxt
                                anchors.centerIn: parent
                                text: "💬 " + Number(cData.dm_count || 0)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                color: "#E9D5FF"
                            }
                        }

                        // Local Mode: File count & Disk size chip
                        Rectangle {
                            visible: creatorsGridPane.view.isLocalMode
                            height: 20
                            width: Math.min(cTelemetryFlow.width, locSzTxt.implicitWidth + 10)
                            clip: true
                            radius: 5
                            color: "#0F172A"
                            Text {
                                id: locSzTxt
                                anchors.centerIn: parent
                                width: Math.min(implicitWidth, parent.width - 8)
                                elide: Text.ElideRight
                                text: "📁 " + Number(cData.local_file_count || 0) + " files • " + creatorsGridPane.view.formatBytes(cData.local_size_bytes)
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }

                        // Drive Badges in Local Mode
                        Repeater {
                            model: cData.local_drives || []
                            delegate: Rectangle {
                                height: 20
                                width: Math.min(cTelemetryFlow.width, dTxt.implicitWidth + 10)
                                clip: true
                                radius: 5
                                color: "#064E3B"
                                border.color: "#10B981"
                                border.width: 1
                                Text {
                                    id: dTxt
                                    anchors.centerIn: parent
                                    text: "💽 " + modelData
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "#A7F3D0"
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Bottom Row: Action Strip (strictly bounded inside card width)
                    RowLayout {
                        id: cCardActionRow
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 6

                        TextMetrics {
                            id: onDiskMetrics
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            text: "On Disk (" + Number(cData.local_post_count || 1) + ") • Open Local"
                        }

                        // Online Mode: "Already on Disk" badge -> Click to open in Local Mode
                        Rectangle {
                            visible: !creatorsGridPane.view.isLocalMode && onDisk
                            Layout.preferredHeight: 24
                            Layout.fillWidth: true
                            Layout.minimumWidth: 48
                            Layout.maximumWidth: onDiskMetrics.width + 32
                            radius: 5
                            z: 3
                            clip: true
                            color: onDiskMouse.containsMouse ? "#065F46" : "#064E3B"
                            border.color: "#10B981"
                            border.width: 1

                            RowLayout {
                                id: onDiskRow
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                anchors.rightMargin: 6
                                spacing: 4
                                Text { text: "💾"; font.pixelSize: 10 }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: onDiskMetrics.text
                                    font: onDiskMetrics.font
                                    color: "#A7F3D0"
                                    elide: Text.ElideRight
                                }
                            }
                            MouseArea {
                                id: onDiskMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (creatorsGridPane.view.bBridge) creatorsGridPane.view.bBridge.openCreatorInLocalMode(cData)
                            }
                        }

                        TextMetrics {
                            id: mvCardMetrics
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            text: "Move Drive…"
                        }

                        // Local Mode: 1-Click Move to Another Drive button
                        Rectangle {
                            visible: creatorsGridPane.view.isLocalMode
                            Layout.preferredHeight: 24
                            Layout.fillWidth: true
                            Layout.minimumWidth: 48
                            Layout.maximumWidth: mvCardMetrics.width + 32
                            radius: 5
                            z: 3
                            clip: true
                            color: mvCardMouse.containsMouse ? "#1E293B" : "#151C2B"
                            border.color: "#38BDF8"
                            border.width: 1
                            Springy { hover: mvCardMouse.containsMouse; pressed: mvCardMouse.pressed }

                            RowLayout {
                                id: mvCardRow
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                anchors.rightMargin: 6
                                spacing: 4
                                Text { text: "💽"; font.pixelSize: 10 }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: mvCardMetrics.text
                                    font: mvCardMetrics.font
                                    color: "#7DD3FC"
                                    elide: Text.ElideRight
                                }
                            }
                            MouseArea {
                                id: mvCardMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    creatorsGridPane.view.openRelocateModal(cData)
                                }
                            }
                        }

                        Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }

                        Rectangle {
                            id: cCardCopyBtn
                            objectName: "creatorCardCopyLinkBtn"
                            property bool justCopied: false
                            Layout.preferredWidth: 24
                            Layout.preferredHeight: 22
                            Layout.minimumWidth: 24
                            radius: 5
                            z: 3
                            color: justCopied
                                   ? "#064E3B"
                                   : (cCardCopyMouse.containsMouse ? "#1E293B" : "#151C2B")
                            border.color: justCopied ? "#10B981" : (cCardCopyMouse.containsMouse ? "#38BDF8" : "#334155")
                            border.width: 1
                            Springy { hover: cCardCopyMouse.containsMouse; pressed: cCardCopyMouse.pressed }
                            Timer {
                                id: cCardCopyTimer
                                interval: 1500
                                onTriggered: cCardCopyBtn.justCopied = false
                            }
                            Text {
                                anchors.centerIn: parent
                                text: cCardCopyBtn.justCopied ? "✓" : "🔗"
                                font.pixelSize: 10
                                color: cCardCopyBtn.justCopied ? "#6EE7B7" : "#7DD3FC"
                            }
                            MouseArea {
                                id: cCardCopyMouse
                                objectName: "creatorCardCopyLinkMouse"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 250
                                ToolTip.text: "Copy creator link"
                                onClicked: (mouse) => {
                                    mouse.accepted = true
                                    if (creatorsGridPane.view.bBridge && creatorsGridPane.view.bBridge.copyCreatorLink(cData)) {
                                        cCardCopyBtn.justCopied = true
                                        cCardCopyTimer.restart()
                                    }
                                }
                            }
                        }

                        Text {
                            id: browsePostsTxt
                            Layout.minimumWidth: 0
                            text: "Browse Posts →"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#38BDF8"
                            elide: Text.ElideRight
                        }
                    }
                }

                MouseArea {
                    id: cardBodyMouse
                    anchors.fill: parent
                    z: 0
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (creatorsGridPane.view.bBridge) creatorsGridPane.view.bBridge.openCreator(cData)
                }
            }
        }
    }

    // Centered Auth / Favorites Login Prompt Card when grid is empty & login required
    Rectangle {
        id: browserAuthPromptCard
        objectName: "browserAuthPromptCard"
        visible: !creatorsGridPane.showingPostsGrid && creatorsGridPane.view.bBridge && !creatorsGridPane.view.bBridge.isLoading && creatorsGrid.count === 0 && creatorsGridPane.view.bBridge.authRequired
        anchors.centerIn: parent
        width: Math.min(440, parent.width - 32)
        implicitHeight: authPromptCol.implicitHeight + 36
        radius: 12
        color: "#0F1420"
        border.color: "#F59E0B"
        border.width: 1.5

        ColumnLayout {
            id: authPromptCol
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "🔐"
                font.pixelSize: 30
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: (creatorsGridPane.view.bBridge && creatorsGridPane.view.bBridge.activeService === "favorites")
                      ? ("Sign in to " + creatorsGridPane.view.activeProviderDisplayName + " to view your favorited creators")
                      : ("Sign in to " + creatorsGridPane.view.activeProviderDisplayName + " required")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 15
                font.weight: Font.Bold
                color: "#F8FAFC"
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: (creatorsGridPane.view.bBridge && creatorsGridPane.view.bBridge.errorMessage)
                      ? creatorsGridPane.view.bBridge.errorMessage
                      : ("Your " + creatorsGridPane.view.activeProviderDisplayName + " account credentials or browser session cookies let you load and sync favorites.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 10

                Rectangle {
                    Layout.preferredHeight: 34
                    implicitWidth: authPromptBtnTxt.implicitWidth + 24
                    radius: 7
                    color: authPromptLoginMouse.containsMouse ? "#D97706" : "#F59E0B"
                    Springy { hover: authPromptLoginMouse.containsMouse; pressed: authPromptLoginMouse.pressed }
                    Text {
                        id: authPromptBtnTxt
                        anchors.centerIn: parent
                        text: "🔑 Log In to " + creatorsGridPane.view.activeProviderDisplayName
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#0F172A"
                    }
                    MouseArea {
                        id: authPromptLoginMouse
                        objectName: "authPromptLoginBtn"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (creatorsGridPane.view.bBridge) {
                                creatorsGridPane.view.openProviderLoginModal(
                                    creatorsGridPane.view.bBridge.activeProvider,
                                    creatorsGridPane.view.bBridge.activeService === "favorites" ? "favorites" : ""
                                )
                            }
                        }
                    }
                }

                Rectangle {
                    visible: !!(creatorsGridPane.view.bBridge && creatorsGridPane.view.bBridge.activeService === "favorites")
                    Layout.preferredHeight: 34
                    implicitWidth: authPromptBackTxt.implicitWidth + 20
                    radius: 7
                    color: authPromptBackMouse.containsMouse ? "#1E293B" : "#151C2B"
                    border.color: "#334155"
                    border.width: 1
                    Text {
                        id: authPromptBackTxt
                        anchors.centerIn: parent
                        text: "Browse All Services"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#CBD5E1"
                    }
                    MouseArea {
                        id: authPromptBackMouse
                        objectName: "authPromptAllServicesBtn"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (creatorsGridPane.view.bBridge) creatorsGridPane.view.bBridge.setServiceFilter("all")
                    }
                }
            }
        }
    }
}
