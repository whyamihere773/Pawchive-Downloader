import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: subTab1Content
    required property var view
    function tr(key, fallback) { return view ? view.tr(key, fallback) : (fallback !== undefined ? fallback : key) }
    visible: subTab1Content.view.currentSubTab === 1
    Layout.fillWidth: true
    spacing: 12

// Network & Authentication
CardSection {
    Layout.fillWidth: true
    interactive: !subTab1Content.view.isScrolling
    title: tr("section_network", "Network & Authentication (Cloudflare / Cookies)")
    iconText: "🌐"
    entranceOffsetY: subTab1Content.view.tabEntranceOffsetY
    entranceOpacity: subTab1Content.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: 10

        Text {
            text: tr("label_cookie", "Session Cookie (Useful for Patreon / Fanbox / Cloudflare bypass):")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            wrapMode: Text.WordWrap
        }

        StyledTextField {
            Layout.fillWidth: true
            placeholderText: tr("placeholder_cookie", "e.g., session=eyJhbGci... or cf_clearance=...")
            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.cookieString : ""
            onTextChanged: if (subTab1Content.view.bridge && subTab1Content.view.bridge.cookieString !== text) subTab1Content.view.bridge.cookieString = text
        }

        // 1-Click Browser Cookie Importer & Expiration Watchdog
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: cookieHelperCol.implicitHeight + 20
            radius: 8
            color: "#141A26"
            border.color: cookieBoxHover.hovered ? "#38BDF8" : "#233147"
            border.width: 1

            HoverHandler { id: cookieBoxHover }

            transform: Translate {
                y: cookieBoxHover.hovered ? -1.5 : 0
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.9; epsilon: 0.25 }
                }
            }

            Behavior on border.color { ColorAnimation { duration: 160 } }

            ColumnLayout {
                id: cookieHelperCol
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text { text: "🍪"; font.pixelSize: 13 }
                    Text {
                        text: tr("cookie_importer_title", "1-Click Browser Session Importer")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#F1F5F9"
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    // Real-time Expiration Watchdog Badge
                    Rectangle {
                        height: 20
                        Layout.preferredWidth: Math.min(watchdogLabel.implicitWidth + 16, 180)
                        Layout.minimumWidth: 0
                        Layout.maximumWidth: 180
                        radius: 10
                        color: "#0F172A"
                        border.color: subTab1Content.view.bridge ? subTab1Content.view.bridge.cookieWatchdogColor : "#64748B"
                        border.width: 1
                        clip: true

                        Row {
                            anchors.centerIn: parent
                            spacing: 5
                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: subTab1Content.view.bridge ? subTab1Content.view.bridge.cookieWatchdogColor : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                id: watchdogLabel
                                text: subTab1Content.view.bridge ? subTab1Content.view.bridge.cookieWatchdogText : tr("cookie_status_none", "No session cookie")
                                font.pixelSize: 10
                                font.weight: 600
                                color: subTab1Content.view.bridge ? subTab1Content.view.bridge.cookieWatchdogColor : "#94A3B8"
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }
                    }
                }

                Text {
                    text: tr("cookie_importer_desc", "Extracts authenticated Kemono/Patreon session cookies directly from your installed browser without locking open sessions or requiring manual DevTools copying.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // Browser selector row
                Flow {
                    width: parent.width
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    ComboBox {
                        id: browserSelector
                        width: Math.min(parent.width, 190)
                        height: 30
                        model: [
                            { id: "",         name: tr("browser_auto",    "Auto-Detect") },
                            { id: "firefox",  name: tr("browser_firefox", "Mozilla Firefox (Recommended)") },
                            { id: "edge",     name: tr("browser_edge",    "Microsoft Edge") },
                            { id: "brave",    name: tr("browser_brave",   "Brave Browser") },
                            { id: "operagx",  name: tr("browser_operagx", "Opera GX") },
                            { id: "opera",    name: tr("browser_opera",   "Opera") },
                            { id: "chrome",   name: tr("browser_chrome",  "Google Chrome") }
                        ]
                        textRole: "name"
                        valueRole: "id"
                        currentIndex: 0

                        background: Rectangle {
                            color: "#141923"
                            border.color: browserSelector.activeFocus ? "#38BDF8" : "#283042"
                            border.width: 1
                            radius: 6
                        }

                        contentItem: Text {
                            leftPadding: 10
                            rightPadding: browserSelector.indicator.width + 10
                            text: browserSelector.displayText
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        indicator: Canvas {
                            id: browserSelectorArrow
                            x: browserSelector.width - width - 8
                            y: (browserSelector.height - height) / 2
                            width: 10; height: 6
                            contextType: "2d"
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                ctx.fillStyle = "#94A3B8"
                                ctx.beginPath()
                                ctx.moveTo(0, 0)
                                ctx.lineTo(width, 0)
                                ctx.lineTo(width / 2, height)
                                ctx.closePath()
                                ctx.fill()
                            }
                        }

                        popup: Popup {
                            y: browserSelector.height + 2
                            width: browserSelector.width
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
                                implicitHeight: Math.min(contentHeight, 260)
                                model: browserSelector.popup.visible ? browserSelector.delegateModel : null
                                currentIndex: browserSelector.highlightedIndex
                                ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
                            }
                        }

                        delegate: ItemDelegate {
                            width: browserSelector.width - 8
                            height: 30
                            highlighted: browserSelector.highlightedIndex === index
                            contentItem: Text {
                                text: modelData.name
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

                    StyledButton {
                        id: importCookieBtn
                        text: tr("btn_import_cookies", "Import from Browser")
                        iconText: subTab1Content.view.importingCookies ? "⏳" : "⚡"
                        variant: "primary"
                        enabled: !subTab1Content.view.importingCookies
                        opacity: subTab1Content.view.importingCookies ? 0.7 : 1.0
                        onClicked: {
                            var bid = browserSelector.model[browserSelector.currentIndex].id
                            subTab1Content.view.importingCookies = true
                            subTab1Content.view.cookieStatusText = tr("cookie_importing", "Importing…")
                            subTab1Content.view.cookieStatusColor = "#94A3B8"
                            if (subTab1Content.view.bridge) subTab1Content.view.bridge.importBrowserCookies(bid)
                        }
                    }
                }

                // Import status feedback
                Text {
                    id: cookieImportStatus
                    Layout.fillWidth: true
                    text: subTab1Content.view.cookieStatusText
                    color: subTab1Content.view.cookieStatusColor
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    wrapMode: Text.WordWrap
                    visible: subTab1Content.view.cookieStatusText !== ""
                    Behavior on opacity { NumberAnimation { duration: 150 } }
                }

                // Connections for import result
                Connections {
                    target: subTab1Content.view.bridge
                    function onCookieImportCompleted(success, message) {
                        subTab1Content.view.importingCookies = false
                        if (success) {
                            subTab1Content.view.cookieStatusText = "✔ Imported from " + message
                            subTab1Content.view.cookieStatusColor = "#10B981"
                        } else {
                            subTab1Content.view.cookieStatusText = "✘ " + message
                            subTab1Content.view.cookieStatusColor = "#F87171"
                        }
                    }
                }
            }
        }

        Text {
            text: tr("label_user_agent", "Custom User-Agent:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
        }

        StyledTextField {
            Layout.fillWidth: true
            placeholderText: tr("placeholder_user_agent", "Leave blank for default Chromium browser header")
            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.userAgent : ""
            onTextChanged: if (subTab1Content.view.bridge && subTab1Content.view.bridge.userAgent !== text) subTab1Content.view.bridge.userAgent = text
        }

        Text {
            text: tr("label_proxy", "HTTP / HTTPS / SOCKS5 Proxy:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
        }

        StyledTextField {
            Layout.fillWidth: true
            placeholderText: tr("placeholder_proxy", "e.g., http://127.0.0.1:8080 or socks5://127.0.0.1:1080")
            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.proxyUrl : ""
            onTextChanged: if (subTab1Content.view.bridge && subTab1Content.view.bridge.proxyUrl !== text) subTab1Content.view.bridge.proxyUrl = text
        }
    }
}

// Download Speed Cap / Bandwidth Limiter
CardSection {
    Layout.fillWidth: true
    interactive: !subTab1Content.view.isScrolling
    title: tr("section_bandwidth_limit", "Download Speed Cap / Bandwidth Limiter")
    iconText: "⚡"
    entranceOffsetY: subTab1Content.view.tabEntranceOffsetY
    entranceOpacity: subTab1Content.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        Layout.fillWidth: true
        spacing: 12

        // Row 1: Enable Toggle Switch
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: tr("opt_bandwidth_limit_title", "Limit Maximum Download Speed")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#F1F5F9"
                }

                Text {
                    text: tr("opt_bandwidth_limit_desc", "Restricts aggregate download throughput across all threads, multipart chunks, and external tools to stay strictly below your cap.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }

            StyledSwitch {
                id: bandwidthSwitch
                checked: subTab1Content.view.bridge ? subTab1Content.view.bridge.bandwidthLimitEnabled : false
                onToggled: function(isChecked) {
                    if (subTab1Content.view.bridge) subTab1Content.view.bridge.bandwidthLimitEnabled = isChecked
                }
            }
        }

        // Row 2: Speed input, unit selector, and quick presets (active when switch is on)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: limitConfigCol.implicitHeight + 20
            radius: 8
            color: "#141A26"
            border.color: subTab1Content.view.bridge && subTab1Content.view.bridge.bandwidthLimitEnabled ? "#38BDF8" : "#233147"
            border.width: 1
            opacity: (subTab1Content.view.bridge && subTab1Content.view.bridge.bandwidthLimitEnabled) ? 1.0 : 0.5
            enabled: subTab1Content.view.bridge && subTab1Content.view.bridge.bandwidthLimitEnabled

            Behavior on border.color { ColorAnimation { duration: 160 } }
            Behavior on opacity { NumberAnimation { duration: 150 } }

            ColumnLayout {
                id: limitConfigCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: tr("label_max_speed", "Maximum Speed:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#E2E8F0"
                    }

                    StyledTextField {
                        id: limitValField
                        Layout.preferredWidth: 100
                        text: subTab1Content.view.bridge ? ("" + subTab1Content.view.bridge.bandwidthLimitValue) : "10"
                        placeholderText: "10"
                        onEditingFinished: {
                            if (subTab1Content.view.bridge) {
                                var v = parseFloat(text)
                                if (!isNaN(v) && v > 0) {
                                    subTab1Content.view.bridge.bandwidthLimitValue = v
                                } else {
                                    text = "" + subTab1Content.view.bridge.bandwidthLimitValue
                                }
                            }
                        }
                    }

                    StyledComboBox {
                        id: unitCombo
                        Layout.preferredWidth: 160
                        model: [
                            { text: "MB/s (MegaBytes)", value: "MB/s" },
                            { text: "mbps (Megabits)", value: "mbps" }
                        ]
                        value: subTab1Content.view.bridge ? subTab1Content.view.bridge.bandwidthLimitUnit : "MB/s"
                        onValuePicked: function(val) {
                            if (subTab1Content.view.bridge) subTab1Content.view.bridge.bandwidthLimitUnit = val
                        }
                    }

                    Item { Layout.fillWidth: true }
                }

                // Quick Presets Row
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: tr("label_presets", "Quick Presets:")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#64748B"
                    }

                    Repeater {
                        model: (subTab1Content.view.bridge && subTab1Content.view.bridge.bandwidthLimitUnit === "mbps")
                            ? [ { l: "10 mbps", v: 10 }, { l: "25 mbps", v: 25 }, { l: "50 mbps", v: 50 }, { l: "100 mbps", v: 100 }, { l: "250 mbps", v: 250 } ]
                            : [ { l: "2 MB/s", v: 2 }, { l: "5 MB/s", v: 5 }, { l: "10 MB/s", v: 10 }, { l: "25 MB/s", v: 25 }, { l: "50 MB/s", v: 50 } ]

                        Rectangle {
                            implicitWidth: presetLabel.implicitWidth + 14
                            implicitHeight: 24
                            radius: 12
                            color: presetMouse.containsMouse ? "#1E293B" : "#0F172A"
                            border.color: (subTab1Content.view.bridge && Math.abs(subTab1Content.view.bridge.bandwidthLimitValue - modelData.v) < 0.01) ? "#38BDF8" : "#334155"
                            border.width: 1

                            Text {
                                id: presetLabel
                                anchors.centerIn: parent
                                text: modelData.l
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 10
                                font.bold: (subTab1Content.view.bridge && Math.abs(subTab1Content.view.bridge.bandwidthLimitValue - modelData.v) < 0.01)
                                color: (subTab1Content.view.bridge && Math.abs(subTab1Content.view.bridge.bandwidthLimitValue - modelData.v) < 0.01) ? "#38BDF8" : "#94A3B8"
                            }

                            MouseArea {
                                id: presetMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (subTab1Content.view.bridge) {
                                        subTab1Content.view.bridge.bandwidthLimitValue = modelData.v
                                        limitValField.text = "" + modelData.v
                                    }
                                }
                            }
                        }
                    }
                }

                // Live Summary Indicator Badge
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 28
                    radius: 6
                    color: "#0B1120"
                    border.color: "#1E293B"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 6

                        Text {
                            text: "⚡"
                            font.pixelSize: 11
                        }

                        Text {
                            text: tr("label_effective_limit", "Effective Limit:")
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: "#94A3B8"
                        }

                        Text {
                            text: subTab1Content.view.bridge ? subTab1Content.view.bridge.bandwidthLimitSummary : "Unlimited"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.bold: true
                            color: "#38BDF8"
                        }

                        Item { Layout.fillWidth: true }
                    }
                }
            }
        }
    }
}

}
