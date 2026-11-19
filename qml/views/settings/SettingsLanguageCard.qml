import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: languageCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    interactive: !languageCard.view.isScrolling
    title: tr("section_language", "Language & Display")
    iconText: "🌐"
    entranceOffsetY: languageCard.view.tabEntranceOffsetY
    entranceOpacity: languageCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: tr("label_language", "Interface Language:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#94A3B8"
            }

            ComboBox {
                id: langCombo
                Layout.fillWidth: true
                Layout.maximumWidth: 240
                Layout.minimumWidth: 130
                Layout.preferredHeight: 32
                model: Lang ? Lang.availableLanguages : []
                textRole: "native"
                valueRole: "code"

                currentIndex: {
                    if (!Lang) return 0
                    var list = Lang.availableLanguages
                    for (var i = 0; i < list.length; i++) {
                        if (list[i].code === Lang.currentLanguage) return i
                    }
                    return 0
                }

                onActivated: function(index) {
                    if (Lang && model[index]) {
                        var selectedCode = model[index].code
                        Lang.setLanguage(selectedCode)
                        if (languageCard.view.bridge) languageCard.view.bridge.language = selectedCode
                    }
                }

                background: Rectangle {
                    color: "#141923"
                    border.color: langCombo.activeFocus ? "#38BDF8" : "#283042"
                    border.width: 1
                    radius: 6
                }

                contentItem: Text {
                    leftPadding: 10
                    rightPadding: (langCombo.indicator ? langCombo.indicator.width : 0) + 10
                    text: langCombo.displayText
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#F1F5F9"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                popup: Popup {
                    y: langCombo.height + 2
                    width: langCombo.width
                    implicitHeight: contentItem.implicitHeight + 10
                    padding: 4
                    background: Rectangle {
                        color: "#141923"
                        border.color: "#283042"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: ListView {
                        clip: true
                        implicitHeight: Math.min(contentHeight, 300)
                        model: langCombo.popup.visible ? langCombo.delegateModel : null
                        currentIndex: langCombo.highlightedIndex
                        ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
                    }
                }

                delegate: ItemDelegate {
                    width: langCombo.width - 8
                    height: 30
                    highlighted: langCombo.highlightedIndex === index
                    contentItem: Text {
                        text: modelData.native
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: highlighted ? "#38BDF8" : "#CBD5E1"
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: highlighted ? "#1E293B" : "transparent"
                        radius: 4
                    }
                }
            }
        }

        // AI Translation Disclaimer Banner
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: disclaimerRow.implicitHeight + 16
            radius: 6
            color: "#141A26"
            border.color: "#233147"
            border.width: 1

            RowLayout {
                id: disclaimerRow
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                spacing: 8

                Text {
                    text: "🤖"
                    font.pixelSize: 13
                    Layout.alignment: Qt.AlignVCenter
                }

                Text {
                    text: tr("disclaimer_translation", "Translations are generated by AI and Google Translate. Some phrasing may not be completely accurate.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        // Divider
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: "#1E293B"
            Layout.topMargin: 4
            Layout.bottomMargin: 4
        }

        // UI Scale (Display Zoom) — Responsive layout
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            // Header row: Label & description
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: languageCard.view.tr("label_ui_scale", "UI Scale (Display Zoom):")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#94A3B8"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                Text {
                    text: languageCard.view.tr("ui_scale_desc", "Scale interface for 4K / High-DPI screens")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#64748B"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }

            // Controls row: Slider, percentage chip, and reset button
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Slider {
                    id: uiScaleSlider
                    objectName: "uiScaleSlider"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 100
                    Layout.maximumWidth: 320
                    from: 100
                    to: 250
                    stepSize: 5
                    value: languageCard.view.bridge ? Math.round(languageCard.view.bridge.uiScale * 100) : 100
                    implicitHeight: 32

                    Binding {
                        target: uiScaleSlider
                        property: "value"
                        value: languageCard.view.bridge ? Math.round(languageCard.view.bridge.uiScale * 100) : 100
                        when: !uiScaleSlider.pressed
                    }

                    onMoved: {
                        if (languageCard.view.bridge) {
                            languageCard.view.bridge.uiScale = Math.round(value) / 100.0
                        }
                    }

                    background: Item {
                        x: uiScaleSlider.leftPadding
                        y: uiScaleSlider.topPadding + uiScaleSlider.availableHeight / 2 - height / 2
                        width: uiScaleSlider.availableWidth
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
                            width: Math.max(6, uiScaleSlider.visualPosition * parent.width)
                            height: parent.height
                            radius: 3
                            color: "#38BDF8"
                        }
                    }

                    handle: Item {
                        x: uiScaleSlider.leftPadding + uiScaleSlider.visualPosition * (uiScaleSlider.availableWidth - width)
                        y: uiScaleSlider.topPadding + uiScaleSlider.availableHeight / 2 - height / 2
                        width: 28; height: 28

                        scale: uiScaleSlider.pressed ? 1.25 : (uiScaleSlider.hovered ? 1.12 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.30; mass: 0.6; epsilon: 0.005 } }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 28; height: 28; radius: 14
                            color: "transparent"
                            border.color: "#38BDF8"
                            border.width: 1
                            opacity: (uiScaleSlider.pressed || uiScaleSlider.hovered) ? 0.5 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 16; height: 16; radius: 8
                            color: "#38BDF8"
                        }
                    }
                }

                // Value chip
                Rectangle {
                    implicitWidth: Math.max(54, scaleValText.implicitWidth + 18)
                    height: 26; radius: 13
                    color: "#0C1828"
                    border.color: (languageCard.view.bridge && languageCard.view.bridge.uiScaleRestartNeeded) ? "#F59E0B" : "#164E63"
                    border.width: 1

                    Text {
                        id: scaleValText
                        anchors.centerIn: parent
                        text: (languageCard.view.bridge ? Math.round(languageCard.view.bridge.uiScale * 100) : Math.round(uiScaleSlider.value)) + "%"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: (languageCard.view.bridge && languageCard.view.bridge.uiScaleRestartNeeded) ? "#FBBF24" : "#38BDF8"
                    }
                }

                // Reset button (resets to 100%)
                Rectangle {
                    height: 26
                    implicitWidth: resetScaleRow.implicitWidth + 14
                    radius: 5
                    color: resetScaleMouse.containsMouse ? "#1E293B" : "#141A26"
                    border.color: "#283042"
                    border.width: 1
                    visible: languageCard.view.bridge ? (Math.round(languageCard.view.bridge.uiScale * 100) !== 100) : false

                    Row {
                        id: resetScaleRow
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            text: "↺"
                            font.pixelSize: 11
                            color: "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "100%"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            font.weight: 600
                            color: "#CBD5E1"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: resetScaleMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: languageCard.view.tr("btn_reset_scale", "Reset UI scale to default 100%")
                        onClicked: {
                            if (languageCard.view.bridge) languageCard.view.bridge.uiScale = 1.0
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }
        }

        // Quick Preset Pills (wrapping Flow to guarantee no horizontal overflow)
        Flow {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: languageCard.view.tr("label_presets", "Presets:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 600
                color: "#64748B"
                height: 22
                verticalAlignment: Text.AlignVCenter
            }

            Repeater {
                model: [100, 125, 150, 175, 200, 250]
                Rectangle {
                    id: presetPill
                    readonly property int pct: modelData
                    readonly property bool isSelected: languageCard.view.bridge ? (Math.round(languageCard.view.bridge.uiScale * 100) === pct) : (pct === 100)
                    implicitWidth: pillText.implicitWidth + 14
                    height: 22
                    radius: 11
                    color: isSelected ? "#0369A1" : (presetMouse.containsMouse ? "#1E293B" : "#141A26")
                    border.color: isSelected ? "#38BDF8" : (presetMouse.containsMouse ? "#334155" : "#233147")
                    border.width: 1

                    Text {
                        id: pillText
                        anchors.centerIn: parent
                        text: presetPill.pct + "%"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        font.weight: presetPill.isSelected ? 700 : 500
                        color: presetPill.isSelected ? "#FFFFFF" : "#94A3B8"
                    }

                    MouseArea {
                        id: presetMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (languageCard.view.bridge) {
                                languageCard.view.bridge.uiScale = presetPill.pct / 100.0
                            }
                        }
                    }
                }
            }
        }

        // Restart banner when UI Scale changes (responsive column layout with non-overflowing button)
        Rectangle {
            Layout.fillWidth: true
            visible: languageCard.view.bridge ? languageCard.view.bridge.uiScaleRestartNeeded : false
            implicitHeight: restartScaleCol.implicitHeight + 20
            radius: 6
            color: "#261908"
            border.color: "#D97706"
            border.width: 1

            ColumnLayout {
                id: restartScaleCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "⚠️"
                        font.pixelSize: 15
                        Layout.alignment: Qt.AlignTop
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: languageCard.view.tr("ui_scale_restart_notice", "Display scale will take effect after restarting (Active: %1% → New: %2%)")
                                  .arg(languageCard.view.bridge ? Math.round(languageCard.view.bridge.activeUiScale * 100) : 100)
                                  .arg(languageCard.view.bridge ? Math.round(languageCard.view.bridge.uiScale * 100) : 100)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: 600
                            color: "#FDE68A"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: languageCard.view.tr("ui_scale_restart_sub", "Click Restart Now to apply the new interface scale immediately.")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 10
                            color: "#D97706"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Action button row: always stays within the card bounds
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 25

                    Rectangle {
                        id: restartScaleBtn
                        objectName: "restartScaleBtn"
                        Layout.preferredHeight: 28
                        Layout.preferredWidth: restartScaleBtnText.implicitWidth + 24
                        radius: 5
                        color: restartScaleMouse.containsMouse ? "#D97706" : "#B45309"
                        border.color: "#F59E0B"
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: "⚡"
                                font.pixelSize: 11
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                id: restartScaleBtnText
                                text: languageCard.view.tr("btn_restart_now", "Restart Now")
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 700
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            id: restartScaleMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (languageCard.view.bridge) languageCard.view.bridge.restartApplication()
                            }
                        }
                    }
                }
            }
        }
    }
}
