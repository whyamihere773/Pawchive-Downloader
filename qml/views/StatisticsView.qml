import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "statistics"

Rectangle {
    id: root
    color: "#0B0E14"

    property var bridge: null
    readonly property var statsBridge: (typeof statisticsBridge !== "undefined" && statisticsBridge) ? statisticsBridge : null

    property var liveData: statsBridge ? statsBridge.liveSnapshot : ({})
    property var diskData: statsBridge ? statsBridge.storageSnapshot : ({})
    property bool isScanning: statsBridge ? statsBridge.isScanning : false
    property bool hasScanned: statsBridge ? statsBridge.hasScanned : false
    property bool confirmResetArmed: false

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            if (res && res !== key) return res
        }
        return fallback !== undefined ? fallback : key
    }

    function fmtInt(val) {
        var n = Math.floor(Number(val || 0))
        if (!isFinite(n)) return "0"
        return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
    }

    function fmtRawBytes(val) {
        return fmtInt(val) + " B"
    }

    function svcColor(svc) {
        var s = String(svc || "").toLowerCase()
        if (s === "patreon") return "#F97316"
        if (s === "fanbox") return "#38BDF8"
        if (s === "fantia") return "#EC4899"
        if (s === "onlyfans" || s === "coomerfans") return "#06B6D4"
        if (s === "fansly") return "#60A5FA"
        if (s === "candfans") return "#F472B6"
        if (s === "gumroad") return "#A78BFA"
        if (s === "subscribestar") return "#818CF8"
        if (s === "boosty") return "#FB923C"
        if (s === "discord") return "#8B5CF6"
        if (s === "bunkr") return "#FACC15"
        if (s === "telegram") return "#22D3EE"
        return "#94A3B8"
    }

    function catLabel(cat) {
        var c = String(cat || "").toLowerCase()
        if (c === "images") return root.tr("stat_cat_images", "Images")
        if (c === "videos") return root.tr("stat_cat_videos", "Videos")
        if (c === "audio") return root.tr("stat_cat_audio", "Audio")
        if (c === "archives") return root.tr("stat_cat_archives", "Archives")
        if (c === "graphics") return root.tr("stat_cat_graphics", "Graphics / PSD")
        if (c === "documents") return root.tr("stat_cat_documents", "Documents")
        if (c === "links") return root.tr("stat_cat_links", "Links / Text")
        return root.tr("stat_cat_other", "Other")
    }

    onVisibleChanged: {
        if (visible && statsBridge) {
            statsBridge.refreshLive()
            if (!statsBridge.hasScanned && !statsBridge.isScanning) {
                statsBridge.refreshStorage(true)
            }
        }
    }

    Component.onCompleted: {
        if (visible && statsBridge) {
            statsBridge.refreshLive()
            if (!statsBridge.hasScanned && !statsBridge.isScanning) {
                statsBridge.refreshStorage(true)
            }
        }
    }

    Timer {
        id: liveRefreshTimer
        interval: 1000
        repeat: true
        running: root.visible && root.statsBridge !== null
        onTriggered: {
            if (root.statsBridge) root.statsBridge.refreshLive()
        }
    }

    Timer {
        id: resetArmTimeout
        interval: 4000
        repeat: false
        onTriggered: root.confirmResetArmed = false
    }

    Connections {
        target: root.statsBridge
        function onToastRequested(msg, kind) {
            if (typeof appWindow !== "undefined" && typeof appWindow.showToast === "function") {
                appWindow.showToast(msg)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Header Bar
        Rectangle {
            objectName: "statsHeaderBar"
            Layout.fillWidth: true
            implicitHeight: Math.max(44, headerInner.implicitHeight + 12)
            color: "#0F1117"
            border.color: "#1E2433"
            border.width: 1

            RowLayout {
                id: headerInner
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.topMargin: 6
                anchors.bottomMargin: 6
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 120
                    spacing: 1

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            text: "📊"
                            font.pixelSize: 14
                        }
                        Text {
                            text: root.tr("stats_title", "Statistics & Raw Telemetry")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 14
                            font.bold: true
                            color: "#F8FAFC"
                            elide: Text.ElideRight
                        }
                        Rectangle {
                            visible: root.isScanning
                            implicitHeight: 18
                            implicitWidth: scanBadgeLbl.implicitWidth + 12
                            radius: 9
                            color: "#082F49"
                            border.color: "#0284C7"
                            border.width: 1
                            Text {
                                id: scanBadgeLbl
                                anchors.centerIn: parent
                                text: root.tr("stats_scanning", "Scanning disk...")
                                font.pixelSize: 9
                                font.bold: true
                                color: "#38BDF8"
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: {
                            if (root.isScanning) {
                                return root.tr("stats_subtitle_scanning", "Walking storage roots and reading archive & history databases...")
                            }
                            if (root.hasScanned && root.diskData && root.diskData.scanned_at) {
                                return root.tr("stats_subtitle_scanned", "Last disk scan: ") + String(root.diskData.scanned_at).replace("T", " ").replace("+00:00", " UTC") + " (" + root.fmtInt(root.diskData.scan_duration_ms) + " ms)"
                            }
                            return root.tr("stats_subtitle_idle", "Live network bandwidth, session counters, disk layout, and artist raw data")
                        }
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    spacing: 5

                    StyledButton {
                        objectName: "statsScanBtn"
                        text: root.isScanning ? root.tr("stats_btn_scanning", "Scanning…") : (root.width < 580 ? "" : root.tr("stats_btn_scan", "Scan Disk"))
                        iconText: "🔄"
                        variant: "primary"
                        implicitHeight: 28
                        enabled: !root.isScanning && root.statsBridge !== null
                        tooltip: root.tr("stats_btn_scan_tip", "Walk configured download drives and recalculate files, folders, artists, and disk sizes")
                        onClicked: {
                            if (root.statsBridge) root.statsBridge.refreshStorage(true)
                        }
                    }

                    StyledButton {
                        objectName: "statsCopyBtn"
                        text: root.width < 880 ? "" : root.tr("stats_btn_copy", "Copy")
                        iconText: "📋"
                        variant: "ghost"
                        implicitHeight: 28
                        tooltip: root.tr("stats_btn_copy_tip", "Copy raw telemetry summary to clipboard")
                        onClicked: {
                            if (root.statsBridge) root.statsBridge.copyRawSummary()
                        }
                    }

                    StyledButton {
                        objectName: "statsExportCsvBtn"
                        text: root.width < 760 ? "" : "CSV"
                        iconText: "📑"
                        variant: "ghost"
                        implicitHeight: 28
                        tooltip: root.tr("stats_btn_csv_tip", "Export downloaded artists raw table to CSV")
                        onClicked: {
                            if (root.statsBridge) root.statsBridge.exportReport("csv")
                        }
                    }

                    StyledButton {
                        objectName: "statsExportJsonBtn"
                        text: root.width < 760 ? "" : "JSON"
                        iconText: "💾"
                        variant: "ghost"
                        implicitHeight: 28
                        tooltip: root.tr("stats_btn_json_tip", "Export full raw telemetry snapshot to JSON")
                        onClicked: {
                            if (root.statsBridge) root.statsBridge.exportReport("json")
                        }
                    }

                    StyledButton {
                        objectName: "statsResetBtn"
                        text: root.confirmResetArmed ? root.tr("stats_btn_confirm_reset", "Confirm Reset?") : (root.width < 940 ? "" : root.tr("stats_btn_reset", "Reset"))
                        iconText: "🗑"
                        variant: root.confirmResetArmed ? "danger" : "ghost"
                        implicitHeight: 28
                        tooltip: root.tr("stats_btn_reset_tip", "Reset tracked session & lifetime bandwidth/engine counters (does not touch files or archive DB)")
                        onClicked: {
                            if (!root.confirmResetArmed) {
                                root.confirmResetArmed = true
                                resetArmTimeout.restart()
                            } else {
                                root.confirmResetArmed = false
                                resetArmTimeout.stop()
                                if (root.statsBridge) root.statsBridge.resetNetworkStats()
                            }
                        }
                    }
                }
            }
        }

        // Scrollable Raw Data Content
        SmoothFlickable {
            id: statsScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: contentCol.implicitHeight + 24

            ColumnLayout {
                id: contentCol
                width: Math.max(200, statsScroll.width - 24)
                x: 12
                y: 12
                spacing: 10

                // ── Section 1: Headline Raw KPI Grid ────────────────────────────────────────
                GridLayout {
                    Layout.fillWidth: true
                    columns: root.width >= 1040 ? 4 : (root.width >= 580 ? 2 : 1)
                    columnSpacing: 8
                    rowSpacing: 8

                    // KPI 1: Bandwidth Down
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: kpiDownCol.implicitHeight + 16
                        radius: 8
                        color: "#141720"
                        border.color: "#1E3A5F"
                        border.width: 1

                        ColumnLayout {
                            id: kpiDownCol
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 3

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "⬇ " + root.tr("stats_kpi_bw_down", "BANDWIDTH DOWN")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#38BDF8"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: (root.liveData && root.liveData.live_down_str) ? root.liveData.live_down_str : "0 B/s"
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: ((root.liveData && root.liveData.live_down_bps > 0) ? "#22D3EE" : "#64748B")
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: (root.liveData && root.liveData.lifetime_down_str) ? root.liveData.lifetime_down_str : "0 B"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 17
                                font.bold: true
                                color: "#F8FAFC"
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: "Raw: " + root.fmtRawBytes(root.liveData ? root.liveData.lifetime_down_bytes : 0) + "  •  Session: " + ((root.liveData && root.liveData.session_down_str) ? root.liveData.session_down_str : "0 B")
                                font.family: "Consolas, Cascadia Mono, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }
                    }

                    // KPI 2: Bandwidth Up
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: kpiUpCol.implicitHeight + 16
                        radius: 8
                        color: "#141720"
                        border.color: "#3B275E"
                        border.width: 1

                        ColumnLayout {
                            id: kpiUpCol
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 3

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "⬆ " + root.tr("stats_kpi_bw_up", "BANDWIDTH UP")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#A78BFA"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: (root.liveData && root.liveData.live_up_str) ? root.liveData.live_up_str : "0 B/s"
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: ((root.liveData && root.liveData.live_up_bps > 0) ? "#C084FC" : "#64748B")
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: (root.liveData && root.liveData.lifetime_up_str) ? root.liveData.lifetime_up_str : "0 B"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 17
                                font.bold: true
                                color: "#F8FAFC"
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: "Raw: " + root.fmtRawBytes(root.liveData ? root.liveData.lifetime_up_bytes : 0) + "  •  Session: " + ((root.liveData && root.liveData.session_up_str) ? root.liveData.session_up_str : "0 B")
                                font.family: "Consolas, Cascadia Mono, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }
                    }

                    // KPI 3: On-Disk Library Size
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: kpiSizeCol.implicitHeight + 16
                        radius: 8
                        color: "#141720"
                        border.color: "#174237"
                        border.width: 1

                        ColumnLayout {
                            id: kpiSizeCol
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 3

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "💽 " + root.tr("stats_kpi_disk_size", "SIZE ON DISK")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#34D399"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: root.fmtInt(root.diskData ? root.diskData.storage_roots_count : 0) + " root(s)"
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 10
                                    color: "#6EE7B7"
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: (root.diskData && root.diskData.disk_total_str) ? root.diskData.disk_total_str : "0 B"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 17
                                font.bold: true
                                color: "#F8FAFC"
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: "Raw: " + root.fmtRawBytes(root.diskData ? root.diskData.disk_total_bytes : 0) + "  •  .part: " + ((root.diskData && root.diskData.disk_part_str) ? root.diskData.disk_part_str : "0 B")
                                font.family: "Consolas, Cascadia Mono, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }
                    }

                    // KPI 4: Artists, Files & Folders
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: kpiCountCol.implicitHeight + 16
                        radius: 8
                        color: "#141720"
                        border.color: "#43311A"
                        border.width: 1

                        ColumnLayout {
                            id: kpiCountCol
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 3

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "📁 " + root.tr("stats_kpi_library", "ARTISTS, FILES & FOLDERS")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: "#F59E0B"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: root.fmtInt(root.diskData ? root.diskData.archive_posts : 0) + " posts"
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 10
                                    color: "#FCD34D"
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: root.fmtInt(root.diskData ? root.diskData.total_artists : 0) + " " + root.tr("stats_lbl_artists", "Artists")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 17
                                font.bold: true
                                color: "#F8FAFC"
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: root.fmtInt(root.diskData ? root.diskData.disk_total_files : 0) + " files  •  " + root.fmtInt(root.diskData ? root.diskData.disk_total_folders : 0) + " folders (" + root.fmtInt(root.diskData ? root.diskData.disk_artist_folders : 0) + " roots)"
                                font.family: "Consolas, Cascadia Mono, monospace"
                                font.pixelSize: 10
                                color: "#94A3B8"
                            }
                        }
                    }
                }

                // ── Section 2: Network & Engine Raw Counters + Databases ─────────────────────
                GridLayout {
                    Layout.fillWidth: true
                    columns: root.width >= 900 ? 2 : 1
                    columnSpacing: 12
                    rowSpacing: 12

                    // Card A: Network I/O & Engine Raw Telemetry
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        implicitHeight: netCardCol.implicitHeight + 24
                        radius: 8
                        color: "#141720"
                        border.color: "#242A38"
                        border.width: 1

                        ColumnLayout {
                            id: netCardCol
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "📡 " + root.tr("stats_sec_network", "Network & Engine Telemetry (Raw)")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: "#F1F5F9"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: "Uptime: " + ((root.liveData && root.liveData.session_uptime_str) ? root.liveData.session_uptime_str : "0s")
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                }
                            }

                            // Column Header
                            RowLayout {
                                Layout.fillWidth: true
                                Text { Layout.fillWidth: true; text: "METRIC"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                                Text { Layout.preferredWidth: root.width >= 520 ? 150 : 100; horizontalAlignment: Text.AlignRight; text: "SESSION"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                                Text { Layout.preferredWidth: root.width >= 520 ? 150 : 105; horizontalAlignment: Text.AlignRight; text: "LIFETIME"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

                            Repeater {
                                model: {
                                    var l = root.liveData || {}
                                    return [
                                        { k: "Total Download", s: (l.session_down_str || "0 B") + " (" + root.fmtInt(l.session_down_bytes) + " B)", t: (l.lifetime_down_str || "0 B") + " (" + root.fmtInt(l.lifetime_down_bytes) + " B)", c: "#38BDF8" },
                                        { k: "Total Upload (Requests)", s: (l.session_up_str || "0 B") + " (" + root.fmtInt(l.session_up_bytes) + " B)", t: (l.lifetime_up_str || "0 B") + " (" + root.fmtInt(l.lifetime_up_bytes) + " B)", c: "#A78BFA" },
                                        { k: "Media Stream Bytes", s: l.session_down_media_str || "0 B", t: l.lifetime_down_media_str || "0 B", c: "#CBD5E1" },
                                        { k: "API / Metadata Bytes", s: l.session_down_api_str || "0 B", t: l.lifetime_down_api_str || "0 B", c: "#CBD5E1" },
                                        { k: "Peak Speed (Down / Up)", s: (l.session_peak_down_str || "0 B/s") + " / " + (l.session_peak_up_str || "0 B/s"), t: (l.lifetime_peak_down_str || "0 B/s") + " / " + (l.lifetime_peak_up_str || "0 B/s"), c: "#22D3EE" },
                                        { k: "HTTP Requests", s: root.fmtInt(l.session_http_requests), t: root.fmtInt(l.lifetime_http_requests), c: "#E2E8F0" },
                                        { k: "HTTP Errors (4xx/5xx / 429)", s: root.fmtInt(l.session_http_errors) + " / " + root.fmtInt(l.session_http_429), t: root.fmtInt(l.lifetime_http_errors) + " / " + root.fmtInt(l.lifetime_http_429), c: ((l.session_http_errors || 0) > 0 ? "#FB7185" : "#94A3B8") },
                                        { k: "Files Completed", s: root.fmtInt(l.session_files_completed), t: root.fmtInt(l.lifetime_files_completed), c: "#34D399" },
                                        { k: "Files Skipped (Existing/Filter)", s: root.fmtInt(l.session_files_skipped), t: root.fmtInt(l.lifetime_files_skipped), c: "#FBBF24" },
                                        { k: "Files Failed / Retries", s: root.fmtInt(l.session_files_failed) + " / " + root.fmtInt(l.session_retries), t: root.fmtInt(l.lifetime_files_failed) + " / " + root.fmtInt(l.lifetime_retries), c: ((l.session_files_failed || 0) > 0 ? "#FB7185" : "#94A3B8") },
                                        { k: "Batches Completed", s: root.fmtInt(l.session_batches_completed), t: root.fmtInt(l.lifetime_batches_completed), c: "#E2E8F0" },
                                        { k: "Compression Saved", s: (l.session_compressed_saved_str || "0 B") + " (" + root.fmtInt(l.session_compressed_files) + "x)", t: (l.lifetime_compressed_saved_str || "0 B") + " (" + root.fmtInt(l.lifetime_compressed_files) + "x)", c: "#34D399" },
                                        { k: "Archives Extracted", s: root.fmtInt(l.session_extracted_archives) + " (" + root.fmtInt(l.session_extracted_files) + " files)", t: root.fmtInt(l.lifetime_extracted_archives) + " (" + root.fmtInt(l.lifetime_extracted_files) + " files)", c: "#E2E8F0" },
                                        { k: "Active Download Time", s: l.session_active_download_str || "0s", t: l.lifetime_active_download_str || "0s", c: "#CBD5E1" }
                                    ]
                                }
                                delegate: RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.k
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#CBD5E1"
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.preferredWidth: root.width >= 520 ? 150 : 100
                                        horizontalAlignment: Text.AlignRight
                                        text: modelData.s
                                        font.family: "Consolas, Cascadia Mono, monospace"
                                        font.pixelSize: 10
                                        color: modelData.c
                                        elide: Text.ElideLeft
                                    }
                                    Text {
                                        Layout.preferredWidth: root.width >= 520 ? 150 : 105
                                        horizontalAlignment: Text.AlignRight
                                        text: modelData.t
                                        font.family: "Consolas, Cascadia Mono, monospace"
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: modelData.c
                                        elide: Text.ElideLeft
                                    }
                                }
                            }
                        }
                    }

                    // Card B: Archive DB, History & Local Disk Raw Counters
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        implicitHeight: dbCardCol.implicitHeight + 24
                        radius: 8
                        color: "#141720"
                        border.color: "#242A38"
                        border.width: 1

                        ColumnLayout {
                            id: dbCardCol
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "🗃️ " + root.tr("stats_sec_databases", "Archive, History & Disk Index (Raw)")
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: "#F1F5F9"
                                }
                                Item { Layout.fillWidth: true }
                                Text {
                                    text: "First track: " + String((root.liveData && root.liveData.first_recorded_at) ? root.liveData.first_recorded_at : "").slice(0, 10)
                                    font.family: "Consolas, Cascadia Mono, monospace"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                Text { Layout.fillWidth: true; text: "STORE / FIELD"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                                Text { Layout.preferredWidth: 185; horizontalAlignment: Text.AlignRight; text: "RAW VALUE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

                            Repeater {
                                model: {
                                    var d = root.diskData || {}
                                    var l = root.liveData || {}
                                    return [
                                        { k: "On-Disk Total Files", v: root.fmtInt(d.disk_total_files) + " files", c: "#F8FAFC" },
                                        { k: "On-Disk Total Folders", v: root.fmtInt(d.disk_total_folders) + " (" + root.fmtInt(d.disk_artist_folders) + " artist dirs)", c: "#F8FAFC" },
                                        { k: "On-Disk Total Bytes", v: (d.disk_total_str || "0 B") + " (" + root.fmtInt(d.disk_total_bytes) + " B)", c: "#34D399" },
                                        { k: "Unfinished .part Files", v: root.fmtInt(d.disk_part_files) + " (" + (d.disk_part_str || "0 B") + ")", c: (d.disk_part_files || 0) > 0 ? "#F59E0B" : "#94A3B8" },
                                        { k: "Archive DB — Indexed Files", v: root.fmtInt(d.archive_files), c: "#38BDF8" },
                                        { k: "Archive DB — Indexed Creators", v: root.fmtInt(d.archive_creators), c: "#A78BFA" },
                                        { k: "Archive DB — Indexed Posts", v: root.fmtInt(d.archive_posts), c: "#E2E8F0" },
                                        { k: "Archive DB — Recorded Size", v: (d.archive_recorded_str || "0 B") + " (" + root.fmtInt(d.archive_recorded_bytes) + " B)", c: "#CBD5E1" },
                                        { k: "Archive Verification (OK / Missing / Unchecked)", v: root.fmtInt(d.archive_verified_files) + " / " + root.fmtInt(d.archive_missing_files) + " / " + root.fmtInt(d.archive_unverified_files), c: "#CBD5E1" },
                                        { k: "Archive SQLite File Size", v: (d.archive_db_str || "0 B") + " (" + root.fmtInt(d.archive_db_bytes) + " B)", c: "#94A3B8" },
                                        { k: "History DB — Sessions / File IDs", v: root.fmtInt(d.history_sessions) + " / " + root.fmtInt(d.history_files), c: "#E2E8F0" },
                                        { k: "History SQLite File Size", v: (d.history_db_str || "0 B") + " (" + root.fmtInt(d.history_db_bytes) + " B)", c: "#94A3B8" },
                                        { k: "Watchlist Tracked Artists", v: root.fmtInt(d.watchlist_creators), c: "#A78BFA" },
                                        { k: "Statistics State File", v: l.stats_file_str || "0 B", c: "#64748B" }
                                    ]
                                }
                                delegate: RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.k
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: "#CBD5E1"
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.preferredWidth: 185
                                        horizontalAlignment: Text.AlignRight
                                        text: modelData.v
                                        font.family: "Consolas, Cascadia Mono, monospace"
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: modelData.c
                                        elide: Text.ElideLeft
                                    }
                                }
                            }
                        }
                    }
                }

                // ── Sections 3 & 4: Storage Drives, Categories & Services ──────────────────
                StatsBreakdownsSection {
                    view: root
                }

                // ── Section 5: Downloaded Artists Raw Table ──────────────────────────────────
                StatsArtistsTable {
                    view: root
                }
            }
        }
    }
}
