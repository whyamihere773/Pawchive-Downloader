import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Phase 1: Archive Rebuild configuration form (recovery banner, scan directories, options).
ColumnLayout {
    id: configPane

    required property var modal
    required property real cardWidth

    Layout.fillWidth: true
    spacing: 14
    visible: !modal.isRunning && !modal.isFinished

    // Interrupted Rebuild Recovery Banner (Crash / Power-Loss / Close Resume)
    Rectangle {
        visible: modal.hasSavedRebuild
        Layout.fillWidth: true
        implicitHeight: recoveryCol.implicitHeight + 20
        radius: 10
        color: "#1B160B"
        border.color: "#B45309"
        border.width: 1.2

        ColumnLayout {
            id: recoveryCol
            anchors {
                left: parent.left
                right: parent.right
                verticalCenter: parent.verticalCenter
                leftMargin: 12
                rightMargin: 12
            }
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "🔄"
                    font.pixelSize: 15
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 2

                    Text {
                        text: modal.tr("rebuild_recovery_title", "Interrupted Archive Rebuild Detected")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 12
                        font.weight: 700
                        color: "#FCD34D"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    Text {
                        text: {
                            var s = modal.savedRebuildSummary || ({})
                            var tot = s.total_files || 0
                            var proc = s.processed_files || 0
                            var pct = s.percent || 0
                            var added = s.added_count || 0
                            var savedAt = s.saved_at ? (" • " + s.saved_at) : ""
                            if (tot > 0) {
                                return proc + " / " + tot + " files (" + pct + "%) • +" + added + " added" + savedAt
                            }
                            return modal.tr("rebuild_recovery_discover_desc", "Saved during folder scan — resume to pick up without re-configuring.") + savedAt
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#FDE68A"
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    text: modal.tr("rebuild_recovery_btn_resume", "Resume Where It Left Off")
                    iconText: "▶️"
                    variant: "success"
                    implicitHeight: 28
                    onClicked: modal.resumeSavedRebuild(false)
                }

                StyledButton {
                    text: modal.tr("rebuild_recovery_btn_resume_bg", "Resume in Background")
                    iconText: "⬇"
                    variant: "outline"
                    implicitHeight: 28
                    onClicked: modal.resumeSavedRebuild(true)
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: modal.tr("rebuild_recovery_btn_discard", "Discard")
                    variant: "ghost"
                    implicitHeight: 28
                    onClicked: modal.discardSavedRebuild()
                }
            }
        }
    }

    // Section: Directories to Scan
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: modal.tr("rebuild_scan_folders_header", "Scan Directories & Drives")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#CBD5E1"
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            StyledButton {
                text: configPane.cardWidth < 480 ? "" : modal.tr("rebuild_reset_defaults", "Reset Defaults")
                iconText: "↺"
                variant: "ghost"
                implicitHeight: 26
                tooltip: modal.tr("rebuild_reset_defaults", "Reset Defaults")
                onClicked: modal.initDirectories()
            }

            StyledButton {
                text: configPane.cardWidth < 420 ? "" : modal.tr("rebuild_add_folder", "Add Folder...")
                iconText: "📁"
                variant: "outline"
                implicitHeight: 26
                tooltip: modal.tr("rebuild_add_folder", "Add Folder...")
                onClicked: {
                    var chosen = modal.bridge.browseFolderDialog("Select Download Folder or Drive to Scan", "")
                    if (chosen) {
                        modal.addDirectory(chosen)
                    }
                }
            }
        }

        // Directory List Container
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.min(130, Math.max(56, dirCol.implicitHeight + 12))
            radius: 8
            color: "#0B0E14"
            border.color: "#1E293B"
            border.width: 1
            clip: true

            SmoothFlickable {
                anchors.fill: parent
                anchors.margins: 6
                contentWidth: width
                contentHeight: dirCol.implicitHeight

                ColumnLayout {
                    id: dirCol
                    width: parent.width
                    spacing: 4

                    Repeater {
                        model: modal.scanDirectories

                        delegate: Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 28
                            radius: 6
                            color: rowHover.containsMouse ? "#161E2E" : "#0F141F"
                            border.color: rowHover.containsMouse ? "#2A374A" : "transparent"
                            border.width: 1

                            MouseArea {
                                id: rowHover
                                anchors.fill: parent
                                hoverEnabled: true
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 6
                                spacing: 8

                                Text {
                                    text: "📁"
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: modelData
                                    font.family: "Consolas, 'Cascadia Code', monospace"
                                    font.pixelSize: 11
                                    color: "#E2E8F0"
                                    Layout.fillWidth: true
                                    elide: Text.ElideMiddle
                                }

                                Rectangle {
                                    width: 18
                                    height: 18
                                    radius: 9
                                    color: delHover.containsMouse ? "#334155" : "transparent"

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✕"
                                        font.pixelSize: 10
                                        color: delHover.containsMouse ? "#F87171" : "#64748B"
                                    }

                                    MouseArea {
                                        id: delHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: modal.removeDirectory(index)
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        text: modal.tr("rebuild_no_folders_hint", "No directories selected. Click 'Add Folder...' to select a download directory or drive.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                        visible: modal.scanDirectories.length === 0
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        Layout.topMargin: 12
                        Layout.bottomMargin: 12
                    }
                }
            }
        }
    }

    // Section: Options
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 6

        StyledCheckBox {
            id: hashCheck
            text: modal.tr("rebuild_opt_hash", "Full SHA-256 Hashing")
            tooltip: modal.tr("rebuild_opt_hash_tip", "Computes cryptographic hashes for 100% duplicate protection. Uncheck for fast timestamp signature mode.")
            checked: modal.fullHashMode
            onCheckedChanged: modal.fullHashMode = checked
        }

        StyledCheckBox {
            id: infoCheck
            text: modal.tr("rebuild_opt_post_info", "Parse post_info.txt Metadata")
            tooltip: modal.tr("rebuild_opt_post_info_tip", "Reads post_info.txt files to recover exact original post IDs, URLs, and creator IDs.")
            checked: modal.detectPostInfo
            onCheckedChanged: modal.detectPostInfo = checked
        }

        StyledCheckBox {
            id: skipCheck
            text: modal.tr("rebuild_opt_skip_existing", "Skip Already Indexed Files")
            tooltip: modal.tr("rebuild_opt_skip_existing_tip", "Bypasses files already recorded in the archive database to save time.")
            checked: modal.skipExisting
            onCheckedChanged: modal.skipExisting = checked
        }
    }
}
