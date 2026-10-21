import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string provider: ""
    property string domain: ""
    property bool showLabel: true
    property int badgeHeight: 20

    readonly property string effectiveProvider: {
        var p = (provider || "").toLowerCase().trim()
        if (p === "pawchive" || p === "cumst" || p === "kemono" || p === "coomer") return p
        var d = (domain || "").toLowerCase()
        if (d.indexOf("cum.st") !== -1 || d.indexOf("cumst") !== -1) return "cumst"
        if (d.indexOf("coomer") !== -1) return "coomer"
        if (d.indexOf("kemono") !== -1) return "kemono"
        return "pawchive"
    }

    readonly property string providerName: {
        switch (effectiveProvider) {
            case "cumst": return "cum.st"
            case "kemono": return "Kemono"
            case "coomer": return "Coomer"
            default: return "Pawchive"
        }
    }

    readonly property color providerColor: {
        switch (effectiveProvider) {
            case "cumst": return "#38BDF8"    // Sky blue
            case "kemono": return "#F59E0B"   // Amber
            case "coomer": return "#818CF8"   // Indigo
            default: return "#10B981"         // Emerald
        }
    }

    readonly property color providerBg: {
        switch (effectiveProvider) {
            case "cumst": return "#082636"
            case "kemono": return "#2B1B06"
            case "coomer": return "#1B1B36"
            default: return "#07271F"
        }
    }

    height: badgeHeight
    implicitWidth: badgeRow.implicitWidth + 14
    radius: height / 2
    color: mouseArea.containsMouse ? Qt.lighter(providerBg, 1.25) : providerBg
    border.color: providerColor
    border.width: 1

    Behavior on color { ColorAnimation { duration: 120 } }

    Row {
        id: badgeRow
        anchors.centerIn: parent
        spacing: 5

        Image {
            id: iconImg
            source: "../../assets/icons/providers/" + root.effectiveProvider + ".svg"
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
            text: root.providerName
            font.family: "Segoe UI, Inter, sans-serif"
            font.pixelSize: 9
            font.weight: Font.Bold
            color: root.providerColor
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        ToolTip.visible: containsMouse
        ToolTip.delay: 250
        ToolTip.text: "Source Archive: " + root.providerName + (root.domain ? " (" + root.domain + ")" : "")
    }
}
