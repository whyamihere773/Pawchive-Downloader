import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab1Content
    required property var view
    visible: subTab1Content.view.currentSubTab === 1
    Layout.fillWidth: true
    spacing: 12

    // Card 1.1: Character & Keyword Rules
    DownloaderFiltersKeywordsCard {
        view: subTab1Content.view
    }

    // Card 1.2: Post Publication Date Range
    CardSection {
        Layout.fillWidth: true
        title: subTab1Content.view.tr("card_date_filtering", "Post Publication Date Range")
        iconText: "📅"
        entranceOffsetY: subTab1Content.view.tabEntranceOffsetY * 1.25
        entranceOpacity: subTab1Content.view.tabEntranceOpacity

        ColumnLayout {
            width: parent.width
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: subTab1Content.view.tr("hint_date_formats", "Accepts full dates (2024-06-15), year & month (2024-06), or year only (2024)")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.fillWidth: true
                }

                // Clear dates with fluid spring hover
                Text {
                    visible: (subTab1Content.view.bridge && ((subTab1Content.view.bridge.dateAfter && subTab1Content.view.bridge.dateAfter.length > 0) || (subTab1Content.view.bridge.dateBefore && subTab1Content.view.bridge.dateBefore.length > 0)))
                    text: subTab1Content.view.tr("btn_clear_dates", "Clear Range ✕")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.bold: true
                    color: dateClearMouse.containsMouse ? "#F87171" : "#94A3B8"
                    scale: dateClearMouse.pressed ? 0.92 : (dateClearMouse.containsMouse ? 1.06 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                    Behavior on color { ColorAnimation { duration: 140 } }

                    MouseArea {
                        id: dateClearMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (subTab1Content.view.bridge) {
                                subTab1Content.view.bridge.dateAfter = ""
                                subTab1Content.view.bridge.dateBefore = ""
                            }
                        }
                    }
                }
            }

            GridLayout {
                columns: subTab1Content.view.width > 540 ? 2 : 1
                Layout.fillWidth: true
                rowSpacing: 6
                columnSpacing: 12

                // Date After (From)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Text {
                        text: subTab1Content.view.tr("label_date_from", "From:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }

                    StyledTextField {
                        id: dateAfterInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        placeholderText: subTab1Content.view.tr("ph_date_from", "e.g. 2024, 2024-06, 2024-06-15")
                        tooltip: subTab1Content.view.tr("tip_date_from", "Earliest date to include. Supports a full year (e.g. 2024 starts Jan 1), month (2024-06 starts 1st), or exact day.")
                        text: subTab1Content.view.bridge ? subTab1Content.view.bridge.dateAfter : ""
                        onTextChanged: {
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.dateAfter !== text) {
                                subTab1Content.view.bridge.dateAfter = text
                            }
                        }
                    }
                }

                // Date Before (To)
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Text {
                        text: subTab1Content.view.tr("label_date_to", "To:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }

                    StyledTextField {
                        id: dateBeforeInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        placeholderText: subTab1Content.view.tr("ph_date_to", "e.g. 2024, 2024-12, 2024-12-31")
                        tooltip: subTab1Content.view.tr("tip_date_to", "Latest date to include. Supports a full year (e.g. 2024 ends Dec 31), month (2024-06 ends June 30), or exact day.")
                        text: subTab1Content.view.bridge ? subTab1Content.view.bridge.dateBefore : ""
                        onTextChanged: {
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.dateBefore !== text) {
                                subTab1Content.view.bridge.dateBefore = text
                            }
                        }
                    }
                }
            }

            // Live interpreted range badge with fluid spring pop-in
            Rectangle {
                id: dateRangeBadge
                property string afterText: subTab1Content.view.bridge ? (subTab1Content.view.bridge.dateAfter || "").trim() : ""
                property string beforeText: subTab1Content.view.bridge ? (subTab1Content.view.bridge.dateBefore || "").trim() : ""
                visible: afterText.length > 0 || beforeText.length > 0
                Layout.fillWidth: true
                implicitHeight: 24
                radius: 5
                color: "#0F172A"
                border.color: "#1E293B"
                border.width: 1

                scale: visible ? 1.0 : 0.8
                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                function describeRange() {
                    if (afterText.length > 0 && beforeText.length > 0) {
                        if (afterText === beforeText) {
                            if (afterText.length === 4) return "Entire year " + afterText + " (Jan 1, " + afterText + " - Dec 31, " + afterText + ")"
                            if (afterText.length === 7) return "Entire month of " + afterText
                        }
                        return "Filtering posts: " + afterText + "  →  " + beforeText
                    } else if (afterText.length > 0) {
                        if (afterText.length === 4) return "Filtering posts from " + afterText + " onwards (Jan 1, " + afterText + " +)"
                        if (afterText.length === 7) return "Filtering posts from " + afterText + " onwards"
                        return "Filtering posts from " + afterText + " onwards"
                    } else if (beforeText.length > 0) {
                        if (beforeText.length === 4) return "Filtering posts up through end of " + beforeText + " (Dec 31, " + beforeText + ")"
                        if (beforeText.length === 7) return "Filtering posts up through end of " + beforeText
                        return "Filtering posts up to " + beforeText
                    }
                    return ""
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text {
                        text: "🗓️"
                        font.pixelSize: 10
                    }
                    Text {
                        text: dateRangeBadge.describeRange()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#38BDF8"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            // Auto-scan pages checkbox
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: subTab1Content.view.bridge ? ((subTab1Content.view.bridge.dateAfter && subTab1Content.view.bridge.dateAfter.length > 0) || (subTab1Content.view.bridge.dateBefore && subTab1Content.view.bridge.dateBefore.length > 0)) : false

                StyledCheckBox {
                    id: dateAutoScanCheck
                    text: subTab1Content.view.tr("opt_date_auto_scan", "Auto-scan all pages for this range")
                    tooltip: subTab1Content.view.tr("opt_date_auto_scan_tip", "Automatically scan past the Page End limit to find all posts within the selected date range. Uncheck to strictly respect your Page Start / End settings.")
                    checked: subTab1Content.view.bridge ? subTab1Content.view.bridge.dateAutoScanPages : true
                    onCheckedChanged: if (subTab1Content.view.bridge) subTab1Content.view.bridge.dateAutoScanPages = checked
                }
            }
        }
    }

    // Card 1.3: File Size Range Limits
    CardSection {
        Layout.fillWidth: true
        title: subTab1Content.view.tr("card_size_filtering", "File Size Range Limits")
        iconText: "📦"
        entranceOffsetY: subTab1Content.view.tabEntranceOffsetY * 1.5
        entranceOpacity: subTab1Content.view.tabEntranceOpacity

        ColumnLayout {
            width: parent.width
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: subTab1Content.view.tr("hint_size_formats", "Only download files within a size window (e.g. 500MB, 1GB, 2.5GB). Leave blank for any size.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    Layout.fillWidth: true
                }

                // Clear size range with fluid spring hover
                Text {
                    visible: (subTab1Content.view.bridge && ((subTab1Content.view.bridge.minFileSize && subTab1Content.view.bridge.minFileSize.length > 0) || (subTab1Content.view.bridge.maxFileSize && subTab1Content.view.bridge.maxFileSize.length > 0)))
                    text: subTab1Content.view.tr("btn_clear_size_range", "Clear Range ✕")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.bold: true
                    color: sizeClearMouse.containsMouse ? "#F87171" : "#94A3B8"
                    scale: sizeClearMouse.pressed ? 0.92 : (sizeClearMouse.containsMouse ? 1.06 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                    Behavior on color { ColorAnimation { duration: 140 } }

                    MouseArea {
                        id: sizeClearMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (subTab1Content.view.bridge) {
                                subTab1Content.view.bridge.minFileSize = ""
                                subTab1Content.view.bridge.maxFileSize = ""
                            }
                        }
                    }
                }
            }

            GridLayout {
                columns: subTab1Content.view.width > 540 ? 2 : 1
                Layout.fillWidth: true
                rowSpacing: 6
                columnSpacing: 12

                // Min File Size
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Text {
                        text: subTab1Content.view.tr("label_size_min", "Min:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }

                    StyledTextField {
                        id: minFileSizeInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        placeholderText: subTab1Content.view.tr("ph_size_min", "e.g. 1GB or 500MB")
                        tooltip: subTab1Content.view.tr("tip_size_min", "Minimum file size. Files smaller than this will be skipped before downloading.")
                        text: subTab1Content.view.bridge ? subTab1Content.view.bridge.minFileSize : ""
                        validator: RegularExpressionValidator {
                            regularExpression: /^\s*(\d+(\.\d*)?|\.\d+)?\s*([KMGTP]B?|B)?\s*$/i
                        }
                        onTextChanged: {
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.minFileSize !== text) {
                                subTab1Content.view.bridge.minFileSize = text
                            }
                        }
                        onEditingFinished: {
                            var norm = subTab1Content.view.normalizeSizeInput(text)
                            if (text !== norm) text = norm
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.minFileSize !== norm) subTab1Content.view.bridge.minFileSize = norm
                        }
                    }
                }

                // Max File Size
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Text {
                        text: subTab1Content.view.tr("label_size_max", "Max:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#64748B"
                    }

                    StyledTextField {
                        id: maxFileSizeInput
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        placeholderText: subTab1Content.view.tr("ph_size_max", "e.g. 2GB or 2048MB")
                        tooltip: subTab1Content.view.tr("tip_size_max", "Maximum file size. Files larger than this will be skipped before downloading.")
                        text: subTab1Content.view.bridge ? subTab1Content.view.bridge.maxFileSize : ""
                        validator: RegularExpressionValidator {
                            regularExpression: /^\s*(\d+(\.\d*)?|\.\d+)?\s*([KMGTP]B?|B)?\s*$/i
                        }
                        onTextChanged: {
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.maxFileSize !== text) {
                                subTab1Content.view.bridge.maxFileSize = text
                            }
                        }
                        onEditingFinished: {
                            var norm = subTab1Content.view.normalizeSizeInput(text)
                            if (text !== norm) text = norm
                            if (subTab1Content.view.bridge && subTab1Content.view.bridge.maxFileSize !== norm) subTab1Content.view.bridge.maxFileSize = norm
                        }
                    }
                }
            }

            // Live interpreted range badge with fluid spring pop-in
            Rectangle {
                id: sizeRangeBadge
                property string minText: subTab1Content.view.bridge ? (subTab1Content.view.bridge.minFileSize || "").trim() : ""
                property string maxText: subTab1Content.view.bridge ? (subTab1Content.view.bridge.maxFileSize || "").trim() : ""
                readonly property bool isMinInvalid: minText.length > 0 && subTab1Content.view.parseBytes(minText) === 0
                readonly property bool isMaxInvalid: maxText.length > 0 && subTab1Content.view.parseBytes(maxText) === 0
                readonly property bool hasInvalid: isMinInvalid || isMaxInvalid
                readonly property bool isInverted: {
                    if (hasInvalid || !minText || !maxText) return false
                    var minB = subTab1Content.view.parseBytes(minText)
                    var maxB = subTab1Content.view.parseBytes(maxText)
                    return minB > 0 && maxB > 0 && minB > maxB
                }
                visible: minText.length > 0 || maxText.length > 0
                Layout.fillWidth: true
                implicitHeight: 24
                radius: 5
                color: (hasInvalid || isInverted) ? "#221C11" : "#0F172A"
                border.color: (hasInvalid || isInverted) ? "#F59E0B" : "#1E293B"
                border.width: 1

                scale: visible ? 1.0 : 0.8
                Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                function describeSizeRange() {
                    if (hasInvalid) {
                        var invalidVal = isMinInvalid ? minText : maxText
                        return subTab1Content.view.tr("notice_invalid_size", "⚠️ Invalid size format: \"") + invalidVal + subTab1Content.view.tr("notice_invalid_size_hint", "\" — use e.g. 500MB, 1.5GB")
                    }
                    var normMin = subTab1Content.view.normalizeSizeInput(minText)
                    var normMax = subTab1Content.view.normalizeSizeInput(maxText)
                    if (minText.length > 0 && maxText.length > 0) {
                        if (isInverted) {
                            return subTab1Content.view.tr("notice_inverted_size", "⚠️ Min exceeds Max — auto-correcting to: ") + normMax + " to " + normMin
                        }
                        return subTab1Content.view.tr("notice_range_size", "Filtering files between ") + normMin + " and " + normMax
                    } else if (minText.length > 0) {
                        return subTab1Content.view.tr("notice_min_size", "Filtering files at least ") + normMin + subTab1Content.view.tr("notice_min_size_end", " (skipping smaller files)")
                    } else if (maxText.length > 0) {
                        return subTab1Content.view.tr("notice_max_size", "Filtering files up to ") + normMax + subTab1Content.view.tr("notice_max_size_end", " (skipping larger files)")
                    }
                    return ""
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text {
                        text: (sizeRangeBadge.hasInvalid || sizeRangeBadge.isInverted) ? "⚠️" : "📦"
                        font.pixelSize: 10
                    }
                    Text {
                        text: sizeRangeBadge.describeSizeRange()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: (sizeRangeBadge.hasInvalid || sizeRangeBadge.isInverted) ? "#FCD34D" : "#38BDF8"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }

    // Card 1.4: Video Duration Filter (Length Filtering)
    CardSection {
        Layout.fillWidth: true
        title: subTab1Content.view.tr("card_duration_filtering", "Video Duration Filter")
        iconText: "⏱️"
        entranceOffsetY: subTab1Content.view.tabEntranceOffsetY * 1.75
        entranceOpacity: subTab1Content.view.tabEntranceOpacity

        ColumnLayout {
            width: parent.width
            spacing: 10

            // Header row: Switch + Title + Clear button
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: subTab1Content.view.tr("opt_video_duration_filter_title", "Filter Posts by Video Length")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#F1F5F9"
                    }

                    Text {
                        text: subTab1Content.view.tr("opt_video_duration_filter_desc", "Only download posts containing videos within a specific runtime window.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                // Clear duration range
                Text {
                    visible: subTab1Content.view.bridge && subTab1Content.view.bridge.videoDurationFilterEnabled && ((subTab1Content.view.bridge.minVideoDuration && subTab1Content.view.bridge.minVideoDuration.length > 0) || (subTab1Content.view.bridge.maxVideoDuration && subTab1Content.view.bridge.maxVideoDuration.length > 0))
                    text: subTab1Content.view.tr("btn_clear_duration_range", "Clear Range ✕")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.bold: true
                    color: durationClearMouse.containsMouse ? "#F87171" : "#94A3B8"
                    scale: durationClearMouse.pressed ? 0.92 : (durationClearMouse.containsMouse ? 1.06 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                    Behavior on color { ColorAnimation { duration: 140 } }

                    MouseArea {
                        id: durationClearMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (subTab1Content.view.bridge) {
                                subTab1Content.view.bridge.minVideoDuration = ""
                                subTab1Content.view.bridge.maxVideoDuration = ""
                            }
                        }
                    }
                }

                StyledSwitch {
                    checked: subTab1Content.view.bridge ? subTab1Content.view.bridge.videoDurationFilterEnabled : false
                    onToggled: function(isChecked) {
                        if (subTab1Content.view.bridge) subTab1Content.view.bridge.videoDurationFilterEnabled = isChecked
                    }
                }
            }

            // Expandable config area when switch is ON
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10
                visible: subTab1Content.view.bridge && subTab1Content.view.bridge.videoDurationFilterEnabled

                // Warning banner explaining probing overhead in short
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: durationWarningRow.implicitHeight + 16
                    radius: 6
                    color: "#181410"
                    border.color: "#B45309"
                    border.width: 1

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 3
                        radius: 1
                        color: "#F59E0B"
                    }

                    RowLayout {
                        id: durationWarningRow
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        spacing: 8

                        Text {
                            text: "⚠️"
                            font.pixelSize: 14
                            Layout.alignment: Qt.AlignVCenter
                        }

                        Text {
                            text: subTab1Content.view.tr("warn_duration_scanning_overhead", "Probing overhead: Direct video hosts do not store duration in their API metadata. Pawchive will inspect video headers via network requests during scanning, which may slightly increase scan time.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#FBBF24"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Min / Max input fields
                GridLayout {
                    columns: subTab1Content.view.width > 540 ? 2 : 1
                    Layout.fillWidth: true
                    rowSpacing: 6
                    columnSpacing: 12

                    // Min Video Duration
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        Text {
                            text: subTab1Content.view.tr("label_duration_min", "Min:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                        }

                        StyledTextField {
                            id: minDurationInput
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            placeholderText: subTab1Content.view.tr("ph_duration_min", "e.g. 0:30 or 1m")
                            tooltip: subTab1Content.view.tr("tip_duration_min", "Minimum video runtime. Videos shorter than this will be skipped.")
                            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.minVideoDuration : ""
                            onTextChanged: {
                                if (subTab1Content.view.bridge && subTab1Content.view.bridge.minVideoDuration !== text) {
                                    subTab1Content.view.bridge.minVideoDuration = text
                                }
                            }
                        }
                    }

                    // Max Video Duration
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        Text {
                            text: subTab1Content.view.tr("label_duration_max", "Max:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#64748B"
                        }

                        StyledTextField {
                            id: maxDurationInput
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            placeholderText: subTab1Content.view.tr("ph_duration_max", "e.g. 10:00 or 15m")
                            tooltip: subTab1Content.view.tr("tip_duration_max", "Maximum video runtime. Videos longer than this will be skipped.")
                            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.maxVideoDuration : ""
                            onTextChanged: {
                                if (subTab1Content.view.bridge && subTab1Content.view.bridge.maxVideoDuration !== text) {
                                    subTab1Content.view.bridge.maxVideoDuration = text
                                }
                            }
                        }
                    }
                }

                // Quick Presets Row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: subTab1Content.view.tr("label_presets", "Quick Presets:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    Repeater {
                        model: [
                            { l: "< 1 min (Clips)", min: "", max: "1:00" },
                            { l: "1 – 5 min", min: "1:00", max: "5:00" },
                            { l: "5 – 15 min", min: "5:00", max: "15:00" },
                            { l: "> 15 min (Full)", min: "15:00", max: "" }
                        ]

                        Rectangle {
                            implicitWidth: durPresetText.implicitWidth + 14
                            implicitHeight: 22
                            radius: 11
                            color: durPresetMouse.containsMouse ? "#1E293B" : "#0F172A"
                            border.color: (subTab1Content.view.bridge && subTab1Content.view.bridge.minVideoDuration === modelData.min && subTab1Content.view.bridge.maxVideoDuration === modelData.max) ? "#38BDF8" : "#334155"
                            border.width: 1

                            Text {
                                id: durPresetText
                                anchors.centerIn: parent
                                text: modelData.l
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.bold: (subTab1Content.view.bridge && subTab1Content.view.bridge.minVideoDuration === modelData.min && subTab1Content.view.bridge.maxVideoDuration === modelData.max)
                                color: (subTab1Content.view.bridge && subTab1Content.view.bridge.minVideoDuration === modelData.min && subTab1Content.view.bridge.maxVideoDuration === modelData.max) ? "#38BDF8" : "#94A3B8"
                            }

                            MouseArea {
                                id: durPresetMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (subTab1Content.view.bridge) {
                                        subTab1Content.view.bridge.minVideoDuration = modelData.min
                                        subTab1Content.view.bridge.maxVideoDuration = modelData.max
                                    }
                                }
                            }
                        }
                    }
                }

                // Live summary badge
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 24
                    radius: 5
                    color: "#0F172A"
                    border.color: "#1E293B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 6

                        Text {
                            text: "⏱️"
                            font.pixelSize: 10
                        }
                        Text {
                            text: subTab1Content.view.tr("lbl_active_duration_filter", "Duration filter: ") + (subTab1Content.view.bridge ? subTab1Content.view.bridge.videoDurationSummary : "Off")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#38BDF8"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
