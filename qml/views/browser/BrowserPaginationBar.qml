import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: paginationBar
    required property var view
    objectName: "browserPaginationBar"
    Layout.fillWidth: true
    Layout.preferredHeight: 38
    radius: 8
    color: "#0F131C"
    border.color: "#1E2536"
    border.width: 1
    clip: true

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        Text {
            text: paginationBar.view.bBridge ? paginationBar.view.bBridge.statusText : ""
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            Layout.fillWidth: true
            Layout.minimumWidth: 30
            elide: Text.ElideRight
        }

        // Prev Page
        Rectangle {
            readonly property bool canPrev: paginationBar.view.hasSelectedCreator
                                            ? (paginationBar.view.bBridge && paginationBar.view.bBridge.creatorPostsOffset > 0)
                                            : (paginationBar.view.bBridge && paginationBar.view.bBridge.currentOffset > 0)
            Layout.preferredHeight: 28
            implicitWidth: 78
            radius: 6
            color: canPrev ? "#1E293B" : "#111622"
            opacity: canPrev ? 1.0 : 0.45
            Springy { hover: prevMouse.containsMouse; pressed: prevMouse.pressed }

            Text {
                anchors.centerIn: parent
                text: "‹ Previous"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#E2E8F0"
            }
            MouseArea {
                id: prevMouse
                anchors.fill: parent
                hoverEnabled: true
                enabled: parent.canPrev
                cursorShape: parent.canPrev ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    if (!paginationBar.view.bBridge) return
                    if (paginationBar.view.hasSelectedCreator) {
                        var stepPrev = paginationBar.view.bBridge.pageSize || 50
                        paginationBar.view.bBridge.loadCreatorPosts(Math.max(0, paginationBar.view.bBridge.creatorPostsOffset - stepPrev), paginationBar.view.creatorPostSearchText)
                    } else {
                        paginationBar.view.bBridge.prevPage()
                    }
                }
            }
        }

        Text {
            text: paginationBar.view.hasSelectedCreator
                  ? ("Offset " + (paginationBar.view.bBridge ? paginationBar.view.bBridge.creatorPostsOffset : 0))
                  : ("Page " + (paginationBar.view.bBridge ? paginationBar.view.bBridge.currentPage : 1) + " of " + (paginationBar.view.bBridge ? paginationBar.view.bBridge.totalPages : 1))
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            font.weight: Font.Bold
            color: "#F8FAFC"
        }

        // Next Page
        Rectangle {
            readonly property bool canNext: paginationBar.view.hasSelectedCreator
                                            ? (paginationBar.view.bBridge && paginationBar.view.bBridge.creatorPostsHasMore)
                                            : (paginationBar.view.bBridge && paginationBar.view.bBridge.hasMore)
            Layout.preferredHeight: 28
            implicitWidth: 68
            radius: 6
            color: canNext ? "#1E293B" : "#111622"
            opacity: canNext ? 1.0 : 0.45
            Springy { hover: nextMouse.containsMouse; pressed: nextMouse.pressed }

            Text {
                anchors.centerIn: parent
                text: "Next ›"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#E2E8F0"
            }
            MouseArea {
                id: nextMouse
                anchors.fill: parent
                hoverEnabled: true
                enabled: parent.canNext
                cursorShape: parent.canNext ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    if (!paginationBar.view.bBridge) return
                    if (paginationBar.view.hasSelectedCreator) {
                        var stepNext = paginationBar.view.bBridge.pageSize || 50
                        paginationBar.view.bBridge.loadCreatorPosts(paginationBar.view.bBridge.creatorPostsOffset + stepNext, paginationBar.view.creatorPostSearchText)
                    } else {
                        paginationBar.view.bBridge.nextPage()
                    }
                }
            }
        }
    }
}
