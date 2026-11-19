import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Creator Name Banner shown with spring entrance after URL resolves.
Item {
    id: bannerRoot
    required property var window
    Layout.fillWidth: true
    Layout.preferredHeight: 28 * bannerRoot.window.chromeProgress
    visible: creatorBanner.hasCreator && bannerRoot.window.chromeProgress > 0
    opacity: bannerRoot.window.chromeOpacity
    clip: bannerRoot.window.chromeMoving

    Rectangle {
        id: creatorBanner
        width: parent.width
        height: 28
        anchors.bottom: parent.bottom
        transform: Translate { y: -16 * bannerRoot.window.chromeSlide }
        property bool hasCreator: appBridge ? appBridge.creatorName.length > 0 : false
        visible: hasCreator
        color: "#0D1019"
        border.color: "#25334D"
        border.width: 1
        radius: 6
        clip: true

        opacity: hasCreator ? 1.0 : 0.0
        scale: hasCreator ? 1.0 : 0.95
        transformOrigin: Item.Center

        Behavior on opacity {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }
        Behavior on scale {
            NumberAnimation { duration: 260; easing.type: Easing.OutBack; easing.overshoot: 1.3 }
        }
        Behavior on border.color {
            ColorAnimation { duration: 200 }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 8

            Text {
                text: "👤"
                font.pixelSize: 12
                scale: (appBridge && appBridge.creatorName.length > 0) ? 1.0 : 0.2
                Behavior on scale {
                    NumberAnimation { duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.8 }
                }
            }

            Text {
                text: bannerRoot.window.tr("label_creator", "Creator:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
            }

            Text {
                text: appBridge ? appBridge.creatorName : ""
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.weight: 600
                color: "#38BDF8"
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            // Service tag if in URL
            Rectangle {
                implicitHeight: 20
                implicitWidth: svcTag.implicitWidth + 14
                Layout.preferredHeight: 20
                Layout.preferredWidth: svcTag.implicitWidth + 14
                Layout.alignment: Qt.AlignVCenter
                radius: 4
                color: "#1A2030"
                border.color: "#2D3748"
                border.width: 1
                visible: appBridge ? (appBridge.currentUrl.length > 0 && svcTag.text.length > 0) : false

                Text {
                    id: svcTag
                    anchors.centerIn: parent
                    text: {
                        if (!appBridge) return ""
                        var u = appBridge.currentUrl.toLowerCase()
                        if (u.indexOf("/fanbox/") >= 0) return "Fanbox"
                        if (u.indexOf("/patreon/") >= 0) return "Patreon"
                        if (u.indexOf("/onlyfans/") >= 0) return "OnlyFans"
                        if (u.indexOf("/fansly/") >= 0) return "Fansly"
                        if (u.indexOf("/gumroad/") >= 0) return "Gumroad"
                        if (u.indexOf("/subscribestar/") >= 0) return "SubscribeStar"
                        if (u.indexOf("/fantia/") >= 0) return "Fantia"
                        if (u.indexOf("/boosty/") >= 0) return "Boosty"
                        if (u.indexOf("/dlsite/") >= 0) return "DLsite"
                        if (u.indexOf("/discord/") >= 0) return "Discord"
                        if (u.indexOf("bunkr") >= 0) return "Bunkr"
                        if (u.indexOf("erome") >= 0) return "Erome"
                        if (u.indexOf("nhentai") >= 0) return "nHentai"
                        if (u.indexOf("saint2") >= 0) return "Saint2"
                        if (u.indexOf("telegram") >= 0 || u.indexOf("t.me") >= 0) return "Telegram"
                        return ""
                    }
                    font.pixelSize: 9
                    font.bold: true
                    color: "#94A3B8"
                }
            }
        }
    }
}
