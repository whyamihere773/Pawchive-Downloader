import QtQuick

Item {
    id: shortcuts
    required property var view
    visible: false

    Shortcut {
        sequences: [StandardKey.SelectAll]
        enabled: shortcuts.view.shortcutsEnabled
        onActivated: shortcuts.view.selectAll()
    }
    Shortcut {
        sequence: "Escape"
        enabled: shortcuts.view.shortcutsEnabled && shortcuts.view.selectionCount > 0
        onActivated: shortcuts.view.clearSelection()
    }
    Shortcut {
        sequences: [StandardKey.Delete]
        enabled: shortcuts.view.shortcutsEnabled && shortcuts.view.selectionCount > 0
        onActivated: shortcuts.view.deleteItems(shortcuts.view.selectedItems())
    }
    Shortcut {
        sequence: "F2"
        enabled: shortcuts.view.shortcutsEnabled && shortcuts.view.selectionCount === 1
        onActivated: shortcuts.view.renameItem(shortcuts.view.selectedItems()[0])
    }
    Shortcut {
        sequences: [StandardKey.Back, "Alt+Left"]
        enabled: shortcuts.view.shortcutsEnabled && shortcuts.view.backStack.length > 0
        onActivated: shortcuts.view.goBack()
    }
    Shortcut {
        sequences: [StandardKey.Forward, "Alt+Right"]
        enabled: shortcuts.view.shortcutsEnabled && shortcuts.view.forwardStack.length > 0
        onActivated: shortcuts.view.goForward()
    }
    Shortcut {
        sequence: "Ctrl+D"   // letters jump to names; the Lightbox keeps F
        enabled: shortcuts.view.markShortcutsEnabled
        onActivated: shortcuts.view.toggleFavorite(shortcuts.view.markTargets())
    }
    Shortcut {
        sequence: "Ctrl+H"
        enabled: (typeof appWindow !== "undefined" ? appWindow.currentTab === 7 : shortcuts.view.visible)
        onActivated: shortcuts.view.togglePrivacy()
    }
    Shortcut {
        sequence: "Ctrl+Shift+N"
        enabled: shortcuts.view.shortcutsEnabled && !!shortcuts.view.tools
        onActivated: shortcuts.view.newFolder()
    }
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: shortcuts.view.shortcutsEnabled && !!shortcuts.view.tools && shortcuts.view.tools.canUndo
        onActivated: shortcuts.view.undoLast()
    }
}
