import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Per-creator Watchlist settings editor modal (folder, auto-check, cutoff date, filter/download options).
Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 99
    focus: visible

    property var bridge: null
    property string targetUserId: ""
    property string targetService: ""
    property string creatorName: ""
    property string downloadDir: ""
    property string resolvedPreview: ""
    property bool pickedAsLeaf: false
    property string lastBrowsedResolved: ""
    property bool autoCheck: true
    property string lastPostDate: ""
    property bool useCustomSettings: false
    property string errorMsg: ""

    // Editable filter/download options snapshot
    property var baseOptions: ({})
    property string optFileType: "all"
    property string optGroupFileType: "none"
    property string optDateFolderMode: "none"
    property string optFilenameStyle: "post_title"
    property string optFilenameTemplate: "{title} - {orig_name}"
    property string optExactExtensions: ""
    property string optCharacters: ""
    property string optCharacterScope: "title"
    property string optSkipWords: ""
    property bool optSkipArchives: false
    property bool optThumbnailsOnly: false
    property bool optDownloadDms: false
    property bool optDownloadEmbeds: false
    property bool optScanContentImages: true
    property bool optCompressWebp: false
    property bool optSubfolderPerPost: true
    property bool optDatePrefix: true
    property bool optSavePostMetadata: false
    property bool optMangaMode: false
    property bool optTagFolderMode: false
    property bool optSeparateByKnown: false

    signal settingsSaved(string message)
    signal redownloadRequested(string uid, string svc)

    function open(uid, svc) {
        if (!root.bridge) return
        var s = root.bridge.getWatchlistEntrySettings(uid, svc)
        if (!s || !s.ok) return
        root.targetUserId = String(s.userId || uid)
        root.targetService = String(s.service || svc)
        root.creatorName = String(s.creatorName || uid)
        root.downloadDir = String(s.downloadDir || "")
        root.resolvedPreview = String(s.resolvedDir || "")
        root.pickedAsLeaf = false
        root.lastBrowsedResolved = ""
        root.autoCheck = Boolean(s.autoCheck)
        root.lastPostDate = String(s.lastPostDate || "")
        root.useCustomSettings = Boolean(s.useCustomSettings)
        root.errorMsg = ""

        var o = s.options || {}
        root.baseOptions = Object.assign({}, o)
        root.optFileType = String(o.file_type || "all")
        root.optGroupFileType = String(o.group_file_type || "none")
        root.optDateFolderMode = String(o.date_folder_mode || "none")
        root.optFilenameStyle = String(o.filename_style || "post_title")
        root.optFilenameTemplate = String(o.filename_template || "{title} - {orig_name}")
        root.optExactExtensions = String(o.exact_extensions || "")
        root.optCharacters = String(o.characters || "")
        root.optCharacterScope = String(o.character_scope || "title")
        root.optSkipWords = String(o.skip_words || "")
        root.optSkipArchives = Boolean(o.skip_archives)
        root.optThumbnailsOnly = Boolean(o.download_thumbnails_only)
        root.optDownloadDms = Boolean(o.download_dms)
        root.optDownloadEmbeds = Boolean(o.download_embeds)
        root.optScanContentImages = o.scan_content_images === undefined ? true : Boolean(o.scan_content_images)
        root.optCompressWebp = Boolean(o.compress_to_webp)
        root.optSubfolderPerPost = o.subfolder_per_post === undefined ? true : Boolean(o.subfolder_per_post)
        root.optDatePrefix = o.date_prefix === undefined ? true : Boolean(o.date_prefix)
        root.optSavePostMetadata = Boolean(o.save_post_metadata)
        root.optMangaMode = Boolean(o.manga_mode)
        root.optTagFolderMode = Boolean(o.tag_folder_mode)
        root.optSeparateByKnown = Boolean(o.separate_by_known)
        root.visible = true
    }

    function close() {
        root.visible = false
    }

    function updateFolderPreview() {
        if (!root.bridge) return
        root.resolvedPreview = root.bridge.previewWatchlistResolvedFolder(
            root.targetUserId,
            root.targetService,
            root.downloadDir,
            root.pickedAsLeaf
        )
    }

    function buildPayload() {
        var opts = Object.assign({}, root.baseOptions || {})
        opts.file_type = root.optFileType
        opts.group_file_type = root.optGroupFileType
        opts.date_folder_mode = root.optDateFolderMode
        opts.filename_style = root.optFilenameStyle
        opts.filename_template = root.optFilenameTemplate
        opts.exact_extensions = root.optExactExtensions
        opts.characters = root.optCharacters
        opts.character_scope = root.optCharacterScope
        opts.skip_words = root.optSkipWords
        opts.skip_archives = root.optSkipArchives
        opts.download_thumbnails_only = root.optThumbnailsOnly
        opts.download_dms = root.optDownloadDms
        opts.download_embeds = root.optDownloadEmbeds
        opts.scan_content_images = root.optScanContentImages
        opts.compress_to_webp = root.optCompressWebp
        opts.subfolder_per_post = root.optSubfolderPerPost
        opts.date_prefix = root.optDatePrefix
        opts.save_post_metadata = root.optSavePostMetadata
        opts.manga_mode = root.optMangaMode
        opts.tag_folder_mode = root.optTagFolderMode
        opts.separate_by_known = root.optSeparateByKnown

        return {
            autoCheck: root.autoCheck,
            lastPostDate: root.lastPostDate,
            downloadDir: root.downloadDir,
            pickedAsLeaf: root.pickedAsLeaf,
            useCustomSettings: root.useCustomSettings,
            options: opts,
            promptMoveIfNeeded: true
        }
    }

    function saveSettings(triggerRedownload) {
        if (!root.bridge) return null
        root.errorMsg = ""
        var payload = buildPayload()
        if (triggerRedownload) {
            payload.promptMoveIfNeeded = false
        }
        var res = root.bridge.saveWatchlistEntrySettings(root.targetUserId, root.targetService, payload)
        if (!res || !res.ok) {
            root.errorMsg = (res && res.error) ? String(res.error) : "Failed to save settings."
            return res
        }
        var uid = root.targetUserId
        var svc = root.targetService
        root.close()
        if (triggerRedownload) {
            root.redownloadRequested(uid, svc)
        } else if (res.activeDownloadConflict) {
            if (root.bridge && root.bridge.requestMidDownloadSettingsPrompt) {
                root.bridge.requestMidDownloadSettingsPrompt("creator", uid, svc)
            }
        } else if (!res.movePrompt) {
            root.settingsSaved("Saved settings for " + root.creatorName)
        }
        return res
    }

    Keys.onEscapePressed: root.close()

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#AA04060A"

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.close()
        }
    }

    // Modal card
    Rectangle {
        anchors.centerIn: parent
        width: Math.min(680, parent.width - 36)
        height: Math.min(720, parent.height - 36)
        radius: 12
        color: "#0E111B"
        border.color: "#242C40"
        border.width: 1

        MouseArea {
            anchors.fill: parent
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "\u2699"
                    font.pixelSize: 18
                    color: "#A78BFA"
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        Layout.fillWidth: true
                        text: "Creator Watchlist Settings"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: 700
                        color: "#F8FAFC"
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.creatorName + "  [" + root.targetService.toUpperCase() + "]  •  ID: " + root.targetUserId
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                        elide: Text.ElideRight
                    }
                }

                StyledButton {
                    text: "\u2715"
                    variant: "ghost"
                    implicitWidth: 32
                    implicitHeight: 32
                    onClicked: root.close()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E2638"
            }

            // Scrollable form body
            SmoothFlickable {
                id: formScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: formCol.implicitHeight + 8

                ColumnLayout {
                    id: formCol
                    width: formScroll.width - 10
                    spacing: 14

                    // 1. Download Folder section
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: folderSec.implicitHeight + 22
                        radius: 8
                        color: "#121726"
                        border.color: "#1E2638"
                        border.width: 1

                        ColumnLayout {
                            id: folderSec
                            anchors.fill: parent
                            anchors.margins: 11
                            spacing: 8

                            Text {
                                text: "DOWNLOAD FOLDER"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#38BDF8"
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                StyledTextField {
                                    id: folderField
                                    objectName: "watchlistSettingsFolderField"
                                    Layout.fillWidth: true
                                    text: root.downloadDir
                                    placeholderText: "Leave empty to use Global Downloader folder"
                                    onTextEdited: {
                                        root.downloadDir = text
                                        if (text !== root.lastBrowsedResolved) {
                                            root.pickedAsLeaf = false
                                        }
                                        root.updateFolderPreview()
                                    }
                                }

                                StyledButton {
                                    text: "Browse"
                                    iconText: "\uD83D\uDCC2"
                                    variant: "outline"
                                    implicitHeight: 36
                                    onClicked: {
                                        if (!root.bridge) return
                                        var res = root.bridge.browseFolderForWatchlistSettings(
                                            root.targetUserId,
                                            root.targetService,
                                            root.downloadDir
                                        )
                                        if (res && res.resolved) {
                                            root.pickedAsLeaf = Boolean(res.isLeaf)
                                            root.lastBrowsedResolved = String(res.resolved)
                                            root.downloadDir = String(res.resolved)
                                            root.resolvedPreview = String(res.resolved)
                                        }
                                    }
                                }

                                StyledButton {
                                    text: "Default"
                                    variant: "ghost"
                                    implicitHeight: 36
                                    tooltip: "Clear custom folder and follow Downloader's default folder"
                                    onClicked: {
                                        root.downloadDir = ""
                                        root.pickedAsLeaf = false
                                        root.lastBrowsedResolved = ""
                                        root.updateFolderPreview()
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Resolved folder: " + root.resolvedPreview
                                font.family: "Consolas, monospace"
                                font.pixelSize: 11
                                color: "#94A3B8"
                                wrapMode: Text.WrapAnywhere
                            }
                        }
                    }

                    // 2. Tracking & Cutoff Date section
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: trackSec.implicitHeight + 22
                        radius: 8
                        color: "#121726"
                        border.color: "#1E2638"
                        border.width: 1

                        ColumnLayout {
                            id: trackSec
                            anchors.fill: parent
                            anchors.margins: 11
                            spacing: 10

                            Text {
                                text: "TRACKING & CUTOFF"
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#38BDF8"
                            }

                            StyledSwitch {
                                Layout.fillWidth: true
                                checked: root.autoCheck
                                label: "Include in 'Check All' automatic updates"
                                accentColor: "#8B5CF6"
                                onToggled: function(val) { root.autoCheck = val }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: "Cutoff Date:"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 12
                                    color: "#CBD5E1"
                                    Layout.preferredWidth: 100
                                }

                                StyledTextField {
                                    Layout.fillWidth: true
                                    text: root.lastPostDate
                                    placeholderText: "YYYY-MM-DD (empty = no date cutoff)"
                                    onTextEdited: root.lastPostDate = text
                                }

                                StyledButton {
                                    text: "Clear"
                                    variant: "ghost"
                                    implicitHeight: 36
                                    onClicked: root.lastPostDate = ""
                                }
                            }
                        }
                    }

                    // 3. Per-Creator Download & Filter Settings section
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: optsSec.implicitHeight + 22
                        radius: 8
                        color: "#121726"
                        border.color: root.useCustomSettings ? "#6D28D9" : "#1E2638"
                        border.width: 1

                        ColumnLayout {
                            id: optsSec
                            anchors.fill: parent
                            anchors.margins: 11
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: "DOWNLOAD & FILTER SETTINGS"
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: 700
                                    color: "#A78BFA"
                                    Layout.fillWidth: true
                                }
                            }

                            StyledSwitch {
                                id: customSettingsSwitch
                                objectName: "watchlistUseCustomSettingsSwitch"
                                Layout.fillWidth: true
                                checked: root.useCustomSettings
                                label: "Use custom settings for this creator (override global settings)"
                                accentColor: "#8B5CF6"
                                onToggled: function(val) { root.useCustomSettings = val }
                            }

                            Text {
                                Layout.fillWidth: true
                                visible: !root.useCustomSettings
                                text: "Currently inheriting Global Settings. Enable the switch above to customize filters, filenames, or folders for this creator alone."
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                color: "#64748B"
                                wrapMode: Text.WordWrap
                            }

                            // Customizable options container
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                enabled: root.useCustomSettings
                                opacity: root.useCustomSettings ? 1.0 : 0.45

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "File Types"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledComboBox {
                                            Layout.fillWidth: true
                                            value: root.optFileType
                                            model: [
                                                { text: "All Files", value: "all" },
                                                { text: "Images Only", value: "images" },
                                                { text: "Videos Only", value: "videos" },
                                                { text: "Audio Only", value: "audio" },
                                                { text: "Archives Only", value: "archives" }
                                            ]
                                            onValuePicked: function(val) { root.optFileType = String(val) }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Group by File Type"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledComboBox {
                                            Layout.fillWidth: true
                                            value: root.optGroupFileType
                                            model: [
                                                { text: "No Grouping", value: "none" },
                                                { text: "Inside Each Post", value: "post" },
                                                { text: "By Creator Root", value: "creator" }
                                            ]
                                            onValuePicked: function(val) { root.optGroupFileType = String(val) }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Sort by Date Folder"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledComboBox {
                                            Layout.fillWidth: true
                                            value: root.optDateFolderMode
                                            model: [
                                                { text: "Off", value: "none" },
                                                { text: "By Year (2025)", value: "year" },
                                                { text: "By Month (2025-03)", value: "month" },
                                                { text: "Year → Month (2025/03)", value: "year_month" }
                                            ]
                                            onValuePicked: function(val) { root.optDateFolderMode = String(val) }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Filename Style"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledComboBox {
                                            Layout.fillWidth: true
                                            value: root.optFilenameStyle
                                            model: [
                                                { text: "Post Title - Original", value: "post_title" },
                                                { text: "Original Filename Only", value: "original" },
                                                { text: "Date - Post Title - Original", value: "date_post_title" },
                                                { text: "Date Numbering", value: "date_based" },
                                                { text: "Global Index + Post Title", value: "post_title_global_numbering" },
                                                { text: "Custom Template", value: "custom" }
                                            ]
                                            onValuePicked: function(val) { root.optFilenameStyle = String(val) }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Exact Extensions (e.g. .png,.mp4)"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledTextField {
                                            Layout.fillWidth: true
                                            text: root.optExactExtensions
                                            placeholderText: "Optional CSV extensions"
                                            onTextEdited: root.optExactExtensions = text
                                        }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    visible: root.optFilenameStyle === "custom"
                                    Text { text: "Custom Filename Template"; font.pixelSize: 11; color: "#CBD5E1" }
                                    StyledTextField {
                                        Layout.fillWidth: true
                                        text: root.optFilenameTemplate
                                        placeholderText: "{title} - {orig_name}"
                                        onTextEdited: root.optFilenameTemplate = text
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Include Keywords / Characters"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledTextField {
                                            Layout.fillWidth: true
                                            text: root.optCharacters
                                            placeholderText: "Optional CSV terms"
                                            onTextEdited: root.optCharacters = text
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4
                                        Text { text: "Skip Words"; font.pixelSize: 11; color: "#CBD5E1" }
                                        StyledTextField {
                                            Layout.fillWidth: true
                                            text: root.optSkipWords
                                            placeholderText: "Optional CSV terms to skip"
                                            onTextEdited: root.optSkipWords = text
                                        }
                                    }
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    columnSpacing: 12
                                    rowSpacing: 4

                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Subfolder Per Post"
                                        checked: root.optSubfolderPerPost
                                        onToggled: root.optSubfolderPerPost = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Date Prefix on Folders/Files"
                                        checked: root.optDatePrefix
                                        onToggled: root.optDatePrefix = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Skip Archive Files (.zip/.rar/.psd)"
                                        checked: root.optSkipArchives
                                        onToggled: root.optSkipArchives = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Thumbnails Only (Images)"
                                        checked: root.optThumbnailsOnly
                                        onToggled: root.optThumbnailsOnly = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Download Direct Messages (DMs)"
                                        checked: root.optDownloadDms
                                        onToggled: root.optDownloadDms = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Download Embeds / Linked Media"
                                        checked: root.optDownloadEmbeds
                                        onToggled: root.optDownloadEmbeds = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Scan Inline Content Images"
                                        checked: root.optScanContentImages
                                        onToggled: root.optScanContentImages = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Compress Images to WebP"
                                        checked: root.optCompressWebp
                                        onToggled: root.optCompressWebp = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Save post_info.txt Metadata"
                                        checked: root.optSavePostMetadata
                                        onToggled: root.optSavePostMetadata = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Manga Chapter Subfolders"
                                        checked: root.optMangaMode
                                        onToggled: root.optMangaMode = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Tag Folder Mode"
                                        checked: root.optTagFolderMode
                                        onToggled: root.optTagFolderMode = checked
                                    }
                                    StyledCheckBox {
                                        Layout.fillWidth: true
                                        text: "Separate Known / Unknown"
                                        checked: root.optSeparateByKnown
                                        onToggled: root.optSeparateByKnown = checked
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Validation error
            Text {
                Layout.fillWidth: true
                visible: root.errorMsg.length > 0
                text: root.errorMsg
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#F87171"
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E2638"
            }

            // Footer buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                StyledButton {
                    text: "Save & Re-download All..."
                    iconText: "\uD83D\uDD04"
                    variant: "outline"
                    implicitHeight: 38
                    onClicked: root.saveSettings(true)
                }

                Item { Layout.fillWidth: true }

                StyledButton {
                    text: "Cancel"
                    variant: "outline"
                    implicitHeight: 38
                    onClicked: root.close()
                }

                StyledButton {
                    id: saveWatchlistSettingsBtn
                    objectName: "saveWatchlistSettingsBtn"
                    text: "Save Settings"
                    variant: "primary"
                    implicitHeight: 38
                    onClicked: root.saveSettings(false)
                }
            }
        }
    }
}
