import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── 1. Top Header Card ──────────────────────────────────────────
Rectangle {
    id: headerCard
    required property var view
    Layout.fillWidth: true
    implicitHeight: headerCol.implicitHeight + 24
    radius: 10
    color: "#121722"
    border.color: "#1E293B"
    border.width: 1
    clip: true

    Behavior on implicitHeight {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        id: headerCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 12

        // Sub-row A: Icon + Title/Description + Enable Switch
        // Kept separate from the action buttons so neither side
        // gets squeezed when the console panel narrows the view.
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Item {
                width: 24
                height: 24
                Layout.alignment: Qt.AlignVCenter

                Text {
                    anchors.centerIn: parent
                    text: "🗃️"
                    font.pixelSize: 18
                    scale: hdrIconHover.hovered ? 1.22 : 1.0
                    rotation: hdrIconHover.hovered ? -8 : 0

                    Behavior on scale {
                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.75 }
                    }
                    Behavior on rotation {
                        SpringAnimation { spring: 4.0; damping: 0.32; mass: 0.7 }
                    }
                }

                HoverHandler { id: hdrIconHover }
            }

            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true

                // Title + status badges
                Flow {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: headerCard.view.tr("tab_archive_title", "Download Archive Database")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        color: "#F8FAFC"
                    }

                    // Mode Badge
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: modeBadgeText.implicitWidth + 12
                        radius: 10
                        color: modeHover.hovered ? "#163859" : "#0F2942"
                        border.color: modeHover.hovered ? "#38BDF8" : "#0284C7"
                        border.width: 1
                        scale: modeHover.hovered ? 1.06 : 1.0

                        Behavior on scale {
                            SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                        }
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }

                        HoverHandler { id: modeHover }

                        Text {
                            id: modeBadgeText
                            anchors.centerIn: parent
                            text: "gallery-dl style"
                            font.pixelSize: 9
                            font.weight: 600
                            color: "#38BDF8"
                        }
                    }

                    // Active / Inactive Pill
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: statusPillRow.implicitWidth + 12
                        radius: 10
                        property bool isActive: headerCard.view.bridge ? headerCard.view.bridge.enableDownloadArchive : false
                        color: isActive ? (pillHover.hovered ? "#065F46" : "#064E3B") : (pillHover.hovered ? "#28354A" : "#1E293B")
                        border.color: isActive ? (pillHover.hovered ? "#34D399" : "#10B981") : (pillHover.hovered ? "#64748B" : "#475569")
                        border.width: 1
                        scale: pillHover.hovered ? 1.06 : 1.0

                        Behavior on scale {
                            SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                        }
                        Behavior on color { ColorAnimation { duration: 180 } }
                        Behavior on border.color { ColorAnimation { duration: 180 } }

                        HoverHandler { id: pillHover }

                        RowLayout {
                            id: statusPillRow
                            anchors.centerIn: parent
                            spacing: 4

                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: parent.parent.isActive ? "#34D399" : "#94A3B8"
                                scale: pillHover.hovered ? 1.25 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                                Behavior on color { ColorAnimation { duration: 180 } }
                            }

                            Text {
                                text: parent.parent.isActive
                                    ? headerCard.view.tr("status_archive_active", "Active & Protecting")
                                    : headerCard.view.tr("status_archive_inactive", "Disabled")
                                font.pixelSize: 9
                                font.weight: 600
                                color: parent.parent.isActive ? "#6EE7B7" : "#94A3B8"
                            }
                        }
                    }

                    // Non-blocking busy status pill (live refresh or background archive operation)
                    Rectangle {
                        visible: headerCard.view._activeJobCount > 0 || headerCard.view._isReloadingCreators
                        implicitHeight: 20
                        implicitWidth: busyPillRow.implicitWidth + 12
                        radius: 10
                        color: "#172554"
                        border.color: "#38BDF8"
                        border.width: 1

                        RowLayout {
                            id: busyPillRow
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                text: "⏳"
                                font.pixelSize: 9
                            }

                            Text {
                                text: headerCard.view._activeJobCount > 0
                                    ? (headerCard.view._activeJobText || headerCard.view.tr("status_archive_updating", "Updating..."))
                                    : headerCard.view.tr("status_archive_loading", "Refreshing...")
                                font.pixelSize: 9
                                font.weight: 600
                                color: "#BAE6FD"
                            }
                        }
                    }
                }

                // Description — wraps naturally, no overflow possible
                Text {
                    visible: !headerCard.view.headerCollapsed
                    text: headerCard.view.tr("desc_archive_tab", "Catalog of all downloaded files. When active, files you have already extracted, converted, or deleted locally will not be re-downloaded.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            // Enable / Disable Switch (stays on the right of the title row)
            StyledSwitch {
                checked: headerCard.view.bridge ? headerCard.view.bridge.enableDownloadArchive : false
                accentColor: "#38BDF8"
                onToggled: function(isChecked) {
                    if (headerCard.view.bridge) headerCard.view.bridge.enableDownloadArchive = isChecked
                }
            }

            // Header Collapse / Expand Toggle Button
            Rectangle {
                implicitHeight: 28
                implicitWidth: 28
                radius: 6
                color: collapseBtnMouse.containsMouse ? "#1E293B" : "#161F30"
                border.color: collapseBtnMouse.containsMouse ? "#38BDF8" : "#243248"
                border.width: 1
                scale: collapseBtnMouse.pressed ? 0.9 : (collapseBtnMouse.containsMouse ? 1.08 : 1.0)

                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                Behavior on color { ColorAnimation { duration: 140 } }
                Behavior on border.color { ColorAnimation { duration: 140 } }

                Text {
                    anchors.centerIn: parent
                    text: "▾"
                    font.pixelSize: 13
                    font.bold: true
                    color: collapseBtnMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                    rotation: headerCard.view.headerCollapsed ? -90 : 0

                    Behavior on rotation {
                        SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
                    }
                }

                MouseArea {
                    id: collapseBtnMouse
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 250
                    ToolTip.text: headerCard.view.headerCollapsed
                        ? headerCard.view.tr("tip_expand_header", "Expand header & statistics")
                        : headerCard.view.tr("tip_collapse_header", "Collapse header & statistics")
                    onClicked: headerCard.view.headerCollapsed = !headerCard.view.headerCollapsed
                }
            }
        }

        // Sub-row B: Action Buttons — own row so they never compete
        // for width with the title column.
        RowLayout {
            Layout.fillWidth: true
            visible: !headerCard.view.headerCollapsed
            spacing: 6

            // Spacer pushes buttons to the right
            Item { Layout.fillWidth: true }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : headerCard.view.tr("btn_refresh", "Refresh")
                iconText: "🔄"
                variant: "outline"
                implicitHeight: 30
                tooltip: headerCard.view.tr("btn_refresh_tip", "Reload archive records from database")
                onClicked: headerCard.view.reload()
            }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : ((headerCard.view.bridge && headerCard.view.bridge.isArchiveRebuilding)
                    ? headerCard.view.tr("rebuild_btn_running", "Rebuilding…")
                    : ((headerCard.view.bridge && headerCard.view.bridge.hasSavedArchiveRebuild)
                        ? headerCard.view.tr("rebuild_btn_resume_short", "Resume Rebuild")
                        : headerCard.view.tr("btn_rebuild_archive", "Rebuild")))
                iconText: (headerCard.view.bridge && headerCard.view.bridge.isArchiveRebuilding)
                    ? "⚡"
                    : ((headerCard.view.bridge && headerCard.view.bridge.hasSavedArchiveRebuild) ? "🔄" : "🔨")
                variant: (headerCard.view.bridge && (headerCard.view.bridge.isArchiveRebuilding || headerCard.view.bridge.hasSavedArchiveRebuild)) ? "primary" : "outline"
                implicitHeight: 30
                tooltip: (headerCard.view.bridge && headerCard.view.bridge.isArchiveRebuilding)
                    ? headerCard.view.tr("btn_rebuild_archive_running_tip", "Archive rebuild is running in the background — click to view live progress")
                    : ((headerCard.view.bridge && headerCard.view.bridge.hasSavedArchiveRebuild)
                        ? headerCard.view.tr("btn_rebuild_archive_resume_tip", "An interrupted Archive Rebuild was saved — click to resume from where it left off")
                        : headerCard.view.tr("btn_rebuild_archive_tip", "Scan one or more local download directories to rebuild or sync the archive database"))
                onClicked: {
                    if (typeof appWindow !== "undefined" && typeof appWindow.openArchiveRebuildModal === "function") {
                        appWindow.openArchiveRebuildModal()
                    }
                }
            }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : headerCard.view.tr("btn_fingerprint_videos", "Fingerprint Videos")
                iconText: "🎬"
                variant: "outline"
                implicitHeight: 30
                enabled: !headerCard.view._hasGlobalJob()
                tooltip: headerCard.view.tr("btn_fingerprint_videos_tip", "Scan a folder to calculate SHA-256 fingerprints for existing videos and index them into the archive database")
                onClicked: headerCard.view.openFingerprintDialog()
            }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : headerCard.view.tr("btn_import_archive", "Import")
                iconText: "📥"
                variant: "outline"
                implicitHeight: 30
                enabled: !headerCard.view._hasGlobalJob()
                tooltip: headerCard.view.tr("btn_import_archive_tip", "Import a Pawchive archive backup (.json, .db) or ID-only text list (.txt)")
                onClicked: headerCard.view.openImportDialog()
            }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : headerCard.view.tr("btn_export_archive", "Export")
                iconText: "📤"
                variant: "outline"
                implicitHeight: 30
                tooltip: headerCard.view.tr("btn_export_archive_tip", "Export archive records as a full JSON backup (recommended — keeps creator names) or an ID-only text list")
                onClicked: headerCard.view.openExportDialog()
            }

            StyledButton {
                text: headerCard.view.width < 640 ? "" : headerCard.view.tr("btn_clear_archive", "Clear")
                iconText: "🗑️"
                variant: "danger"
                implicitHeight: 30
                enabled: !headerCard.view._hasGlobalJob()
                tooltip: headerCard.view.tr("btn_clear_archive_tip", "Wipe all records from the archive database")
                onClicked: headerCard.view.openClearConfirm()
            }
        }

        // Non-blocking background job progress bar
        Rectangle {
            visible: headerCard.view._activeJobCount > 0 || headerCard.view._isReloadingCreators
            Layout.fillWidth: true
            implicitHeight: 24
            radius: 6
            color: "#0C1524"
            border.color: "#1E3A5F"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                Text {
                    text: headerCard.view._activeJobCount > 0
                        ? ((headerCard.view._activeJobText || "Running background archive job...") + (headerCard.view._activeJobCount > 1 ? (" (+" + (headerCard.view._activeJobCount - 1) + ")") : ""))
                        : headerCard.view.tr("msg_archive_loading_creators", "Loading creator index...")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#93C5FD"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        // Telemetry Micro-Cards — GridLayout wraps to 2×2 when the
        // view is narrow (console panel open) so cards never overflow.
        GridLayout {
            Layout.fillWidth: true
            visible: !headerCard.view.headerCollapsed
            columns: headerCard.view.width < 620 ? 2 : 4
            rowSpacing: 8
            columnSpacing: 8

            // Stat 1: Total Files & Links
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 8
                color: statHover1.hovered ? "#141B29" : "#0D111A"
                border.color: statHover1.hovered ? "#38BDF8" : "#1E2638"
                border.width: 1
                scale: statHover1.hovered ? 1.02 : 1.0

                transform: Translate {
                    y: statHover1.hovered ? -2.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                }
                Behavior on color { ColorAnimation { duration: 160 } }
                Behavior on border.color { ColorAnimation { duration: 160 } }

                HoverHandler { id: statHover1 }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    // Icon Box
                    Rectangle {
                        width: 34
                        height: 34
                        radius: 7
                        color: statHover1.hovered ? "#0C3854" : "#082F49"
                        border.color: statHover1.hovered ? "#38BDF8" : "#0284C7"
                        border.width: 1
                        scale: statHover1.hovered ? 1.12 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Text {
                            anchors.centerIn: parent
                            text: "📦"
                            font.pixelSize: 15
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: (headerCard.view.statistics ? headerCard.view.statistics.total_files : 0).toLocaleString()
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }
                        Text {
                            text: headerCard.view.tr("stat_total_files", "Files Indexed")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: statHover1.hovered ? "#94A3B8" : "#64748B"
                            elide: Text.ElideRight
                        }
                    }

                    // Right-side indicator: Links badge or Indexed pill
                    Rectangle {
                        property int linkCount: (headerCard.view.statistics && headerCard.view.statistics.category_counts) ? headerCard.view.statistics.category_counts.links || 0 : 0
                        visible: headerCard.view.width >= 460 || linkCount > 0
                        implicitHeight: 18
                        Layout.preferredHeight: 18
                        implicitWidth: 66
                        Layout.preferredWidth: 66
                        radius: 9
                        color: linkCount > 0 ? "#083344" : "#162030"
                        border.color: linkCount > 0 ? "#06B6D4" : "#242E42"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: stat1BadgeText
                            anchors.centerIn: parent
                            text: parent.linkCount > 0 ? ("🔗 " + parent.linkCount) : "Indexed"
                            font.pixelSize: 9
                            font.bold: true
                            color: parent.linkCount > 0 ? "#22D3EE" : "#64748B"
                        }
                    }
                }
            }

            // Stat 2: Total Creators
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 8
                color: statHover2.hovered ? "#18152E" : "#0D111A"
                border.color: statHover2.hovered ? "#A78BFA" : "#1E2638"
                border.width: 1
                scale: statHover2.hovered ? 1.02 : 1.0

                transform: Translate {
                    y: statHover2.hovered ? -2.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                }
                Behavior on color { ColorAnimation { duration: 160 } }
                Behavior on border.color { ColorAnimation { duration: 160 } }

                HoverHandler { id: statHover2 }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    // Icon Box
                    Rectangle {
                        width: 34
                        height: 34
                        radius: 7
                        color: statHover2.hovered ? "#3B1478" : "#2E1065"
                        border.color: statHover2.hovered ? "#C084FC" : "#7C3AED"
                        border.width: 1
                        scale: statHover2.hovered ? 1.12 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Text {
                            anchors.centerIn: parent
                            text: "👤"
                            font.pixelSize: 15
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: (headerCard.view.statistics ? headerCard.view.statistics.total_creators : 0).toLocaleString()
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.bold: true
                            color: "#C4B5FD"
                            elide: Text.ElideRight
                        }
                        Text {
                            text: headerCard.view.tr("stat_total_creators", "Creators Protected")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: statHover2.hovered ? "#C4B5FD" : "#64748B"
                            elide: Text.ElideRight
                        }
                    }

                    // Right-side indicator: Protected pill
                    Rectangle {
                        visible: headerCard.view.width >= 460
                        implicitHeight: 18
                        Layout.preferredHeight: 18
                        implicitWidth: 66
                        Layout.preferredWidth: 66
                        radius: 9
                        color: "#24143D"
                        border.color: "#581C87"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: stat2BadgeText
                            anchors.centerIn: parent
                            text: "Protected"
                            font.pixelSize: 9
                            font.bold: true
                            color: "#A78BFA"
                        }
                    }
                }
            }

            // Stat 3: Total Posts
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 8
                color: statHover3.hovered ? "#101B2E" : "#0D111A"
                border.color: statHover3.hovered ? "#38BDF8" : "#1E2638"
                border.width: 1
                scale: statHover3.hovered ? 1.02 : 1.0

                transform: Translate {
                    y: statHover3.hovered ? -2.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                }
                Behavior on color { ColorAnimation { duration: 160 } }
                Behavior on border.color { ColorAnimation { duration: 160 } }

                HoverHandler { id: statHover3 }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    // Icon Box
                    Rectangle {
                        width: 34
                        height: 34
                        radius: 7
                        color: statHover3.hovered ? "#0C3854" : "#0F2942"
                        border.color: statHover3.hovered ? "#38BDF8" : "#0284C7"
                        border.width: 1
                        scale: statHover3.hovered ? 1.12 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Text {
                            anchors.centerIn: parent
                            text: "📑"
                            font.pixelSize: 15
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: (headerCard.view.statistics ? headerCard.view.statistics.total_posts : 0).toLocaleString()
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.bold: true
                            color: "#7DD3FC"
                            elide: Text.ElideRight
                        }
                        Text {
                            text: headerCard.view.tr("stat_total_posts", "Posts Cataloged")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: statHover3.hovered ? "#7DD3FC" : "#64748B"
                            elide: Text.ElideRight
                        }
                    }

                    // Right-side indicator: Catalog pill
                    Rectangle {
                        visible: headerCard.view.width >= 460
                        implicitHeight: 18
                        Layout.preferredHeight: 18
                        implicitWidth: 66
                        Layout.preferredWidth: 66
                        radius: 9
                        color: "#0F243A"
                        border.color: "#0369A1"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: stat3BadgeText
                            anchors.centerIn: parent
                            text: "Catalog"
                            font.pixelSize: 9
                            font.bold: true
                            color: "#38BDF8"
                        }
                    }
                }
            }

            // Stat 4: Database Size
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 52
                radius: 8
                color: statHover4.hovered ? "#0C231E" : "#0D111A"
                border.color: statHover4.hovered ? "#34D399" : "#1E2638"
                border.width: 1
                scale: statHover4.hovered ? 1.02 : 1.0

                transform: Translate {
                    y: statHover4.hovered ? -2.5 : 0
                    Behavior on y {
                        SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 }
                }
                Behavior on color { ColorAnimation { duration: 160 } }
                Behavior on border.color { ColorAnimation { duration: 160 } }

                HoverHandler { id: statHover4 }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10

                    // Icon Box
                    Rectangle {
                        width: 34
                        height: 34
                        radius: 7
                        color: statHover4.hovered ? "#065F46" : "#064E3B"
                        border.color: statHover4.hovered ? "#34D399" : "#059669"
                        border.width: 1
                        scale: statHover4.hovered ? 1.12 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Text {
                            anchors.centerIn: parent
                            text: "💾"
                            font.pixelSize: 15
                        }
                    }

                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: headerCard.view.statistics ? headerCard.view.statistics.db_size_str : "0 KB"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 15
                            font.bold: true
                            color: "#6EE7B7"
                            elide: Text.ElideRight
                        }
                        Text {
                            text: headerCard.view.tr("stat_db_size", "Database Size")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: statHover4.hovered ? "#6EE7B7" : "#64748B"
                            elide: Text.ElideRight
                        }
                    }

                    // Right-side indicator: SQLite pill
                    Rectangle {
                        visible: headerCard.view.width >= 460
                        implicitHeight: 18
                        Layout.preferredHeight: 18
                        implicitWidth: 66
                        Layout.preferredWidth: 66
                        radius: 9
                        color: "#064E3B"
                        border.color: "#047857"
                        border.width: 1
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            id: stat4BadgeText
                            anchors.centerIn: parent
                            text: "SQLite"
                            font.pixelSize: 9
                            font.bold: true
                            color: "#34D399"
                        }
                    }
                }
            }
        }
    }
}
