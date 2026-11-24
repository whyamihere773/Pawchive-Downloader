import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab2Content
    required property var view
    visible: subTab2Content.view.currentSubTab === 2
    Layout.fillWidth: true
    spacing: 12

    // Card 2.1: Folder Organization & Naming
    CardSection {
        Layout.fillWidth: true
        title: subTab2Content.view.tr("card_folder_structure", "Folder Organization & Naming")
        iconText: "📁"
        entranceOffsetY: subTab2Content.view.tabEntranceOffsetY
        entranceOpacity: subTab2Content.view.tabEntranceOpacity

        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 14

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_subfolder_per_post", "Subfolder per post")
                tooltip: subTab2Content.view.tr("opt_subfolder_per_post_tip", "Organize downloads into subfolders named after each post")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.subfolderPerPost : true
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.subfolderPerPost = checked
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_site_in_folder_name", "Site in Folder Name")
                tooltip: subTab2Content.view.tr("opt_site_in_folder_name_tip", "Name creator folders \"Artist [onlyfans]\". Turn off for just \"Artist\". Folders made either way are still found.")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.siteInFolderName : true
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.siteInFolderName = checked
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_date_prefix", "Date Prefix")
                tooltip: subTab2Content.view.tr("opt_date_prefix_tip", "Prefix subfolder names with the post publication date [YYYY-MM-DD]")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.datePrefix : true
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.datePrefix = checked
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_file_index_prefix", "Index Prefix (001_...)")
                tooltip: subTab2Content.view.tr("opt_file_index_prefix_tip", "Prefix downloaded filenames with sequential index numbers (001_, 002_, ...) so they can be browsed in order without relying on time sorting")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.fileIndexPrefix : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.fileIndexPrefix = checked
            }

            // Which file of a post is #1 (index prefix, numbered names, download order)
            Row {
                spacing: 8
                height: 28

                Text {
                    text: subTab2Content.view.tr("opt_file_order", "File order in posts:")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    color: fileOrderCombo.value !== "posted" ? "#F1F5F9" : "#94A3B8"
                    anchors.verticalCenter: parent.verticalCenter
                }

                StyledComboBox {
                    id: fileOrderCombo
                    implicitHeight: 28
                    implicitWidth: 150
                    anchors.verticalCenter: parent.verticalCenter
                    model: [
                        { text: subTab2Content.view.tr("file_order_posted", "As posted"), value: "posted" },
                        { text: subTab2Content.view.tr("file_order_reversed", "Reversed"), value: "reversed" },
                        { text: subTab2Content.view.tr("file_order_name", "By file name"), value: "name" }
                    ]
                    value: subTab2Content.view.bridge ? subTab2Content.view.bridge.fileOrder : "posted"
                    tooltip: subTab2Content.view.tr("opt_file_order_tip", "Which file of a post comes first: it is downloaded first and gets #1 with the index prefix and numbered file names.\n\nAs posted: the order the site shows.\nReversed: for creators who upload the newest version first.\nBy file name: sorted by name with numbers counted properly (2 before 10), in any language.")
                    onValuePicked: function(v) { if (subTab2Content.view.bridge) subTab2Content.view.bridge.fileOrder = v }
                }
            }

            // Sort posts into Year / Month / Year -> Month folders inside each creator directory
            Row {
                spacing: 8
                height: 28

                Text {
                    text: subTab2Content.view.tr("opt_date_folder_mode", "Sort by Date Folder:")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: 12
                    color: dateFolderCombo.value !== "none" ? "#F1F5F9" : "#94A3B8"
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                StyledComboBox {
                    id: dateFolderCombo
                    objectName: "dateFolderModeCombo"
                    implicitHeight: 28
                    implicitWidth: 195
                    anchors.verticalCenter: parent.verticalCenter
                    model: [
                        { text: subTab2Content.view.tr("date_folder_none", "Off"), value: "none" },
                        { text: subTab2Content.view.tr("date_folder_year", "By Year (2025)"), value: "year" },
                        { text: subTab2Content.view.tr("date_folder_month", "By Month (2025-03)"), value: "month" },
                        { text: subTab2Content.view.tr("date_folder_year_month", "Year → Month (2025/03)"), value: "year_month" }
                    ]
                    value: subTab2Content.view.bridge ? subTab2Content.view.bridge.dateFolderMode : "none"
                    tooltip: subTab2Content.view.tr("opt_date_folder_mode_tip", "Organize a creator's posts into date folders based on publication date:\n• By Year: Creator/2025/...\n• By Month: Creator/2025-03/...\n• Year → Month: Creator/2025/03 - March/...\nPosts without a date go into Unknown Date.")
                    onValuePicked: function(v) { if (subTab2Content.view.bridge) subTab2Content.view.bridge.dateFolderMode = v }
                }

                Rectangle {
                    id: dateFolderPreviewPill
                    readonly property string curMode: dateFolderCombo.value || "none"
                    readonly property bool shown: curMode !== "none"
                    property real reveal: shown ? 1.0 : 0.0
                    Behavior on reveal { SpringAnimation { spring: 4.6; damping: 0.36; mass: 0.85; epsilon: 0.005 } }
                    visible: shown || reveal > 0.02
                    opacity: Math.max(0.0, Math.min(1.0, reveal))
                    scale: 0.86 + 0.14 * reveal
                    anchors.verticalCenter: parent.verticalCenter
                    implicitHeight: 22
                    implicitWidth: dateFolderPreviewRow.implicitWidth + 14
                    radius: 11
                    color: "#132238"
                    border.color: "#38BDF8"
                    border.width: 1

                    RowLayout {
                        id: dateFolderPreviewRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text { text: "📅"; font.pixelSize: 10 }
                        Text {
                            text: dateFolderPreviewPill.curMode === "year"
                                  ? "Creator/2025/…"
                                  : (dateFolderPreviewPill.curMode === "month"
                                     ? "Creator/2025-03/…"
                                     : "Creator/2025/03 - March/…")
                            font.family: "Cascadia Code, Consolas, monospace"
                            font.pixelSize: 10
                            color: "#7DD3FC"
                        }
                    }
                }
            }

            // Same switch as in the Quick tab (they stay in sync), with its quality level
            Row {
                spacing: 8
                height: 28

                StyledCheckBox {
                    id: webpCheckEngine
                    text: subTab2Content.view.tr("opt_compress_webp", "Compress to WebP")
                    tooltip: subTab2Content.view.tr("opt_compress_webp_tip", "Convert downloaded PNG and JPG images to compressed WebP format")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.compressWebp : false
                    onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.compressWebp = checked
                    anchors.verticalCenter: parent.verticalCenter
                }

                StyledComboBox {
                    visible: webpCheckEngine.checked
                    implicitHeight: 28
                    implicitWidth: 120
                    anchors.verticalCenter: parent.verticalCenter
                    model: [
                        { text: subTab2Content.view.tr("webp_q_lossless", "Lossless"), value: "lossless" },
                        { text: subTab2Content.view.tr("webp_q_high", "High"), value: "high" },
                        { text: subTab2Content.view.tr("webp_q_balanced", "Balanced"), value: "balanced" },
                        { text: subTab2Content.view.tr("webp_q_small", "Small"), value: "small" },
                        { text: subTab2Content.view.tr("webp_q_smallest", "Smallest"), value: "smallest" }
                    ]
                    value: subTab2Content.view.bridge ? subTab2Content.view.bridge.webpQuality : "balanced"
                    tooltip: subTab2Content.view.tr("webp_quality_tip", "How strongly pictures are compressed. Lossless keeps every pixel; Balanced is barely visible and much smaller; Small and Smallest save the most space. A picture is kept as it was if the WebP wouldn't be smaller.")
                    onValuePicked: function(v) { if (subTab2Content.view.bridge) subTab2Content.view.bridge.webpQuality = v }
                }
            }

            Row {
                spacing: 8

                StyledCheckBox {
                    id: groupTypeCheck
                    text: subTab2Content.view.tr("opt_group_file_type", "Group by File Type")
                    tooltip: subTab2Content.view.tr("opt_group_file_type_tip", "Organize attachments into /Images, /Video, /Archive, /Audio, /Other folders")
                    checked: subTab2Content.view.bridge ? (subTab2Content.view.bridge.groupFileType !== "none") : false
                    onCheckedChanged: {
                        if (subTab2Content.view.bridge) {
                            subTab2Content.view.bridge.groupFileType = checked ? (subTab2Content.view.bridge.groupFileType !== "none" ? subTab2Content.view.bridge.groupFileType : "post") : "none"
                        }
                    }
                }

                Rectangle {
                    id: groupScopePill
                    visible: groupTypeCheck.checked
                    y: Math.round((groupTypeCheck.height - height) / 2)
                    implicitHeight: 22
                    implicitWidth: groupScopeRow.implicitWidth + 14
                    radius: 11
                    color: groupScopeMouse.containsMouse ? "#2A364E" : "#1B2232"
                    border.color: groupScopeMouse.containsMouse ? "#38BDF8" : "#334155"
                    border.width: 1

                    scale: groupScopeMouse.pressed ? 0.94 : (groupScopeMouse.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.8; epsilon: 0.005 } }

                    RowLayout {
                        id: groupScopeRow
                        anchors.centerIn: parent
                        spacing: 4

                        Text {
                            text: subTab2Content.view.bridge && subTab2Content.view.bridge.groupFileType === "creator" ? "📁" : "📂"
                            font.pixelSize: 10
                        }

                        Text {
                            text: subTab2Content.view.bridge && subTab2Content.view.bridge.groupFileType === "creator"
                                  ? subTab2Content.view.tr("opt_group_scope_creator", "Creator Root")
                                  : subTab2Content.view.tr("opt_group_scope_post", "Inside Post")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: Font.Medium
                            color: "#38BDF8"
                        }
                    }

                    MouseArea {
                        id: groupScopeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (subTab2Content.view.bridge) {
                                subTab2Content.view.bridge.groupFileType = (subTab2Content.view.bridge.groupFileType === "creator" ? "post" : "creator")
                            }
                        }
                    }

                    ToolTip {
                        visible: groupScopeMouse.containsMouse
                        delay: 400
                        timeout: 5000
                        text: subTab2Content.view.bridge && subTab2Content.view.bridge.groupFileType === "creator"
                              ? subTab2Content.view.tr("tip_group_scope_creator", "Files grouped by type at creator level: Creator/Images/Post/... (click to switch)")
                              : subTab2Content.view.tr("tip_group_scope_post", "Files grouped inside post folders: Creator/Post/Images/... (click to switch)")
                    }
                }
            }

            Row {
                spacing: 6
                StyledCheckBox {
                    id: tagFolderCheck
                    text: subTab2Content.view.tr("opt_tag_folder_mode", "Sort by Tag Folder")
                    tooltip: subTab2Content.view.tr("opt_tag_folder_mode_tip", "(Pawchive & cum.st only) Groups downloaded files into subfolders named after the post's primary tag")
                    checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.tagFolderMode : false
                    onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.tagFolderMode = checked
                }

                Rectangle {
                    readonly property string curUrl: subTab2Content.view.bridge ? (subTab2Content.view.bridge.currentUrl || "").toLowerCase() : ""
                    readonly property bool isNonTagDomain: curUrl.length > 0 && curUrl.indexOf("pawchive.pw") === -1 && curUrl.indexOf("cum.st") === -1
                    visible: isNonTagDomain
                    y: Math.round((tagFolderCheck.height - height) / 2)
                    implicitHeight: 20
                    implicitWidth: tagWarnText.implicitWidth + 10
                    radius: 4
                    color: "#1E1B18"
                    border.color: "#854D0E"
                    border.width: 1

                    Text {
                        id: tagWarnText
                        anchors.centerIn: parent
                        text: "⚠ Pawchive/cum.st only"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#FBBF24"
                    }
                }
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_separate_known", "Separate folders by Known.txt")
                tooltip: subTab2Content.view.tr("opt_separate_known_tip", "Sort files into subfolders corresponding to matched characters/series from Known.txt")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.separateFoldersByKnown : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.separateFoldersByKnown = checked
                onToggled: {
                    if (checked) {
                        var isAiOn = subTab2Content.view.bridge && subTab2Content.view.bridge.aiRecognitionEnabled && (subTab2Content.view.bridge.aiFastSemanticReady || subTab2Content.view.bridge.aiDeepReasonerReady)
                        if (!isAiOn && typeof appWindow !== "undefined" && typeof appWindow.showToast === "function") {
                            appWindow.showToast(
                                "💡 " + subTab2Content.view.tr("toast_known_ai_hint", "Tip: Enable offline AI in Settings → AI to deduce obscure & misspelled characters! (Click to open)"),
                                function() {
                                    if (typeof appWindow.openSettingsTab === "function") {
                                        appWindow.openSettingsTab(3)
                                    }
                                }
                            )
                        } else if (isAiOn && typeof appWindow !== "undefined" && typeof appWindow.showToast === "function") {
                            appWindow.showToast("✨ " + subTab2Content.view.tr("toast_known_ai_active", "Folder separation active with Offline AI engine"))
                        }
                    }
                }
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_manga_mode", "Manga Mode (Oldest First)")
                tooltip: subTab2Content.view.tr("opt_manga_mode_tip", "Sort posts chronologically (oldest first) so chapters and pages download in reading order")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.mangaMode : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.mangaMode = checked
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_download_revisions", "Download Revisions")
                tooltip: subTab2Content.view.tr("opt_download_revisions_tip", "Download older superseded revisions of edited posts")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.downloadRevisions : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.downloadRevisions = checked
            }

            StyledCheckBox {
                text: subTab2Content.view.tr("opt_keep_duplicates", "Keep Duplicates")
                tooltip: subTab2Content.view.tr("opt_keep_duplicates_tip", "Re-download files even if identical files already exist in destination")
                checked: subTab2Content.view.bridge ? subTab2Content.view.bridge.keepDuplicates : false
                onCheckedChanged: if (subTab2Content.view.bridge) subTab2Content.view.bridge.keepDuplicates = checked
            }
        }
    }

    // Card 2.2: Concurrency & Performance Engine
    DownloaderEngineCard {
        view: subTab2Content.view
    }

    // Card 2.2b: Pawchive Two-Layer Rate Guard & Persistent Calibration
    PawchiveRateGuardCard {
        view: subTab2Content.view
    }

    // Card 2.3: Post-Download Automation
    CardSection {
        Layout.fillWidth: true
        title: subTab2Content.view.tr("card_post_automation", "Post-Download Automation")
        iconText: "✨"
        entranceOffsetY: subTab2Content.view.tabEntranceOffsetY * 1.5
        entranceOpacity: subTab2Content.view.tabEntranceOpacity

        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 10

            // Save post_info.txt toggle
            Rectangle {
                id: saveMetaToggle
                property bool active: subTab2Content.view.bridge ? subTab2Content.view.bridge.savePostMetadata : true
                // as wide as its text (long translations used to spill out of the card)
                implicitWidth: Math.min(parent.width, Math.max(230, metaTexts.implicitWidth + 66))
                implicitHeight: 36
                radius: 10
                color: active ? "#1E1B35" : "#141922"
                border.color: active ? "#7C3AED" : "#1E2433"
                border.width: 1

                scale: metaMouse.pressed ? 0.95 : (metaMouse.containsMouse ? 1.025 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                transform: Translate {
                    y: metaMouse.containsMouse ? -1.5 : 0
                    Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                }

                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on border.color { ColorAnimation { duration: 180 } }

                Rectangle {
                    width: 3
                    height: parent.height - 10
                    radius: 2
                    anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                    color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                    Behavior on color { ColorAnimation { duration: 180 } }
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                    spacing: 8

                    Rectangle {
                        id: metaTrack
                        width: 32; height: 18; radius: 9
                        color: saveMetaToggle.active ? "#7C3AED" : "#2D3748"
                        Behavior on color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            id: metaThumb
                            width: 12; height: 12; radius: 6
                            color: "white"
                            anchors.verticalCenter: parent.verticalCenter
                            x: saveMetaToggle.active ? parent.width - width - 3 : 3
                            Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                        }
                    }

                    ColumnLayout {
                        id: metaTexts
                        spacing: 1
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_save_post_info", "Save post_info.txt")
                            color: saveMetaToggle.active ? "#E2E8F0" : "#64748B"
                            font.pixelSize: 12
                            font.family: "Segoe UI, sans-serif"
                            font.weight: Font.Medium
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_save_post_info_sub", "caption, tags & comments")
                            color: saveMetaToggle.active ? "#7C3AED" : "#374151"
                            font.pixelSize: 9
                            font.family: "Segoe UI, sans-serif"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                    }
                }

                MouseArea {
                    id: metaMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (subTab2Content.view.bridge) subTab2Content.view.bridge.savePostMetadata = !saveMetaToggle.active
                    }
                }

                Connections {
                    target: subTab2Content.view.bridge
                    function onSavePostMetadataChanged() {
                        saveMetaToggle.active = subTab2Content.view.bridge.savePostMetadata
                    }
                }
            }

            // Open folder when done toggle
            Rectangle {
                id: openFolderToggle
                property bool active: subTab2Content.view.bridge ? subTab2Content.view.bridge.openFolderOnComplete : false
                // as wide as its text (long translations used to spill out of the card)
                implicitWidth: Math.min(parent.width, Math.max(210, folderTexts.implicitWidth + 66))
                implicitHeight: 36
                radius: 10
                color: active ? "#0D1F1A" : "#141922"
                border.color: active ? "#10B981" : "#1E2433"
                border.width: 1

                scale: folderMouse.pressed ? 0.95 : (folderMouse.containsMouse ? 1.025 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                transform: Translate {
                    y: folderMouse.containsMouse ? -1.5 : 0
                    Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                }

                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on border.color { ColorAnimation { duration: 180 } }

                Rectangle {
                    width: 3
                    height: parent.height - 10
                    radius: 2
                    anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                    color: openFolderToggle.active ? "#10B981" : "#2D3748"
                    Behavior on color { ColorAnimation { duration: 180 } }
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                    spacing: 8

                    Rectangle {
                        id: folderTrack
                        width: 32; height: 18; radius: 9
                        color: openFolderToggle.active ? "#10B981" : "#2D3748"
                        Behavior on color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 12; height: 12; radius: 6
                            color: "white"
                            anchors.verticalCenter: parent.verticalCenter
                            x: openFolderToggle.active ? parent.width - width - 3 : 3
                            Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                        }
                    }

                    ColumnLayout {
                        id: folderTexts
                        spacing: 1
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_open_folder", "Open folder when done")
                            color: openFolderToggle.active ? "#E2E8F0" : "#64748B"
                            font.pixelSize: 12
                            font.family: "Segoe UI, sans-serif"
                            font.weight: Font.Medium
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_open_folder_sub", "auto-opens on completion")
                            color: openFolderToggle.active ? "#10B981" : "#374151"
                            font.pixelSize: 9
                            font.family: "Segoe UI, sans-serif"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                    }
                }

                MouseArea {
                    id: folderMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (subTab2Content.view.bridge) subTab2Content.view.bridge.openFolderOnComplete = !openFolderToggle.active
                    }
                }

                Connections {
                    target: subTab2Content.view.bridge
                    function onOpenFolderOnCompleteChanged() {
                        openFolderToggle.active = subTab2Content.view.bridge.openFolderOnComplete
                    }
                }
            }

            // Desktop report toggle
            Rectangle {
                id: desktopReportToggle
                property bool active: subTab2Content.view.bridge ? subTab2Content.view.bridge.saveDesktopReport : false
                // as wide as its text (long translations used to spill out of the card)
                implicitWidth: Math.min(parent.width, Math.max(210, reportTexts.implicitWidth + 66))
                implicitHeight: 36
                radius: 10
                color: active ? "#0C202F" : "#141922"
                border.color: active ? "#0284C7" : "#1E2433"
                border.width: 1

                scale: reportMouse.pressed ? 0.95 : (reportMouse.containsMouse ? 1.025 : 1.0)
                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.34; mass: 0.75; epsilon: 0.005 } }

                transform: Translate {
                    y: reportMouse.containsMouse ? -1.5 : 0
                    Behavior on y { SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 } }
                }

                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on border.color { ColorAnimation { duration: 180 } }

                Rectangle {
                    width: 3
                    height: parent.height - 10
                    radius: 2
                    anchors { left: parent.left; leftMargin: 0; verticalCenter: parent.verticalCenter }
                    color: desktopReportToggle.active ? "#38BDF8" : "#2D3748"
                    Behavior on color { ColorAnimation { duration: 180 } }
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                    spacing: 8

                    Rectangle {
                        id: reportTrack
                        width: 32; height: 18; radius: 9
                        color: desktopReportToggle.active ? "#0284C7" : "#2D3748"
                        Behavior on color { ColorAnimation { duration: 180 } }

                        Rectangle {
                            width: 12; height: 12; radius: 6
                            color: "white"
                            anchors.verticalCenter: parent.verticalCenter
                            x: desktopReportToggle.active ? parent.width - width - 3 : 3
                            Behavior on x { SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 } }
                        }
                    }

                    ColumnLayout {
                        id: reportTexts
                        spacing: 1
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_desktop_report", "Desktop report")
                            color: desktopReportToggle.active ? "#E2E8F0" : "#64748B"
                            font.pixelSize: 12
                            font.family: "Segoe UI, sans-serif"
                            font.weight: Font.Medium
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: subTab2Content.view.tr("toggle_desktop_report_sub", "summary log on desktop")
                            color: desktopReportToggle.active ? "#38BDF8" : "#374151"
                            font.pixelSize: 9
                            font.family: "Segoe UI, sans-serif"
                            Behavior on color { ColorAnimation { duration: 180 } }
                        }
                    }
                }

                MouseArea {
                    id: reportMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (subTab2Content.view.bridge) subTab2Content.view.bridge.saveDesktopReport = !desktopReportToggle.active
                    }
                }

                Connections {
                    target: subTab2Content.view.bridge
                    function onSaveDesktopReportChanged() {
                        desktopReportToggle.active = subTab2Content.view.bridge.saveDesktopReport
                    }
                }
            }
        }
    }
}
