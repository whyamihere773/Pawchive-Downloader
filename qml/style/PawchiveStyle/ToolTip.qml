import QtQuick
import QtQuick.Templates as T

T.ToolTip {
    id: control

    x: parent ? Math.round((parent.width - implicitWidth) / 2) : 0
    y: -implicitHeight - 8

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            contentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             contentHeight + topPadding + bottomPadding)

    margins: 6
    padding: 8
    topPadding: 6
    bottomPadding: 6
    leftPadding: 10
    rightPadding: 10

    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: 150; easing.type: Easing.OutCubic }
        NumberAnimation { property: "scale"; from: 0.95; to: 1.0; duration: 150; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: 120; easing.type: Easing.InCubic }
    }

    contentItem: Text {
        text: control.text
        font.family: "Segoe UI, Inter, sans-serif"
        font.pixelSize: 11
        font.weight: Font.Normal
        color: "#F1F5F9"
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }

    background: Rectangle {
        color: "#141924"
        border.color: "#38BDF8"
        border.width: 1
        radius: 6
    }
}
