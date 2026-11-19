import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Add / Harvest Artist Modal ─────────────────────────────────────────────
Item {
    id: addArtistModal
    required property var view
    anchors.fill: parent
    z: 1000
    visible: opacity > 0
    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    property bool isOpen: false
    property bool probeImmediately: true
    property bool allPages: true

    function open() {
        isOpen = true
        artistUrlField.forceActiveFocus()
    }

    function close() {
        isOpen = false
    }

    // Dim backdrop
    Rectangle {
        anchors.fill: parent
        color: "#B0060910"
        MouseArea {
            anchors.fill: parent
            onClicked: {} // Prevent click-through to underlying views
        }
    }

    // Modal Content Card
    Rectangle {
        id: modalCard
        width: Math.min(520, parent.width - 32)
        implicitHeight: modalCardCol.implicitHeight + 36
        anchors.centerIn: parent
        radius: 14
        color: "#131722"
        border.color: "#2D3748"
        border.width: 1.5

        transform: Translate {
            y: addArtistModal.isOpen ? 0 : -22
            Behavior on y {
                SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85 }
            }
        }
        scale: addArtistModal.isOpen ? 1.0 : 0.92
        Behavior on scale {
            SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85 }
        }

        // Absorb unhandled clicks inside the card so nothing passes through
        MouseArea {
            anchors.fill: parent
        }

        ColumnLayout {
            id: modalCardCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 16

            // Modal Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 32
                    height: 32
                    radius: 8
                    color: "#065F46"
                    border.color: "#10B981"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "🌾"; font.pixelSize: 16 }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: addArtistModal.view.tr("modal_harvest_artist_title", "Harvest Artist to Vault")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }
                    Text {
                        text: addArtistModal.view.tr("modal_harvest_artist_sub", "Extract all cloud links and passwords into Link Vault without downloading files.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Close (X) button
                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: closeBtnMouse.containsMouse ? "#1E293B" : "transparent"
                    scale: closeBtnMouse.pressed ? 0.9 : 1.0
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.4 } }
                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 13
                        color: closeBtnMouse.containsMouse ? "#FFFFFF" : "#64748B"
                    }
                    MouseArea {
                        id: closeBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: addArtistModal.close()
                    }
                }
            }

            // URL Input Field
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: addArtistModal.view.tr("label_artist_url", "Artist or Post URL")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: "#CBD5E1"
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 38
                    radius: 8
                    color: "#0F172A"
                    border.color: artistUrlField.activeFocus ? "#10B981" : (artistUrlBoxMouse.containsMouse ? "#475569" : "#334155")
                    border.width: artistUrlField.activeFocus ? 1.5 : 1.2
                    Behavior on border.color { ColorAnimation { duration: 120 } }

                    TextBarContextArea {
                        id: artistUrlBoxMouse
                        target: artistUrlField
                        focusOnLeftClick: true
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 10
                        spacing: 8

                        TextInput {
                            id: artistUrlField
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            color: "#F8FAFC"
                            selectionColor: "#0284C7"
                            selectedTextColor: "#FFFFFF"
                            selectByMouse: true
                            clip: true
                            TextBarContextArea {}

                            Text {
                                text: addArtistModal.view.tr("placeholder_artist_url", "https://kemono.cr/fanbox/user/1234567...")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 12
                                color: "#475569"
                                visible: !artistUrlField.text && !artistUrlField.activeFocus
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                            }
                        }

                        // Clear button
                        Text {
                            text: "✕"
                            font.pixelSize: 12
                            color: "#64748B"
                            visible: artistUrlField.text.length > 0
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: artistUrlField.text = ""
                            }
                        }
                    }
                }
            }

            // Options Section
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                // Option 1: Probe health immediately
                StyledSwitch {
                    label: addArtistModal.view.tr("opt_probe_health_now", "Probe link health immediately after harvest")
                    accentColor: "#10B981"
                    checked: addArtistModal.probeImmediately
                    onToggled: function(val) { addArtistModal.probeImmediately = val }
                }

                // Option 2: Page Range (All pages vs Custom Range)
                StyledSwitch {
                    label: addArtistModal.view.tr("opt_harvest_all_posts", "Harvest all posts (entire creator history)")
                    accentColor: "#10B981"
                    checked: addArtistModal.allPages
                    onToggled: function(val) { addArtistModal.allPages = val }
                }

                // Page range inputs (if not all pages)
                RowLayout {
                    visible: !addArtistModal.allPages
                    spacing: 12
                    Layout.leftMargin: 24

                    Text {
                        text: addArtistModal.view.tr("label_pages_from", "From page:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }

                    StyledSpinBox {
                        id: startPageSpin
                        from: 1
                        to: 9999
                        value: 1
                        accentColor: "#10B981"
                    }

                    Text {
                        text: addArtistModal.view.tr("label_pages_to", "To page:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }

                    StyledSpinBox {
                        id: endPageSpin
                        from: 1
                        to: 9999
                        value: 10
                        accentColor: "#10B981"
                    }
                }
            }

            // In-Progress Harvest Status Card (visible when bridge is harvesting)
            Rectangle {
                visible: addArtistModal.view.bridge && addArtistModal.view.bridge.linkVaultHarvestingActive
                Layout.fillWidth: true
                implicitHeight: modalStatusCol.implicitHeight + 18
                radius: 8
                color: "#064E3B"
                border.color: "#34D399"
                border.width: 1

                ColumnLayout {
                    id: modalStatusCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    RowLayout {
                        spacing: 8
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: "#34D399"
                            SequentialAnimation on opacity {
                                loops: Animation.Infinite
                                NumberAnimation { from: 1.0; to: 0.2; duration: 500 }
                                NumberAnimation { from: 0.2; to: 1.0; duration: 500 }
                            }
                        }
                        Text {
                            text: addArtistModal.view.tr("label_harvest_in_progress", "Harvesting in progress...")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#A7F3D0"
                        }
                    }

                    Text {
                        text: addArtistModal.view.bridge ? addArtistModal.view.bridge.linkVaultHarvestingStatus : ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#ECFDF5"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            // Action Buttons Row (Cancel / Start Harvest)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Layout.topMargin: 4

                Item { Layout.fillWidth: true }

                // Cancel / Close
                Rectangle {
                    implicitWidth: cancelBtnText.implicitWidth + 24
                    height: 34
                    radius: 8
                    color: cancelModalMouse.containsMouse ? "#334155" : "#1E293B"
                    border.color: "#475569"
                    border.width: 1
                    scale: cancelModalMouse.pressed ? 0.94 : (cancelModalMouse.containsMouse ? 1.03 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38 } }

                    Text {
                        id: cancelBtnText
                        anchors.centerIn: parent
                        text: addArtistModal.view.tr("btn_close", "Close")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: 600
                        color: "#CBD5E1"
                    }

                    MouseArea {
                        id: cancelModalMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: addArtistModal.close()
                    }
                }

                // Start Harvest Button
                Rectangle {
                    id: startBtnRect
                    property bool isRunning: addArtistModal.view.bridge && addArtistModal.view.bridge.linkVaultHarvestingActive
                    property bool canStart: artistUrlField.text.trim().length > 0 && !startBtnRect.isRunning

                    implicitWidth: startBtnRow.implicitWidth + 28
                    height: 34
                    radius: 8
                    color: startBtnRect.canStart
                           ? (startModalMouse.containsMouse ? "#059669" : "#10B981")
                           : (startBtnRect.isRunning ? "#065F46" : "#1F2937")
                    border.color: startBtnRect.canStart ? "#34D399" : (startBtnRect.isRunning ? "#10B981" : "#374151")
                    border.width: 1
                    opacity: (startBtnRect.canStart || startBtnRect.isRunning) ? 1.0 : 0.6
                    scale: startModalMouse.pressed && startBtnRect.canStart ? 0.94 : (startModalMouse.containsMouse && startBtnRect.canStart ? 1.03 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: startBtnRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: startBtnRect.isRunning ? "⏳" : "🌾"
                            font.pixelSize: 12
                        }
                        Text {
                            text: startBtnRect.isRunning
                                  ? addArtistModal.view.tr("btn_harvesting", "Harvesting...")
                                  : addArtistModal.view.tr("btn_start_harvest", "Start Harvest")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                    }

                    MouseArea {
                        id: startModalMouse
                        anchors.fill: parent
                        hoverEnabled: startBtnRect.canStart
                        cursorShape: startBtnRect.canStart ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (startBtnRect.canStart && addArtistModal.view.bridge) {
                                var pStart = addArtistModal.allPages ? 1 : startPageSpin.value
                                var pEnd = addArtistModal.allPages ? 999999 : endPageSpin.value
                                addArtistModal.view.bridge.harvestArtistToVault(
                                    artistUrlField.text.trim(),
                                    addArtistModal.probeImmediately,
                                    pStart,
                                    pEnd
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
