import QtQuick
import QtQuick.Controls

// Individual tab pill in the main top tab strip.
Rectangle {
    id: tabBtn
    required property var window
    required property int tabIdx
    property string tabKey: ""
    property string iconText: ""
    property string labelText: ""
    property string tipText: ""
    property color activeBorderColor: "#38BDF8"
    property bool alwaysPermitted: false
    property int badgeCount: 0
    property color badgeColor: "#0284C7"

    readonly property bool tabPermitted: alwaysPermitted || (!window.tabsVaulted && (tabKey === "" || !window.isTabDisabled(tabKey)))
    readonly property bool isActive: window.currentTab === tabIdx

    visible: alwaysPermitted ? true : (width > 0.5)
    clip: !alwaysPermitted
    width: tabPermitted ? (tabInnerRow.implicitWidth + 18) : 0
    opacity: tabPermitted ? 1.0 : 0.0
    height: 30
    radius: 6
    color: isActive ? "#181B22" : (tabMouse.containsMouse ? "#141720" : "transparent")
    border.color: isActive ? activeBorderColor : "transparent"
    border.width: 1

    scale: tabMouse.pressed ? 0.94 : (tabMouse.containsMouse ? 1.035 : (tabPermitted ? 1.0 : 0.8))
    transformOrigin: Item.Center

    Behavior on width {
        enabled: !tabBtn.alwaysPermitted
        NumberAnimation {
            duration: tabBtn.tabPermitted ? 280 : 180
            easing.type: tabBtn.tabPermitted ? Easing.OutBack : Easing.InQuad
            easing.overshoot: 1.3
        }
    }
    Behavior on opacity {
        enabled: !tabBtn.alwaysPermitted
        NumberAnimation { duration: tabBtn.tabPermitted ? 240 : 140; easing.type: Easing.OutCubic }
    }
    Behavior on scale {
        NumberAnimation { duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.5 }
    }
    Behavior on color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: 150; easing.type: Easing.OutCubic } }

    Row {
        id: tabInnerRow
        anchors.centerIn: parent
        spacing: 6
        Text { text: tabBtn.iconText; font.pixelSize: 12 }
        Text {
            text: tabBtn.labelText
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            font.weight: tabBtn.isActive ? 600 : Font.Normal
            color: tabBtn.isActive ? "#F8FAFC" : "#94A3B8"
        }
        Rectangle {
            visible: tabBtn.badgeCount > 0
            width: Math.max(16, badgeTxt.implicitWidth + 8)
            height: 16
            radius: 8
            color: tabBtn.badgeColor
            anchors.verticalCenter: parent.verticalCenter

            Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutBack } }

            Text {
                id: badgeTxt
                anchors.centerIn: parent
                text: tabBtn.badgeCount
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 9
                font.weight: Font.Bold
                color: "#FFFFFF"
            }
        }
    }

    MouseArea {
        id: tabMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        ToolTip.visible: containsMouse
        ToolTip.delay: 400
        ToolTip.text: tabBtn.tipText
        onClicked: tabBtn.window.currentTab = tabBtn.tabIdx
    }
}
