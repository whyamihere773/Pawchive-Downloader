import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── 1. Top Header Banner & Actions (Console Log Aware) ────────────────
Rectangle {
    id: headerSection
    required property var view
    Layout.fillWidth: true
    implicitHeight: headerCol.implicitHeight + 24
    color: "#141720"
    radius: 10
    border.color: "#1E2430"
    border.width: 1

    opacity: headerSection.view.entranceStage >= 1 ? 1.0 : 0.0
    transform: Translate {
        y: headerSection.view.entranceStage >= 1 ? 0 : 20
        Behavior on y {
            SpringAnimation { spring: 4.2; damping: 0.38; mass: 1.0; epsilon: 0.25 }
        }
    }
    Behavior on opacity { NumberAnimation { duration: 180 } }

    ColumnLayout {
        id: headerCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 10

        // Title + Subtitle Row (+ Actions on Wide View)
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 40; height: 40; radius: 8
                color: "#0C4A6E"
                border.color: "#38BDF8"; border.width: 1.2
                Text { anchors.centerIn: parent; text: "🗝️"; font.pixelSize: 20 }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                RowLayout {
                    spacing: 8
                    Text {
                        text: headerSection.view.tr("vault_title", "Permanent Link Vault")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 17
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }

                    Rectangle {
                        height: 20
                        implicitWidth: totalPillText.implicitWidth + 14
                        radius: 10
                        color: "#0369A1"
                        border.color: "#38BDF8"
                        border.width: 1
                        Text {
                            id: totalPillText
                            anchors.centerIn: parent
                            text: (headerSection.view.bridge ? headerSection.view.bridge.linkVaultTotalLinks : 0) + " " + headerSection.view.tr("vault_links_pill", "Links")
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            color: "#FFFFFF"
                        }
                    }
                }

                Text {
                    text: headerSection.view.tr("vault_subtitle", "Permanent cloud harvest repository with smart proximity passwords and live health verification.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            // Action Buttons (Wide View: > 780px)
            RowLayout {
                visible: headerSection.view.width > 780
                spacing: 8
                Layout.alignment: Qt.AlignVCenter

                // Action: Add / Harvest Artist
                Rectangle {
                    implicitWidth: addArtistRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: addArtistMouse1.containsMouse ? "#047857" : "#065F46"
                    border.color: addArtistMouse1.containsMouse ? "#34D399" : "#10B981"
                    border.width: 1
                    scale: addArtistMouse1.pressed ? 0.92 : (addArtistMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: addArtistRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "➕"; font.pixelSize: 12 }
                        Text {
                            text: headerSection.view.tr("btn_harvest_artist", "Harvest Artist")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FFFFFF"
                        }
                    }

                    MouseArea {
                        id: addArtistMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_harvest_artist", "Harvest all links & passwords from an artist into the vault without downloading files")
                        onClicked: {
                            headerSection.view.openAddArtistModal()
                        }
                    }
                }

                // Action: Probe All Health
                Rectangle {
                    implicitWidth: probeRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: probeMouse1.containsMouse ? "#0284C7" : "#0369A1"
                    border.color: probeMouse1.containsMouse ? "#7DD3FC" : "#38BDF8"
                    border.width: 1
                    scale: probeMouse1.pressed ? 0.92 : (probeMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: probeRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: headerSection.view.bridge && headerSection.view.bridge.linkVaultProbingActive ? "⏳" : "⚡"
                            font.pixelSize: 12
                        }
                        Text {
                            text: headerSection.view.bridge && headerSection.view.bridge.linkVaultProbingActive ? headerSection.view.tr("btn_probing", "Probing...") : headerSection.view.tr("btn_probe_all", "Probe Health")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FFFFFF"
                        }
                    }

                    MouseArea {
                        id: probeMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_probe_health", "Checks link status (Mega, Pixeldrain, GoFile, Catbox) asynchronously in background")
                        onClicked: {
                            if (headerSection.view.bridge) headerSection.view.bridge.probeVaultHealth()
                        }
                    }
                }

                // Action: Clean Dead Links
                Rectangle {
                    implicitWidth: cleanRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: cleanMouse1.containsMouse ? "#3B181E" : "#1A202C"
                    border.color: cleanMouse1.containsMouse ? "#F87171" : "#EF4444"
                    border.width: 1
                    scale: cleanMouse1.pressed ? 0.92 : (cleanMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: cleanRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "🧹"; font.pixelSize: 12 }
                        Text {
                            text: headerSection.view.tr("btn_clean_dead", "Clean Dead")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FCA5A5"
                        }
                    }

                    MouseArea {
                        id: cleanMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_clean_dead", "Removes verified 404 dead links from the vault")
                        onClicked: {
                            if (headerSection.view.bridge) {
                                var removed = headerSection.view.bridge.cleanDeadVaultLinks()
                                headerSection.view.showToast(headerSection.view.tr("toast_cleaned_dead", "Cleaned dead links: ") + removed)
                            }
                        }
                    }
                }

                // Action: Copy Passwords to Decompressor
                Rectangle {
                    implicitWidth: decompressorRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: decompMouse1.containsMouse ? "#1E293B" : "#141720"
                    border.color: decompMouse1.containsMouse ? "#C4B5FD" : "#A78BFA"
                    border.width: 1
                    scale: decompMouse1.pressed ? 0.92 : (decompMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: decompressorRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📦"; font.pixelSize: 12 }
                        Text {
                            text: headerSection.view.tr("btn_feed_decompressor", "Send Passwords to Decompressor")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#C4B5FD"
                        }
                    }

                    MouseArea {
                        id: decompMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_send_passwords", "Adds all extracted passwords to Bulk Decompressor archive dictionary")
                        onClicked: {
                            if (headerSection.view.bridge) {
                                var count = headerSection.view.bridge.copyPasswordsToDecompressor()
                                headerSection.view.showToast(headerSection.view.tr("toast_passwords_copied", "Sent to Decompressor: ") + count + " " + headerSection.view.tr("vault_passwords_label", "passwords"))
                            }
                        }
                    }
                }

                // Action: Copy All Links
                Rectangle {
                    implicitWidth: copyAllRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: copyAllMouse1.containsMouse ? "#1E293B" : "#141720"
                    border.color: copyAllMouse1.containsMouse ? "#7DD3FC" : "#38BDF8"
                    border.width: 1
                    scale: copyAllMouse1.pressed ? 0.92 : (copyAllMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: copyAllRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "📋"; font.pixelSize: 12 }
                        Text {
                            text: headerSection.view.tr("btn_copy_all_links", "Copy All Links")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#38BDF8"
                        }
                    }

                    MouseArea {
                        id: copyAllMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_copy_all_links", "Copy all stored links across all creators to the clipboard")
                        onClicked: {
                            if (headerSection.view.bridge) {
                                var count = headerSection.view.bridge.copyVaultLinks("")
                                headerSection.view.showToast(headerSection.view.tr("toast_links_copied", "Copied to clipboard: ") + count + " " + headerSection.view.tr("vault_links_pill", "Links"))
                            }
                        }
                    }
                }

                // Action: Bulk Export to Files
                Rectangle {
                    implicitWidth: exportRow1.implicitWidth + 20
                    height: 32
                    radius: 6
                    color: exportMouse1.containsMouse ? "#1F2D2A" : "#141B1A"
                    border.color: exportMouse1.containsMouse ? "#6EE7B7" : "#10B981"
                    border.width: 1
                    scale: exportMouse1.pressed ? 0.92 : (exportMouse1.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Row {
                        id: exportRow1
                        anchors.centerIn: parent
                        spacing: 6
                        Text { text: "💾"; font.pixelSize: 12 }
                        Text {
                            text: headerSection.view.tr("btn_export_files", "Export to Files")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#34D399"
                        }
                    }

                    MouseArea {
                        id: exportMouse1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: headerSection.view.tr("tip_export_files", "Export each creator's links into individual unique text files in a selected folder")
                        onClicked: {
                            if (headerSection.view.bridge) {
                                var folder = headerSection.view.bridge.browseFolderDialog(headerSection.view.tr("dlg_select_export_dir", "Select Folder for Link Vault Export"), "")
                                if (folder) {
                                    var count = headerSection.view.bridge.exportVaultToFolder(folder)
                                    headerSection.view.showToast(headerSection.view.tr("toast_vault_exported", "Exported ") + count + " " + headerSection.view.tr("vault_files_exported", "creator file(s) to ") + folder)
                                }
                            }
                        }
                    }
                }
            }
        }

        // Action Buttons (Narrow View: <= 780px, stacks neatly so never cut off)
        Flow {
            visible: headerSection.view.width <= 780
            Layout.fillWidth: true
            spacing: 8

            // Action: Add / Harvest Artist
            Rectangle {
                implicitWidth: addArtistRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: addArtistMouse2.containsMouse ? "#047857" : "#065F46"
                border.color: addArtistMouse2.containsMouse ? "#34D399" : "#10B981"
                border.width: 1
                scale: addArtistMouse2.pressed ? 0.92 : (addArtistMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: addArtistRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "➕"; font.pixelSize: 11 }
                    Text {
                        text: headerSection.view.tr("btn_harvest_artist", "Harvest Artist")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FFFFFF"
                    }
                }

                MouseArea {
                    id: addArtistMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        headerSection.view.openAddArtistModal()
                    }
                }
            }

            // Action: Probe All Health
            Rectangle {
                implicitWidth: probeRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: probeMouse2.containsMouse ? "#0284C7" : "#0369A1"
                border.color: probeMouse2.containsMouse ? "#7DD3FC" : "#38BDF8"
                border.width: 1
                scale: probeMouse2.pressed ? 0.92 : (probeMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: probeRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: headerSection.view.bridge && headerSection.view.bridge.linkVaultProbingActive ? "⏳" : "⚡"
                        font.pixelSize: 11
                    }
                    Text {
                        text: headerSection.view.bridge && headerSection.view.bridge.linkVaultProbingActive ? headerSection.view.tr("btn_probing", "Probing...") : headerSection.view.tr("btn_probe_all", "Probe Health")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FFFFFF"
                    }
                }

                MouseArea {
                    id: probeMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (headerSection.view.bridge) headerSection.view.bridge.probeVaultHealth()
                    }
                }
            }

            // Action: Clean Dead Links
            Rectangle {
                implicitWidth: cleanRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: cleanMouse2.containsMouse ? "#3B181E" : "#1A202C"
                border.color: cleanMouse2.containsMouse ? "#F87171" : "#EF4444"
                border.width: 1
                scale: cleanMouse2.pressed ? 0.92 : (cleanMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: cleanRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🧹"; font.pixelSize: 11 }
                    Text {
                        text: headerSection.view.tr("btn_clean_dead", "Clean Dead")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FCA5A5"
                    }
                }

                MouseArea {
                    id: cleanMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (headerSection.view.bridge) {
                            var removed = headerSection.view.bridge.cleanDeadVaultLinks()
                            headerSection.view.showToast(headerSection.view.tr("toast_cleaned_dead", "Cleaned dead links: ") + removed)
                        }
                    }
                }
            }

            // Action: Copy Passwords to Decompressor
            Rectangle {
                implicitWidth: decompressorRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: decompMouse2.containsMouse ? "#1E293B" : "#141720"
                border.color: decompMouse2.containsMouse ? "#C4B5FD" : "#A78BFA"
                border.width: 1
                scale: decompMouse2.pressed ? 0.92 : (decompMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: decompressorRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "📦"; font.pixelSize: 11 }
                    Text {
                        text: headerSection.view.tr("btn_feed_decompressor", "Send Passwords to Decompressor")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#C4B5FD"
                    }
                }

                MouseArea {
                    id: decompMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (headerSection.view.bridge) {
                            var count = headerSection.view.bridge.copyPasswordsToDecompressor()
                            headerSection.view.showToast(headerSection.view.tr("toast_passwords_copied", "Sent to Decompressor: ") + count + " " + headerSection.view.tr("vault_passwords_label", "passwords"))
                        }
                    }
                }
            }

            // Action: Copy All Links
            Rectangle {
                implicitWidth: copyAllRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: copyAllMouse2.containsMouse ? "#1E293B" : "#141720"
                border.color: copyAllMouse2.containsMouse ? "#7DD3FC" : "#38BDF8"
                border.width: 1
                scale: copyAllMouse2.pressed ? 0.92 : (copyAllMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: copyAllRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "📋"; font.pixelSize: 11 }
                    Text {
                        text: headerSection.view.tr("btn_copy_all_links", "Copy All Links")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#38BDF8"
                    }
                }

                MouseArea {
                    id: copyAllMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: headerSection.view.tr("tip_copy_all_links", "Copy all stored links across all creators to the clipboard")
                    onClicked: {
                        if (headerSection.view.bridge) {
                            var count = headerSection.view.bridge.copyVaultLinks("")
                            headerSection.view.showToast(headerSection.view.tr("toast_links_copied", "Copied to clipboard: ") + count + " " + headerSection.view.tr("vault_links_pill", "Links"))
                        }
                    }
                }
            }

            // Action: Bulk Export to Files
            Rectangle {
                implicitWidth: exportRow2.implicitWidth + 18
                height: 30
                radius: 6
                color: exportMouse2.containsMouse ? "#1F2D2A" : "#141B1A"
                border.color: exportMouse2.containsMouse ? "#6EE7B7" : "#10B981"
                border.width: 1
                scale: exportMouse2.pressed ? 0.92 : (exportMouse2.containsMouse ? 1.04 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                Row {
                    id: exportRow2
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "💾"; font.pixelSize: 11 }
                    Text {
                        text: headerSection.view.tr("btn_export_files", "Export to Files")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#34D399"
                    }
                }

                MouseArea {
                    id: exportMouse2
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: headerSection.view.tr("tip_export_files", "Export each creator's links into individual unique text files in a selected folder")
                    onClicked: {
                        if (headerSection.view.bridge) {
                            var folder = headerSection.view.bridge.browseFolderDialog(headerSection.view.tr("dlg_select_export_dir", "Select Folder for Link Vault Export"), "")
                            if (folder) {
                                var count = headerSection.view.bridge.exportVaultToFolder(folder)
                                headerSection.view.showToast(headerSection.view.tr("toast_vault_exported", "Exported ") + count + " " + headerSection.view.tr("vault_files_exported", "creator file(s) to ") + folder)
                            }
                        }
                    }
                }
            }
        }
    }
}
