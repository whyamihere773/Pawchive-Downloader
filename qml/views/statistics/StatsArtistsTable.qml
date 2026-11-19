import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Filterable, sortable virtualized Downloaded Artists raw telemetry table.
Rectangle {
    id: artistsSection

    required property var view
    Layout.fillWidth: true
    implicitHeight: artistsCardCol.implicitHeight + 24
    radius: 8
    color: "#141720"
    border.color: "#242A38"
    border.width: 1

    ColumnLayout {
        id: artistsCardCol
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "🎨 " + view.tr("stats_sec_artists", "Downloaded Artists Raw Data")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 13
                font.bold: true
                color: "#F1F5F9"
            }

            Rectangle {
                implicitHeight: 20
                implicitWidth: artistCntLbl.implicitWidth + 12
                radius: 10
                color: "#1B2232"
                Text {
                    id: artistCntLbl
                    anchors.centerIn: parent
                    text: view.fmtInt(artistsList.count) + " / " + view.fmtInt(view.diskData ? view.diskData.total_artists : 0)
                    font.family: "Consolas, Cascadia Mono, monospace"
                    font.pixelSize: 10
                    font.bold: true
                    color: "#38BDF8"
                }
            }

            Item { Layout.fillWidth: true }
        }

        // Filter & Sort Controls
        Flow {
            Layout.fillWidth: true
            spacing: 8

            StyledTextField {
                id: artistSearchField
                objectName: "statsArtistSearch"
                width: Math.min(280, Math.max(180, artistsCardCol.width * 0.35))
                implicitHeight: 30
                leadingIcon: "🔍"
                placeholderText: view.tr("stats_search_artists", "Filter artist, service, ID, drive...")
                onTextChanged: {
                    if (view.statsBridge) view.statsBridge.artistSearch = text
                }
            }

            StyledComboBox {
                implicitHeight: 30
                implicitWidth: 150
                model: view.statsBridge ? view.statsBridge.availableServices : [{ text: "All Services", value: "all" }]
                value: view.statsBridge ? view.statsBridge.artistServiceFilter : "all"
                onValuePicked: function(val) {
                    if (view.statsBridge) view.statsBridge.artistServiceFilter = String(val)
                }
            }

            StyledComboBox {
                implicitHeight: 30
                implicitWidth: 165
                model: [
                    { text: view.tr("stats_sort_size", "Sort: Size (Largest)"), value: "size_desc" },
                    { text: view.tr("stats_sort_files", "Sort: Files (Most)"), value: "files_desc" },
                    { text: view.tr("stats_sort_folders", "Sort: Folders (Most)"), value: "folders_desc" },
                    { text: view.tr("stats_sort_posts", "Sort: Posts (Most)"), value: "posts_desc" },
                    { text: view.tr("stats_sort_name", "Sort: Artist (A-Z)"), value: "name_asc" }
                ]
                value: view.statsBridge ? view.statsBridge.artistSortBy : "size_desc"
                onValuePicked: function(val) {
                    if (view.statsBridge) view.statsBridge.artistSortBy = String(val)
                }
            }
        }

        // Table Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { Layout.preferredWidth: 36; text: "#"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.fillWidth: true; text: "ARTIST"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 92; text: "SERVICE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 72; horizontalAlignment: Text.AlignRight; text: "FILES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: "FOLDERS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; text: "POSTS"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 90; horizontalAlignment: Text.AlignRight; text: "SIZE"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { visible: view.width >= 960; Layout.preferredWidth: 115; horizontalAlignment: Text.AlignRight; text: "BYTES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { visible: view.width >= 780; Layout.preferredWidth: 80; horizontalAlignment: Text.AlignRight; text: "DRIVES"; font.pixelSize: 10; font.bold: true; color: "#64748B" }
            Text { Layout.preferredWidth: 28; text: ""; font.pixelSize: 10 }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: "#1E2433" }

        ListView {
            id: artistsList
            Layout.fillWidth: true
            Layout.preferredHeight: count > 0 ? Math.min(440, Math.max(120, count * 34)) : 70
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: view.statsBridge ? view.statsBridge.filteredArtists : []

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 6
            }

            delegate: Rectangle {
                width: artistsList.width - 6
                height: 34
                radius: 4
                color: rowHover.hovered ? "#1B2232" : (index % 2 === 0 ? "#10131B" : "transparent")

                HoverHandler { id: rowHover }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    spacing: 8

                    Text {
                        Layout.preferredWidth: 36
                        text: String(index + 1)
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    Text {
                        Layout.fillWidth: true
                        text: modelData.artist_name || "Unknown"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#F1F5F9"
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.preferredWidth: 92
                        text: String(modelData.service || "local").toUpperCase()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.bold: true
                        color: view.svcColor(modelData.service)
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.preferredWidth: 72
                        horizontalAlignment: Text.AlignRight
                        text: view.fmtInt(modelData.files)
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#F8FAFC"
                    }

                    Text {
                        Layout.preferredWidth: 66
                        horizontalAlignment: Text.AlignRight
                        text: view.fmtInt(modelData.folders)
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#CBD5E1"
                    }

                    Text {
                        Layout.preferredWidth: 66
                        horizontalAlignment: Text.AlignRight
                        text: view.fmtInt(modelData.posts)
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }

                    Text {
                        Layout.preferredWidth: 90
                        horizontalAlignment: Text.AlignRight
                        text: modelData.size_str || "0 B"
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        font.bold: true
                        color: "#34D399"
                    }

                    Text {
                        visible: view.width >= 960
                        Layout.preferredWidth: 115
                        horizontalAlignment: Text.AlignRight
                        text: view.fmtInt(modelData.size_bytes)
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    Text {
                        visible: view.width >= 780
                        Layout.preferredWidth: 80
                        horizontalAlignment: Text.AlignRight
                        text: modelData.drives || "-"
                        font.family: "Consolas, Cascadia Mono, monospace"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        Layout.preferredWidth: 26
                        Layout.preferredHeight: 22
                        radius: 4
                        color: openBtnHover.hovered && modelData.primary_folder ? "#26324A" : "transparent"
                        visible: Boolean(modelData.primary_folder)
                        HoverHandler { id: openBtnHover }
                        TapHandler {
                            onTapped: if (view.statsBridge && modelData.primary_folder) view.statsBridge.openFolder(modelData.primary_folder)
                        }
                        Text {
                            anchors.centerIn: parent
                            text: "📂"
                            font.pixelSize: 11
                        }
                    }
                    Item {
                        Layout.preferredWidth: 26
                        visible: !modelData.primary_folder
                    }
                }
            }
        }

        Text {
            visible: artistsList.count === 0
            text: view.isScanning ? view.tr("stats_artists_scanning", "Scanning artists...") : view.tr("stats_artists_empty", "No matching downloaded artists found.")
            font.pixelSize: 11
            color: "#64748B"
            Layout.alignment: Qt.AlignHCenter
        }
    }
}
