import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"

Rectangle {
    id: root

    property var bridge: null
    property var hierarchyData: []
    property var statistics: ({
        total_files: 0,
        total_creators: 0,
        total_posts: 0,
        db_size_str: "0 KB",
        category_counts: {},
        service_counts: {}
    })

    property string searchFilter: ""
    property string serviceFilter: "all"
    property string fileTypeFilter: "all"
    property string sortOrder: "creator_az"
    property var collapsedCreators: ({})
    property var collapsedPosts: ({})
    property bool headerCollapsed: false

    // Verification state map: key = service+":"+creatorId
    // value = { running: bool, current: int, total: int, present: int, missing: int, done: bool }
    property var verificationState: ({})

    function _verifyKey(service, creatorId) { return service + ":" + creatorId }
    function creatorVerifyState(service, creatorId) {
        return verificationState[_verifyKey(service, creatorId)] || null
    }

    color: "#0B0E14"

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    function reload() {
        if (!root.bridge) return
        root.hierarchyData = root.bridge.getArchiveHierarchy(root.searchFilter, root.serviceFilter, root.fileTypeFilter, root.sortOrder)
        root.statistics = root.bridge.getArchiveStatistics()
    }

    Connections {
        target: root.bridge
        function onArchiveUpdated() {
            root.reload()
        }
        function onArchiveRecordCountChanged() {
            root.reload()
        }
        function onEnableDownloadArchiveChanged() {
            root.reload()
        }

        function onArchiveCreatorVerificationStarted(service, creatorId) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            newMap[key] = { running: true, current: 0, total: 0, present: 0, missing: 0, done: false }
            root.verificationState = newMap
        }

        function onArchiveCreatorVerificationProgress(service, creatorId, current, total) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            var prev = newMap[key] || { running: true, current: 0, total: 0, present: 0, missing: 0, done: false }
            newMap[key] = Object.assign({}, prev, { current: current, total: total })
            root.verificationState = newMap
        }

        function onArchiveCreatorVerificationFinished(service, creatorId, result) {
            var key = root._verifyKey(service, creatorId)
            var newMap = Object.assign({}, root.verificationState)
            newMap[key] = {
                running: false, done: true,
                current: result.total || 0, total: result.total || 0,
                present: result.present || 0, missing: result.missing || 0
            }
            root.verificationState = newMap
        }
    }

    Component.onCompleted: {
        root.reload()
    }

    // Status Toast notification overlay
    property string toastMessage: ""
    property bool toastVisible: false
    Timer {
        id: toastTimer
        interval: 3000
        onTriggered: root.toastVisible = false
    }
    function showToast(msg) {
        toastMessage = msg
        toastVisible = true
        toastTimer.restart()
    }

    // Main Layout
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // ── 1. Top Header Card ──────────────────────────────────────────
        Rectangle {
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
                                text: root.tr("tab_archive_title", "Download Archive Database")
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
                                property bool isActive: root.bridge ? root.bridge.enableDownloadArchive : false
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
                                            ? root.tr("status_archive_active", "Active & Protecting")
                                            : root.tr("status_archive_inactive", "Disabled")
                                        font.pixelSize: 9
                                        font.weight: 600
                                        color: parent.parent.isActive ? "#6EE7B7" : "#94A3B8"
                                    }
                                }
                            }
                        }

                        // Description — wraps naturally, no overflow possible
                        Text {
                            visible: !root.headerCollapsed
                            text: root.tr("desc_archive_tab", "Catalog of all downloaded files. When active, files you have already extracted, converted, or deleted locally will not be re-downloaded.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    // Enable / Disable Switch (stays on the right of the title row)
                    StyledSwitch {
                        checked: root.bridge ? root.bridge.enableDownloadArchive : false
                        accentColor: "#38BDF8"
                        onToggled: function(isChecked) {
                            if (root.bridge) root.bridge.enableDownloadArchive = isChecked
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
                            rotation: root.headerCollapsed ? -90 : 0

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
                            ToolTip.text: root.headerCollapsed
                                ? root.tr("tip_expand_header", "Expand header & statistics")
                                : root.tr("tip_collapse_header", "Collapse header & statistics")
                            onClicked: root.headerCollapsed = !root.headerCollapsed
                        }
                    }
                }

                // Sub-row B: Action Buttons — own row so they never compete
                // for width with the title column.
                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.headerCollapsed
                    spacing: 6

                    // Spacer pushes buttons to the right
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: root.width < 640 ? "" : root.tr("btn_refresh", "Refresh")
                        iconText: "🔄"
                        variant: "outline"
                        implicitHeight: 30
                        tooltip: root.tr("btn_refresh_tip", "Reload archive records from database")
                        onClicked: root.reload()
                    }

                    StyledButton {
                        text: root.width < 640 ? "" : root.tr("btn_import_archive", "Import")
                        iconText: "📥"
                        variant: "outline"
                        implicitHeight: 30
                        tooltip: root.tr("btn_import_archive_tip", "Import gallery-dl archive.txt or Pawchive JSON export")
                        onClicked: importFileDialog.open()
                    }

                    StyledButton {
                        text: root.width < 640 ? "" : root.tr("btn_export_archive", "Export")
                        iconText: "📤"
                        variant: "outline"
                        implicitHeight: 30
                        tooltip: root.tr("btn_export_archive_tip", "Export archive records to gallery-dl TXT or JSON")
                        onClicked: exportFileDialog.open()
                    }

                    StyledButton {
                        text: root.width < 640 ? "" : root.tr("btn_clear_archive", "Clear")
                        iconText: "🗑️"
                        variant: "danger"
                        implicitHeight: 30
                        tooltip: root.tr("btn_clear_archive_tip", "Wipe all records from the archive database")
                        onClicked: clearConfirmModal.isOpen = true
                    }
                }

                // Telemetry Micro-Cards — GridLayout wraps to 2×2 when the
                // view is narrow (console panel open) so cards never overflow.
                GridLayout {
                    Layout.fillWidth: true
                    visible: !root.headerCollapsed
                    columns: root.width < 620 ? 2 : 4
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
                                    text: (root.statistics ? root.statistics.total_files : 0).toLocaleString()
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: "#F8FAFC"
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: root.tr("stat_total_files", "Files Indexed")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: statHover1.hovered ? "#94A3B8" : "#64748B"
                                    elide: Text.ElideRight
                                }
                            }

                            // Right-side indicator: Links badge or Indexed pill
                            Rectangle {
                                property int linkCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.links || 0 : 0
                                visible: root.width >= 460 || linkCount > 0
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
                                    text: (root.statistics ? root.statistics.total_creators : 0).toLocaleString()
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: "#C4B5FD"
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: root.tr("stat_total_creators", "Creators Protected")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: statHover2.hovered ? "#C4B5FD" : "#64748B"
                                    elide: Text.ElideRight
                                }
                            }

                            // Right-side indicator: Protected pill
                            Rectangle {
                                visible: root.width >= 460
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
                                    text: (root.statistics ? root.statistics.total_posts : 0).toLocaleString()
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: "#7DD3FC"
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: root.tr("stat_total_posts", "Posts Cataloged")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: statHover3.hovered ? "#7DD3FC" : "#64748B"
                                    elide: Text.ElideRight
                                }
                            }

                            // Right-side indicator: Catalog pill
                            Rectangle {
                                visible: root.width >= 460
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
                                    text: root.statistics ? root.statistics.db_size_str : "0 KB"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: "#6EE7B7"
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: root.tr("stat_db_size", "Database Size")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: statHover4.hovered ? "#6EE7B7" : "#64748B"
                                    elide: Text.ElideRight
                                }
                            }

                            // Right-side indicator: SQLite pill
                            Rectangle {
                                visible: root.width >= 460
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

        // ── 2. Filter, Search & Category Strip ─────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: filterStripCol.implicitHeight + 16
            radius: 8
            color: "#0F131C"
            border.color: "#1B2232"
            border.width: 1

            ColumnLayout {
                id: filterStripCol
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                // Search & Sort Row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // Search input with debouncer
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        radius: 6
                        color: searchInput.activeFocus ? "#1B2232" : (searchBoxHover.hovered ? "#19202E" : "#161B26")
                        border.color: searchInput.activeFocus ? "#38BDF8" : (searchBoxHover.hovered ? "#334155" : "#242E42")
                        border.width: 1

                        Behavior on border.color { ColorAnimation { duration: 150 } }
                        Behavior on color { ColorAnimation { duration: 150 } }

                        HoverHandler { id: searchBoxHover }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 8
                            spacing: 6

                            Text {
                                text: "🔍"
                                font.pixelSize: 11
                                color: "#64748B"
                                scale: searchBoxHover.hovered ? 1.15 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7 } }
                            }

                            TextInput {
                                id: searchInput
                                Layout.fillWidth: true
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: "#F8FAFC"
                                selectByMouse: true
                                text: root.searchFilter

                                Text {
                                    text: root.tr("placeholder_archive_search", "Search files, links, creators, posts, hashes...")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#475569"
                                    visible: !searchInput.text && !searchInput.activeFocus
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    elide: Text.ElideRight
                                }

                                onTextChanged: {
                                    searchDebounceTimer.restart()
                                }
                            }

                            Timer {
                                id: searchDebounceTimer
                                interval: 250
                                onTriggered: {
                                    root.searchFilter = searchInput.text
                                    root.reload()
                                }
                            }

                            // Clear button
                            Text {
                                text: "✕"
                                font.pixelSize: 10
                                color: clearSearchMouse.containsMouse ? "#F8FAFC" : "#64748B"
                                visible: searchInput.text.length > 0
                                scale: clearSearchMouse.pressed ? 0.82 : (clearSearchMouse.containsMouse ? 1.25 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }

                                MouseArea {
                                    id: clearSearchMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    hoverEnabled: true
                                    onClicked: {
                                        searchInput.text = ""
                                        root.searchFilter = ""
                                        root.reload()
                                    }
                                }
                            }
                        }
                    }

                    // Sort Order selector
                    Rectangle {
                        id: sortSelectorBtn
                        Layout.preferredWidth: 160
                        Layout.preferredHeight: 32
                        radius: 6
                        color: sortPopup.visible ? "#1E2A3F" : (sortMouse.containsMouse ? "#1C2333" : "#161B26")
                        border.color: sortPopup.visible ? "#38BDF8" : (sortMouse.containsMouse ? "#38BDF8" : "#242E42")
                        border.width: sortPopup.visible ? 1.5 : 1
                        scale: sortMouse.pressed ? 0.96 : (sortMouse.containsMouse ? 1.02 : 1.0)

                        transform: Translate {
                            y: (sortMouse.containsMouse && !sortPopup.visible) ? -1.5 : 0
                            Behavior on y {
                                SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                            }
                        }

                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 9
                            spacing: 6

                            Text {
                                text: {
                                    if (root.sortOrder === "creator_az") return "🔤"
                                    if (root.sortOrder === "creator_za") return "🔤"
                                    if (root.sortOrder === "files_desc") return "📦"
                                    if (root.sortOrder === "newest") return "🕒"
                                    if (root.sortOrder === "oldest") return "📅"
                                    return "↕"
                                }
                                font.pixelSize: 11
                                scale: sortMouse.containsMouse ? 1.15 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: {
                                    if (root.sortOrder === "creator_az") return root.tr("sort_creator_az", "Creator A-Z")
                                    if (root.sortOrder === "creator_za") return root.tr("sort_creator_za", "Creator Z-A")
                                    if (root.sortOrder === "files_desc") return root.tr("sort_files_desc", "Most Files")
                                    if (root.sortOrder === "newest") return root.tr("sort_newest", "Newest Added")
                                    if (root.sortOrder === "oldest") return root.tr("sort_oldest", "Oldest Added")
                                    return root.tr("sort_creator_az", "Creator A-Z")
                                }
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: sortPopup.visible ? "#38BDF8" : "#E2E8F0"
                                elide: Text.ElideRight
                            }

                            Text {
                                text: "▾"
                                font.pixelSize: 10
                                color: sortPopup.visible ? "#38BDF8" : "#64748B"
                                rotation: sortPopup.visible ? 180 : 0
                                transformOrigin: Item.Center
                                Behavior on rotation {
                                    SpringAnimation { spring: 5.0; damping: 0.4; mass: 0.8 }
                                }
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }

                        MouseArea {
                            id: sortMouse
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            hoverEnabled: true
                            onClicked: {
                                if (sortPopup.visible) {
                                    sortPopup.close()
                                } else {
                                    sortPopup.open()
                                }
                            }
                        }

                        Popup {
                            id: sortPopup
                            objectName: "sortPopup"
                            y: parent.height + 4
                            width: 175
                            padding: 5
                            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
                            transformOrigin: Popup.Top

                            enter: Transition {
                                NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                                NumberAnimation { property: "scale"; from: 0.94; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                            }
                            exit: Transition {
                                NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 100; easing.type: Easing.InCubic }
                                NumberAnimation { property: "scale"; from: 1.0; to: 0.96; duration: 100; easing.type: Easing.InCubic }
                            }

                            background: Rectangle {
                                color: "#0E1422"
                                border.color: "#1E293B"
                                border.width: 1.5
                                radius: 8
                            }

                            contentItem: ColumnLayout {
                                spacing: 3

                                Repeater {
                                    model: [
                                        { key: "creator_az", label: root.tr("sort_creator_az", "Creator A-Z"), icon: "🔤", tag: "A → Z" },
                                        { key: "creator_za", label: root.tr("sort_creator_za", "Creator Z-A"), icon: "🔤", tag: "Z → A" },
                                        { key: "files_desc", label: root.tr("sort_files_desc", "Most Files"), icon: "📦", tag: "Count" },
                                        { key: "newest", label: root.tr("sort_newest", "Newest Added"), icon: "🕒", tag: "Recent" },
                                        { key: "oldest", label: root.tr("sort_oldest", "Oldest Added"), icon: "📅", tag: "Earliest" }
                                    ]

                                    delegate: Rectangle {
                                        id: sortItemRect
                                        Layout.fillWidth: true
                                        implicitHeight: 32
                                        radius: 6

                                        readonly property bool isSelected: root.sortOrder === modelData.key
                                        readonly property bool isHovered: itemMouseArea.containsMouse

                                        color: isSelected ? "#162234" : (isHovered ? "#151D2C" : "transparent")
                                        border.color: isSelected ? "#1E3A5F" : (isHovered ? "#1E293B" : "transparent")
                                        border.width: 1
                                        clip: true

                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        Behavior on border.color { ColorAnimation { duration: 100 } }

                                        // Left accent bar
                                        Rectangle {
                                            width: 3
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            anchors.topMargin: 4
                                            anchors.bottomMargin: 4
                                            radius: 1.5
                                            color: "#38BDF8"
                                            visible: sortItemRect.isSelected
                                        }

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: sortItemRect.isSelected ? 10 : 8
                                            anchors.rightMargin: 8
                                            spacing: 7

                                            Text {
                                                text: modelData.icon
                                                font.pixelSize: 11
                                                opacity: sortItemRect.isSelected ? 1.0 : 0.75
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.label
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.weight: sortItemRect.isSelected ? Font.DemiBold : Font.Normal
                                                color: sortItemRect.isSelected ? "#38BDF8" : (sortItemRect.isHovered ? "#F1F5F9" : "#CBD5E1")
                                                elide: Text.ElideRight
                                            }

                                            // Sub-tag badge
                                            Rectangle {
                                                implicitHeight: 16
                                                implicitWidth: tagTxt.implicitWidth + 8
                                                radius: 4
                                                color: sortItemRect.isSelected ? "#0F2942" : "#131A26"
                                                border.color: sortItemRect.isSelected ? "#0369A1" : "#1E293B"
                                                border.width: 1

                                                Text {
                                                    id: tagTxt
                                                    anchors.centerIn: parent
                                                    text: modelData.tag
                                                    font.pixelSize: 9
                                                    font.weight: Font.DemiBold
                                                    color: sortItemRect.isSelected ? "#7DD3FC" : "#64748B"
                                                }
                                            }

                                            Text {
                                                text: "✓"
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#38BDF8"
                                                visible: sortItemRect.isSelected
                                            }
                                        }

                                        MouseArea {
                                            id: itemMouseArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.sortOrder = modelData.key
                                                root.reload()
                                                sortPopup.close()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Expand / Collapse All toggle
                    StyledButton {
                        property bool allExpanded: Object.keys(root.collapsedCreators).length === 0
                        text: allExpanded ? root.tr("btn_collapse_all", "Collapse All") : root.tr("btn_expand_all", "Expand All")
                        iconText: allExpanded ? "🔼" : "🔽"
                        variant: "outline"
                        implicitHeight: 32
                        onClicked: {
                            if (allExpanded) {
                                var newMap = {}
                                for (var i = 0; i < root.hierarchyData.length; i++) {
                                    newMap[root.hierarchyData[i].creator_name] = true
                                }
                                root.collapsedCreators = newMap
                            } else {
                                root.collapsedCreators = {}
                            }
                        }
                    }
                }

                // File Type Category Pills Container with Smooth Scroll & Navigation Arrows
                Item {
                    id: catContainer
                    Layout.fillWidth: true
                    implicitHeight: 34

                    readonly property bool canScrollLeft: catFlickable.contentX > 2
                    readonly property bool canScrollRight: catFlickable.contentX < (catFlickable.contentWidth - catFlickable.width - 2)
                    readonly property bool isOverflowing: catFlickable.contentWidth > catFlickable.width

                    function scrollBy(delta) {
                        var targetX = catFlickable.contentX + delta
                        var maxX = Math.max(0, catFlickable.contentWidth - catFlickable.width)
                        catScrollAnim.to = Math.max(0, Math.min(maxX, targetX))
                        catScrollAnim.restart()
                    }

                    NumberAnimation {
                        id: catScrollAnim
                        target: catFlickable
                        property: "contentX"
                        duration: 180
                        easing.type: Easing.OutCubic
                    }

                    RowLayout {
                        anchors.fill: parent
                        spacing: 4

                        // Left Arrow Button
                        Rectangle {
                            id: leftScrollBtn
                            Layout.preferredWidth: (catContainer.isOverflowing && catContainer.canScrollLeft) ? 24 : 0
                            Layout.preferredHeight: 26
                            visible: catContainer.isOverflowing
                            opacity: catContainer.canScrollLeft ? 1.0 : 0.0
                            radius: 6
                            color: leftScrollMouse.containsMouse ? "#1E293B" : "#131824"
                            border.color: leftScrollMouse.containsMouse ? "#38BDF8" : "#1F293D"
                            border.width: 1
                            clip: true

                            Behavior on Layout.preferredWidth { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Text {
                                anchors.centerIn: parent
                                text: "◀"
                                font.pixelSize: 10
                                color: leftScrollMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                            }

                            MouseArea {
                                id: leftScrollMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: catContainer.scrollBy(-180)
                            }
                        }

                        // Flickable
                        Flickable {
                            id: catFlickable
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            contentWidth: catPillsRow.implicitWidth + 8
                            contentHeight: height
                            flickableDirection: Flickable.HorizontalFlick
                            boundsBehavior: Flickable.StopAtBounds
                            clip: true

                            onWidthChanged: {
                                var maxX = Math.max(0, contentWidth - width)
                                if (contentX > maxX) contentX = maxX
                            }
                            onContentWidthChanged: {
                                var maxX = Math.max(0, contentWidth - width)
                                if (contentX > maxX) contentX = maxX
                            }

                            WheelHandler {
                                id: catWheelHandler
                                target: catFlickable
                                orientation: Qt.Horizontal | Qt.Vertical
                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                onWheel: function(event) {
                                    var delta = event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
                                    catContainer.scrollBy(-delta)
                                }
                            }

                            RowLayout {
                                id: catPillsRow
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 6

                                // Helper component for category pill
                                component CategoryPill: Rectangle {
                                    property string catId: ""
                                    property string catLabel: ""
                                    property string catIcon: ""
                                    property int catCount: 0
                                    property string activeColor: "#38BDF8"

                                    property bool isSelected: root.fileTypeFilter === catId
                                    implicitHeight: 24
                                    implicitWidth: pillInnerRow.implicitWidth + 16
                                    radius: 12

                                    color: isSelected ? activeColor : (pillMouse.containsMouse ? "#1E2638" : "#131824")
                                    border.color: isSelected ? activeColor : (pillMouse.containsMouse ? "#334155" : "#1F293D")
                                    border.width: 1

                                    scale: pillMouse.pressed ? 0.93 : (pillMouse.containsMouse ? 1.05 : 1.0)
                                    transformOrigin: Item.Center
                                    transform: Translate {
                                        y: pillMouse.containsMouse ? -1.5 : 0
                                        Behavior on y { SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.8; epsilon: 0.1 } }
                                    }

                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                    Behavior on border.color { ColorAnimation { duration: 140 } }

                                    RowLayout {
                                        id: pillInnerRow
                                        anchors.centerIn: parent
                                        spacing: 5

                                        Text {
                                            text: catIcon
                                            font.pixelSize: 10
                                            visible: catIcon.length > 0
                                            scale: pillMouse.containsMouse ? 1.2 : 1.0
                                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                        }

                                        Text {
                                            text: catLabel
                                            font.family: "Segoe UI, sans-serif"
                                            font.pixelSize: 10
                                            font.weight: isSelected ? 600 : Font.Normal
                                            color: isSelected ? "#0F172A" : "#E2E8F0"
                                        }

                                        Rectangle {
                                            visible: catCount > 0
                                            implicitHeight: 14
                                            implicitWidth: countTxt.implicitWidth + 6
                                            radius: 7
                                            color: isSelected ? "#0F172A" : "#1E293B"
                                            scale: isSelected ? 1.08 : 1.0
                                            Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 } }

                                            Text {
                                                id: countTxt
                                                anchors.centerIn: parent
                                                text: catCount.toString()
                                                font.pixelSize: 8
                                                font.bold: true
                                                color: isSelected ? activeColor : "#94A3B8"
                                            }
                                        }
                                    }

                                    MouseArea {
                                        id: pillMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        onClicked: {
                                            root.fileTypeFilter = catId
                                            root.reload()
                                        }
                                    }
                                }

                                CategoryPill {
                                    catId: "all"
                                    catLabel: root.tr("pill_all_files", "All Files")
                                    catCount: root.statistics ? root.statistics.total_files : 0
                                    activeColor: "#38BDF8"
                                }

                                CategoryPill {
                                    catId: "archives"
                                    catIcon: "📦"
                                    catLabel: root.tr("pill_archives", "Archives (.zip, .rar)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.archives || 0 : 0
                                    activeColor: "#F59E0B"
                                }

                                CategoryPill {
                                    catId: "graphics"
                                    catIcon: "🎨"
                                    catLabel: root.tr("pill_graphics", "Graphics (.psd, .clip)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.graphics || 0 : 0
                                    activeColor: "#38BDF8"
                                }

                                CategoryPill {
                                    catId: "images"
                                    catIcon: "🖼️"
                                    catLabel: root.tr("pill_images", "Images (.png, .jpg)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.images || 0 : 0
                                    activeColor: "#10B981"
                                }

                                CategoryPill {
                                    catId: "videos"
                                    catIcon: "🎬"
                                    catLabel: root.tr("pill_videos", "Videos (.mp4, .mkv)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.videos || 0 : 0
                                    activeColor: "#EC4899"
                                }

                                CategoryPill {
                                    catId: "audio"
                                    catIcon: "🎵"
                                    catLabel: root.tr("pill_audio", "Audio (.mp3, .wav)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.audio || 0 : 0
                                    activeColor: "#A855F7"
                                }

                                CategoryPill {
                                    catId: "documents"
                                    catIcon: "📄"
                                    catLabel: root.tr("pill_documents", "Documents (.pdf, .txt)")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.documents || 0 : 0
                                    activeColor: "#94A3B8"
                                }

                                CategoryPill {
                                    catId: "links"
                                    catIcon: "🔗"
                                    catLabel: root.tr("pill_links", "Links & Embeds")
                                    catCount: (root.statistics && root.statistics.category_counts) ? root.statistics.category_counts.links || 0 : 0
                                    activeColor: "#06B6D4"
                                }
                            }
                        }

                        // Right Arrow Button
                        Rectangle {
                            id: rightScrollBtn
                            Layout.preferredWidth: (catContainer.isOverflowing && catContainer.canScrollRight) ? 24 : 0
                            Layout.preferredHeight: 26
                            visible: catContainer.isOverflowing
                            opacity: catContainer.canScrollRight ? 1.0 : 0.0
                            radius: 6
                            color: rightScrollMouse.containsMouse ? "#1E293B" : "#131824"
                            border.color: rightScrollMouse.containsMouse ? "#38BDF8" : "#1F293D"
                            border.width: 1
                            clip: true

                            Behavior on Layout.preferredWidth { NumberAnimation { duration: 150; easing.type: Easing.OutQuad } }
                            Behavior on opacity { NumberAnimation { duration: 150 } }
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Text {
                                anchors.centerIn: parent
                                text: "▶"
                                font.pixelSize: 10
                                color: rightScrollMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                            }

                            MouseArea {
                                id: rightScrollMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: catContainer.scrollBy(180)
                            }
                        }
                    }
                }
            }
        }

        // ── 3. Hierarchical Accordion View (Creator ➔ Post ➔ Files) ────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Empty State
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 12
                visible: root.hierarchyData.length === 0

                Text {
                    text: "🗃️"
                    font.pixelSize: 42
                    Layout.alignment: Qt.AlignHCenter
                    opacity: 0.6
                }

                Text {
                    text: root.searchFilter.length > 0
                          ? root.tr("empty_archive_search", "No archived files match your search criteria.")
                          : root.tr("empty_archive_empty", "The download archive database is currently empty.")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 14
                    font.weight: 600
                    color: "#94A3B8"
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: root.searchFilter.length > 0
                          ? root.tr("empty_archive_search_sub", "Try searching for a different keyword, artist, post ID, or file extension.")
                          : root.tr("empty_archive_empty_sub", "When 'Active & Protecting' is toggled ON, every successfully downloaded file is indexed here so it won't be re-downloaded.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                    Layout.alignment: Qt.AlignHCenter
                }

                StyledButton {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.tr("btn_import_archive_empty", "Import gallery-dl archive.txt")
                    iconText: "📥"
                    variant: "outline"
                    visible: root.searchFilter.length === 0
                    onClicked: importFileDialog.open()
                }
            }

            // SmoothListView with virtual scrolling
            SmoothListView {
                id: creatorsListView
                anchors.fill: parent
                visible: root.hierarchyData.length > 0
                spacing: 8
                model: root.hierarchyData

                delegate: Rectangle {
                    id: creatorCard
                    width: creatorsListView.width
                    radius: 8
                    clip: true

                    property var creatorModel: modelData
                    property bool isCollapsed: root.collapsedCreators[creatorModel.creator_name] === true

                    property int creatorMissingCount: {
                        if (typeof creatorModel.missing_count !== "undefined") return creatorModel.missing_count
                        var count = 0
                        if (creatorModel && creatorModel.posts) {
                            for (var p = 0; p < creatorModel.posts.length; p++) {
                                var post = creatorModel.posts[p]
                                if (post.files) {
                                    for (var f = 0; f < post.files.length; f++) {
                                        if (post.files[f].is_missing === 1) count++
                                    }
                                }
                            }
                        }
                        return count
                    }
                    property int creatorTotalCount: creatorModel.total_files || 0
                    property bool isCreatorSomeMissing: creatorMissingCount > 0 && creatorMissingCount < creatorTotalCount
                    property bool isCreatorAllMissing: creatorTotalCount > 0 && creatorMissingCount >= creatorTotalCount

                    color: isCreatorHovered.hovered
                        ? (isCreatorAllMissing ? "#1C0D11" : (isCreatorSomeMissing ? "#1C140A" : "#161D2C"))
                        : (isCreatorAllMissing ? "#14080B" : (isCreatorSomeMissing ? "#140E07" : "#121722"))
                    border.color: isCreatorHovered.hovered
                        ? (isCreatorAllMissing ? "#EF4444" : (isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF"))
                        : (isCreatorAllMissing ? "#991B1B" : (isCreatorSomeMissing ? "#B45309" : "#1E2738"))
                    border.width: 1

                    implicitHeight: creatorCardCol.implicitHeight + 16
                    Behavior on implicitHeight {
                        enabled: !creatorsListView.isScrolling
                        SpringAnimation {
                            spring: 3.4
                            damping: 0.36
                            mass: 1.05
                            epsilon: 1.0
                        }
                    }

                    transform: Translate {
                        y: isCreatorHovered.hovered && !creatorsListView.isScrolling ? -2.0 : 0
                        Behavior on y {
                            enabled: !creatorsListView.isScrolling
                            SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.9; epsilon: 0.1 }
                        }
                    }

                    HoverHandler { id: isCreatorHovered }

                    Behavior on border.color { ColorAnimation { duration: 160 } }
                    Behavior on color { ColorAnimation { duration: 160 } }

                    // Left vertical accent status bar
                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        color: creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF")
                        Behavior on color { ColorAnimation { duration: 180 } }
                    }

                    ColumnLayout {
                        id: creatorCardCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        // Creator Header Row — wrapped in Rectangle so the
                        // collapse-toggle MouseArea is NOT a direct Layout child
                        // (avoids "anchors on item managed by layout" warnings)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: creatorHdrRow.implicitHeight + 4
                            color: "transparent"

                            // Collapse-toggle sits behind the RowLayout content
                            // but in front of the card background (z: 0 default)
                            MouseArea {
                                anchors.fill: parent
                                anchors.rightMargin: 56   // keep clear of verify + delete btns
                                cursorShape: Qt.PointingHandCursor
                                z: 0
                                onClicked: {
                                    var newMap = Object.assign({}, root.collapsedCreators)
                                    if (newMap[creatorModel.creator_name]) {
                                        delete newMap[creatorModel.creator_name]
                                    } else {
                                        newMap[creatorModel.creator_name] = true
                                    }
                                    root.collapsedCreators = newMap
                                }
                            }

                            RowLayout {
                                id: creatorHdrRow
                                anchors.fill: parent
                                spacing: 8

                                // Modern circular chevron button
                                Rectangle {
                                    width: 22
                                    height: 22
                                    radius: 11
                                    color: isCreatorHovered.hovered ? "#1E293B" : "#162032"
                                    border.color: isCreatorHovered.hovered
                                        ? (creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF"))
                                        : "#243248"
                                    border.width: 1
                                    scale: isCreatorHovered.hovered ? 1.08 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                    Behavior on border.color { ColorAnimation { duration: 140 } }
                                    Behavior on color { ColorAnimation { duration: 140 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "▶"
                                        font.pixelSize: 9
                                        color: creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF")
                                        rotation: creatorCard.isCollapsed ? 0 : 90
                                        Behavior on rotation {
                                            SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
                                        }
                                    }
                                }

                                // Service Badge
                                Rectangle {
                                    implicitHeight: 18
                                    implicitWidth: creatorSvcTxt.implicitWidth + 10
                                    radius: 4
                                    color: {
                                        var s = (creatorModel.service || "").toLowerCase()
                                        if (s === "patreon") return "#2A1508"
                                        if (s === "fanbox") return "#2A2008"
                                        if (s === "fantia") return "#0D2818"
                                        if (s === "boosty") return "#1E1030"
                                        if (s === "discord") return "#141530"
                                        return "#161B26"
                                    }
                                    border.color: {
                                        var s = (creatorModel.service || "").toLowerCase()
                                        if (s === "patreon") return "#F97316"
                                        if (s === "fanbox") return "#F59E0B"
                                        if (s === "fantia") return "#10B981"
                                        if (s === "boosty") return "#8B5CF6"
                                        if (s === "discord") return "#6366F1"
                                        return "#334155"
                                    }
                                    border.width: 1
                                    scale: isCreatorHovered.hovered ? 1.04 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                                    Text {
                                        id: creatorSvcTxt
                                        anchors.centerIn: parent
                                        text: (creatorModel.service || "").toUpperCase()
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: parent.border.color
                                    }
                                }

                                // Creator Name
                                Text {
                                    text: creatorModel.creator_name
                                    font.family: "Segoe UI, Inter, sans-serif"
                                    font.pixelSize: 13
                                    font.weight: 600
                                    color: "#F8FAFC"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                // Missing files status badge (Amber if partial, Crimson if all)
                                Rectangle {
                                    implicitHeight: 20
                                    implicitWidth: creatorMissingTxt.implicitWidth + 10
                                    radius: 10
                                    visible: creatorCard.creatorMissingCount > 0
                                    color: creatorCard.isCreatorAllMissing ? "#3F1318" : "#3D2406"
                                    border.color: creatorCard.isCreatorAllMissing ? "#EF4444" : "#F59E0B"
                                    border.width: 1
                                    scale: isCreatorHovered.hovered ? 1.04 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                                    Text {
                                        id: creatorMissingTxt
                                        anchors.centerIn: parent
                                        text: creatorCard.isCreatorAllMissing
                                            ? ("⚠️ " + root.tr("status_all_missing", "All missing"))
                                            : ("⚠️ " + creatorCard.creatorMissingCount + " " + root.tr("unit_missing", "missing"))
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: creatorCard.isCreatorAllMissing ? "#FCA5A5" : "#FCD34D"
                                    }
                                }

                                // Post Count Badge
                                Rectangle {
                                    implicitHeight: 20
                                    implicitWidth: postCntTxt.implicitWidth + 10
                                    radius: 10
                                    color: "#161D2B"
                                    border.color: "#25334D"
                                    border.width: 1
                                    visible: root.width >= 480
                                    scale: isCreatorHovered.hovered ? 1.04 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                                    Text {
                                        id: postCntTxt
                                        anchors.centerIn: parent
                                        text: creatorModel.post_count + " " + root.tr("unit_posts", "posts")
                                        font.pixelSize: 9
                                        color: "#94A3B8"
                                    }
                                }

                                // File Count Badge
                                Rectangle {
                                    implicitHeight: 20
                                    implicitWidth: fileCntTxt.implicitWidth + 10
                                    radius: 10
                                    color: "#0D2924"
                                    border.color: "#14B8A6"
                                    border.width: 1
                                    scale: isCreatorHovered.hovered ? 1.04 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                                    Text {
                                        id: fileCntTxt
                                        anchors.centerIn: parent
                                        text: creatorModel.total_files + " " + root.tr("unit_files", "files")
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: "#2DD4BF"
                                    }
                                }

                                // Verify Integrity Action Button
                                Rectangle {
                                    id: verifyCreatorBtn
                                    implicitHeight: 22
                                    implicitWidth: 22
                                    radius: 4
                                    z: 1
                                    property bool isVerifying: {
                                        var st = root.creatorVerifyState(creatorModel.service, creatorModel.creator_id)
                                        return st !== null && st.running
                                    }
                                    color: verifyCreatorMouse.containsMouse ? "#0D2033" : "transparent"
                                    border.color: verifyCreatorMouse.containsMouse ? "#38BDF8" : (isVerifying ? "#38BDF8" : "transparent")
                                    border.width: 1
                                    scale: verifyCreatorMouse.pressed ? 0.85 : (verifyCreatorMouse.containsMouse ? 1.18 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: verifyCreatorBtn.isVerifying ? "⏳" : "🔍"
                                        font.pixelSize: 10
                                        opacity: verifyCreatorMouse.containsMouse ? 1.0 : (verifyCreatorBtn.isVerifying ? 0.9 : 0.6)
                                        RotationAnimator on rotation {
                                            running: verifyCreatorBtn.isVerifying
                                            from: 0; to: 360
                                            duration: 1400
                                            loops: Animation.Infinite
                                        }
                                    }

                                    MouseArea {
                                        id: verifyCreatorMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: root.tr("tip_verify_creator_archive", "Verify that all archived files still exist on disk")
                                        onClicked: {
                                            if (!verifyCreatorBtn.isVerifying && root.bridge) {
                                                root.bridge.verifyCreatorArchiveIntegrity(
                                                    creatorModel.service,
                                                    creatorModel.creator_id,
                                                    creatorModel.creator_name
                                                )
                                            }
                                        }
                                    }
                                }

                                // Delete Creator Action Button (z: 1 so clicks reach it over the bg MouseArea)
                                Rectangle {
                                    implicitHeight: 22
                                    implicitWidth: 22
                                    radius: 4
                                    z: 1
                                    color: delCreatorMouse.containsMouse ? "#3A1212" : "transparent"
                                    border.color: delCreatorMouse.containsMouse ? "#EF4444" : "transparent"
                                    border.width: 1
                                    scale: delCreatorMouse.pressed ? 0.85 : (delCreatorMouse.containsMouse ? 1.18 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    Behavior on border.color { ColorAnimation { duration: 120 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "🗑️"
                                        font.pixelSize: 10
                                        opacity: delCreatorMouse.containsMouse ? 1.0 : 0.6
                                    }

                                    MouseArea {
                                        id: delCreatorMouse
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        hoverEnabled: true
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: root.tr("tip_delete_creator_archive", "Remove all archived files for this creator (allows re-download)")
                                        onClicked: {
                                            deleteTargetCreator = creatorModel
                                            deleteCreatorConfirmModal.isOpen = true
                                        }
                                    }
                                }
                            } // RowLayout (creatorHdrRow)
                        } // Rectangle (creator header wrapper)

                        // Verification Status Banner (shown when verify has run or is running)
                        Rectangle {
                            id: verifyBanner
                            Layout.fillWidth: true
                            property var vst: root.creatorVerifyState(creatorModel.service, creatorModel.creator_id)
                            visible: vst !== null
                            implicitHeight: visible ? verifyBannerContent.implicitHeight + 14 : 0
                            radius: 6
                            color: {
                                if (!vst || vst.running) return "#0B1620"
                                if (vst.missing > 0) return "#1A0E00"
                                return "#071811"
                            }
                            border.color: {
                                if (!vst || vst.running) return "#1E3A4A"
                                if (vst.missing > 0) return "#F59E0B"
                                return "#10B981"
                            }
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 200 } }
                            Behavior on border.color { ColorAnimation { duration: 200 } }

                            ColumnLayout {
                                id: verifyBannerContent
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 6

                                // Progress bar (shown while running)
                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: 4
                                    radius: 2
                                    color: "#1E2D3A"
                                    visible: verifyBanner.vst !== null && verifyBanner.vst.running

                                    Rectangle {
                                        width: {
                                            var st = verifyBanner.vst
                                            if (!st || st.total <= 0) return 0
                                            return Math.max(4, parent.width * (st.current / st.total))
                                        }
                                        height: parent.height
                                        radius: 2
                                        color: "#38BDF8"
                                        Behavior on width { NumberAnimation { duration: 80 } }
                                    }
                                }

                                // Status row
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Text {
                                        text: {
                                            var st = verifyBanner.vst
                                            if (!st) return ""
                                            if (st.running) {
                                                var pct = st.total > 0 ? Math.round(st.current * 100 / st.total) : 0
                                                return "⏳ " + root.tr("verify_running", "Verifying… %1%").replace("%1", pct)
                                            }
                                            if (st.missing > 0)
                                                return "⚠️ " + root.tr("verify_missing", "%1 missing, %2 present").replace("%1", st.missing).replace("%2", st.present)
                                            return "✅ " + root.tr("verify_ok", "All %1 files present").replace("%1", st.present)
                                        }
                                        font.pixelSize: 10
                                        font.family: "Segoe UI, sans-serif"
                                        color: {
                                            var st = verifyBanner.vst
                                            if (!st || st.running) return "#38BDF8"
                                            if (st.missing > 0) return "#F59E0B"
                                            return "#10B981"
                                        }
                                        Layout.fillWidth: true
                                        Behavior on color { ColorAnimation { duration: 200 } }
                                    }

                                    // "Clean up" button — shown only when missing > 0 and done
                                    Rectangle {
                                        visible: {
                                            var st = verifyBanner.vst
                                            return st !== null && st.done && st.missing > 0
                                        }
                                        implicitHeight: 20
                                        implicitWidth: cleanupTxt.implicitWidth + 14
                                        radius: 4
                                        color: cleanupMouse.containsMouse ? "#2D1800" : "#1A1000"
                                        border.color: cleanupMouse.containsMouse ? "#F59E0B" : "#7A4A00"
                                        border.width: 1
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                        Text {
                                            id: cleanupTxt
                                            anchors.centerIn: parent
                                            text: root.tr("btn_remove_missing", "Remove missing")
                                            font.pixelSize: 9
                                            color: cleanupMouse.containsMouse ? "#FCD34D" : "#F59E0B"
                                            Behavior on color { ColorAnimation { duration: 120 } }
                                        }

                                        MouseArea {
                                            id: cleanupMouse
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: root.tr("tip_remove_missing", "Delete archive records for files no longer on disk")
                                            onClicked: {
                                                removeMissingTargetCreator = creatorModel
                                                removeMissingConfirmModal.isOpen = true
                                            }
                                        }
                                    }

                                    // Dismiss button
                                    Text {
                                        text: "✕"
                                        font.pixelSize: 9
                                        color: dismissVerifyMouse.containsMouse ? "#94A3B8" : "#475569"
                                        Behavior on color { ColorAnimation { duration: 100 } }
                                        MouseArea {
                                            id: dismissVerifyMouse
                                            anchors.fill: parent
                                            anchors.margins: -4
                                            cursorShape: Qt.PointingHandCursor
                                            hoverEnabled: true
                                            onClicked: {
                                                var key = root._verifyKey(creatorModel.service, creatorModel.creator_id)
                                                var newMap = Object.assign({}, root.verificationState)
                                                delete newMap[key]
                                                root.verificationState = newMap
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Subtle horizontal divider when dropped down
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: "#1E2738"
                            visible: !creatorCard.isCollapsed
                        }

                        // Dropped-down Posts Container with Left Connector Rail
                        Item {
                            Layout.fillWidth: true
                            visible: !creatorCard.isCollapsed
                            implicitHeight: postsInnerCol.implicitHeight

                            // Left vertical connector rail line
                            Rectangle {
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 6
                                width: 2
                                radius: 1
                                color: creatorCard.isCreatorAllMissing ? "#7F1D1D" : (creatorCard.isCreatorSomeMissing ? "#78350F" : "#1E293B")
                            }

                            ColumnLayout {
                                id: postsInnerCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.leftMargin: 18
                                spacing: 6

                                Repeater {
                                    model: creatorModel.posts

                                    delegate: Rectangle {
                                        id: postCard
                                        Layout.fillWidth: true
                                        property var postModel: modelData
                                        property string postKey: creatorModel.creator_name + "_" + postModel.post_id
                                        property bool isPostCollapsed: root.collapsedPosts[postKey] === true

                                        property int missingCount: {
                                            if (!postModel || !postModel.files) return 0
                                            var count = 0
                                            for (var i = 0; i < postModel.files.length; i++) {
                                                if (postModel.files[i].is_missing === 1) count++
                                            }
                                            return count
                                        }
                                        property int totalFiles: (postModel && postModel.files) ? postModel.files.length : (postModel.file_count || 0)
                                        property bool isSomeMissing: missingCount > 0 && missingCount < totalFiles
                                        property bool isAllMissing: totalFiles > 0 && missingCount >= totalFiles
                                        property bool hasMissingFiles: missingCount > 0

                                        implicitHeight: postCol.implicitHeight + 12
                                        Behavior on implicitHeight {
                                            enabled: !creatorsListView.isScrolling
                                            SpringAnimation {
                                                spring: 3.8
                                                damping: 0.36
                                                mass: 0.95
                                                epsilon: 1.0
                                            }
                                        }

                                        clip: true
                                        radius: 6
                                        color: isPostHovered.hovered
                                            ? (isAllMissing ? "#2B0E14" : (isSomeMissing ? "#261B09" : "#0F1420"))
                                            : (isAllMissing ? "#1A070A" : (isSomeMissing ? "#1B1306" : "#0B0E16"))
                                        border.color: isPostHovered.hovered
                                            ? (isAllMissing ? "#EF4444" : (isSomeMissing ? "#F59E0B" : "#38BDF8"))
                                            : (isAllMissing ? "#DC2626" : (isSomeMissing ? "#D97706" : "#182030"))
                                        border.width: 1

                                        transform: Translate {
                                            y: isPostHovered.hovered && !creatorsListView.isScrolling ? -1.5 : 0
                                            Behavior on y {
                                                enabled: !creatorsListView.isScrolling
                                                SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                            }
                                        }

                                        HoverHandler { id: isPostHovered }

                                        Behavior on border.color { ColorAnimation { duration: 140 } }
                                        Behavior on color { ColorAnimation { duration: 140 } }

                                        ColumnLayout {
                                            id: postCol
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 6

                                            // Post Header — wrapped in Rectangle so the
                                            // collapse-toggle MouseArea is NOT a Layout child
                                            Rectangle {
                                                Layout.fillWidth: true
                                                implicitHeight: postHdrRow.implicitHeight + 4
                                                color: "transparent"

                                                // Collapse-toggle background MouseArea
                                                MouseArea {
                                                    anchors.fill: parent
                                                    anchors.rightMargin: 24   // keep clear of delete btn
                                                    cursorShape: Qt.PointingHandCursor
                                                    z: 0
                                                    onClicked: {
                                                        var newMap = Object.assign({}, root.collapsedPosts)
                                                        if (newMap[postKey]) {
                                                            delete newMap[postKey]
                                                        } else {
                                                            newMap[postKey] = true
                                                        }
                                                        root.collapsedPosts = newMap
                                                    }
                                                }

                                                RowLayout {
                                                    id: postHdrRow
                                                    anchors.fill: parent
                                                    spacing: 6

                                                    // Sub-chevron
                                                    Text {
                                                        text: "▾"
                                                        font.pixelSize: 10
                                                        color: postCard.isAllMissing ? "#EF4444" : (postCard.isSomeMissing ? "#F59E0B" : "#38BDF8")
                                                        rotation: postCard.isPostCollapsed ? -90 : 0
                                                        scale: isPostHovered.hovered ? 1.15 : 1.0
                                                        Behavior on rotation {
                                                            SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
                                                        }
                                                        Behavior on scale {
                                                            SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                                        }
                                                    }

                                                    // Post Title
                                                    Text {
                                                        text: postModel.post_title
                                                        font.family: "Segoe UI, sans-serif"
                                                        font.pixelSize: 11
                                                        font.weight: 600
                                                        color: postCard.isAllMissing ? "#FCA5A5" : (postCard.isSomeMissing ? "#FCD34D" : "#E2E8F0")
                                                        elide: Text.ElideRight
                                                        Layout.fillWidth: true
                                                    }

                                                    // Missing Files Warning Badge (Amber if partial, Crimson if all)
                                                    Rectangle {
                                                        implicitHeight: 16
                                                        implicitWidth: postMissingTxt.implicitWidth + 8
                                                        radius: 3
                                                        visible: postCard.hasMissingFiles
                                                        color: postCard.isAllMissing ? "#3F1318" : "#3D2406"
                                                        border.color: postCard.isAllMissing ? "#EF4444" : "#F59E0B"
                                                        border.width: 1
                                                        scale: isPostHovered.hovered ? 1.05 : 1.0
                                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                                                        Text {
                                                            id: postMissingTxt
                                                            anchors.centerIn: parent
                                                            text: postCard.isAllMissing
                                                                ? ("⚠️ " + root.tr("status_all_x_missing", "All %1 missing").replace("%1", postCard.missingCount))
                                                                : ("⚠️ " + postCard.missingCount + " / " + postCard.totalFiles + " " + root.tr("unit_missing", "missing"))
                                                            font.pixelSize: 8
                                                            font.weight: 600
                                                            color: postCard.isAllMissing ? "#FCA5A5" : "#FCD34D"
                                                        }
                                                    }

                                                    // Post ID Badge
                                                    Rectangle {
                                                        implicitHeight: 16
                                                        implicitWidth: pidTxt.implicitWidth + 8
                                                        radius: 3
                                                        color: "#161D2B"
                                                        border.color: "#28354A"
                                                        border.width: 1
                                                        visible: root.width >= 520
                                                        scale: isPostHovered.hovered ? 1.05 : 1.0
                                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                                                        Text {
                                                            id: pidTxt
                                                            anchors.centerIn: parent
                                                            text: "#" + postModel.post_id
                                                            font.pixelSize: 8
                                                            color: "#64748B"
                                                        }
                                                    }

                                                    // Post File Count
                                                    Text {
                                                        text: postModel.file_count + " " + root.tr("unit_files", "files")
                                                        font.pixelSize: 9
                                                        color: "#94A3B8"
                                                    }

                                                    // Delete Post Action Button (z: 1 so it receives clicks over bg MouseArea)
                                                    Rectangle {
                                                        implicitHeight: 18
                                                        implicitWidth: 18
                                                        radius: 3
                                                        z: 1
                                                        color: delPostMouse.containsMouse ? "#3A1212" : "transparent"
                                                        border.color: delPostMouse.containsMouse ? "#EF4444" : "transparent"
                                                        border.width: 1
                                                        scale: delPostMouse.pressed ? 0.85 : (delPostMouse.containsMouse ? 1.18 : 1.0)
                                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                                        Behavior on color { ColorAnimation { duration: 120 } }
                                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                                        Text {
                                                            anchors.centerIn: parent
                                                            text: "🗑️"
                                                            font.pixelSize: 9
                                                            opacity: delPostMouse.containsMouse ? 1.0 : 0.5
                                                        }

                                                        MouseArea {
                                                            id: delPostMouse
                                                            anchors.fill: parent
                                                            cursorShape: Qt.PointingHandCursor
                                                            hoverEnabled: true
                                                            ToolTip.visible: containsMouse
                                                            ToolTip.delay: 300
                                                            ToolTip.text: root.tr("tip_delete_post_archive", "Remove all files of this post from archive")
                                                            onClicked: {
                                                                deleteTargetPost = postModel
                                                                deletePostConfirmModal.isOpen = true
                                                            }
                                                        }
                                                    }
                                                } // RowLayout (postHdrRow)
                                            } // Rectangle (post header wrapper)

                                            // Files Under This Post
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                visible: !postCard.isPostCollapsed
                                                spacing: 4
                                                Layout.leftMargin: 14

                                                Repeater {
                                                    model: postModel.files

                                                    delegate: Rectangle {
                                                        Layout.fillWidth: true
                                                        implicitHeight: 28
                                                        radius: 4
                                                        property var fileData: modelData
                                                        property bool isMissing: fileData.is_missing === 1
                                                        color: fileRowMouse.hovered
                                                            ? (isMissing ? (postCard.isAllMissing ? "#2B1117" : "#261A09") : "#162030")
                                                            : (isMissing ? (postCard.isAllMissing ? "#1A090D" : "#1B1306") : "#0E121A")
                                                        border.color: fileRowMouse.hovered
                                                            ? (isMissing ? (postCard.isAllMissing ? "#EF4444" : "#F59E0B") : "#2B3C57")
                                                            : (isMissing ? (postCard.isAllMissing ? "#7F1D1D" : "#B45309") : "#161B26")
                                                        border.width: 1

                                                        transform: Translate {
                                                            x: fileRowMouse.hovered && !creatorsListView.isScrolling ? 4.0 : 0
                                                            Behavior on x {
                                                                enabled: !creatorsListView.isScrolling
                                                                SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                                            }
                                                        }

                                                        Behavior on border.color { ColorAnimation { duration: 120 } }
                                                        Behavior on color { ColorAnimation { duration: 120 } }

                                                        HoverHandler { id: fileRowMouse }

                                                        RowLayout {
                                                            anchors.fill: parent
                                                            anchors.leftMargin: 8
                                                            anchors.rightMargin: 8
                                                            spacing: 8

                                                            // File Extension Badge
                                                            Rectangle {
                                                                implicitHeight: 18
                                                                implicitWidth: extTxt.implicitWidth + 8
                                                                radius: 3
                                                                color: {
                                                                    var e = (fileData.file_ext || "").toLowerCase()
                                                                    if (e === "link" || e === "url") return "#083344"
                                                                    if (e === "zip" || e === "rar" || e === "7z") return "#2A1F0D"
                                                                    if (e === "psd" || e === "clip") return "#0E2838"
                                                                    if (e === "png" || e === "jpg" || e === "webp") return "#0C2418"
                                                                    if (e === "mp4" || e === "mkv") return "#2E0E20"
                                                                    if (e === "mp3" || e === "wav") return "#220E2E"
                                                                    return "#1E2430"
                                                                }
                                                                border.color: {
                                                                    var e = (fileData.file_ext || "").toLowerCase()
                                                                    if (e === "link" || e === "url") return "#06B6D4"
                                                                    if (e === "zip" || e === "rar" || e === "7z") return "#F59E0B"
                                                                    if (e === "psd" || e === "clip") return "#38BDF8"
                                                                    if (e === "png" || e === "jpg" || e === "webp") return "#10B981"
                                                                    if (e === "mp4" || e === "mkv") return "#EC4899"
                                                                    if (e === "mp3" || e === "wav") return "#A855F7"
                                                                    return "#64748B"
                                                                }
                                                                border.width: 1
                                                                scale: fileRowMouse.hovered ? 1.08 : 1.0
                                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }

                                                                Text {
                                                                    id: extTxt
                                                                    anchors.centerIn: parent
                                                                    text: (fileData.file_ext || "").toUpperCase() === "LINK" ? "🔗 LINK" : (fileData.file_ext || "FILE")
                                                                    font.pixelSize: 8
                                                                    font.bold: true
                                                                    color: parent.border.color
                                                                }
                                                            }

                                                            // Filename or Link URL
                                                            Text {
                                                                text: fileData.filename
                                                                font.family: "Segoe UI, sans-serif"
                                                                font.pixelSize: 11
                                                                color: isMissing ? (postCard.isAllMissing ? "#FCA5A5" : "#FCD34D") : ((fileData.file_ext || "").toLowerCase() === "link" ? "#38BDF8" : "#E2E8F0")
                                                                font.underline: (fileData.file_ext || "").toLowerCase() === "link" && fileRowMouse.hovered
                                                                elide: Text.ElideRight
                                                                Layout.fillWidth: true
                                                            }

                                                            // Quick Open button for external links
                                                            Rectangle {
                                                                visible: (fileData.file_ext || "").toLowerCase() === "link"
                                                                implicitHeight: 18
                                                                implicitWidth: openLinkRow.implicitWidth + 8
                                                                radius: 3
                                                                color: linkBtnMouse.containsMouse ? "#083344" : "#0A1926"
                                                                border.color: linkBtnMouse.containsMouse ? "#22D3EE" : "#0E7490"
                                                                border.width: 1
                                                                scale: linkBtnMouse.pressed ? 0.92 : (linkBtnMouse.containsMouse ? 1.08 : 1.0)
                                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                                                Behavior on color { ColorAnimation { duration: 120 } }

                                                                RowLayout {
                                                                    id: openLinkRow
                                                                    anchors.centerIn: parent
                                                                    spacing: 3

                                                                    Text {
                                                                        text: "↗"
                                                                        font.pixelSize: 9
                                                                        color: "#22D3EE"
                                                                    }
                                                                    Text {
                                                                        text: root.tr("btn_open", "Open")
                                                                        font.pixelSize: 8
                                                                        font.bold: true
                                                                        color: "#22D3EE"
                                                                    }
                                                                }

                                                                MouseArea {
                                                                    id: linkBtnMouse
                                                                    anchors.fill: parent
                                                                    cursorShape: Qt.PointingHandCursor
                                                                    hoverEnabled: true
                                                                    ToolTip.visible: containsMouse
                                                                    ToolTip.delay: 200
                                                                    ToolTip.text: root.tr("tip_open_external_link", "Open external link in browser")
                                                                    onClicked: {
                                                                        var raw = fileData.filename || ""
                                                                        var u = raw
                                                                        var m = raw.match(/https?:\/\/[^\s]+/)
                                                                        if (m) u = m[0]
                                                                        if (u.indexOf("http") === 0) {
                                                                            Qt.openUrlExternally(u)
                                                                        }
                                                                    }
                                                                }
                                                            }

                                                            // File Size (or "Link" for link records)
                                                            Text {
                                                                text: (fileData.file_ext || "").toLowerCase() === "link" ? "Link" : fileData.file_size_str
                                                                font.family: "Segoe UI, sans-serif"
                                                                font.pixelSize: 10
                                                                color: (fileData.file_ext || "").toLowerCase() === "link" ? "#06B6D4" : "#64748B"
                                                                visible: ((fileData.file_ext || "").toLowerCase() === "link" || fileData.file_size_str.length > 0) && root.width >= 420
                                                            }

                                                            // Hash preview with copy button — hidden when narrow
                                                            Rectangle {
                                                                visible: fileData.file_hash.length > 0 && root.width >= 560
                                                                implicitHeight: 18
                                                                implicitWidth: hashRow.implicitWidth + 8
                                                                radius: 3
                                                                color: hashHover.containsMouse ? "#1E293B" : "#121722"
                                                                border.color: "#242E42"
                                                                border.width: 1
                                                                scale: hashHover.pressed ? 0.92 : (hashHover.containsMouse ? 1.06 : 1.0)
                                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                                                Behavior on color { ColorAnimation { duration: 120 } }

                                                                RowLayout {
                                                                    id: hashRow
                                                                    anchors.centerIn: parent
                                                                    spacing: 4

                                                                    Text {
                                                                        text: "#" + fileData.file_hash.substring(0, 8) + "…"
                                                                        font.family: "Consolas, monospace"
                                                                        font.pixelSize: 9
                                                                        color: "#94A3B8"
                                                                    }

                                                                    Text {
                                                                        text: "📋"
                                                                        font.pixelSize: 8
                                                                        opacity: hashHover.containsMouse ? 1.0 : 0.5
                                                                    }
                                                                }

                                                                MouseArea {
                                                                    id: hashHover
                                                                    anchors.fill: parent
                                                                    cursorShape: Qt.PointingHandCursor
                                                                    hoverEnabled: true
                                                                    ToolTip.visible: containsMouse
                                                                    ToolTip.delay: 200
                                                                    ToolTip.text: root.tr("tip_copy_sha256", "SHA256: %1 (Click to copy)").replace("%1", fileData.file_hash)
                                                                    onClicked: {
                                                                        if (typeof appBridge !== "undefined" && appBridge) {
                                                                            appBridge.copyToClipboard(fileData.file_hash)
                                                                            root.showToast(root.tr("toast_hash_copied", "Hash copied to clipboard!"))
                                                                        }
                                                                    }
                                                                }
                                                            }

                                                            // Download Date — hidden at narrow widths
                                                            Text {
                                                                text: fileData.downloaded_at_str
                                                                font.family: "Segoe UI, sans-serif"
                                                                font.pixelSize: 9
                                                                color: "#475569"
                                                                visible: root.width >= 500
                                                            }

                                                            // Missing Status Tag (Amber if partial, Crimson if all)
                                                            Rectangle {
                                                                visible: isMissing
                                                                implicitHeight: 18
                                                                implicitWidth: missingFileTxt.implicitWidth + 8
                                                                radius: 3
                                                                color: postCard.isAllMissing ? "#3F1318" : "#3D2406"
                                                                border.color: postCard.isAllMissing ? "#EF4444" : "#F59E0B"
                                                                border.width: 1

                                                                Text {
                                                                    id: missingFileTxt
                                                                    anchors.centerIn: parent
                                                                    text: "⚠️ " + root.tr("status_missing", "Missing")
                                                                    font.pixelSize: 8
                                                                    font.bold: true
                                                                    color: postCard.isAllMissing ? "#FCA5A5" : "#FCD34D"
                                                                }
                                                            }

                                                            // Delete single file button
                                                            Rectangle {
                                                                implicitHeight: 20
                                                                implicitWidth: 20
                                                                radius: 3
                                                                color: delFileMouse.containsMouse ? "#3A1212" : "transparent"
                                                                border.color: delFileMouse.containsMouse ? "#EF4444" : "transparent"
                                                                border.width: 1
                                                                scale: delFileMouse.pressed ? 0.85 : (delFileMouse.containsMouse ? 1.18 : 1.0)
                                                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                                                Behavior on color { ColorAnimation { duration: 120 } }
                                                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                                                Text {
                                                                    anchors.centerIn: parent
                                                                    text: "🗑️"
                                                                    font.pixelSize: 9
                                                                    opacity: delFileMouse.containsMouse ? 1.0 : 0.4
                                                                }

                                                                MouseArea {
                                                                    id: delFileMouse
                                                                    anchors.fill: parent
                                                                    cursorShape: Qt.PointingHandCursor
                                                                    hoverEnabled: true
                                                                    ToolTip.visible: containsMouse
                                                                    ToolTip.delay: 300
                                                                    ToolTip.text: root.tr("tip_delete_file_archive", "Remove this file from archive (allows re-downloading)")
                                                                    onClicked: {
                                                                        if (root.bridge) {
                                                                            var ok = root.bridge.deleteArchiveRecord(fileData.id)
                                                                            if (ok) {
                                                                                root.showToast(root.tr("toast_file_removed", "File removed from archive."))
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
                }
            }
        }
    }

    // ── Toast Notification Banner ──────────────────────────────────────
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        implicitWidth: toastRow.implicitWidth + 24
        implicitHeight: 34
        radius: 17
        color: "#0F172A"
        border.color: "#38BDF8"
        border.width: 1
        z: 100
        visible: opacity > 0.001
        opacity: root.toastVisible ? 1.0 : 0.0

        scale: root.toastVisible ? 1.0 : 0.85
        Behavior on scale {
            SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
        }

        transform: Translate {
            y: root.toastVisible ? 0 : 25
            Behavior on y {
                SpringAnimation { spring: 4.2; damping: 0.36; mass: 0.85; epsilon: 0.1 }
            }
        }

        Behavior on opacity { NumberAnimation { duration: 180 } }

        RowLayout {
            id: toastRow
            anchors.centerIn: parent
            spacing: 8
            Text { text: "ℹ️"; font.pixelSize: 12 }
            Text {
                text: root.toastMessage
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#F8FAFC"
            }
        }
    }

    // ── Dialogs & Modals ───────────────────────────────────────────────
    // Import File Dialog
    FileDialog {
        id: importFileDialog
        title: root.tr("dialog_import_archive", "Import Download Archive File")
        nameFilters: ["Archive Files (*.txt *.json)", "Text files (*.txt)", "JSON files (*.json)", "All Files (*.*)"]
        onAccepted: {
            if (root.bridge && selectedFile) {
                var path = selectedFile.toString()
                var imported = root.bridge.importArchiveFile(path)
                root.showToast(root.tr("toast_imported_count", "Imported %1 records into archive.").replace("%1", imported))
            }
        }
    }

    // Export File Dialog
    FileDialog {
        id: exportFileDialog
        title: root.tr("dialog_export_archive", "Export Download Archive")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        nameFilters: ["gallery-dl Archive (*.txt)", "JSON File (*.json)"]
        onAccepted: {
            if (root.bridge && selectedFile) {
                var path = selectedFile.toString()
                var fmt = path.toLowerCase().endsWith(".json") ? "json" : "txt"
                var exported = root.bridge.exportArchiveFile(path, fmt)
                root.showToast(root.tr("toast_exported_count", "Exported %1 records to archive file.").replace("%1", exported))
            }
        }
    }

    // Clear All Confirmation Modal
    property bool clearConfirmOpen: false
    Rectangle {
        id: clearConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: clearCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            scale: clearConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: clearConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: clearCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    spacing: 8
                    Text { text: "⚠️"; font.pixelSize: 20 }
                    Text {
                        text: root.tr("modal_clear_archive_title", "Clear Download Archive Database?")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 14
                        font.bold: true
                        color: "#F8FAFC"
                    }
                }

                Text {
                    text: root.tr("modal_clear_archive_desc", "This will wipe all indexed records from the database. Downloaded files that were deleted from disk will become eligible for re-downloading on next scan.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: root.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: clearConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: root.tr("btn_confirm_clear", "Clear Everything")
                        iconText: "🗑️"
                        variant: "danger"
                        onClicked: {
                            clearConfirmModal.isOpen = false
                            if (root.bridge) {
                                root.bridge.clearDownloadArchive()
                                root.showToast(root.tr("toast_archive_cleared", "Download archive cleared."))
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete Creator Confirmation Modal
    property var deleteTargetCreator: null
    Rectangle {
        id: deleteCreatorConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: delCreatorCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            scale: deleteCreatorConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: deleteCreatorConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: delCreatorCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: root.tr("modal_delete_creator_title", "Remove Creator Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: root.deleteTargetCreator
                          ? root.tr("modal_delete_creator_desc", "Remove all %1 archived files for '%2'? Files deleted from disk will be re-downloaded next time.")
                            .replace("%1", root.deleteTargetCreator.total_files)
                            .replace("%2", root.deleteTargetCreator.creator_name)
                          : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: root.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: deleteCreatorConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: root.tr("btn_remove_creator", "Remove Creator")
                        variant: "danger"
                        onClicked: {
                            deleteCreatorConfirmModal.isOpen = false
                            if (root.bridge && root.deleteTargetCreator) {
                                var delCnt = root.bridge.deleteArchiveCreator(root.deleteTargetCreator.creator_id, root.deleteTargetCreator.service)
                                root.showToast(root.tr("toast_creator_removed", "Removed %1 files for creator.").replace("%1", delCnt))
                            }
                        }
                    }
                }
            }
        }
    }

    // Remove Missing Records Confirmation Modal
    property var removeMissingTargetCreator: null
    Rectangle {
        id: removeMissingConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 201

        Behavior on opacity { NumberAnimation { duration: 180 } }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: removeMissingCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#F59E0B"
            border.width: 1

            scale: removeMissingConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: removeMissingConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: removeMissingCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: root.tr("modal_remove_missing_title", "Remove Missing Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: {
                        if (!root.removeMissingTargetCreator) return ""
                        var st = root.creatorVerifyState(
                            root.removeMissingTargetCreator.service,
                            root.removeMissingTargetCreator.creator_id
                        )
                        var cnt = st ? st.missing : 0
                        return root.tr("modal_remove_missing_desc",
                            "Delete %1 archive record(s) for '%2' whose files are no longer on disk? This lets Pawchive re-download them next time."
                        ).replace("%1", cnt).replace("%2", root.removeMissingTargetCreator.creator_name)
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: root.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: removeMissingConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: root.tr("btn_remove_missing_confirm", "Remove Records")
                        variant: "warning"
                        onClicked: {
                            removeMissingConfirmModal.isOpen = false
                            if (root.bridge && root.removeMissingTargetCreator) {
                                var delCnt = root.bridge.removeMissingArchiveRecordsForCreator(
                                    root.removeMissingTargetCreator.service,
                                    root.removeMissingTargetCreator.creator_id
                                )
                                // Clear the verify state so the banner reflects fresh state
                                var key = root._verifyKey(
                                    root.removeMissingTargetCreator.service,
                                    root.removeMissingTargetCreator.creator_id
                                )
                                var newMap = Object.assign({}, root.verificationState)
                                delete newMap[key]
                                root.verificationState = newMap
                                root.showToast(
                                    root.tr("toast_missing_removed", "Removed %1 missing record(s).").replace("%1", delCnt)
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete Post Confirmation Modal
    property var deleteTargetPost: null
    Rectangle {
        id: deletePostConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: delPostCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            scale: deletePostConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: deletePostConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: delPostCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: root.tr("modal_delete_post_title", "Remove Post Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: root.deleteTargetPost
                          ? root.tr("modal_delete_post_desc", "Remove all %1 files for post '%2' from archive?")
                            .replace("%1", root.deleteTargetPost.file_count)
                            .replace("%2", root.deleteTargetPost.post_title)
                          : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: root.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: deletePostConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: root.tr("btn_remove_post", "Remove Post")
                        variant: "danger"
                        onClicked: {
                            deletePostConfirmModal.isOpen = false
                            if (root.bridge && root.deleteTargetPost) {
                                var delCnt = root.bridge.deleteArchivePost(root.deleteTargetPost.service, root.deleteTargetPost.post_id)
                                root.showToast(root.tr("toast_post_removed", "Removed %1 files for post.").replace("%1", delCnt))
                            }
                        }
                    }
                }
            }
        }
    }
}
