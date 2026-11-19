import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Storage Drives & Roots, File Categories, and Platforms/Services breakdowns.
ColumnLayout {
    id: breakdownsSection

    required property var view

    Layout.fillWidth: true
    spacing: 10

    // ── Section 3: Storage Drives & Roots Breakdown ──────────────────────────────
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: drivesCol.implicitHeight + 24
        radius: 8
        color: "#141720"
        border.color: "#242A38"
        border.width: 1

        ColumnLayout {
            id: drivesCol
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "💾 " + view.tr("stats_sec_drives", "Storage Roots & Drives")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    font.bold: true
                    color: "#F1F5F9"
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: view.fmtInt((view.diskData && view.diskData.drives) ? view.diskData.drives.length : 0) + " configured root(s)"
                    font.family: "Consolas, Cascadia Mono, monospace"
                    font.pixelSize: 10
                    color: "#64748B"
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { Layout.preferredWidth: 96; text: "ROLE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { Layout.fillWidth: true; text: "PATH"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight; text: "ARTISTS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { Layout.preferredWidth: 76; horizontalAlignment: Text.AlignRight; text: "FOLDERS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight; text: "FILES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { Layout.preferredWidth: 96; horizontalAlignment: Text.AlignRight; text: "USED DATA"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                Text { visible: view.width >= 820; Layout.preferredWidth: 165; horizontalAlignment: Text.AlignRight; text: "VOLUME FREE / TOTAL"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

            Repeater {
                model: (view.diskData && view.diskData.drives) ? view.diskData.drives : []
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 30
                    radius: 5
                    color: drvHover.hovered ? "#1A202D" : "transparent"

                    HoverHandler { id: drvHover }
                    TapHandler {
                        onTapped: if (modelData.exists && view.statsBridge) view.statsBridge.openFolder(modelData.path)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        anchors.rightMargin: 4
                        spacing: 8

                        Rectangle {
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 20
                            radius: 4
                            color: modelData.role === "Primary" ? "#0C2D48" : (modelData.role === "Overflow Pool" ? "#2E1065" : "#1F2937")
                            Text {
                                anchors.centerIn: parent
                                text: modelData.role || "Root"
                                font.pixelSize: 9
                                font.bold: true
                                color: modelData.role === "Primary" ? "#38BDF8" : (modelData.role === "Overflow Pool" ? "#C084FC" : "#94A3B8")
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: modelData.path + (modelData.exists ? "" : "  [Missing]")
                            font.family: "Consolas, Cascadia Mono, monospace"
                            font.pixelSize: 11
                            color: modelData.exists ? (drvHover.hovered ? "#38BDF8" : "#E2E8F0") : "#FB7185"
                            elide: Text.ElideMiddle
                        }
                        Text { Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.artist_folders); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 11; color: "#CBD5E1" }
                        Text { Layout.preferredWidth: 76; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.folders); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 11; color: "#CBD5E1" }
                        Text { Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.files); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 11; color: "#F8FAFC" }
                        Text { Layout.preferredWidth: 96; horizontalAlignment: Text.AlignRight; text: modelData.used_str || "0 B"; font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 11; font.bold: true; color: "#34D399" }
                        Text {
                            visible: view.width >= 820
                            Layout.preferredWidth: 165
                            horizontalAlignment: Text.AlignRight
                            text: (modelData.volume_free_str || "0 B") + " / " + (modelData.volume_total_str || "0 B") + " (" + Number(modelData.volume_used_pct || 0).toFixed(0) + "%)"
                            font.family: "Consolas, Cascadia Mono, monospace"
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                    }
                }
            }

            Text {
                visible: !view.diskData || !view.diskData.drives || view.diskData.drives.length === 0
                text: view.tr("stats_no_drives", "No storage roots scanned yet.")
                font.pixelSize: 11
                color: "#64748B"
            }
        }
    }

    // ── Section 4: Categories & Services Side-by-Side ────────────────────────────
    GridLayout {
        Layout.fillWidth: true
        columns: view.width >= 900 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 12

        // File Categories Breakdown
        Rectangle {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            implicitHeight: catsCol.implicitHeight + 24
            radius: 8
            color: "#141720"
            border.color: "#242A38"
            border.width: 1

            ColumnLayout {
                id: catsCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "🗂️ " + view.tr("stats_sec_categories", "Media Types & File Categories (Raw)")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 13
                    font.bold: true
                    color: "#F1F5F9"
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: "CATEGORY"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 75; horizontalAlignment: Text.AlignRight; text: "DISK FILES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 85; horizontalAlignment: Text.AlignRight; text: "DISK SIZE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 50; horizontalAlignment: Text.AlignRight; text: "SHARE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight; text: "ARCHIVE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

                Repeater {
                    model: (view.diskData && view.diskData.categories) ? view.diskData.categories : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text { Layout.fillWidth: true; text: view.catLabel(modelData.category); font.pixelSize: 11; color: "#E2E8F0" }
                        Text { Layout.preferredWidth: 75; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.disk_files); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#CBD5E1" }
                        Text { Layout.preferredWidth: 85; horizontalAlignment: Text.AlignRight; text: modelData.disk_bytes_str || "0 B"; font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; font.bold: true; color: "#38BDF8" }
                        Text { Layout.preferredWidth: 50; horizontalAlignment: Text.AlignRight; text: Number(modelData.share_pct || 0).toFixed(1) + "%"; font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#94A3B8" }
                        Text { Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.archive_files); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#94A3B8" }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433"; visible: ((view.diskData && view.diskData.extensions) ? view.diskData.extensions.length : 0) > 0 }

                Text {
                    visible: ((view.diskData && view.diskData.extensions) ? view.diskData.extensions.length : 0) > 0
                    text: view.tr("stats_sec_extensions", "Top Extensions on Disk")
                    font.pixelSize: 11
                    font.bold: true
                    color: "#94A3B8"
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: {
                            var exts = (view.diskData && view.diskData.extensions) ? view.diskData.extensions : []
                            return exts.slice(0, 16)
                        }
                        delegate: Rectangle {
                            implicitHeight: 22
                            implicitWidth: extLbl.implicitWidth + 14
                            radius: 4
                            color: "#0D111A"
                            border.color: "#1E2638"
                            border.width: 1
                            Text {
                                id: extLbl
                                anchors.centerIn: parent
                                text: modelData.ext + "  " + view.fmtInt(modelData.files) + " (" + modelData.size_str + ")"
                                font.family: "Consolas, Cascadia Mono, monospace"
                                font.pixelSize: 10
                                color: "#CBD5E1"
                            }
                        }
                    }
                }
            }
        }

        // Platforms / Services Breakdown
        Rectangle {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            implicitHeight: svcsCol.implicitHeight + 24
            radius: 8
            color: "#141720"
            border.color: "#242A38"
            border.width: 1

            ColumnLayout {
                id: svcsCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "🌐 " + view.tr("stats_sec_services", "Services & Platforms (Raw)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 13
                        font.bold: true
                        color: "#F1F5F9"
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: view.fmtInt((view.diskData && view.diskData.services) ? view.diskData.services.length : 0) + " service(s)"
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#64748B"
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text { Layout.fillWidth: true; text: "SERVICE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 58; horizontalAlignment: Text.AlignRight; text: "ARTISTS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 58; horizontalAlignment: Text.AlignRight; text: "POSTS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: "FILES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: "FOLDERS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                    Text { Layout.preferredWidth: 85; horizontalAlignment: Text.AlignRight; text: "SIZE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

                Repeater {
                    model: (view.diskData && view.diskData.services) ? view.diskData.services : []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text {
                            Layout.fillWidth: true
                            text: String(modelData.service || "unknown").toUpperCase()
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: view.svcColor(modelData.service)
                            elide: Text.ElideRight
                        }
                        Text { Layout.preferredWidth: 58; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.artists); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#E2E8F0" }
                        Text { Layout.preferredWidth: 58; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.posts); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#CBD5E1" }
                        Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.files); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#F8FAFC" }
                        Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: view.fmtInt(modelData.folders); font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; color: "#94A3B8" }
                        Text { Layout.preferredWidth: 85; horizontalAlignment: Text.AlignRight; text: modelData.size_str || "0 B"; font.family: "Consolas, Cascadia Mono, monospace"; font.pixelSize: 10; font.bold: true; color: "#34D399" }
                    }
                }

                Text {
                    visible: !view.diskData || !view.diskData.services || view.diskData.services.length === 0
                    text: view.tr("stats_no_services", "No service data yet.")
                    font.pixelSize: 11
                    color: "#64748B"
                }
            }
        }
    }

}
