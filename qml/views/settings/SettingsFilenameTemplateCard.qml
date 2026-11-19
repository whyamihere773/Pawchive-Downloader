import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: filenameTemplateCard
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    Layout.fillWidth: true
    implicitHeight: filenameCol.implicitHeight + 22
    radius: 8
    color: "#141A26"
    border.color: filenameBoxHover.hovered ? "#38BDF8" : "#233147"
    border.width: 1

    HoverHandler { id: filenameBoxHover }

    transform: Translate {
        y: filenameBoxHover.hovered ? -1.5 : 0
        Behavior on y {
            SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
        }
    }

    Behavior on border.color { ColorAnimation { duration: 160 } }

    ColumnLayout {
        id: filenameCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        spacing: 10

        // Title Row
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            Text {
                text: "🏷️"
                font.pixelSize: 14
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                text: filenameTemplateCard.view.tr("label_filename_style", "Filename Formatting Pattern")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#F1F5F9"
                Layout.fillWidth: true
                Layout.preferredWidth: 0
                Layout.minimumWidth: 0
                elide: Text.ElideRight
            }
        }

        // Pattern Selector ComboBox (Full Width)
        ComboBox {
            id: filenameStyleCombo
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: 36

            ToolTip.visible: filenameStyleCombo.hovered && !filenameStyleCombo.popup.visible
            ToolTip.text: filenameTemplateCard.view.tr("tip_filename_pattern", "Choose how downloaded files are named and organized on your disk")
            ToolTip.delay: 450

                model: [
                    {
                        text: filenameTemplateCard.view.tr("style_post_title", "Post Title - Original (Default)"),
                        value: "post_title",
                        icon: "📄",
                        example: "Post Title - original_filename.jpg",
                        tag: filenameTemplateCard.view.tr("badge_default", "Default")
                    },
                    {
                        text: filenameTemplateCard.view.tr("style_original", "Original Filename Only"),
                        value: "original",
                        icon: "🏷️",
                        example: "original_filename.jpg (source name)",
                        tag: ""
                    },
                    {
                        text: filenameTemplateCard.view.tr("style_date_post_title", "Date - Post Title - Original"),
                        value: "date_post_title",
                        icon: "📅",
                        example: "2026-09-17 - Post Title - image.png",
                        tag: ""
                    },
                    {
                        text: filenameTemplateCard.view.tr("style_date_based", "Date Numbering"),
                        value: "date_based",
                        icon: "🔢",
                        example: "2026-09-17_001_01.png (chronological)",
                        tag: ""
                    },
                    {
                        text: filenameTemplateCard.view.tr("style_global_numbering", "Global Index + Post Title"),
                        value: "post_title_global_numbering",
                        icon: "🌐",
                        example: "001_Post Title_01.png",
                        tag: ""
                    },
                    {
                        text: filenameTemplateCard.view.tr("style_custom_template", "Custom Template…"),
                        value: "custom",
                        icon: "✨",
                        example: "Define tags: {artist}, {date}, {title}…",
                        tag: filenameTemplateCard.view.tr("badge_advanced", "Advanced")
                    }
                ]
                textRole: "text"
                valueRole: "value"

                currentIndex: {
                    if (!filenameTemplateCard.view.bridge) return 0
                    var cur = filenameTemplateCard.view.bridge.filenameStyle || "post_title"
                    for (var i = 0; i < model.length; i++) {
                        if (model[i].value === cur) return i
                    }
                    return 0
                }

                onActivated: function(index) {
                    var item = model[index]
                    if (filenameTemplateCard.view.bridge && item) {
                        filenameTemplateCard.view.bridge.filenameStyle = item.value
                    }
                }

                background: Rectangle {
                    radius: 7
                    color: filenameStyleCombo.pressed ? "#0A0E17" : (filenameStyleCombo.hovered ? "#131B2A" : "#0E1420")
                    border.color: (filenameStyleCombo.activeFocus || filenameStyleCombo.popup.visible)
                                  ? "#38BDF8"
                                  : (filenameStyleCombo.hovered ? "#3B5275" : "#233147")
                    border.width: (filenameStyleCombo.activeFocus || filenameStyleCombo.popup.visible) ? 1.5 : 1

                    Behavior on color { ColorAnimation { duration: 120 } }
                    Behavior on border.color { ColorAnimation { duration: 120 } }
                }

                contentItem: RowLayout {
                    spacing: 8
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 34

                    Text {
                        text: (filenameStyleCombo.model[filenameStyleCombo.currentIndex] && filenameStyleCombo.model[filenameStyleCombo.currentIndex].icon)
                              ? filenameStyleCombo.model[filenameStyleCombo.currentIndex].icon
                              : "🏷️"
                        font.pixelSize: 14
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: filenameStyleCombo.displayText
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: "#F1F5F9"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                    }
                }

                indicator: Item {
                    x: filenameStyleCombo.width - width - 10
                    y: (filenameStyleCombo.height - height) / 2
                    width: 18
                    height: 18

                    Text {
                        anchors.centerIn: parent
                        text: "▾"
                        font.pixelSize: 14
                        color: filenameStyleCombo.popup.visible ? "#38BDF8" : (filenameStyleCombo.hovered ? "#94A3B8" : "#64748B")
                        rotation: filenameStyleCombo.popup.visible ? 180 : 0
                        transformOrigin: Item.Center

                        Behavior on rotation {
                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }
                        Behavior on color {
                            ColorAnimation { duration: 120 }
                        }
                    }
                }

                popup: Popup {
                    y: filenameStyleCombo.height + 4
                    width: filenameStyleCombo.width
                    implicitHeight: Math.min(contentItem.implicitHeight + 12, 330)
                    padding: 5
                    transformOrigin: Popup.Top

                    enter: Transition {
                        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                        NumberAnimation { property: "scale"; from: 0.96; to: 1.0; duration: 140; easing.type: Easing.OutCubic }
                    }
                    exit: Transition {
                        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 100; easing.type: Easing.InCubic }
                    }

                    background: Rectangle {
                        color: "#0E1420"
                        border.color: "#25354C"
                        border.width: 1.5
                        radius: 8
                    }

                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: filenameStyleCombo.popup.visible ? filenameStyleCombo.delegateModel : null
                        currentIndex: filenameStyleCombo.highlightedIndex
                        boundsBehavior: Flickable.StopAtBounds
                        spacing: 2
                        ScrollBar.vertical: ScrollBar {
                            active: true
                            policy: ScrollBar.AsNeeded
                        }
                    }
                }

                delegate: ItemDelegate {
                    id: itemDel
                    width: filenameStyleCombo.popup.width - 10
                    height: 48
                    highlighted: filenameStyleCombo.highlightedIndex === index
                    hoverEnabled: true

                    readonly property bool isCurrent: filenameStyleCombo.currentIndex === index

                    background: Rectangle {
                        radius: 6
                        color: itemDel.isCurrent
                               ? "#14253D"
                               : (itemDel.hovered ? "#162030" : "transparent")
                        border.color: itemDel.isCurrent ? "#224A75" : (itemDel.hovered ? "#223147" : "transparent")
                        border.width: 1

                        // Left active indicator pill
                        Rectangle {
                            width: 3
                            height: 24
                            radius: 1.5
                            color: "#38BDF8"
                            anchors.left: parent.left
                            anchors.leftMargin: 2
                            anchors.verticalCenter: parent.verticalCenter
                            visible: itemDel.isCurrent
                        }

                        Behavior on color { ColorAnimation { duration: 100 } }
                    }

                    contentItem: RowLayout {
                        spacing: 9
                        anchors.fill: parent
                        anchors.leftMargin: itemDel.isCurrent ? 12 : 8
                        anchors.rightMargin: 10

                        // Icon container
                        Rectangle {
                            width: 28
                            height: 28
                            radius: 6
                            color: itemDel.isCurrent ? "#1E3352" : (itemDel.hovered ? "#1C273A" : "#121824")
                            border.color: itemDel.isCurrent ? "#38BDF8" : "#222D3E"
                            border.width: 1
                            Layout.alignment: Qt.AlignVCenter

                            Text {
                                anchors.centerIn: parent
                                text: modelData.icon || "🏷️"
                                font.pixelSize: 13
                            }
                        }

                        // Title + example subtitle
                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignVCenter

                            RowLayout {
                                spacing: 6
                                Layout.fillWidth: true

                                Text {
                                    text: modelData.text
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 11
                                    font.weight: itemDel.isCurrent ? Font.DemiBold : Font.Normal
                                    color: itemDel.isCurrent ? "#38BDF8" : (itemDel.hovered ? "#FFFFFF" : "#E2E8F0")
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                // Tag pill (e.g. Default / Advanced)
                                Rectangle {
                                    visible: modelData.tag && modelData.tag.length > 0
                                    height: 16
                                    implicitWidth: tagText.implicitWidth + 8
                                    radius: 4
                                    color: modelData.tag === "Default" ? "#0369A1" : "#334155"
                                    Layout.alignment: Qt.AlignVCenter

                                    Text {
                                        id: tagText
                                        anchors.centerIn: parent
                                        text: modelData.tag || ""
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        font.weight: Font.DemiBold
                                        color: "#FFFFFF"
                                    }
                                }
                            }

                            Text {
                                text: modelData.example || ""
                                font.family: "Consolas, Segoe UI, sans-serif"
                                font.pixelSize: 10
                                color: itemDel.isCurrent ? "#7DD3FC" : "#64748B"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        // Checkmark for current selection
                        Text {
                            text: "✓"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 13
                            font.weight: Font.Bold
                            color: "#38BDF8"
                            visible: itemDel.isCurrent
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }
            }

        // Newtonian Expanding Custom Template Editor
        Item {
            id: customTemplateExpand
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            width: parent.width
            readonly property bool isCustom: filenameTemplateCard.view.bridge ? filenameTemplateCard.view.bridge.filenameStyle === "custom" : false
            implicitHeight: isCustom ? (templateInnerCol.implicitHeight + 8) : 0
            clip: true
            visible: height > 0.5
            height: implicitHeight

            Behavior on height {
                SpringAnimation {
                    spring: 3.5
                    damping: 0.35
                    mass: 1.0
                    epsilon: 0.5
                }
            }

            ColumnLayout {
                id: templateInnerCol
                width: parent.width
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    StyledTextField {
                        id: templateInput
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        Layout.minimumWidth: 0
                        placeholderText: "{artist} - [{date}] - {title} - {orig_name}"
                        tooltip: filenameTemplateCard.view.tr("tip_template_input", "Enter custom pattern using tags below. Preview updates in real-time.")
                        text: filenameTemplateCard.view.bridge ? filenameTemplateCard.view.bridge.filenameTemplate : ""
                        onTextChanged: {
                            if (filenameTemplateCard.view.bridge && filenameTemplateCard.view.bridge.filenameTemplate !== text) {
                                filenameTemplateCard.view.bridge.filenameTemplate = text
                            }
                        }
                    }

                    StyledButton {
                        text: filenameTemplateCard.view.tr("btn_reset_template", "Reset")
                        tooltip: filenameTemplateCard.view.tr("tip_reset_template", "Reset filename template to: {title} - {orig_name}")
                        variant: "ghost"
                        implicitWidth: Math.max(65, contentItem.implicitWidth + 20)
                        implicitHeight: 32
                        onClicked: {
                            if (filenameTemplateCard.view.bridge) {
                                filenameTemplateCard.view.bridge.filenameTemplate = "{title} - {orig_name}"
                                templateInput.text = "{title} - {orig_name}"
                            }
                        }
                    }
                }

                // Clickable Tag Chips with Newtonian Press Bounce
                Flow {
                    width: templateInnerCol.width
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 6

                    Repeater {
                        model: [
                            { tag: "{title}", label: "Title" },
                            { tag: "{captionText}", label: "Caption / Description" },
                            { tag: "{post_id}", label: "Post ID" },
                            { tag: "{artist}", label: "Artist" },
                            { tag: "{date}", label: "Date (YYYY-MM-DD)" },
                            { tag: "{orig_name}", label: "Original Filename" },
                            { tag: "{name}", label: "Filename Stem" },
                            { tag: "{ext}", label: "Extension (.ext)" },
                            { tag: "{file_index}", label: "File Index (01)" },
                            { tag: "{post_index}", label: "Post Index (001)" }
                        ]

                        delegate: Rectangle {
                            height: 24
                            implicitWidth: chipRow.implicitWidth + 14
                            radius: 4
                            color: chipMouse.containsMouse ? "#1E293B" : "#0E141E"
                            border.color: chipMouse.containsMouse ? "#38BDF8" : "#233147"
                            border.width: 1

                            ToolTip.visible: chipMouse.containsMouse
                            ToolTip.text: modelData.label + " (" + modelData.tag + ")"
                            ToolTip.delay: 350

                            scale: chipMouse.pressed ? 0.94 : (chipMouse.containsMouse ? 1.05 : 1.0)
                            Behavior on scale { SpringAnimation { spring: 4.2; damping: 0.35; mass: 1.0 } }

                            Row {
                                id: chipRow
                                anchors.centerIn: parent
                                spacing: 4
                                Text { text: "+"; font.pixelSize: 10; color: "#38BDF8"; font.weight: Font.Bold }
                                Text {
                                    text: modelData.tag
                                    font.family: "Segoe UI, monospace"
                                    font.pixelSize: 11
                                    color: "#E2E8F0"
                                }
                            }

                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    var cur = templateInput.text || ""
                                    if (cur.length > 0 && !cur.endsWith(" ") && !cur.endsWith("-") && !cur.endsWith("_")) {
                                        cur += "_"
                                    }
                                    templateInput.text = cur + modelData.tag
                                }
                            }
                        }
                    }
                }

                // Live Preview Row
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 6

                    Text {
                        text: "👁️ " + filenameTemplateCard.view.tr("label_preview", "Live Preview:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#64748B"
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 0
                        Layout.minimumWidth: 0
                        text: filenameTemplateCard.view.bridge ? filenameTemplateCard.view.bridge.previewCustomFilename(templateInput.text) : ""
                        font.family: "Segoe UI, monospace"
                        font.pixelSize: 11
                        color: "#38BDF8"
                        elide: Text.ElideMiddle
                    }
                }
            }
        }
    }
}
