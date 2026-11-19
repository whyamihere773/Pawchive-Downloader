import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab3Content
    required property var view
    readonly property string batchText: batchInput ? batchInput.text : ""
    visible: !subTab3Content.view.embeddedInModal && subTab3Content.view.currentSubTab === 3
    Layout.fillWidth: true
    spacing: 12

    CardSection {
        Layout.fillWidth: true
        title: subTab3Content.view.tr("section_batch_queue", "Batch Download Queue")
        iconText: "📋"
        entranceOffsetY: subTab3Content.view.tabEntranceOffsetY
        entranceOpacity: subTab3Content.view.tabEntranceOpacity

        ColumnLayout {
            width: parent.width
            spacing: 12

            // ── Favorite Mode Active Warning Banner ──
            Rectangle {
                id: batchFavWarningBanner
                visible: subTab3Content.view.bridge ? subTab3Content.view.bridge.favoriteMode : false
                Layout.fillWidth: true
                implicitHeight: visible ? batchFavBannerRow.implicitHeight + 20 : 0
                radius: 8
                color: "#181410"
                border.color: "#B45309"
                border.width: 1
                clip: true

                Behavior on implicitHeight {
                    NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
                }

                // Left vertical amber accent strip
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 4
                    radius: 2
                    color: "#F59E0B"
                }

                RowLayout {
                    id: batchFavBannerRow
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 14
                    anchors.topMargin: 10
                    anchors.bottomMargin: 10
                    spacing: 12

                    Text {
                        text: "⚠️"
                        font.pixelSize: 18
                        Layout.alignment: Qt.AlignVCenter
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: subTab3Content.view.tr("banner_batch_fav_mode_title", "Favorite Mode is active")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: "#FDE68A"
                        }

                        Text {
                            text: subTab3Content.view.tr("banner_batch_fav_mode_desc", "Batch Importer queues standard URLs directly and does not support Favorite Mode. Turn off Favorite Mode to process these URLs.")
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#FBBF24"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    StyledButton {
                        text: subTab3Content.view.tr("btn_turn_off_favorite_mode", "Turn Off Favorite Mode")
                        iconText: "✕"
                        variant: "outline"
                        Layout.alignment: Qt.AlignVCenter
                        onClicked: {
                            if (subTab3Content.view.bridge) {
                                subTab3Content.view.bridge.favoriteMode = false
                            }
                        }
                    }
                }
            }

            Text {
                text: subTab3Content.view.tr("desc_batch_queue", "Paste multiple creator / album URLs below, one per line. Each URL uses its own folder inside the download destination.")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            ScrollView {
                Layout.fillWidth: true
                implicitHeight: 140
                clip: true

                TextArea {
                    id: batchInput
                    placeholderText: "https://kemono.cr/patreon/user/12345\nhttps://coomer.st/onlyfans/user/67890\nhttps://cum.st/creators/onlyfans/32696630\nhttps://bunkr.cr/a/example"
                    placeholderTextColor: "#64748B"
                    background: Rectangle {
                        color: batchInput.activeFocus ? "#0E1118" : "#141922"
                        border.color: batchInput.activeFocus ? "#38BDF8" : (batchInput.hovered ? "#475569" : "#1E2433")
                        border.width: batchInput.activeFocus ? 1.5 : 1
                        radius: 6
                    }
                    color: "#E2E8F0"
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    selectByMouse: true
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    wrapMode: TextArea.Wrap
                    padding: 10
                    TextBarContextArea {}
                }
            }

            RowLayout {
                spacing: 8

                StyledButton {
                    text: (subTab3Content.view.bridge && subTab3Content.view.bridge.isDownloading) ? subTab3Content.view.tr("action_queue_at_end", "Queue at End") : subTab3Content.view.tr("btn_add_all_queue", "Add All to Queue")
                    iconText: (subTab3Content.view.bridge && subTab3Content.view.bridge.isDownloading) ? "➕" : "▶"
                    variant: "primary"
                    tooltip: (subTab3Content.view.bridge && subTab3Content.view.bridge.isDownloading) ? subTab3Content.view.tr("btn_add_all_queue_active_tip", "Add all URLs to the end of the active download queue with current filter settings") : subTab3Content.view.tr("btn_add_all_queue_tip", "Parse and start downloading all URLs above")
                    enabled: batchInput.text.trim().length > 0 && subTab3Content.view.bridge
                    onClicked: {
                        if (subTab3Content.view.bridge) {
                            if (subTab3Content.view.bridge.favoriteMode) {
                                subTab3Content.view.bridge.favoriteMode = false
                            }
                            var count = subTab3Content.view.bridge.batchLoadUrls(batchInput.text)
                            if (count > 0) {
                                batchInput.text = ""
                            }
                        }
                    }
                }

                StyledButton {
                    text: subTab3Content.view.tr("btn_clear", "Clear")
                    iconText: "✕"
                    variant: "ghost"
                    onClicked: batchInput.text = ""
                }

                // URL detection badge with Newtonian spring pop
                Rectangle {
                    visible: subTab3Content.view.detectedBatchUrlCount > 0
                    implicitHeight: 24
                    implicitWidth: batchCountLabel.implicitWidth + 16
                    radius: 12
                    color: "#064E3B"
                    border.color: "#10B981"
                    border.width: 1

                    scale: visible ? 1.0 : 0.4
                    Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                    Text {
                        id: batchCountLabel
                        anchors.centerIn: parent
                        text: subTab3Content.view.detectedBatchUrlCount + " " + subTab3Content.view.tr("label_urls_detected", "URL(s) detected")
                        color: "#A7F3D0"
                        font.pixelSize: 11
                        font.bold: true
                        font.family: "Segoe UI, sans-serif"
                    }
                }
            }
        }
    }
}
