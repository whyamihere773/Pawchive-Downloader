import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ══════════════════════════════════════════════════════════════════════
// ── ARCHIVE ITEMS LIST VIEW ───────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════
// ── ARCHIVE ITEMS CREATOR TREE VIEW ───────────────────────────────────
// ══════════════════════════════════════════════════════════════════════
Rectangle {
    id: listPanel
    required property var view
    required property var pageFlick
    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumHeight: 320
    radius: 10
    color: "#0B0E14"
    border.color: "#182030"
    border.width: 1
    clip: true

    // Empty state
    ColumnLayout {
        anchors.centerIn: parent
        visible: listPanel.view.groupCount === 0
        spacing: 8

        Text {
            text: "📭"
            font.pixelSize: 32
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: listPanel.view.tr("decompressor_no_archives", "No archives found.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 14
            font.weight: 600
            color: "#64748B"
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: listPanel.view.tr("decompressor_scan_hint", "Click 'Scan Archives' to search watchlist creators' folders, or 'Add Folder' for custom directories.")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#475569"
            Layout.alignment: Qt.AlignHCenter
        }
    }

    SmoothListView {
        id: archiveListView
        chainTo: listPanel.pageFlick
        anchors.fill: parent
        anchors.margins: 8
        spacing: 0
        clip: true
        visible: listPanel.view.groupCount > 0
        model: listPanel.view.groupsModel

        // One row per creator group header and per archive (rows of folded groups aren't in the
        // list): only the rows on screen are built, however many archives a creator has
        delegate: Item {
            id: rowCell
            width: archiveListView.width - 12
            readonly property bool isGroup: modelData.kind === "group"
            height: isGroup ? 46 : 41

            Loader {
                active: rowCell.isGroup
                visible: active
                y: 8
                width: parent.width
                height: 38
                sourceComponent: Component {
                        // ── 1. Creator Group Header Row ───────────────────────
                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: headerMouse.containsMouse ? "#161D2C" : "#111622"
                            border.color: headerMouse.containsMouse ? "#334155" : (listPanel.view.isCreatorCollapsed(modelData) ? "#1A2234" : "#28344E")
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8

                                // Expand/Collapse Chevron
                                Text {
                                    text: listPanel.view.isCreatorCollapsed(modelData) ? "▶" : "▼"
                                    font.pixelSize: 10
                                    color: "#94A3B8"
                                    Layout.alignment: Qt.AlignVCenter
                                }

                                // Creator Checkbox (Batch select/deselect all in this creator)
                                Rectangle {
                                    width: 18
                                    height: 18
                                    radius: 4
                                    color: modelData.allSelected ? "#38BDF8" : (modelData.someSelected ? "#1E293B" : "#111827")
                                    border.color: modelData.allSelected ? "#38BDF8" : (modelData.someSelected ? "#60A5FA" : (crCheckMouse.containsMouse ? "#64748B" : "#334155"))
                                    border.width: (modelData.allSelected || modelData.someSelected) ? 1.5 : 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.allSelected ? "✓" : (modelData.someSelected ? "−" : "")
                                        font.pixelSize: 11
                                        font.weight: Font.Bold
                                        color: modelData.allSelected ? "#0F172A" : "#60A5FA"
                                    }

                                    MouseArea {
                                        id: crCheckMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: listPanel.view.rowText.decompressor_creator_toggle_tip
                                        onClicked: {
                                            if (listPanel.view.decompressor)
                                                listPanel.view.decompressor.toggleCreatorByScanRoot(modelData.creator, modelData.directory);
                                        }
                                    }
                                }

                                // Creator Icon & Name + folder path
                                Text { text: "🎨"; font.pixelSize: 12 }
                                Column {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Text {
                                        text: modelData.creator || "Unknown"
                                        font.family: "Segoe UI, Inter, sans-serif"
                                        font.pixelSize: 13
                                        font.weight: 600
                                        color: "#F8FAFC"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                    Text {
                                        text: modelData.directory || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        color: "#4B5563"
                                        elide: Text.ElideLeft
                                        width: parent.width
                                        visible: text !== ""
                                    }
                                }

                                // Archive count & total size badge
                                Rectangle {
                                    height: 20
                                    implicitWidth: crCountText.implicitWidth + 12
                                    radius: 10
                                    color: "#1E293B"
                                    border.color: "#334155"
                                    border.width: 1

                                    Text {
                                        id: crCountText
                                        anchors.centerIn: parent
                                        text: modelData.totalCount + " " + (modelData.totalCount === 1 ? "archive" : "archives") + " • " + listPanel.view.formatBytes(modelData.totalBytes)
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: Font.Medium
                                        color: "#94A3B8"
                                    }
                                }

                                // Selection counter badge
                                Rectangle {
                                    height: 20
                                    implicitWidth: crSelText.implicitWidth + 10
                                    radius: 10
                                    color: modelData.selectedCount > 0 ? "#064E3B" : "#181D26"
                                    border.color: modelData.selectedCount > 0 ? "#059669" : "#242C3B"
                                    border.width: 1
                                    visible: modelData.selectedCount > 0

                                    Text {
                                        id: crSelText
                                        anchors.centerIn: parent
                                        text: modelData.selectedCount + " selected"
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        font.weight: 600
                                        color: "#34D399"
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                // Open creator folder button
                                Rectangle {
                                    height: 24
                                    implicitWidth: 26
                                    radius: 4
                                    color: crFoldMouse.containsMouse ? "#1E293B" : "transparent"
                                    border.color: crFoldMouse.containsMouse ? "#475569" : "transparent"
                                    border.width: 1
                                    visible: !!modelData.directory

                                    Text {
                                        anchors.centerIn: parent
                                        text: "📂"
                                        font.pixelSize: 11
                                    }

                                    MouseArea {
                                        id: crFoldMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: listPanel.view.rowText.tip_open_folder
                                        onClicked: {
                                            if (listPanel.view.decompressor) listPanel.view.decompressor.openFolder(modelData.directory);
                                        }
                                    }
                                }
                            }

                            // Header click toggles expand/collapse
                            MouseArea {
                                id: headerMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                z: -1
                                onClicked: listPanel.view.toggleCreatorCollapse(modelData)
                            }
                        }
                }
            }

            Loader {
                active: !rowCell.isGroup
                visible: active
                x: 14
                width: parent.width - 18
                height: 38
                sourceComponent: Component {
                        Rectangle {
                            id: archiveRow
                            anchors.fill: parent
                            radius: 5
                            // Color coding:
                            //  - already extracted (extractedPresent): warm amber tint
                            //  - selected: dark blue
                            //  - hovered: very dark
                            //  - default: near black
                            color: {
                                if (modelData.extractedPresent && modelData.status !== "extracting")
                                    return modelData.selected ? "#1C1500" : (rowMouse.containsMouse ? "#161000" : "#100C00");
                                return modelData.selected ? "#141C2B" : (rowMouse.containsMouse ? "#101622" : "#0A0E17");
                            }
                            border.color: {
                                if (modelData.status === "error") return "#7F1D1D";
                                if (modelData.status === "done" && modelData.extractedPresent) return "#78350F";  // amber for already-extracted
                                if (modelData.status === "done") return "#14532D";
                                if (modelData.extractedPresent) return "#92400E";  // amber border when known-extracted but not yet done in this session
                                return modelData.selected ? "#1E3A5F" : "#141A26";
                            }
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8

                                // Tree branch symbol
                                Text {
                                    text: "└─"
                                    font.family: "Consolas, monospace"
                                    font.pixelSize: 11
                                    color: "#334155"
                                }

                                // Archive Checkbox
                                Rectangle {
                                    width: 16
                                    height: 16
                                    radius: 3
                                    color: modelData.selected ? "#38BDF8" : "#111827"
                                    border.color: modelData.selected ? "#38BDF8" : (subCheckMouse.containsMouse ? "#64748B" : "#334155")
                                    border.width: modelData.selected ? 1.5 : 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                        color: "#0F172A"
                                        visible: modelData.selected
                                    }

                                    MouseArea {
                                        id: subCheckMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: if (listPanel.view.decompressor) listPanel.view.decompressor.toggleItem(modelData.id)
                                    }
                                }

                                // Format badge (ZIP, RAR, 7Z, TAR)
                                Rectangle {
                                    height: 18
                                    implicitWidth: 32
                                    radius: 4
                                    color: {
                                        var f = (modelData.filename || "").toLowerCase();
                                        if (f.indexOf(".zip") !== -1) return "#0284C7";
                                        if (f.indexOf(".rar") !== -1) return "#7C3AED";
                                        if (f.indexOf(".7z") !== -1) return "#DB2777";
                                        return "#475569";
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: {
                                            var f = (modelData.filename || "").toLowerCase();
                                            if (f.indexOf(".zip") !== -1) return "ZIP";
                                            if (f.indexOf(".rar") !== -1) return "RAR";
                                            if (f.indexOf(".7z") !== -1) return "7Z";
                                            if (f.indexOf(".tar") !== -1) return "TAR";
                                            return "ARC";
                                        }
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                        color: "#FFFFFF"
                                    }
                                }

                                // Filename
                                Text {
                                    text: modelData.filename || ""
                                    font.family: "Segoe UI, Inter, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: Font.Normal
                                    color: modelData.status === "error" ? "#FCA5A5"
                                         : modelData.extractedPresent && modelData.status !== "extracting" ? "#D97706"
                                         : (modelData.selected ? "#F1F5F9" : "#94A3B8")
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }

                                // Size text
                                Text {
                                    text: listPanel.view.formatBytes(modelData.size)
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    color: "#64748B"
                                }

                                // Status / Progress indicator
                                Item {
                                    width: listPanel.view.isNarrow ? 90 : 120
                                    height: 22

                                    // Pending / Already Extracted badge
                                    Rectangle {
                                        anchors.centerIn: parent
                                        visible: modelData.status === "pending"
                                        height: modelData.extractedPresent ? 18 : 0
                                        implicitWidth: modelData.extractedPresent ? (alreadyExtractedTxt.implicitWidth + 10) : 0
                                        radius: 9
                                        color: modelData.extractedPresent ? "#451A00" : "transparent"
                                        border.color: modelData.extractedPresent ? "#D97706" : "transparent"
                                        border.width: modelData.extractedPresent ? 1 : 0

                                        Text {
                                            id: alreadyExtractedTxt
                                            anchors.centerIn: parent
                                            text: modelData.extractedPresent ? ("🗂 " + listPanel.view.rowText.decompressor_already_extracted) : listPanel.view.rowText.decompressor_pending
                                            font.pixelSize: 9
                                            font.weight: modelData.extractedPresent ? Font.Bold : Font.Normal
                                            color: modelData.extractedPresent ? "#FBB040" : "#64748B"
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: modelData.extractedPresent
                                            ToolTip.visible: containsMouse && modelData.extractedPresent
                                            ToolTip.delay: 300
                                            ToolTip.text: listPanel.view.rowText.tip_already_extracted
                                        }
                                    }

                                    // Extracting / compressing progress bar
                                    RowLayout {
                                        anchors.fill: parent
                                        visible: modelData.status === "extracting" || modelData.status === "compressing"
                                        spacing: 4
                                        ToolTip.visible: compressHover.hovered && modelData.status === "compressing"
                                        ToolTip.text: listPanel.view.rowText.decompressor_compressing
                                        HoverHandler { id: compressHover }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 5
                                            radius: 2.5
                                            color: "#1E293B"
                                            clip: true
                                            Rectangle {
                                                height: parent.height
                                                radius: 2.5
                                                width: parent.width * (Math.max(0, Math.min(100, modelData.progress)) / 100.0)
                                                color: modelData.status === "compressing" ? "#38BDF8" : "#8B5CF6"
                                            }
                                        }
                                        Text {
                                            text: (modelData.status === "compressing" ? "🗜 " : "") + Math.round(modelData.progress) + "%"
                                            font.pixelSize: 10
                                            color: modelData.status === "compressing" ? "#7DD3FC" : "#A78BFA"
                                        }
                                    }

                                    // Done badge
                                    Rectangle {
                                        anchors.centerIn: parent
                                        visible: modelData.status === "done"
                                        height: 18
                                        implicitWidth: doneTxt.implicitWidth + 10
                                        radius: 9
                                        // Amber = was already extracted before this session; Green = freshly extracted now
                                        color: modelData.extractedPresent && modelData.progress < 100.0 ? "#451A00" : "#064E3B"
                                        border.color: modelData.extractedPresent && modelData.progress < 100.0 ? "#D97706" : "#10B981"
                                        border.width: 1
                                        Text {
                                            id: doneTxt
                                            anchors.centerIn: parent
                                            text: (modelData.extractedPresent && modelData.progress < 100.0)
                                                  ? ("🗂 " + listPanel.view.rowText.decompressor_pre_extracted)
                                                  : ("✓ " + listPanel.view.rowText.decompressor_done)
                                            font.pixelSize: 9
                                            font.weight: 600
                                            color: modelData.extractedPresent && modelData.progress < 100.0 ? "#FBB040" : "#34D399"
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: modelData.extractedPresent && modelData.progress < 100.0
                                            ToolTip.visible: containsMouse && modelData.extractedPresent && modelData.progress < 100.0
                                            ToolTip.delay: 300
                                            ToolTip.text: listPanel.view.rowText.tip_pre_extracted
                                        }
                                    }

                                    // Error badge with tooltip
                                    Rectangle {
                                        anchors.centerIn: parent
                                        visible: modelData.status === "error"
                                        height: 18
                                        implicitWidth: errTxt.implicitWidth + 10
                                        radius: 9
                                        color: "#450A0A"
                                        border.color: "#EF4444"
                                        border.width: 1
                                        Text {
                                            id: errTxt
                                            anchors.centerIn: parent
                                            text: "⚠️ " + listPanel.view.rowText.decompressor_error
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: "#FCA5A5"
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 100
                                            ToolTip.text: modelData.errorMessage || "Decompression error"
                                        }
                                    }

                                    // 🔐 Password Required badge
                                    Rectangle {
                                        id: pwReqBadge
                                        anchors.centerIn: parent
                                        visible: modelData.status === "password_required"
                                        height: 18
                                        implicitWidth: pwReqTxt.implicitWidth + 10
                                        radius: 9
                                        color: "#451A03"
                                        border.color: "#F59E0B"
                                        border.width: 1
                                        Text {
                                            id: pwReqTxt
                                            anchors.centerIn: parent
                                            text: "🔐 " + listPanel.view.rowText.status_password_required
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: "#FCD34D"
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 100
                                            ToolTip.text: listPanel.view.rowText.tip_enter_password
                                        }
                                    }
                                }

                                // 🔑 Enter Password inline button (password_required only)
                                Rectangle {
                                    height: 22
                                    implicitWidth: enterPwRow.implicitWidth + 10
                                    radius: 4
                                    visible: modelData.status === "password_required"
                                    color: enterPwMouse.containsMouse ? "#1C3A52" : "#0F2237"
                                    border.color: enterPwMouse.containsMouse ? "#38BDF8" : "#1E3A5F"
                                    border.width: 1

                                    Row {
                                        id: enterPwRow
                                        anchors.centerIn: parent
                                        spacing: 4
                                        Text { text: "🔑"; font.pixelSize: 9 }
                                        Text {
                                            text: listPanel.view.rowText.btn_try_extract
                                            font.pixelSize: 9
                                            font.weight: Font.Medium
                                            color: "#38BDF8"
                                        }
                                    }

                                    MouseArea {
                                        id: enterPwMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: listPanel.view.rowText.tip_enter_password
                                        onClicked: {
                                            listPanel.view.promptItemId = modelData.id;
                                            listPanel.view.promptFilename = modelData.filename;
                                            listPanel.view.promptCreator = modelData.creator;
                                            listPanel.view.promptDirectory = modelData.directory;
                                            listPanel.view.promptErrorMsg = "";
                                            listPanel.view.promptArchiveSize = modelData.size;
                                            listPanel.view.promptRemember = true;
                                            listPanel.view.promptWrongPw = false;
                                            listPanel.view.showPasswordPrompt = true;
                                        }
                                    }
                                }

                                // Open single archive directory button
                                Rectangle {
                                    height: 22
                                    implicitWidth: 22
                                    radius: 3
                                    color: singleFoldMouse.containsMouse ? "#1E293B" : "transparent"
                                    border.color: singleFoldMouse.containsMouse ? "#334155" : "transparent"
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: "📂"
                                        font.pixelSize: 10
                                    }

                                    MouseArea {
                                        id: singleFoldMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        ToolTip.visible: containsMouse
                                        ToolTip.delay: 300
                                        ToolTip.text: listPanel.view.rowText.tip_open_folder
                                        onClicked: if (listPanel.view.decompressor) listPanel.view.decompressor.openFolder(modelData.directory)
                                    }
                                }
                            }

                            // Row click toggles selection
                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                z: -1
                                onClicked: if (listPanel.view.decompressor) listPanel.view.decompressor.toggleItem(modelData.id)
                            }
                        }
                }
            }
        }
    }
}
