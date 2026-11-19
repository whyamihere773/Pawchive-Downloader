import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ══════════════════════════════════════════════════════════════════════
// ── TOP CONTROLS & HEADER CARD ────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════
Rectangle {
    id: headerCard
    required property var view
    Layout.fillWidth: true
    implicitHeight: headerCol.implicitHeight + 24
    radius: 12
    color: "#0F141C"
    border.color: "#1E2638"
    border.width: 1

    // Cyber-styled option checkbox for "Delete archive after successful extraction"
    component DeleteArchiveOption: MouseArea {
        id: delMouse
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        implicitHeight: Math.max(22, delRow.implicitHeight)
        implicitWidth: delRow.implicitWidth
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: headerCard.view.tr("decompressor_delete_tip", "The archive is moved to the Recycle Bin, and only after 7-Zip finishes without errors.")
        onClicked: {
            if (headerCard.view.decompressor) headerCard.view.decompressor.deleteAfter = !headerCard.view.decompressor.deleteAfter;
        }

        RowLayout {
            id: delRow
            anchors.fill: parent
            spacing: 8

            Rectangle {
                width: 18
                height: 18
                radius: 4
                color: (headerCard.view.decompressor && headerCard.view.decompressor.deleteAfter) ? "#EF4444" : "#111827"
                border.color: (headerCard.view.decompressor && headerCard.view.decompressor.deleteAfter) ? "#F87171" : (delMouse.containsMouse ? "#64748B" : "#334155")
                border.width: (headerCard.view.decompressor && headerCard.view.decompressor.deleteAfter) ? 1.5 : 1

                Text {
                    anchors.centerIn: parent
                    text: "✓"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                    visible: headerCard.view.decompressor && headerCard.view.decompressor.deleteAfter
                }
            }

            Text {
                text: headerCard.view.tr("decompressor_delete_opt", "Move archive to the Recycle Bin after extracting")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Medium
                color: headerCard.view.decompressor && headerCard.view.decompressor.deleteAfter ? "#FCA5A5" : (delMouse.containsMouse ? "#CBD5E1" : "#94A3B8")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }

    ColumnLayout {
        id: headerCol
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // Row 1: Title and (when wide) Action Buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: "📦"
                font.pixelSize: 22
                Layout.alignment: Qt.AlignVCenter
            }

            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true

                Text {
                    text: headerCard.view.tr("tab_bulk_decompressor", "Bulk Decompressor")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 15
                    font.weight: 600
                    color: "#F1F5F9"
                }
                Text {
                    text: headerCard.view.tr("decompressor_desc", "Auto-scan watchlist artists & folders for archives, verify disk space, and extract.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#64748B"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    visible: !headerCard.view.isNarrow
                }
            }

            // Action buttons in title row ONLY when wide (>= 720px)
            RowLayout {
                spacing: 8
                visible: !headerCard.view.isNarrow

                // Add Custom Folder Button
                Rectangle {
                    height: 30
                    implicitWidth: addFolderRowWide.implicitWidth + 18
                    radius: 6
                    color: addFolderMouseWide.containsMouse ? "#1E293B" : "#141C2A"
                    border.color: addFolderMouseWide.containsMouse ? "#475569" : "#334155"
                    border.width: 1

                    Row {
                        id: addFolderRowWide
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "📁+"; font.pixelSize: 11 }
                        Text {
                            text: headerCard.view.tr("decompressor_add_folder", "Add Folder")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: "#E2E8F0"
                        }
                    }

                    MouseArea {
                        id: addFolderMouseWide
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (headerCard.view.decompressor) headerCard.view.decompressor.browseCustomFolder()
                    }
                }

                // Scan Archives Button
                Rectangle {
                    height: 30
                    implicitWidth: scanRowWide.implicitWidth + 20
                    radius: 6
                    color: scanMouseWide.containsMouse ? "#4338CA" : "#3730A3"
                    border.color: "#6366F1"
                    border.width: 1
                    opacity: headerCard.view.decompressor && headerCard.view.decompressor.isBusy ? 0.6 : 1.0

                    Row {
                        id: scanRowWide
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: headerCard.view.decompressor && headerCard.view.decompressor.isScanning ? "⏳" : "🔍"
                            font.pixelSize: 11
                        }
                        Text {
                            text: headerCard.view.decompressor && headerCard.view.decompressor.isScanning
                                  ? headerCard.view.tr("decompressor_scanning", "Scanning...")
                                  : headerCard.view.tr("decompressor_scan_btn", "Scan Archives")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FFFFFF"
                        }
                    }

                    MouseArea {
                        id: scanMouseWide
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !(headerCard.view.decompressor && headerCard.view.decompressor.isBusy)
                        onClicked: if (headerCard.view.decompressor) headerCard.view.decompressor.scanLocations()
                    }
                }

                // Password Bank Button
                Rectangle {
                    height: 30
                    implicitWidth: pwBankRowWide.implicitWidth + 18
                    radius: 6
                    color: pwBankMouseWide.containsMouse ? "#15293D" : "#0F1F2E"
                    border.color: pwBankMouseWide.containsMouse ? "#38BDF8" : "#1E3A5F"
                    border.width: 1
                    ToolTip.visible: pwBankMouseWide.containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: headerCard.view.tr("tip_password_bank", "Manage remembered passwords for automatic archive extraction")

                    Row {
                        id: pwBankRowWide
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "🔑"; font.pixelSize: 11 }
                        Text {
                            text: headerCard.view.tr("btn_password_bank", "Password Bank")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: "#38BDF8"
                        }
                        Rectangle {
                            width: pwBankCountTxt.implicitWidth + 8
                            height: 14
                            radius: 7
                            color: "#1E3A5F"
                            visible: headerCard.view.decompressor && headerCard.view.decompressor.savedPasswordsCount > 0
                            Text {
                                id: pwBankCountTxt
                                anchors.centerIn: parent
                                text: headerCard.view.decompressor ? headerCard.view.decompressor.savedPasswordsCount : 0
                                font.pixelSize: 8
                                font.weight: Font.Bold
                                color: "#7DD3FC"
                            }
                        }
                    }

                    MouseArea {
                        id: pwBankMouseWide
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: headerCard.view.showPasswordBank = true
                    }
                }
            }

            // Fold the options away / bring them back
            Rectangle {
                objectName: "decompressorFold"
                implicitWidth: 30
                implicitHeight: 30
                radius: 6
                Layout.alignment: Qt.AlignVCenter
                color: foldMouse.containsMouse ? "#1E293B" : "#141C2A"
                border.color: foldMouse.containsMouse ? "#475569" : "#334155"
                border.width: 1
                Springy { hover: foldMouse.containsMouse; pressed: foldMouse.pressed }

                Canvas {
                    anchors.centerIn: parent
                    width: 12
                    height: 7
                    rotation: headerCard.view.optionsOpen ? 180 : 0
                    Behavior on rotation { SpringAnimation { spring: 4.2; damping: 0.32; mass: 0.7; epsilon: 0.2 } }
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.strokeStyle = "#CBD5E1"
                        ctx.lineWidth = 1.8
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        ctx.moveTo(1, 1)
                        ctx.lineTo(width / 2, height - 1)
                        ctx.lineTo(width - 1, 1)
                        ctx.stroke()
                    }
                }

                MouseArea {
                    id: foldMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: headerCard.view.optionsOpen ? headerCard.view.tr("decompressor_hide_options", "Hide options")
                                                   : headerCard.view.tr("decompressor_show_options", "Show options")
                    onClicked: if (headerCard.view.decompressor) headerCard.view.decompressor.headerCollapsed = !headerCard.view.decompressor.headerCollapsed
                }
            }
        }

        // Action buttons on dedicated row when narrow (< 720px, e.g. when Progress Log is open)
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: headerCard.view.isNarrow

            // Add Custom Folder Button (50% width)
            Rectangle {
                Layout.fillWidth: true
                height: 32
                radius: 6
                color: addFolderMouseNarrow.containsMouse ? "#1E293B" : "#141C2A"
                border.color: addFolderMouseNarrow.containsMouse ? "#475569" : "#334155"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "📁+"; font.pixelSize: 12 }
                    Text {
                        text: headerCard.view.tr("decompressor_add_folder", "Add Folder")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#E2E8F0"
                    }
                }

                MouseArea {
                    id: addFolderMouseNarrow
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (headerCard.view.decompressor) headerCard.view.decompressor.browseCustomFolder()
                }
            }

            // Scan Archives Button
            Rectangle {
                Layout.fillWidth: true
                height: 32
                radius: 6
                color: scanMouseNarrow.containsMouse ? "#4338CA" : "#3730A3"
                border.color: "#6366F1"
                border.width: 1
                opacity: headerCard.view.decompressor && headerCard.view.decompressor.isBusy ? 0.6 : 1.0

                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: headerCard.view.decompressor && headerCard.view.decompressor.isScanning ? "⏳" : "🔍"
                        font.pixelSize: 12
                    }
                    Text {
                        text: headerCard.view.decompressor && headerCard.view.decompressor.isScanning
                              ? headerCard.view.tr("decompressor_scanning", "Scanning...")
                              : headerCard.view.tr("decompressor_scan_btn", "Scan Archives")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#FFFFFF"
                    }
                }

                MouseArea {
                    id: scanMouseNarrow
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: !(headerCard.view.decompressor && headerCard.view.decompressor.isBusy)
                    onClicked: if (headerCard.view.decompressor) headerCard.view.decompressor.scanLocations()
                }
            }

            // Password Bank Button (Narrow)
            Rectangle {
                Layout.fillWidth: true
                height: 32
                radius: 6
                color: pwBankMouseNarrow.containsMouse ? "#15293D" : "#0F1F2E"
                border.color: pwBankMouseNarrow.containsMouse ? "#38BDF8" : "#1E3A5F"
                border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 5
                    Text { text: "🔑"; font.pixelSize: 11 }
                    Text {
                        text: headerCard.view.tr("btn_password_bank", "Password Bank")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#38BDF8"
                    }
                    Rectangle {
                        width: pwBankCountTxtNarrow.implicitWidth + 8
                        height: 14
                        radius: 7
                        color: "#1E3A5F"
                        visible: headerCard.view.decompressor && headerCard.view.decompressor.savedPasswordsCount > 0
                        Text {
                            id: pwBankCountTxtNarrow
                            anchors.centerIn: parent
                            text: headerCard.view.decompressor ? headerCard.view.decompressor.savedPasswordsCount : 0
                            font.pixelSize: 8
                            font.weight: Font.Bold
                            color: "#7DD3FC"
                        }
                    }
                }

                MouseArea {
                    id: pwBankMouseNarrow
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: headerCard.view.showPasswordBank = true
                }
            }
        }

        // The options fold away with the button on the title row: a spring whose weight grows with the
        // panel's height, so a tall panel swings in heavier and slower than a short one
        Item {
            id: optionsPane
            objectName: "decompressorOptions"
            Layout.fillWidth: true
            clip: true
            readonly property real fullHeight: optionsCol.implicitHeight
            readonly property real weight: Math.max(0.8, Math.min(2.4, fullHeight / 150))
            property real shown: headerCard.view.optionsOpen ? fullHeight : 0
            Behavior on shown {
                SpringAnimation { spring: 2.8; damping: 0.5; mass: optionsPane.weight; epsilon: 0.3 }
            }
            Layout.preferredHeight: Math.max(0, shown)
            visible: shown > 0.5
            opacity: headerCard.view.optionsOpen ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutQuad } }

            ColumnLayout {
                id: optionsCol
                width: parent.width
                spacing: 12

                // Divider
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#1E2638"
                }

                // Configuration settings & Options (Responsive)
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16

                        // Parallel extraction count
                        RowLayout {
                            spacing: 6
                            Text {
                                text: headerCard.view.tr("decompressor_parallel", "Parallel:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            DecompressorNumberStepper {
                                from: 1
                                to: 8
                                value: headerCard.view.decompressor ? headerCard.view.decompressor.maxParallel : 2
                                onValueModified: function(val) {
                                    if (headerCard.view.decompressor) headerCard.view.decompressor.maxParallel = val;
                                }
                            }
                        }

                        // Threads per archive
                        RowLayout {
                            spacing: 6
                            Text {
                                text: headerCard.view.tr("decompressor_threads", "Threads:")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#94A3B8"
                            }
                            DecompressorNumberStepper {
                                from: 1
                                to: 16
                                value: headerCard.view.decompressor ? headerCard.view.decompressor.threadsPerArchive : 2
                                onValueModified: function(val) {
                                    if (headerCard.view.decompressor) headerCard.view.decompressor.threadsPerArchive = val;
                                }
                            }
                        }

                        // When wide (>= 820px), show delete option on the same row
                        DeleteArchiveOption {
                            visible: headerCard.view.width >= 820
                        }

                        Item { Layout.fillWidth: true }
                    }

                    // When narrow (< 820px), show delete option on its own full-width row below
                    DeleteArchiveOption {
                        Layout.fillWidth: true
                        visible: headerCard.view.width < 820
                    }

                    CompressAfterOptions {
                        Layout.fillWidth: true
                        decompressor: headerCard.view.decompressor
                    }
                }
            }
        }
    }
}
