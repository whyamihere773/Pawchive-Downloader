import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Decompressor → "Compress pictures and videos after extracting" (off by default): format and quality for
// pictures and for videos, and FFmpeg (needed for videos) when it isn't installed yet.
ColumnLayout {
    id: root
    property var decompressor: null
    // Inside the Gallery's compress window: just the formats (no on / off option, no extraction note)
    property bool embedded: false
    spacing: 8

    function tr(key, fallback) {
        if (typeof Lang === "undefined" || !Lang) return fallback !== undefined ? fallback : key
        var _ = Lang.activeLanguage
        var res = Lang.t(key)
        return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
    }

    function qualityWord(q) {
        if (q >= 95) return tr("compress_q_near_lossless", "Near lossless")
        if (q >= 85) return tr("compress_q_high", "High")
        if (q >= 70) return tr("compress_q_balanced", "Balanced")
        if (q >= 50) return tr("compress_q_small", "Small")
        return tr("compress_q_smallest", "Smallest")
    }

    readonly property bool on: embedded || (decompressor ? decompressor.compressAfter : false)

    // Quality slider styled like the Downloader's
    component QualitySlider: RowLayout {
        id: qs
        property int value: 75
        property bool active: true
        signal moved(int v)
        spacing: 8

        Slider {
            id: sl
            from: 1
            to: 100
            stepSize: 1
            value: qs.value
            enabled: qs.active
            implicitWidth: 120
            implicitHeight: 28
            onMoved: qs.moved(Math.round(value))

            background: Item {
                x: sl.leftPadding
                y: sl.topPadding + sl.availableHeight / 2 - height / 2
                width: sl.availableWidth
                implicitHeight: 6
                height: 6
                Rectangle {
                    width: parent.width; height: parent.height
                    radius: 3
                    color: "#101827"
                    border.color: "#1E2D42"
                    border.width: 1
                }
                Rectangle {
                    width: Math.max(6, sl.visualPosition * parent.width)
                    height: parent.height
                    radius: 3
                    color: "#38BDF8"
                    opacity: sl.enabled ? 1.0 : 0.35
                }
            }
            handle: Item {
                x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
                y: sl.topPadding + sl.availableHeight / 2 - height / 2
                width: 24; height: 24
                Rectangle {
                    anchors.centerIn: parent
                    width: 24; height: 24; radius: 12
                    color: "transparent"
                    border.color: "#38BDF8"
                    border.width: 1
                    opacity: (sl.pressed || sl.hovered) ? 0.5 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 160 } }
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 14; height: 14; radius: 7
                    color: "#38BDF8"
                    opacity: sl.enabled ? 1.0 : 0.3
                }
            }
        }
        Text {
            text: Math.round(sl.value) + " · " + root.qualityWord(Math.round(sl.value))
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: qs.active ? "#CBD5E1" : "#475569"
            Layout.minimumWidth: 110
        }
    }

    // The on / off option (same look as "Move archive to the Recycle Bin")
    MouseArea {
        id: toggle
        objectName: "compress_after_toggle"
        visible: !root.embedded
        Layout.fillWidth: true
        implicitHeight: Math.max(22, toggleRow.implicitHeight)
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        ToolTip.visible: containsMouse
        ToolTip.delay: 300
        ToolTip.text: root.tr("compress_after_tip", "After each archive is extracted, its pictures and videos are saved again in a smaller format. A copy is only kept when it's at least 5% smaller, and you're asked at the end whether to keep the originals.")
        onClicked: if (root.decompressor) root.decompressor.compressAfter = !root.decompressor.compressAfter

        RowLayout {
            id: toggleRow
            anchors.fill: parent
            spacing: 8
            Rectangle {
                width: 18; height: 18; radius: 4
                color: root.on ? "#0284C7" : "#111827"
                border.color: root.on ? "#38BDF8" : (toggle.containsMouse ? "#64748B" : "#334155")
                border.width: root.on ? 1.5 : 1
                Text {
                    anchors.centerIn: parent
                    text: "✓"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                    visible: root.on
                }
            }
            Text {
                text: root.tr("compress_after_opt", "Compress pictures and videos after extracting")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: Font.Medium
                color: root.on ? "#7DD3FC" : (toggle.containsMouse ? "#CBD5E1" : "#94A3B8")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }

    // Pictures
    Flow {
        Layout.fillWidth: true
        Layout.leftMargin: root.embedded ? 0 : 26
        visible: root.on
        spacing: 10

        Text {
            text: root.tr("compress_pictures", "Pictures:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            width: 80
            height: 28
            verticalAlignment: Text.AlignVCenter
        }
        StyledComboBox {
            objectName: "compress_image_format"
            implicitHeight: 28
            implicitWidth: 190
            model: [
                { text: root.tr("compress_fmt_jpg", "JPG (opens anywhere)"), value: "jpg" },
                { text: root.tr("compress_fmt_png", "PNG (lossless)"), value: "png" },
                { text: root.tr("compress_fmt_webp", "WebP (recommended)"), value: "webp" },
                { text: root.tr("compress_fmt_avif", "AVIF (smallest)"), value: "avif" },
                { text: root.tr("compress_fmt_keep", "Don't compress"), value: "keep" }
            ]
            value: root.decompressor ? root.decompressor.imageFormat : "webp"
            tooltip: root.tr("compress_image_fmt_tip3", "JPG opens anywhere but can't keep transparency. PNG loses nothing at 90 and above; lower values use fewer colours, which suits drawings. WebP keeps the quality at about half the size. AVIF is smaller still but slower.")
            onValuePicked: function(v) { if (root.decompressor) root.decompressor.imageFormat = v }
        }
        QualitySlider {
            height: 28
            value: root.decompressor ? root.decompressor.imageQuality : 82
            active: root.decompressor ? root.decompressor.imageFormat !== "keep" : true
            onMoved: function(v) { if (root.decompressor) root.decompressor.imageQuality = v }
        }
    }

    // Videos
    Flow {
        Layout.fillWidth: true
        Layout.leftMargin: root.embedded ? 0 : 26
        visible: root.on
        spacing: 10

        Text {
            text: root.tr("compress_videos", "Videos:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            width: 80
            height: 28
            verticalAlignment: Text.AlignVCenter
        }
        StyledComboBox {
            objectName: "compress_video_format"
            implicitHeight: 28
            implicitWidth: 190
            model: [
                { text: root.tr("compress_fmt_h265", "H.265 (recommended)"), value: "h265" },
                { text: root.tr("compress_fmt_h264", "H.264 (plays anywhere)"), value: "h264" },
                { text: root.tr("compress_fmt_mkv", "MKV (H.265, keeps subtitles)"), value: "mkv" },
                { text: root.tr("compress_fmt_av1", "AV1 (smallest, slow)"), value: "av1" },
                { text: root.tr("compress_fmt_keep", "Don't compress"), value: "keep" }
            ]
            value: root.decompressor ? root.decompressor.videoFormat : "h265"
            tooltip: root.tr("compress_video_fmt_tip2", "H.265 keeps the quality at a much smaller size (.mp4). H.264 is bigger but plays on every device (.mp4). MKV is H.265 in an .mkv file that keeps every audio track, subtitles and fonts. AV1 is the smallest but takes much longer (.mp4). Videos already in the chosen format are left as they are.")
            onValuePicked: function(v) { if (root.decompressor) root.decompressor.videoFormat = v }
        }
        QualitySlider {
            height: 28
            value: root.decompressor ? root.decompressor.videoQuality : 75
            active: root.decompressor ? (root.decompressor.videoFormat !== "keep" && root.decompressor.ffmpegAvailable) : true
            onMoved: function(v) { if (root.decompressor) root.decompressor.videoQuality = v }
        }
    }

    // Animated pictures (GIF, APNG, animated WebP / AVIF): their own setting. They stay animated, in their own
    // format or as another animated one: an animation never becomes a still picture
    Flow {
        Layout.fillWidth: true
        Layout.leftMargin: root.embedded ? 0 : 26
        visible: root.on
        spacing: 10

        Text {
            text: root.tr("compress_animated2", "Animated:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            width: 80
            height: 28
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
        }
        StyledComboBox {
            objectName: "compress_animated_format"
            implicitHeight: 28
            implicitWidth: 190
            model: [
                { text: root.tr("compress_fmt_same", "Same format (recommended)"), value: "same" },
                { text: root.tr("compress_fmt_gif2", "GIF"), value: "gif" },
                { text: root.tr("compress_fmt_apng", "APNG (animated PNG)"), value: "png" },
                { text: root.tr("compress_fmt_webp_anim", "WebP (animated)"), value: "webp" },
                { text: root.tr("compress_fmt_avif_anim", "AVIF (animated)"), value: "avif" },
                { text: root.tr("compress_fmt_keep", "Don't compress"), value: "keep" }
            ]
            value: root.decompressor ? root.decompressor.animatedFormat : "same"
            tooltip: root.tr("compress_animated_tip", "GIFs, animated PNGs (APNG) and animated WebP / AVIF pictures. They always stay animated: in their own format, or as the animated format you pick (animated WebP and AVIF are usually much smaller than GIF). Every frame, its timing and transparency are checked before a copy is kept.")
            onValuePicked: function(v) { if (root.decompressor) root.decompressor.animatedFormat = v }
        }
        QualitySlider {
            height: 28
            value: root.decompressor ? root.decompressor.animatedQuality : 82
            active: root.decompressor ? root.decompressor.animatedFormat !== "keep" : true
            onMoved: function(v) { if (root.decompressor) root.decompressor.animatedQuality = v }
        }
    }

    // FFmpeg, needed for videos
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: root.embedded ? 0 : 26
        visible: root.on && root.decompressor && root.decompressor.videoFormat !== "keep" && !root.decompressor.ffmpegAvailable
        spacing: 10

        Text {
            text: root.decompressor && root.decompressor.ffmpegDownloading
                  ? root.tr("compress_ffmpeg_downloading", "Downloading FFmpeg… %1%").replace("%1", Math.round(root.decompressor.ffmpegProgress))
                  : (root.decompressor && root.decompressor.ffmpegMessage
                     ? "⚠️ " + root.decompressor.ffmpegMessage
                     : root.tr("compress_ffmpeg_needed", "Videos need FFmpeg, a free video tool (about 200 MB to download)."))
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: root.decompressor && root.decompressor.ffmpegMessage ? "#FCA5A5" : "#FBBF24"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        StyledButton {
            objectName: "compress_ffmpeg_download"
            visible: !(root.decompressor && root.decompressor.ffmpegDownloading)
            text: root.tr("compress_ffmpeg_download", "Download FFmpeg")
            tooltip: root.tr("compress_ffmpeg_download_tip", "Downloads the official FFmpeg build from GitHub (BtbN/FFmpeg-Builds), checks it, and keeps it in the app's dependencies folder.")
            variant: "outline"
            implicitHeight: 28
            onClicked: if (root.decompressor) root.decompressor.downloadFfmpeg()
        }
        StyledButton {
            visible: root.decompressor && root.decompressor.ffmpegDownloading
            text: root.tr("btn_cancel", "Cancel")
            variant: "ghost"
            implicitHeight: 28
            onClicked: if (root.decompressor) root.decompressor.cancelFfmpegDownload()
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.leftMargin: root.embedded ? 0 : 26
        visible: root.on && !root.embedded
        text: root.tr("compress_after_note", "Copies are saved next to the originals and only kept when they're at least 5% smaller. When everything's done you choose whether to keep the originals.")
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 10
        color: "#64748B"
        wrapMode: Text.WordWrap
    }
}
