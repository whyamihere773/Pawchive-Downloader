import QtQuick
import QtQuick.Controls

// Dropdown styled like the ones in Settings. model: [{ text: "...", value: "..." }, ...]
ComboBox {
    id: control

    property string value: ""            // the selected item's value
    property string tooltip: ""
    signal valuePicked(string value)

    textRole: "text"
    valueRole: "value"
    implicitHeight: 30
    implicitWidth: 170
    hoverEnabled: true

    currentIndex: {
        for (var i = 0; i < (model ? model.length : 0); i++) {
            if (model[i].value === control.value) return i
        }
        return 0
    }
    onActivated: function(index) {
        if (model && model[index]) control.valuePicked(model[index].value)
    }

    ToolTip {
        text: control.tooltip
        visible: control.tooltip.length > 0 && control.hovered && !control.popup.visible
        delay: 400
        timeout: 5000
    }

    background: Rectangle {
        color: control.hovered ? "#1A2130" : "#141923"
        border.color: (control.activeFocus || control.popup.visible) ? "#38BDF8" : "#283042"
        border.width: 1
        radius: 6
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    contentItem: Text {
        leftPadding: 10
        rightPadding: control.indicator.width + 14
        text: control.displayText
        font.family: "Segoe UI, sans-serif"
        font.pixelSize: 11
        color: "#F1F5F9"
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Canvas {
        x: control.width - width - 9
        y: (control.height - height) / 2
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
        y: control.height + 2
        width: Math.max(control.width, 160)
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
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }
    }

    delegate: ItemDelegate {
        width: control.popup.width - 8
        height: 30
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: modelData.text
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            font.weight: control.currentIndex === index ? Font.DemiBold : Font.Normal
            color: (highlighted || control.currentIndex === index) ? "#38BDF8" : "#CBD5E1"
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: highlighted ? "#1E293B" : "transparent"
            radius: 4
        }
    }
}
