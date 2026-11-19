import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ═══════════════════════════════════════════════════════════════════════════
// ── 🔑 PASSWORD BANK MODAL ────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
Item {
    id: passwordBankOverlay
    required property var view
    anchors.fill: parent
    // Visibility gate: element stays rendered while fading out
    visible: opacity > 0
    opacity: passwordBankOverlay.view.showPasswordBank ? 1.0 : 0.0
    z: 999

    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutQuad }
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.70
        MouseArea { anchors.fill: parent; onClicked: passwordBankOverlay.view.showPasswordBank = false }
    }

    Rectangle {
        id: pwBankCard
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 40)
        height: Math.min(620, parent.height - 50)
        radius: 14
        color: "#0F141C"
        border.color: "#38BDF8"
        border.width: 1

        // Absorb mouse clicks so clicking inside the modal dialog never propagates to the backdrop
        MouseArea {
            anchors.fill: parent
        }

        // Newtonian spring animation on modal entry
        scale: passwordBankOverlay.view.showPasswordBank ? 1.0 : 0.86
        opacity: passwordBankOverlay.view.showPasswordBank ? 1.0 : 0.0
        transformOrigin: Item.Center

        Behavior on scale {
            SpringAnimation {
                spring: 6.0
                damping: 0.55
                mass: 1.0
                epsilon: 0.001
            }
        }
        Behavior on opacity {
            NumberAnimation { duration: 170; easing.type: Easing.OutQuad }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // Header
            RowLayout {
                spacing: 10
                Text { text: "🔑"; font.pixelSize: 20 }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text {
                        text: passwordBankOverlay.view.tr("title_password_bank", "Decompressor Password Bank")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 14
                        font.weight: 700
                        color: "#38BDF8"
                    }
                    Text {
                        text: passwordBankOverlay.view.tr("desc_password_bank", "Passwords saved here are automatically tested when extracting password-protected archives.")
                        font.pixelSize: 10
                        color: "#64748B"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
                Rectangle {
                    implicitWidth: 26
                    implicitHeight: 26
                    radius: 6
                    color: closeBankMouse.containsMouse ? "#1E293B" : "transparent"
                    border.color: closeBankMouse.containsMouse ? "#334155" : "transparent"
                    scale: closeBankMouse.pressed ? 0.85 : (closeBankMouse.containsMouse ? 1.15 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 14
                        color: closeBankMouse.containsMouse ? "#F1F5F9" : "#64748B"
                    }

                    MouseArea {
                        id: closeBankMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: passwordBankOverlay.view.showPasswordBank = false
                    }
                }
            }

            // Sync from Link Vault button
            Rectangle {
                Layout.fillWidth: true
                height: 30
                radius: 6
                color: syncVaultMouse.containsMouse ? "#1E293B" : "#141C2A"
                border.color: syncVaultMouse.containsMouse ? "#8B5CF6" : "#4C1D95"
                border.width: 1
                scale: syncVaultMouse.pressed ? 0.97 : (syncVaultMouse.containsMouse ? 1.015 : 1.0)
                transformOrigin: Item.Center

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                }

                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "🔄"; font.pixelSize: 11 }
                    Text {
                        text: passwordBankOverlay.view.tr("btn_sync_vault_pw", "Sync from Link Vault")
                        font.pixelSize: 11
                        font.weight: Font.Medium
                        color: syncVaultMouse.containsMouse ? "#C4B5FD" : "#A78BFA"
                    }
                }
                MouseArea {
                    id: syncVaultMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (passwordBankOverlay.view.decompressor) {
                            passwordBankOverlay.view.decompressor.syncFromLinkVault();
                        }
                    }
                }
            }

            // Passwords tree list
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: "#080C12"
                border.color: "#1E2638"
                border.width: 1
                clip: true

                // Absorb clicks on empty list areas so they never close the modal
                MouseArea {
                    anchors.fill: parent
                }

                // Empty state
                Text {
                    anchors.centerIn: parent
                    visible: passwordBankOverlay.view.pwBankTree.length === 0
                    text: "No saved passwords yet."
                    font.pixelSize: 12
                    color: "#334155"
                }

                ListView {
                    id: bankListView
                    objectName: "bankListView"
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true
                    spacing: 8
                    model: passwordBankOverlay.view.pwBankTree
                    visible: passwordBankOverlay.view.pwBankTree.length > 0

                    delegate: Rectangle {
                        id: creatorSectionCard
                        property var creatorData: modelData
                        property bool isCollapsed: passwordBankOverlay.view.isBankCreatorCollapsed(creatorData.creator)
                        width: bankListView.width
                        radius: 7
                        // Special Emerald/Teal color highlight if matched to active archives!
                        color: creatorData.isMatched ? "#05261C" : "#0D131F"
                        border.color: creatorData.isMatched ? "#10B981" : "#1E2638"
                        border.width: creatorData.isMatched ? 1.5 : 1
                        clip: true

                        // Physical spring height response for entire card when expanded/collapsed
                        implicitHeight: sectionCol.implicitHeight + 12

                        Behavior on implicitHeight {
                            SpringAnimation {
                                spring: 4.8
                                damping: 0.45
                                mass: 0.9
                                epsilon: 0.2
                            }
                        }

                        ColumnLayout {
                            id: sectionCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 6
                            spacing: 6

                            // Header row
                            Rectangle {
                                Layout.fillWidth: true
                                height: 32
                                radius: 5
                                color: groupHdrMouse.containsMouse 
                                    ? (creatorData.isMatched ? "#065F46" : "#1A2234") 
                                    : (creatorData.isMatched ? "#064E3B" : "#141C2B")
                                scale: groupHdrMouse.pressed ? 0.985 : (groupHdrMouse.containsMouse ? 1.006 : 1.0)
                                transformOrigin: Item.Center

                                Behavior on scale {
                                    SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                                }

                                // Background mouse area for header row to toggle collapse
                                MouseArea {
                                    id: groupHdrMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: passwordBankOverlay.view.toggleBankCreatorCollapse(creatorData.creator)
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    // Chevron icon with Newtonian rotational inertia
                                    Text {
                                        text: "▼"
                                        font.pixelSize: 10
                                        color: creatorData.isMatched ? "#A7F3D0" : "#64748B"
                                        transformOrigin: Item.Center
                                        rotation: creatorSectionCard.isCollapsed ? -90 : 0

                                        Behavior on rotation {
                                            SpringAnimation {
                                                spring: 4.5
                                                damping: 0.36
                                                mass: 0.85
                                                epsilon: 0.1
                                            }
                                        }
                                    }

                                    Text {
                                        text: creatorData.isGlobal ? "🌐" : "👤"
                                        font.pixelSize: 12
                                    }

                                    Text {
                                        text: creatorData.creator
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: creatorData.isMatched ? "#ECFDF5" : "#E2E8F0"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    // Special Match Badge
                                    Rectangle {
                                        visible: creatorData.isMatched
                                        height: 18
                                        width: matchBadgeTxt.implicitWidth + 10
                                        radius: 4
                                        color: "#065F46"
                                        border.color: "#10B981"
                                        border.width: 1
                                        Text {
                                            id: matchBadgeTxt
                                            anchors.centerIn: parent
                                            text: "🎯 ACTIVE TARGET"
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: "#34D399"
                                        }
                                    }

                                    // Count badge
                                    Rectangle {
                                        height: 18
                                        width: Math.max(18, countBadgeTxt.implicitWidth + 8)
                                        radius: 9
                                        color: creatorData.isMatched ? "#047857" : "#1E293B"
                                        Text {
                                            id: countBadgeTxt
                                            anchors.centerIn: parent
                                            text: creatorData.count
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                            color: creatorData.isMatched ? "#D1FAE5" : "#94A3B8"
                                        }
                                    }

                                    // Quick '+' button with Newtonian spring bounce
                                    Rectangle {
                                        id: quickAddBtn
                                        objectName: "quickAddBtn"
                                        z: 2
                                        height: 20
                                        width: 20
                                        radius: 4
                                        color: quickAddMouse.containsMouse ? (creatorData.isMatched ? "#10B981" : "#38BDF8") : "transparent"
                                        scale: quickAddMouse.pressed ? 0.82 : (quickAddMouse.containsMouse ? 1.18 : 1.0)
                                        transformOrigin: Item.Center

                                        Behavior on scale {
                                            SpringAnimation { spring: 6.0; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            text: "+"
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                            color: quickAddMouse.containsMouse ? "#FFFFFF" : (creatorData.isMatched ? "#A7F3D0" : "#64748B")
                                        }
                                        MouseArea {
                                            id: quickAddMouse
                                            objectName: "quickAddMouse"
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            ToolTip.visible: containsMouse
                                            ToolTip.text: "Add password for " + creatorData.creator
                                            onClicked: {
                                                passwordBankOverlay.view.selectedBankCreator = creatorData.creator;
                                                passwordBankOverlay.view.isCreatorMenuOpen = false;
                                                addPwInput.forceActiveFocus();
                                            }
                                        }
                                    }
                                }
                            }

                            // Passwords container with Newtonian physical height expansion & collapse
                            Item {
                                id: passwordsContainer
                                Layout.fillWidth: true
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                clip: true
                                implicitHeight: creatorSectionCard.isCollapsed ? 0 : passwordsInnerCol.implicitHeight
                                opacity: creatorSectionCard.isCollapsed ? 0.0 : 1.0
                                visible: implicitHeight > 0

                                Behavior on implicitHeight {
                                    SpringAnimation {
                                        spring: 4.8
                                        damping: 0.45
                                        mass: 0.9
                                        epsilon: 0.2
                                    }
                                }
                                Behavior on opacity {
                                    NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
                                }

                                ColumnLayout {
                                    id: passwordsInnerCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    spacing: 4

                                    Repeater {
                                        model: creatorSectionCard.isCollapsed ? null : creatorData.passwords
                                        delegate: Rectangle {
                                            id: pwRow
                                            property var pwObj: modelData
                                            property string groupCreator: creatorSectionCard.creatorData.creator
                                            Layout.fillWidth: true
                                            height: 28
                                            radius: 5
                                            // Special highlight for matched password
                                            color: pwObj.isMatched ? (pwRowHover.containsMouse ? "#064E3B" : "#062C22")
                                                                   : (pwRowHover.containsMouse ? "#131C2A" : "#0A0E15")
                                            border.color: pwObj.isMatched ? "#059669" : (pwRowHover.containsMouse ? "#28344E" : "#1A2234")
                                            border.width: 1
                                            scale: pwRowHover.pressed ? 0.985 : (pwRowHover.containsMouse ? 1.015 : 1.0)
                                            transformOrigin: Item.Center

                                            Behavior on scale {
                                                SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                                            }

                                            // Background hover and click-absorber for row
                                            MouseArea {
                                                id: pwRowHover
                                                anchors.fill: parent
                                                hoverEnabled: true
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 8
                                                anchors.rightMargin: 8
                                                spacing: 8

                                                Text {
                                                    text: pwObj.isMatched ? "🎯" : "🔑"
                                                    font.pixelSize: 10
                                                }

                                                Text {
                                                    text: pwObj.password
                                                    font.family: "Consolas, monospace"
                                                    font.pixelSize: 11
                                                    color: pwObj.isMatched ? "#A7F3D0" : "#CBD5E1"
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: "Matched"
                                                    font.pixelSize: 9
                                                    font.weight: Font.DemiBold
                                                    color: "#34D399"
                                                    visible: pwObj.isMatched
                                                }

                                                // Delete button with spring scale
                                                Rectangle {
                                                    implicitWidth: 18
                                                    implicitHeight: 18
                                                    radius: 4
                                                    color: delPwRowMouse.containsMouse ? "#2D1515" : "transparent"
                                                    scale: delPwRowMouse.pressed ? 0.80 : (delPwRowMouse.containsMouse ? 1.2 : 1.0)
                                                    transformOrigin: Item.Center

                                                    Behavior on scale {
                                                        SpringAnimation { spring: 6.0; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                                                    }

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "✕"
                                                        font.pixelSize: 10
                                                        color: delPwRowMouse.containsMouse ? "#EF4444" : "#475569"
                                                    }

                                                    MouseArea {
                                                        id: delPwRowMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: {
                                                            if (passwordBankOverlay.view.decompressor) {
                                                                passwordBankOverlay.view.decompressor.removePassword(pwObj.password, groupCreator);
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Add new password row with creator selector
            RowLayout {
                id: addPasswordRow
                Layout.fillWidth: true
                spacing: 8

                // Creator Selector Pill Button
                Rectangle {
                    id: creatorSelectorBtn
                    objectName: "creatorSelectorBtn"
                    height: 34
                    implicitWidth: 135
                    radius: 6
                    color: passwordBankOverlay.view.isCreatorMenuOpen ? "#162032" : (creatorBtnMouse.containsMouse ? "#111A29" : "#0B1420")
                    border.color: passwordBankOverlay.view.isCreatorMenuOpen ? "#38BDF8" : (creatorBtnMouse.containsMouse ? "#475569" : "#334155")
                    border.width: passwordBankOverlay.view.isCreatorMenuOpen ? 1.5 : 1
                    scale: creatorBtnMouse.pressed ? 0.96 : (creatorBtnMouse.containsMouse ? 1.015 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 5.5; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        spacing: 5

                        Text {
                            text: passwordBankOverlay.view.selectedBankCreator === "Global" ? "🌐" : "👤"
                            font.pixelSize: 11
                        }

                        Text {
                            text: passwordBankOverlay.view.selectedBankCreator
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: passwordBankOverlay.view.isCreatorMenuOpen ? "#38BDF8" : "#E2E8F0"
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "▾"
                            font.pixelSize: 10
                            color: passwordBankOverlay.view.isCreatorMenuOpen ? "#38BDF8" : "#94A3B8"
                            rotation: passwordBankOverlay.view.isCreatorMenuOpen ? 180 : 0
                            transformOrigin: Item.Center

                            Behavior on rotation {
                                SpringAnimation { spring: 4.5; damping: 0.36; mass: 0.85; epsilon: 0.1 }
                            }
                        }
                    }

                    MouseArea {
                        id: creatorBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            passwordBankOverlay.view.isCreatorMenuOpen = !passwordBankOverlay.view.isCreatorMenuOpen;
                            if (passwordBankOverlay.view.isCreatorMenuOpen) {
                                creatorDropdownMenu.focusAndSelect(passwordBankOverlay.view.selectedBankCreator);
                            }
                        }
                    }
                }

                // Input field
                Rectangle {
                    Layout.fillWidth: true
                    height: 34
                    radius: 7
                    color: addPwInput.activeFocus ? "#0B1420" : "#0B0E14"
                    border.color: addPwInput.activeFocus ? "#38BDF8" : (addPwBoxMouse.containsMouse ? "#475569" : "#334155")
                    border.width: addPwInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: addPwBoxMouse
                        target: addPwInput
                        focusOnLeftClick: true
                    }

                    TextInput {
                        id: addPwInput
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 12
                        font.family: "Segoe UI, Inter, sans-serif"
                        color: "#E2E8F0"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        TextBarContextArea {}
                        onAccepted: {
                            if (text.trim() && passwordBankOverlay.view.decompressor) {
                                passwordBankOverlay.view.decompressor.addPassword(text.trim(), passwordBankOverlay.view.selectedBankCreator);
                                text = "";
                            }
                        }
                        // Placeholder overlay
                        Text {
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                            elide: Text.ElideRight
                            text: "Add password for " + passwordBankOverlay.view.selectedBankCreator + "..."
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#475569"
                            visible: addPwInput.text.length === 0 && !addPwInput.activeFocus
                        }
                    }
                }

                // Add Button with Newtonian spring feedback
                Rectangle {
                    id: addPwBtn
                    height: 34
                    implicitWidth: addPwBtnTxt.implicitWidth + 18
                    radius: 6
                    color: addPwBtnMouse.containsMouse ? "#0369A1" : "#0284C7"
                    border.color: "#38BDF8"
                    border.width: 1
                    scale: addPwBtnMouse.pressed ? 0.93 : (addPwBtnMouse.containsMouse ? 1.04 : 1.0)
                    transformOrigin: Item.Center

                    Behavior on scale {
                        SpringAnimation { spring: 5.5; damping: 0.35; mass: 0.75; epsilon: 0.005 }
                    }

                    Text {
                        id: addPwBtnTxt
                        anchors.centerIn: parent
                        text: passwordBankOverlay.view.tr("btn_add_pw", "Add")
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: addPwBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (addPwInput.text.trim() && passwordBankOverlay.view.decompressor) {
                                passwordBankOverlay.view.decompressor.addPassword(addPwInput.text.trim(), passwordBankOverlay.view.selectedBankCreator);
                                addPwInput.text = "";
                            }
                        }
                    }
                }
            }

            // Clear all button with Newtonian spring feedback
            Rectangle {
                id: clearAllBtn
                Layout.fillWidth: true
                height: 30
                radius: 6
                color: clearAllMouse.containsMouse ? "#450A0A" : "transparent"
                border.color: clearAllMouse.containsMouse ? "#EF4444" : "#334155"
                border.width: 1
                visible: passwordBankOverlay.view.decompressor && passwordBankOverlay.view.decompressor.savedPasswordsCount > 0
                scale: clearAllMouse.pressed ? 0.97 : (clearAllMouse.containsMouse ? 1.015 : 1.0)
                transformOrigin: Item.Center

                Behavior on scale {
                    SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8; epsilon: 0.005 }
                }

                Text {
                    anchors.centerIn: parent
                    text: "🗑️ Clear All Passwords"
                    font.pixelSize: 10
                    color: clearAllMouse.containsMouse ? "#FCA5A5" : "#64748B"
                }
                MouseArea {
                    id: clearAllMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (passwordBankOverlay.view.decompressor) passwordBankOverlay.view.decompressor.clearSavedPasswords()
                }
            }

        }

        // Transparent backdrop for creator dropdown: closes dropdown when clicking anywhere else in the modal
        MouseArea {
            anchors.fill: parent
            z: 98
            visible: passwordBankOverlay.view.isCreatorMenuOpen
            onClicked: passwordBankOverlay.view.isCreatorMenuOpen = false
        }


        DecompressorBankCreatorDropdown {
            id: creatorDropdownMenu
            view: passwordBankOverlay.view
            anchorBottomY: pwBankCard.height - 18 - (clearAllBtn.visible ? 42 : 0) - 34
            onCreatorPicked: addPwInput.forceActiveFocus()
        }
    }
}
