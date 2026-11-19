import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: keywordsCard
    required property var view
    Layout.fillWidth: true
    title: keywordsCard.view.tr("section_filters", "Filters & Keyword Rules")
    iconText: "🎯"
    entranceOffsetY: keywordsCard.view.tabEntranceOffsetY
    entranceOpacity: keywordsCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        spacing: 10

        // Filter by Characters
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 4
                Text {
                    text: keywordsCard.view.tr("label_filter_characters", "Filter by Character(s) (comma-separated):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
                StyledTextField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    placeholderText: keywordsCard.view.tr("placeholder_characters", "e.g., Tifa, Aerith, (Cloud, Zack)")
                    text: keywordsCard.view.bridge ? keywordsCard.view.bridge.filterCharacters : ""
                    onTextChanged: {
                        if (keywordsCard.view.bridge && keywordsCard.view.bridge.filterCharacters !== text) {
                            keywordsCard.view.bridge.filterCharacters = text
                        }
                    }
                }
            }

            // Scope selector
            ColumnLayout {
                spacing: 4
                Text {
                    text: keywordsCard.view.tr("label_scope", "Scope:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
                StyledButton {
                    implicitWidth: Math.max(100, keywordsCard.view.widestLabel([
                        keywordsCard.view.tr("scope_filter_title", "Filter: Title"),
                        keywordsCard.view.tr("scope_filter_content", "Filter: Content"),
                        keywordsCard.view.tr("scope_filter_both", "Filter: Both")]) + 24)
                    text: {
                        if (!keywordsCard.view.bridge) return keywordsCard.view.tr("scope_filter_title", "Filter: Title")
                        var s = keywordsCard.view.bridge.characterScope
                        if (s === "content") return keywordsCard.view.tr("scope_filter_content", "Filter: Content")
                        if (s === "both") return keywordsCard.view.tr("scope_filter_both", "Filter: Both")
                        return keywordsCard.view.tr("scope_filter_title", "Filter: Title")
                    }
                    variant: "outline"
                    tooltip: keywordsCard.view.tr("tooltip_scope_character", "Switch character filtering scope (Title, Content, or Both)")
                    onClicked: {
                        if (!keywordsCard.view.bridge) return
                        if (keywordsCard.view.bridge.characterScope === "title") keywordsCard.view.bridge.characterScope = "content"
                        else if (keywordsCard.view.bridge.characterScope === "content") keywordsCard.view.bridge.characterScope = "both"
                        else keywordsCard.view.bridge.characterScope = "title"
                    }
                }
            }
        }

        // Skip words & Remove words grid
        GridLayout {
            columns: keywordsCard.view.width > 540 ? 2 : 1
            Layout.fillWidth: true
            rowSpacing: 10
            columnSpacing: 12

            // Skip words
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 6

                // Header row: Label + Preset Dropdown
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: keywordsCard.view.tr("label_skip_words", "🚫 Skip with words (comma-separated):")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    StyledComboBox {
                        id: filterProfileCombo
                        implicitHeight: 24
                        implicitWidth: 160
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                        model: [
                            { text: keywordsCard.view.tr("profile_none", "Preset: None"), value: "clear" },
                            { text: keywordsCard.view.tr("profile_wip_sketches", "✏️ WIP & Sketches"), value: "wip_sketches" },
                            { text: keywordsCard.view.tr("profile_low_quality", "📉 Low Quality & Previews"), value: "low_quality" },
                            { text: keywordsCard.view.tr("profile_wip_and_low_quality", "🎨 WIP, Sketches & Low-Res"), value: "wip_and_low_quality" },
                            { text: keywordsCard.view.tr("profile_watermarks", "🏷️ Watermarks & Samples"), value: "watermarks_samples" },
                            { text: keywordsCard.view.tr("profile_final_art_only", "⭐ Final Art Only"), value: "final_art_only" },
                            { text: keywordsCard.view.tr("profile_large_media_only", "📦 Large Media Only"), value: "large_media_only" },
                            { text: keywordsCard.view.tr("profile_custom", "Preset: Custom / Manual"), value: "custom" }
                        ]
                        value: keywordsCard.view.bridge ? keywordsCard.view.bridge.filterProfile : "clear"
                        tooltip: keywordsCard.view.tr("tooltip_filter_profile", "Select a preset filter profile to automatically skip unwanted posts or files (e.g., drafts, low-resolution previews, or work-in-progress).")
                        onValuePicked: function(v) {
                            if (keywordsCard.view.bridge) keywordsCard.view.bridge.applyFilterProfile(v)
                        }
                    }
                }

                // Text Field + Scope Button
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    StyledTextField {
                        id: skipWordsField
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        placeholderText: keywordsCard.view.tr("placeholder_skip_words", "e.g., WIP, preview, [1GB-2GB]")
                        tooltip: keywordsCard.view.tr("tooltip_skip_words_size", "Skip specific words or filter by file size! Use [1GB-2GB], [>=1GB], [<500MB], or [1024-2048] (in MB)")
                        text: keywordsCard.view.bridge ? keywordsCard.view.bridge.skipWords : ""
                        onTextChanged: {
                            if (keywordsCard.view.bridge && keywordsCard.view.bridge.skipWords !== text) {
                                keywordsCard.view.bridge.skipWords = text
                            }
                        }
                    }

                    StyledButton {
                        implicitWidth: Math.max(100, keywordsCard.view.widestLabel([
                            keywordsCard.view.tr("scope_skip_posts", "Scope: Posts"),
                            keywordsCard.view.tr("scope_skip_files", "Scope: Files")]) + 24)
                        text: {
                            if (!keywordsCard.view.bridge) return keywordsCard.view.tr("scope_skip_posts", "Scope: Posts")
                            return (keywordsCard.view.bridge.skipScope === "files")
                                ? keywordsCard.view.tr("scope_skip_files", "Scope: Files")
                                : keywordsCard.view.tr("scope_skip_posts", "Scope: Posts")
                        }
                        variant: "outline"
                        tooltip: keywordsCard.view.tr("tooltip_skip_scope", "Switch skip filter scope between Post Titles and Filenames")
                        onClicked: {
                            if (!keywordsCard.view.bridge) return
                            keywordsCard.view.bridge.skipScope = (keywordsCard.view.bridge.skipScope === "posts") ? "files" : "posts"
                        }
                    }
                }

                // Quick add chips flow
                Flow {
                    Layout.fillWidth: true
                    spacing: 5

                    Text {
                        text: keywordsCard.view.tr("label_quick_add", "Quick add:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        height: 20
                        verticalAlignment: Text.AlignVCenter
                    }

                    Repeater {
                        model: [
                            { label: "+ WIP", tag: "WIP" },
                            { label: "+ Sketch", tag: "sketch" },
                            { label: "+ Draft", tag: "draft" },
                            { label: "+ Preview", tag: "preview" },
                            { label: "+ Low-Res [>=500KB]", tag: "lowres, [>=500KB]" },
                            { label: "+ Watermark", tag: "watermark" }
                        ]

                        delegate: Rectangle {
                            implicitHeight: 20
                            implicitWidth: chipText.implicitWidth + 14
                            radius: 4
                            color: chipMouse.pressed ? "#0F172A" : (chipMouse.containsMouse ? "#1E293B" : "#141923")
                            border.color: chipMouse.containsMouse ? "#38BDF8" : "#283042"
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 100 } }
                            Behavior on border.color { ColorAnimation { duration: 100 } }

                            Text {
                                id: chipText
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                color: chipMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (keywordsCard.view.bridge) keywordsCard.view.bridge.appendKeywordsToSkip(modelData.tag)
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: keywordsCard.view.bridge && keywordsCard.view.bridge.skipWords.length > 0
                        implicitHeight: 20
                        implicitWidth: clearChipText.implicitWidth + 12
                        radius: 4
                        color: clearChipMouse.pressed ? "#450A0A" : (clearChipMouse.containsMouse ? "#2A1215" : "#181316")
                        border.color: clearChipMouse.containsMouse ? "#EF4444" : "#4A2024"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            id: clearChipText
                            anchors.centerIn: parent
                            text: keywordsCard.view.tr("chip_clear", "Clear ✕")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: clearChipMouse.containsMouse ? "#F87171" : "#A85353"
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        MouseArea {
                            id: clearChipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (keywordsCard.view.bridge) keywordsCard.view.bridge.applyFilterProfile("clear")
                            }
                        }
                    }
                }
            }

            // Remove words
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 6

                // Header row: Label + Preset Dropdown
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: keywordsCard.view.tr("label_remove_words", "✂️ Remove words from name:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    StyledComboBox {
                        id: removeProfileCombo
                        implicitHeight: 24
                        implicitWidth: 160
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                        model: [
                            { text: keywordsCard.view.tr("profile_none", "Preset: None"), value: "clear" },
                            { text: keywordsCard.view.tr("profile_clean_names", "✨ Clean Names"), value: "clean_names" },
                            { text: keywordsCard.view.tr("profile_patreon_promo", "✂️ Patreon & Promo"), value: "patreon_promo" },
                            { text: keywordsCard.view.tr("profile_watermarks", "🏷️ Watermark Tags"), value: "watermark_tags" },
                            { text: keywordsCard.view.tr("profile_custom", "Preset: Custom / Manual"), value: "custom" }
                        ]
                        value: keywordsCard.view.bridge ? keywordsCard.view.bridge.removeWordsProfile : "clear"
                        tooltip: keywordsCard.view.tr("tooltip_remove_words_profile", "Select a preset profile to strip unwanted platform tags and sample markers from saved filenames.")
                        onValuePicked: function(v) {
                            if (keywordsCard.view.bridge) keywordsCard.view.bridge.applyRemoveWordsProfile(v)
                        }
                    }
                }

                StyledTextField {
                    id: removeWordsField
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    placeholderText: keywordsCard.view.tr("placeholder_remove_words", "e.g., patreon, HD, [sample]")
                    text: keywordsCard.view.bridge ? keywordsCard.view.bridge.removeWords : ""
                    onTextChanged: {
                        if (keywordsCard.view.bridge && keywordsCard.view.bridge.removeWords !== text) {
                            keywordsCard.view.bridge.removeWords = text
                        }
                    }
                }

                // Quick add chips flow
                Flow {
                    Layout.fillWidth: true
                    spacing: 5

                    Text {
                        text: keywordsCard.view.tr("label_quick_add", "Quick add:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        height: 20
                        verticalAlignment: Text.AlignVCenter
                    }

                    Repeater {
                        model: [
                            { label: "+ patreon", tag: "patreon" },
                            { label: "+ fanbox", tag: "fanbox" },
                            { label: "+ HD", tag: "HD" },
                            { label: "+ [sample]", tag: "[sample]" },
                            { label: "+ preview", tag: "preview" }
                        ]

                        delegate: Rectangle {
                            implicitHeight: 20
                            implicitWidth: remChipText.implicitWidth + 14
                            radius: 4
                            color: remChipMouse.pressed ? "#0F172A" : (remChipMouse.containsMouse ? "#1E293B" : "#141923")
                            border.color: remChipMouse.containsMouse ? "#38BDF8" : "#283042"
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 100 } }
                            Behavior on border.color { ColorAnimation { duration: 100 } }

                            Text {
                                id: remChipText
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                color: remChipMouse.containsMouse ? "#38BDF8" : "#94A3B8"
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            MouseArea {
                                id: remChipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (keywordsCard.view.bridge) keywordsCard.view.bridge.appendKeywordsToRemove(modelData.tag)
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: keywordsCard.view.bridge && keywordsCard.view.bridge.removeWords.length > 0
                        implicitHeight: 20
                        implicitWidth: clearRemChipText.implicitWidth + 12
                        radius: 4
                        color: clearRemChipMouse.pressed ? "#450A0A" : (clearRemChipMouse.containsMouse ? "#2A1215" : "#181316")
                        border.color: clearRemChipMouse.containsMouse ? "#EF4444" : "#4A2024"
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 100 } }
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            id: clearRemChipText
                            anchors.centerIn: parent
                            text: keywordsCard.view.tr("chip_clear", "Clear ✕")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: clearRemChipMouse.containsMouse ? "#F87171" : "#A85353"
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        MouseArea {
                            id: clearRemChipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (keywordsCard.view.bridge) keywordsCard.view.bridge.applyRemoveWordsProfile("clear")
                            }
                        }
                    }
                }
            }
        }
    }
}
