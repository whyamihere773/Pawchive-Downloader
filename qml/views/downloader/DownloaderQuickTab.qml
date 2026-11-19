import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab0Content
    required property var view
    readonly property alias fallbackThumbTarget: fallbackThumbHighlightContainer
    visible: subTab0Content.view.currentSubTab === 0
    Layout.fillWidth: true
    spacing: 12

    // Card 0.1: Media Categories & Core Formats
    CardSection {
        Layout.fillWidth: true
        title: subTab0Content.view.tr("section_file_types", "Filter Files & Content Mode")
        iconText: "🗂️"
        entranceOffsetY: subTab0Content.view.tabEntranceOffsetY
        entranceOpacity: subTab0Content.view.tabEntranceOpacity

        ColumnLayout {
            width: parent.width
            spacing: 10

            // Media type filter pills (Single-select category)
            Flow {
                width: parent.width
                Layout.fillWidth: true
                spacing: 6

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_all_files", "All Files")
                    iconText: "📁"
                    tooltip: subTab0Content.view.tr("filter_all_files_tip", "Download all attachments and media files")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "all" : true
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "all"
                }

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_images", "Images/GIFs")
                    iconText: "🖼️"
                    tooltip: subTab0Content.view.tr("filter_images_tip", "Download image formats (PNG, JPG, GIF, WebP, BMP)")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "images" : false
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "images"
                }

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_videos", "Videos")
                    iconText: "🎬"
                    tooltip: subTab0Content.view.tr("filter_videos_tip", "Download video formats (MP4, MKV, WebM, MOV, M4V)")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "videos" : false
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "videos"
                }

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_archives", "Archives")
                    iconText: "📦"
                    tooltip: subTab0Content.view.tr("filter_archives_tip", "Download compressed archive packages (ZIP, RAR, 7Z, TAR)")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "archives" : false
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "archives"
                }

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_audio", "Audio")
                    iconText: "🎵"
                    tooltip: subTab0Content.view.tr("filter_audio_tip", "Download audio formats (MP3, FLAC, WAV, M4A, OGG)")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "audio" : false
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "audio"
                }

                FilterCheckbox {
                    label: subTab0Content.view.tr("filter_links_only", "Links Only")
                    iconText: "🔗"
                    tooltip: subTab0Content.view.tr("filter_links_only_tip", "Scan post descriptions & comments for external cloud links (Mega.nz, Google Drive, Dropbox, Pixeldrain, etc.) — no media files are downloaded. Use 'Export Links' in Queue tab to save results.")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.filterType === "links" : false
                    onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.filterType = "links"
                }
            }

            // Divider
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E293B"
            }

            // Exact File Extensions Section
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                // Header with Title, Hint, and Clear Button
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: subTab0Content.view.tr("label_exact_extensions", "Exact File Extensions")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#E2E8F0"
                    }

                    Text {
                        text: subTab0Content.view.tr("hint_exact_extensions", "Only download files matching selected or entered extensions (e.g. .zip, .png, .psd)")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    // Clear Extensions Button with Newtonian fluid hover
                    Text {
                        visible: subTab0Content.view.bridge && subTab0Content.view.bridge.exactExtensions.length > 0
                        text: subTab0Content.view.tr("btn_clear_extensions", "Clear All ✕")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.bold: true
                        color: extClearMouse0.containsMouse ? "#F87171" : "#94A3B8"
                        scale: extClearMouse0.pressed ? 0.92 : (extClearMouse0.containsMouse ? 1.06 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }
                        Behavior on color { ColorAnimation { duration: 140 } }

                        MouseArea {
                            id: extClearMouse0
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (subTab0Content.view.bridge) {
                                    subTab0Content.view.bridge.clearExactExtensions()
                                }
                            }
                        }
                    }
                }

                // ── 1. ACTIVE EXTENSIONS DISPLAY BANNER ──
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: activeContentCol0.implicitHeight + 16
                    radius: 8
                    color: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0) ? "#0B1120" : "#0F172A"
                    border.color: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0) ? "#3B82F6" : "#1E293B"
                    border.width: 1

                    Behavior on color { ColorAnimation { duration: 180 } }
                    Behavior on border.color { ColorAnimation { duration: 180 } }

                    ColumnLayout {
                        id: activeContentCol0
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                implicitWidth: 8
                                implicitHeight: 8
                                radius: 4
                                color: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0) ? "#38BDF8" : "#10B981"
                            }

                            Text {
                                text: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0)
                                    ? (subTab0Content.view.tr("label_active_extensions", "Active Extensions:") + " (" + subTab0Content.view.bridge.activeExtensionsList.length + ")")
                                    : subTab0Content.view.tr("msg_all_extensions_allowed", "All file extensions allowed (no filter active)")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0)
                                color: (subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0) ? "#93C5FD" : "#64748B"
                                Layout.fillWidth: true
                            }
                        }

                        // Interactive Active Chips
                        Flow {
                            visible: subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0
                            Layout.fillWidth: true
                            spacing: 6

                            Repeater {
                                model: subTab0Content.view.bridge ? subTab0Content.view.bridge.activeExtensionsList : []

                                Item {
                                    id: activeChipItem0
                                    required property string modelData
                                    implicitHeight: 26
                                    implicitWidth: activeChipRow0.implicitWidth + 14

                                    scale: activeChipMouse0.pressed ? 0.92 : (activeChipMouse0.containsMouse ? 1.05 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.35; mass: 0.7; epsilon: 0.005 } }

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 6
                                        color: activeChipMouse0.containsMouse ? "#1E293B" : "#172033"
                                        border.color: activeChipMouse0.containsMouse ? "#F87171" : "#60A5FA"
                                        border.width: 1

                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                        RowLayout {
                                            id: activeChipRow0
                                            anchors.centerIn: parent
                                            spacing: 5

                                            Text {
                                                text: activeChipItem0.modelData
                                                font.family: "Segoe UI, sans-serif"
                                                font.pixelSize: 11
                                                font.bold: true
                                                color: "#E0F2FE"
                                            }

                                            Text {
                                                text: "✕"
                                                font.pixelSize: 10
                                                font.bold: true
                                                color: activeChipMouse0.containsMouse ? "#F87171" : "#93C5FD"
                                            }
                                        }

                                        MouseArea {
                                            id: activeChipMouse0
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(activeChipItem0.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── 2. QUICK-PICK STANDARD EXTENSIONS FLOW ──
                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    spacing: 6

                    // Archive types
                    FilterCheckbox {
                        label: ".zip"
                        activeColor: "#F59E0B"
                        tooltip: "Only download ZIP archives (.zip)"
                        checked: subTab0Content.view.isExtActive(".zip")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".zip")
                    }
                    FilterCheckbox {
                        label: ".rar"
                        activeColor: "#F59E0B"
                        tooltip: "Only download RAR archives (.rar)"
                        checked: subTab0Content.view.isExtActive(".rar")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".rar")
                    }
                    FilterCheckbox {
                        label: ".7z"
                        activeColor: "#F59E0B"
                        tooltip: "Only download 7-Zip archives (.7z)"
                        checked: subTab0Content.view.isExtActive(".7z")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".7z")
                    }

                    // Image / Art types
                    FilterCheckbox {
                        label: ".png"
                        activeColor: "#38BDF8"
                        tooltip: "Only download PNG lossless images (.png)"
                        checked: subTab0Content.view.isExtActive(".png")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".png")
                    }
                    FilterCheckbox {
                        label: ".jpg"
                        activeColor: "#38BDF8"
                        tooltip: "Only download JPG / JPEG images (.jpg, .jpeg)"
                        checked: subTab0Content.view.isExtActive(".jpg")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".jpg")
                    }
                    FilterCheckbox {
                        label: ".gif"
                        activeColor: "#38BDF8"
                        tooltip: "Only download animated GIF images (.gif)"
                        checked: subTab0Content.view.isExtActive(".gif")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".gif")
                    }
                    FilterCheckbox {
                        label: ".webp"
                        activeColor: "#38BDF8"
                        tooltip: "Only download WebP images (.webp)"
                        checked: subTab0Content.view.isExtActive(".webp")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".webp")
                    }
                    FilterCheckbox {
                        label: ".psd"
                        activeColor: "#EC4899"
                        tooltip: "Only download Photoshop PSD project files (.psd)"
                        checked: subTab0Content.view.isExtActive(".psd")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".psd")
                    }
                    FilterCheckbox {
                        label: ".clip"
                        activeColor: "#EC4899"
                        tooltip: "Only download Clip Studio Paint CLIP files (.clip)"
                        checked: subTab0Content.view.isExtActive(".clip")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".clip")
                    }

                    // Video types
                    FilterCheckbox {
                        label: ".mp4"
                        activeColor: "#818CF8"
                        tooltip: "Only download MP4 videos (.mp4)"
                        checked: subTab0Content.view.isExtActive(".mp4")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".mp4")
                    }
                    FilterCheckbox {
                        label: ".mkv"
                        activeColor: "#818CF8"
                        tooltip: "Only download Matroska MKV videos (.mkv)"
                        checked: subTab0Content.view.isExtActive(".mkv")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".mkv")
                    }
                    FilterCheckbox {
                        label: ".webm"
                        activeColor: "#818CF8"
                        tooltip: "Only download WebM videos (.webm)"
                        checked: subTab0Content.view.isExtActive(".webm")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".webm")
                    }

                    // Audio types
                    FilterCheckbox {
                        label: ".mp3"
                        activeColor: "#10B981"
                        tooltip: "Only download MP3 audio (.mp3)"
                        checked: subTab0Content.view.isExtActive(".mp3")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".mp3")
                    }
                    FilterCheckbox {
                        label: ".flac"
                        activeColor: "#10B981"
                        tooltip: "Only download FLAC lossless audio (.flac)"
                        checked: subTab0Content.view.isExtActive(".flac")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".flac")
                    }

                    // Document types
                    FilterCheckbox {
                        label: ".pdf"
                        activeColor: "#F87171"
                        tooltip: "Only download PDF documents (.pdf)"
                        checked: subTab0Content.view.isExtActive(".pdf")
                        onClicked: if (subTab0Content.view.bridge) subTab0Content.view.bridge.toggleExactExtension(".pdf")
                    }
                }

                // ── 3. SAVED CUSTOM EXTENSIONS SECTION ──
                ColumnLayout {
                    visible: subTab0Content.view.bridge && subTab0Content.view.bridge.savedCustomExtensions.length > 0
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: subTab0Content.view.tr("label_saved_custom_extensions", "Custom Extensions:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.bold: true
                        color: "#A5B4FC"
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 6

                        Repeater {
                            model: subTab0Content.view.bridge ? subTab0Content.view.bridge.savedCustomExtensions : []

                            Item {
                                id: savedPillRoot0
                                required property string modelData
                                readonly property bool isChecked: subTab0Content.view.isExtActive(modelData)
                                implicitHeight: 28
                                implicitWidth: savedPillRow0.implicitWidth + 14

                                scale: savedPillMouse0.pressed ? 0.93 : (savedPillMouse0.containsMouse ? 1.04 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.01 } }

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 6
                                    color: savedPillRoot0.isChecked ? "#312E81" : (savedPillMouse0.containsMouse ? "#222733" : "#181B24")
                                    border.color: savedPillRoot0.isChecked ? "#818CF8" : (savedPillMouse0.containsMouse ? "#475569" : "#2E3544")
                                    border.width: savedPillRoot0.isChecked ? 1.5 : 1
                                    Behavior on color { ColorAnimation { duration: 160 } }
                                    Behavior on border.color { ColorAnimation { duration: 160 } }

                                    RowLayout {
                                        id: savedPillRow0
                                        anchors.centerIn: parent
                                        spacing: 6

                                        Text {
                                            text: "✨"
                                            font.pixelSize: 10
                                        }

                                        Text {
                                            text: savedPillRoot0.modelData
                                            font.family: "Segoe UI, Inter, sans-serif"
                                            font.pixelSize: 11
                                            font.weight: savedPillRoot0.isChecked ? Font.Bold : Font.Medium
                                            color: savedPillRoot0.isChecked ? "#EEF2FF" : "#94A3B8"
                                        }

                                        // Remove from saved (✕)
                                        Rectangle {
                                            implicitWidth: 16
                                            implicitHeight: 16
                                            radius: 8
                                            color: removeSavedMouse0.containsMouse ? "#EF4444" : "transparent"
                                            Behavior on color { ColorAnimation { duration: 120 } }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "✕"
                                                font.pixelSize: 9
                                                color: removeSavedMouse0.containsMouse ? "#FFFFFF" : "#64748B"
                                            }

                                            MouseArea {
                                                id: removeSavedMouse0
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    if (subTab0Content.view.bridge) {
                                                        subTab0Content.view.bridge.removeSavedCustomExtension(savedPillRoot0.modelData)
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    MouseArea {
                                        id: savedPillMouse0
                                        anchors.fill: parent
                                        anchors.rightMargin: 20
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (subTab0Content.view.bridge) {
                                                subTab0Content.view.bridge.toggleExactExtension(savedPillRoot0.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ── 4. ADD / SAVE CUSTOM EXTENSION INPUT ROW ──
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    StyledTextField {
                        id: exactExtInputTab0
                        Layout.fillWidth: true
                        placeholderText: subTab0Content.view.tr("ph_save_custom_ext", "Add custom extension (e.g. .blend, .fbx, .cbr)")
                        tooltip: subTab0Content.view.tr("hint_exact_extensions", "Only download files matching selected or entered extensions (e.g. .zip, .png, .psd)")
                        onAccepted: {
                            if (text.trim().length > 0 && subTab0Content.view.bridge) {
                                subTab0Content.view.bridge.addSavedCustomExtension(text.trim())
                                text = ""
                            }
                        }
                    }

                    StyledButton {
                        text: subTab0Content.view.tr("btn_save_extension", "+ Save")
                        variant: "primary"
                        tooltip: "Save extension to your permanent custom extensions and activate it"
                        onClicked: {
                            if (exactExtInputTab0.text.trim().length > 0 && subTab0Content.view.bridge) {
                                subTab0Content.view.bridge.addSavedCustomExtension(exactExtInputTab0.text.trim())
                                exactExtInputTab0.text = ""
                            }
                        }
                    }

                    // Active Filter badge indicator with Newtonian fluid pop
                    Rectangle {
                        visible: subTab0Content.view.bridge && subTab0Content.view.bridge.activeExtensionsList.length > 0
                        implicitHeight: 34
                        implicitWidth: activeExtLabel0.implicitWidth + 20
                        radius: 8
                        color: "#1E1B4B"
                        border.color: "#6366F1"
                        border.width: 1

                        scale: visible ? 1.0 : 0.8
                        opacity: visible ? 1.0 : 0.0
                        Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.7; epsilon: 0.005 } }
                        Behavior on opacity { NumberAnimation { duration: 180 } }

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                id: activeExtLabel0
                                text: (subTab0Content.view.bridge ? subTab0Content.view.bridge.activeExtensionsList.length : 0) + " " + subTab0Content.view.tr("badge_exact_extensions", "Active")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.bold: true
                                color: "#A5B4FC"
                            }
                        }
                    }
                }
            }

            // Key Format Modifiers
            Flow {
                width: parent.width
                Layout.fillWidth: true
                spacing: 12

                FilterCheckbox {
                    label: subTab0Content.view.tr("opt_favorite_mode", "Favorite Mode")
                    iconText: "⭐"
                    activeColor: "#FBBF24"
                    tooltip: subTab0Content.view.tr("opt_favorite_mode_tip", "Download and incrementally sync followed creators from your account")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.favoriteMode : false
                    onClicked: {
                        if (subTab0Content.view.bridge) {
                            subTab0Content.view.bridge.favoriteMode = !subTab0Content.view.bridge.favoriteMode
                        }
                    }
                }

                StyledCheckBox {
                    text: subTab0Content.view.tr("opt_skip_archives", "Skip Archives")
                    tooltip: subTab0Content.view.tr("opt_skip_archives_tip", "Skip all archive files (.zip, .rar, .7z) regardless of active category")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.skipArchives : false
                    onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.skipArchives = checked
                }

                Row {
                    spacing: 8

                    StyledCheckBox {
                        id: webpCheck
                        text: subTab0Content.view.tr("opt_compress_webp", "Compress to WebP")
                        tooltip: subTab0Content.view.tr("opt_compress_webp_tip", "Convert downloaded PNG and JPG images to compressed WebP format")
                        checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.compressWebp : false
                        onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.compressWebp = checked
                    }

                    // How strongly (only while compressing)
                    StyledComboBox {
                        visible: webpCheck.checked
                        implicitHeight: 26
                        implicitWidth: 120
                        anchors.verticalCenter: webpCheck.verticalCenter
                        model: [
                                { text: subTab0Content.view.tr("webp_q_lossless", "Lossless"), value: "lossless" },
                                { text: subTab0Content.view.tr("webp_q_high", "High"), value: "high" },
                                { text: subTab0Content.view.tr("webp_q_balanced", "Balanced"), value: "balanced" },
                                { text: subTab0Content.view.tr("webp_q_small", "Small"), value: "small" },
                                { text: subTab0Content.view.tr("webp_q_smallest", "Smallest"), value: "smallest" }
                            ]
                        value: subTab0Content.view.bridge ? subTab0Content.view.bridge.webpQuality : "balanced"
                        tooltip: subTab0Content.view.tr("webp_quality_tip", "How strongly pictures are compressed. Lossless keeps every pixel; Balanced is barely visible and much smaller; Small and Smallest save the most space. A picture is kept as it was if the WebP wouldn't be smaller.")
                        onValuePicked: function(v) { if (subTab0Content.view.bridge) subTab0Content.view.bridge.webpQuality = v }
                    }
                }
            }
        }
    }

    // Card 0.2: Quality & Thumbnails
    CardSection {
        Layout.fillWidth: true
        title: subTab0Content.view.tr("card_quality_thumbnails", "Download Quality & Thumbnails")
        iconText: "💎"
        entranceOffsetY: subTab0Content.view.tabEntranceOffsetY * 1.25
        entranceOpacity: subTab0Content.view.tabEntranceOpacity

        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 14

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_thumbnails_only", "Download thumbnails only")
                tooltip: subTab0Content.view.tr("opt_thumbnails_only_tip", "Download lightweight preview thumbnails instead of full original files")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.downloadThumbnailsOnly : false
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.downloadThumbnailsOnly = checked
            }

            Item {
                id: fallbackThumbHighlightContainer
                objectName: "fallbackThumbHighlightContainer"
                implicitWidth: fallbackThumbCheck.implicitWidth
                implicitHeight: fallbackThumbCheck.implicitHeight
                z: subTab0Content.view.fallbackThumbGlowAlpha > 0.01 ? 10 : 0

                // Outer soft luminous halo
                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: -10
                    anchors.rightMargin: -10
                    anchors.topMargin: -7
                    anchors.bottomMargin: -7
                    radius: 10
                    visible: subTab0Content.view.fallbackThumbGlowAlpha > 0.01
                    color: Qt.rgba(56 / 255, 189 / 255, 248 / 255, 0.16 * subTab0Content.view.fallbackThumbGlowAlpha)
                    border.color: Qt.rgba(56 / 255, 189 / 255, 248 / 255, 0.42 * subTab0Content.view.fallbackThumbGlowAlpha)
                    border.width: 2
                }

                // Inner crisp glow highlight
                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: -6
                    anchors.rightMargin: -6
                    anchors.topMargin: -4
                    anchors.bottomMargin: -4
                    radius: 7
                    visible: subTab0Content.view.fallbackThumbGlowAlpha > 0.01
                    color: Qt.rgba(56 / 255, 189 / 255, 248 / 255, 0.22 * subTab0Content.view.fallbackThumbGlowAlpha)
                    border.color: Qt.rgba(125 / 255, 211 / 255, 252 / 255, 0.95 * subTab0Content.view.fallbackThumbGlowAlpha)
                    border.width: 1.5
                }

                StyledCheckBox {
                    id: fallbackThumbCheck
                    objectName: "fallbackToThumbnailsCheck"
                    anchors.fill: parent
                    text: subTab0Content.view.tr("opt_fallback_to_thumbnails", "Fallback to thumbnails if full-size missing")
                    tooltip: subTab0Content.view.tr("opt_fallback_to_thumbnails_tip", "If the original full-resolution file is missing on the server (404), allow downloading the preview thumbnail instead")
                    checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.fallbackToThumbnails : false
                    onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.fallbackToThumbnails = checked
                }
            }

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_redownload_small_files", "Re-download small / thumbnail files")
                tooltip: subTab0Content.view.tr("opt_redownload_small_files_tip", "Re-download existing files that appear to be low-quality thumbnails to upgrade them to full resolution")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.redownloadSmallFiles : false
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.redownloadSmallFiles = checked
            }

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_skip_post_covers", "Skip Post Cover Images")
                tooltip: subTab0Content.view.tr("opt_skip_post_covers_tip", "Do not download the post's featured cover/thumbnail image when attachments or content are present")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.skipPostCovers : false
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.skipPostCovers = checked
            }
        }
    }

    // Card 0.3: Post Content & Media Extraction
    CardSection {
        Layout.fillWidth: true
        title: subTab0Content.view.tr("card_content_extraction", "Content Scanning & Embedded Media")
        iconText: "🔍"
        entranceOffsetY: subTab0Content.view.tabEntranceOffsetY * 1.5
        entranceOpacity: subTab0Content.view.tabEntranceOpacity

        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 14

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_scan_content_images", "Scan content for images")
                tooltip: subTab0Content.view.tr("opt_scan_content_images_tip", "Scan HTML post descriptions for embedded inline artwork")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.scanContentImages : true
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.scanContentImages = checked
            }

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_download_dms", "Download Direct Messages (DMs)")
                tooltip: subTab0Content.view.tr("opt_download_dms_tip", "Fetch and download creator direct messages alongside posts (cum.st / Pawchive)")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.downloadDms : false
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.downloadDms = checked
            }

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_download_embeds", "Download Embedded Media (yt-dlp)")
                tooltip: subTab0Content.view.tr("opt_download_embeds_tip", "Download embedded video players (Vimeo, YouTube, Streamable, RedGifs, etc.) via standalone yt-dlp")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.downloadEmbeds : true
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.downloadEmbeds = checked
            }

            StyledCheckBox {
                text: subTab0Content.view.tr("opt_tag_audio_files", "Tag Audio Metadata (Artist/Title)")
                tooltip: subTab0Content.view.tr("opt_tag_audio_files_tip", "Embed creator name into Artist tag and post title into Title tag for MP3, FLAC, M4A, and audio files")
                checked: subTab0Content.view.bridge ? subTab0Content.view.bridge.writeAudioMetadata : false
                onCheckedChanged: if (subTab0Content.view.bridge) subTab0Content.view.bridge.writeAudioMetadata = checked
            }
        }
    }
}
