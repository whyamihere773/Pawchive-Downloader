import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string service: "patreon"
    property bool showLabel: true
    property int badgeHeight: 20

    readonly property string normalizedService: (service || "patreon").toLowerCase().trim()

    readonly property string serviceLabel: {
        switch (normalizedService) {
            case "onlyfans": return "ONLYFANS"
            case "fansly": return "FANSLY"
            case "patreon": return "PATREON"
            case "fanbox": return "FANBOX"
            case "gumroad": return "GUMROAD"
            case "subscribestar": return "SUBSCRIBESTAR"
            case "fantia": return "FANTIA"
            case "boosty": return "BOOSTY"
            case "candfans": return "CANDFANS"
            case "discord": return "DISCORD"
            case "dlsite": return "DLSITE"
            case "afdian": return "AFDIAN"
            default: return normalizedService.toUpperCase()
        }
    }

    readonly property color serviceColor: {
        switch (normalizedService) {
            case "onlyfans": return "#00AFF0"
            case "fansly": return "#FF6B9D"
            case "patreon": return "#FF424D"
            case "fanbox": return "#007AFF"
            case "gumroad": return "#36C5AB"
            case "subscribestar": return "#5C9DFF"
            case "fantia": return "#E84393"
            case "boosty": return "#F76A23"
            case "candfans": return "#FF577F"
            case "discord": return "#5865F2"
            case "dlsite": return "#2563EB"
            case "afdian": return "#9466FF"
            default: return "#64748B"
        }
    }

    readonly property color serviceBg: Qt.rgba(serviceColor.r, serviceColor.g, serviceColor.b, 0.14)

    height: badgeHeight
    implicitWidth: badgeRow.implicitWidth + 14
    radius: height / 2
    color: mouseArea.containsMouse ? Qt.rgba(serviceColor.r, serviceColor.g, serviceColor.b, 0.25) : serviceBg
    border.color: serviceColor
    border.width: 1

    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        id: badgeRow
        anchors.centerIn: parent
        spacing: 5

        Image {
            id: iconImg
            source: "../../assets/icons/services/" + root.normalizedService + ".svg"
            width: 13
            height: 13
            sourceSize: Qt.size(13, 13)
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            id: labelText
            visible: root.showLabel
            text: root.serviceLabel
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 9
            font.weight: Font.Bold
            color: root.serviceColor
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        ToolTip.visible: containsMouse
        ToolTip.delay: 250
        ToolTip.text: "Platform: " + root.serviceLabel
    }
}
