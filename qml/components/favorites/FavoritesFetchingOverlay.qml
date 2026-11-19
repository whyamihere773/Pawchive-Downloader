import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// In-modal loading overlay with animated progress dashboard when browsing an artist's posts.
Rectangle {
    id: fetchingPostsOverlay

    required property var modal
    anchors.fill: parent
    color: Qt.rgba(5/255, 7/255, 11/255, 0.82)
    visible: opacity > 0.001
    opacity: modal.isBrowsingArtist ? 1.0 : 0.0
    z: 1100

    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        // Absorb pointer events so user cannot interact with elements behind the overlay
    }

    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: function(event) { event.accepted = true }
    }

    Rectangle {
        id: loadingCard
        width: Math.min(460, modal.width - 32)
        implicitHeight: loadingCol.implicitHeight + 48
        anchors.centerIn: parent
        radius: 16
        color: "#0F1422"
        border.color: "#24324D"
        border.width: 1
        clip: true

        // Glowing amber accent border
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: 17
            color: "transparent"
            border.color: Qt.rgba(245/255, 158/255, 11/255, 0.35)
            border.width: 1
            z: -1
        }

        // Top ambient gradient glow
        Rectangle {
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: 130
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(245/255, 158/255, 11/255, 0.08) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        ColumnLayout {
            id: loadingCol
            anchors.fill: parent
            anchors.margins: 28
            spacing: 16

            // Avatar with Pulsing Amber Glow Rings
            Item {
                Layout.alignment: Qt.AlignHCenter
                width: 76
                height: 76

                // Outer expanding pulse ring 1 (Amber)
                Rectangle {
                    id: pulseRing1
                    anchors.centerIn: parent
                    width: 76
                    height: 76
                    radius: 38
                    color: "transparent"
                    border.color: "#F59E0B"
                    border.width: 2

                    SequentialAnimation on scale {
                        running: modal.isBrowsingArtist
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.95; to: 1.25; duration: 1400; easing.type: Easing.OutQuad }
                        NumberAnimation { from: 1.25; to: 0.95; duration: 1400; easing.type: Easing.InOutQuad }
                    }

                    SequentialAnimation on opacity {
                        running: modal.isBrowsingArtist
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.7; to: 0.05; duration: 1400; easing.type: Easing.OutQuad }
                        NumberAnimation { from: 0.05; to: 0.7; duration: 1400; easing.type: Easing.InOutQuad }
                    }
                }

                // Outer pulse ring 2 (Sky blue accent)
                Rectangle {
                    id: pulseRing2
                    anchors.centerIn: parent
                    width: 76
                    height: 76
                    radius: 38
                    color: "transparent"
                    border.color: "#38BDF8"
                    border.width: 1.5

                    SequentialAnimation on scale {
                        running: modal.isBrowsingArtist
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.18; to: 0.95; duration: 1400; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: 0.95; to: 1.18; duration: 1400; easing.type: Easing.OutQuad }
                    }

                    SequentialAnimation on opacity {
                        running: modal.isBrowsingArtist
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.15; to: 0.6; duration: 1400; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: 0.6; to: 0.15; duration: 1400; easing.type: Easing.OutQuad }
                    }
                }

                // Avatar Circle Frame
                Rectangle {
                    anchors.centerIn: parent
                    width: 60
                    height: 60
                    radius: 30
                    color: "#182236"
                    border.color: "#F59E0B"
                    border.width: 2
                    clip: true

                    Image {
                        id: loadingAvatarImg
                        anchors.fill: parent
                        source: modal.browsingArtistAvatar
                        fillMode: Image.PreserveAspectCrop
                        visible: status === Image.Ready && modal.browsingArtistAvatar.length > 0
                    }

                    Text {
                        anchors.centerIn: parent
                        text: (modal.browsingArtistName && modal.browsingArtistName.length > 0)
                              ? modal.browsingArtistName.charAt(0).toUpperCase()
                              : "?"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 24
                        font.bold: true
                        color: "#FCD34D"
                        visible: !loadingAvatarImg.visible
                    }
                }
            }

            // Creator Info Header
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                spacing: 4

                Text {
                    text: modal.browsingArtistName || "Artist"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 17
                    font.bold: true
                    color: "#F8FAFC"
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }

                // Badges row (Provider & Service)
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 6

                    ProviderBadge {
                        provider: modal.browsingArtistProvider || "pawchive"
                        domain: modal.browsingArtistDomain || ""
                        badgeHeight: 20
                    }

                    ServiceBadge {
                        service: modal.browsingArtistService || "patreon"
                        badgeHeight: 20
                    }
                }
            }

            // Status Heading (Clean title — no duplicated page/post count)
            Text {
                text: modal.tr("msg_fetching_artist_posts", "Fetching creator posts…")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.weight: 600
                color: "#94A3B8"
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }

            // Dedicated Progress Dashboard (Fixed width 380px — rock-steady, 0px jitter, within bounds)
            Item {
                id: progressDashboard
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(380, loadingCol.width)
                Layout.preferredHeight: 64

                // ── Upper Row: Fixed-position Badges (No resizing or horizontal shifting) ──
                Item {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 24

                    // Left Side Badges
                    Row {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8

                        // Page Pill (Fixed 74px width)
                        Rectangle {
                            width: 74
                            height: 24
                            radius: 6
                            color: "#0F263D"
                            border.color: "#38BDF8"
                            border.width: 1

                            Row {
                                anchors.centerIn: parent
                                spacing: 4
                                Text { text: "📄"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: modal.tr("lbl_page", "Page") + " " + Math.max(1, modal.browsePage)
                                    font.family: "Consolas, 'Segoe UI', monospace"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: "#7DD3FC"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        // Posts Counter Pill (Fixed 172px width — plenty of room, never overflows or shifts)
                        Rectangle {
                            width: 172
                            height: 24
                            radius: 6
                            color: modal.browseCount > 0 ? "#2A1F08" : "#1A2234"
                            border.color: modal.browseCount > 0 ? "#F59E0B" : "#2E3B56"
                            border.width: 1
                            clip: true

                            Row {
                                anchors.centerIn: parent
                                spacing: 5
                                Text { text: "📝"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }
                                Text {
                                    text: modal.browseTotal > 0
                                          ? (modal.browseCount + " / " + modal.browseTotal + " " + modal.tr("lbl_posts", "posts"))
                                          : (modal.browseCount + " " + modal.tr("lbl_posts_found", "posts"))
                                    font.family: "Consolas, 'Segoe UI', monospace"
                                    font.pixelSize: 11
                                    font.weight: 600
                                    color: modal.browseCount > 0 ? "#FCD34D" : "#94A3B8"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }

                    // Right Side Badges (Anchored to right edge)
                    Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8

                        // Percentage Pill (Fixed 52px width, visible when total is known)
                        Rectangle {
                            visible: modal.browseTotal > 0
                            width: 52
                            height: 24
                            radius: 6
                            color: "#064E3B"
                            border.color: "#10B981"
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: Math.round(modal.browseProgressFraction * 100) + "%"
                                font.family: "Consolas, 'Segoe UI', monospace"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#6EE7B7"
                            }
                        }

                        // Active Glowing Pulse Dot
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: "#10B981"
                            anchors.verticalCenter: parent.verticalCenter

                            SequentialAnimation on opacity {
                                loops: Animation.Infinite
                                running: modal.isBrowsingArtist
                                NumberAnimation { from: 1.0; to: 0.25; duration: 600; easing.type: Easing.InOutQuad }
                                NumberAnimation { from: 0.25; to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
                            }
                        }
                    }
                }

                // ── Middle: Dual-Mode Progress Bar (Fixed anchors to left/right of dashboard) ──
                Rectangle {
                    id: progressBarTrack
                    anchors.top: parent.top
                    anchors.topMargin: 32
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 8
                    radius: 4
                    color: "#151E30"
                    border.color: "#27354E"
                    border.width: 1
                    clip: true

                    // 1. Determinate fill (When total is known)
                    Rectangle {
                        id: determinateFill
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        visible: modal.browseTotal > 0
                        width: Math.max(modal.browseCount > 0 ? 12 : 0, parent.width * modal.browseProgressFraction)
                        radius: 3
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#D97706" }
                            GradientStop { position: 0.7; color: "#F59E0B" }
                            GradientStop { position: 1.0; color: "#FCD34D" }
                        }

                        Behavior on width {
                            NumberAnimation { duration: 100; easing.type: Easing.OutQuad }
                        }
                    }

                    // 2. Incremental Page Step Fill (When total is unknown, advances smoothly with pages)
                    Rectangle {
                        id: pageStepFill
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        visible: modal.browseTotal === 0 && modal.browseCount > 0
                        width: Math.min(parent.width * 0.88, Math.max(24, modal.browsePage * 32))
                        radius: 3
                        color: Qt.rgba(245/255, 158/255, 11/255, 0.35)

                        Behavior on width {
                            NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                        }
                    }

                    // 3. Shimmer wave runner (Smooth fluid loop across track)
                    Rectangle {
                        id: progressBarIndicator
                        width: modal.browseTotal > 0 ? 80 : 120
                        height: parent.height
                        radius: 3
                        opacity: modal.browseTotal > 0 ? 0.3 : 0.7
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.rgba(217/255, 119/255, 6/255, 0.0) }
                            GradientStop { position: 0.5; color: Qt.rgba(252/255, 211/255, 77/255, 0.35) }
                            GradientStop { position: 1.0; color: Qt.rgba(245/255, 158/255, 11/255, 0.0) }
                        }

                        NumberAnimation on x {
                            from: -120
                            to: progressBarTrack.width
                            duration: 1200
                            loops: Animation.Infinite
                            running: modal.isBrowsingArtist
                            easing.type: Easing.InOutQuad
                        }
                    }
                }

                // ── Lower Line: Stable hint caption ──
                Text {
                    anchors.top: progressBarTrack.bottom
                    anchors.topMargin: 8
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modal.tr("hint_fetching_posts_desc", "Connecting to server and retrieving post index…")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }

            Item { Layout.preferredHeight: 4 }

            // Cancel Button
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: 120
                implicitHeight: 34
                radius: 7
                color: cancelLoadingMouse.containsMouse ? "#2A364F" : "#192233"
                border.color: cancelLoadingMouse.containsMouse ? "#475569" : "#2E3B56"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                        text: "✕"
                        font.pixelSize: 11
                        font.bold: true
                        color: cancelLoadingMouse.containsMouse ? "#F87171" : "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: modal.tr("btn_cancel", "Cancel")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: cancelLoadingMouse.containsMouse ? "#F1F5F9" : "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: cancelLoadingMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: modal.cancelBrowsingArtist()
                }
            }
        }
    }
}
