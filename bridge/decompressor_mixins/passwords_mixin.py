"""
DecompressorBridge Password Bank & Interactive Password Prompt Mixin
Decomposed from bridge/decompressor_bridge.py to keep modules cohesive and under 1,000 lines.
"""

import json
import os
import sys
import threading
import time
from typing import List

from PySide6.QtCore import Property, Slot

from bridge.decompressor_mixins.signals_mixin import DecompressorSignalsMixin
from core.archive_password_manager import archive_password_manager as _default_apm
from core.logger import logger
from services.bulk_decompressor import ArchiveItem


def _apm():
    """Resolve archive_password_manager via bridge.decompressor_bridge so test patches work."""
    mod = sys.modules.get("bridge.decompressor_bridge")
    if mod is not None and hasattr(mod, "archive_password_manager"):
        return mod.archive_password_manager
    return _default_apm


class DecompressorPasswordsMixin(DecompressorSignalsMixin):
    """Manages saved archive password bank tree, creator matching, and interactive password prompts."""

    @Property('QVariant', notify=DecompressorSignalsMixin.passwordBankChanged)
    def savedPasswords(self) -> List[str]:
        return _apm().get_passwords()

    @Property(int, notify=DecompressorSignalsMixin.passwordBankChanged)
    def savedPasswordsCount(self) -> int:
        return len(_apm().get_passwords())

    @Property(str, notify=DecompressorSignalsMixin.passwordBankChanged)
    def passwordBankTreeJson(self) -> str:
        """Returns JSON tree of creators and their passwords, with isMatched flags."""
        with self._items_lock:
            if self._is_extracting:
                active_items = [it for it in self._items if it.status in ("extracting", "pending", "password_required")]
                if not active_items:
                    active_items = [it for it in self._items if it.selected]
            else:
                active_items = [it for it in self._items if it.selected]

            active_creators = {it.creator.strip().lower() for it in active_items if it.creator}
            active_passwords = set()
            for it in active_items:
                if it.password:
                    active_passwords.add(it.password.strip())
                mapped = _apm().get_archive_password(it.path)
                if mapped:
                    active_passwords.add(mapped.strip())

        creator_groups = _apm().get_passwords_by_creator()
        groups = []
        for creator_name, pws in creator_groups.items():
            is_global = (creator_name == "Global")
            creator_clean = creator_name.strip().lower()
            group_matched = (not is_global and creator_clean in active_creators) or any(p in active_passwords for p in pws)
            pw_list = []
            for p in pws:
                pw_matched = (p in active_passwords) or (not is_global and creator_clean in active_creators)
                pw_list.append({
                    "password": p,
                    "isMatched": pw_matched
                })
            groups.append({
                "creator": creator_name,
                "isGlobal": is_global,
                "isMatched": group_matched,
                "passwords": pw_list,
                "count": len(pw_list)
            })

        # Sort: matched first, then creators A-Z, Global last unless matched
        groups.sort(key=lambda g: (not g["isMatched"], g["isGlobal"], g["creator"].lower()))
        return json.dumps(groups, ensure_ascii=False)

    @Property('QVariant', notify=DecompressorSignalsMixin.passwordBankChanged)
    def bankCreatorNames(self) -> List[str]:
        """Returns list of all available creator names for password assignment, sorted alphabetically."""
        creators = set()
        with self._items_lock:
            for it in self._items:
                if it.creator and it.creator.strip():
                    creators.add(it.creator.strip())
        from_bank = _apm().get_passwords_by_creator().keys()
        for c in from_bank:
            if c and c.strip() and c.strip() != "Global":
                creators.add(c.strip())
        try:
            # (this imported a module-level watchlist_manager that doesn't exist and read a missing
            # field, so Watchlist creators never appeared here)
            for w in list(getattr(self._watchlist_manager, "entries", []) or []):
                name = (getattr(w, "creator_name", "") or "").strip()
                if name:
                    creators.add(name)
        except Exception:
            pass
        try:
            from core.link_vault_manager import link_vault_manager
            with link_vault_manager._lock:
                for c_key, c_val in link_vault_manager._data.get("creators", {}).items():
                    c_name = c_val.get("creator_name") or c_key
                    if c_name and c_name.strip() and c_name.strip() != "Global":
                        creators.add(c_name.strip())
        except Exception:
            pass

        # Sort alphabetically A-Z (case-insensitive)
        clean_creators = [c for c in creators if c and c.lower() != "global"]
        sorted_creators = sorted(clean_creators, key=lambda s: s.lower())
        return ["Global"] + sorted_creators

    @Slot(result='QVariant')
    def getSavedPasswords(self) -> List[str]:
        return _apm().get_passwords()

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def addPassword(self, password: str, creator: str = "Global") -> bool:
        ok = _apm().add_password(password, creator)
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(str, result=int)
    def addMultiplePasswords(self, text: str) -> int:
        if not text:
            return 0
        lines = [l.strip() for l in text.replace(",", "\n").splitlines() if l.strip()]
        count = _apm().add_passwords(lines)
        if count > 0:
            self.passwordBankChanged.emit()
        return count

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def removePassword(self, password: str, creator: str = "") -> bool:
        ok = _apm().remove_password(password, creator)
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(result=bool)
    def clearSavedPasswords(self) -> bool:
        ok = _apm().clear_passwords()
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(result=int)
    def syncFromLinkVault(self) -> int:
        count = _apm().sync_from_link_vault()
        if count > 0:
            self.passwordBankChanged.emit()
        return count

    @Slot(str, str)
    def setItemPassword(self, itemId: str, password: str):
        with self._items_lock:
            for item in self._items:
                if item.item_id == itemId:
                    item.password = str(password or "").strip()
                    if item.status == "password_required":
                        item.status = "pending"
                        item.error_message = ""
                    break
        self.itemsChanged.emit()

    @Slot(str, str, result=bool)
    def testItemPassword(self, itemId: str, password: str) -> bool:
        target_item = None
        with self._items_lock:
            for it in self._items:
                if it.item_id == itemId:
                    target_item = it
                    break
        if not target_item or not os.path.exists(target_item.path):
            return False
        return self.engine.test_password(target_item.path, str(password or "").strip())

    @Slot(str, str, bool)
    def submitPromptPassword(self, itemId: str, password: str, remember: bool = True):
        with self._prompt_lock:
            self._prompt_responses[itemId] = {
                "action": "submit",
                "password": str(password or "").strip(),
                "remember": remember
            }
            ev = self._prompt_events.get(itemId)
            if ev:
                ev.set()
        self.passwordPromptDismissed.emit(itemId)

    @Slot(str)
    def skipPasswordPrompt(self, itemId: str):
        with self._prompt_lock:
            self._prompt_responses[itemId] = {"action": "skip"}
            ev = self._prompt_events.get(itemId)
            if ev:
                ev.set()
        self.passwordPromptDismissed.emit(itemId)

    @Slot()
    def skipAllPasswordPrompts(self):
        self._skip_all_password_prompts = True
        with self._prompt_lock:
            for it_id, ev in list(self._prompt_events.items()):
                self._prompt_responses[it_id] = {"action": "skip"}
                ev.set()
                self.passwordPromptDismissed.emit(it_id)
        self.passwordPromptDismissed.emit("mock_locked_archive")
        # Release the semaphore in case a worker is queued waiting to show its prompt.
        # We release up to once — if no one holds it this is a no-op (try/except).
        try:
            self._prompt_serial_sem.release()
        except ValueError:
            pass  # semaphore was already at max value (no one was waiting)

    @Slot()
    def triggerTestPasswordPrompt(self):
        """Creates a mock encrypted archive item and requests the password prompt modal for UI testing."""
        mock_id = "mock_locked_archive"
        mock_filename = "exclusive_art_pack.zip"
        mock_creator = "CloZzY"
        mock_directory = "C:/Downloads/CloZzY [fanbox]"
        mock_error = "ERROR: Can not open encrypted archive. Wrong password?"
        mock_size = 15400000

        with self._items_lock:
            found = False
            for it in self._items:
                if it.item_id == mock_id:
                    it.status = "password_required"
                    it.error_message = mock_error
                    found = True
                    break
            if not found:
                self._items.insert(0, ArchiveItem(
                    item_id=mock_id,
                    path=os.path.join(mock_directory, mock_filename),
                    filename=mock_filename,
                    directory=mock_directory,
                    size=mock_size,
                    creator=mock_creator,
                    status="password_required",
                    error_message=mock_error
                ))
        self.itemsChanged.emit()
        self.passwordPromptRequested.emit(
            mock_id, mock_filename, mock_creator, mock_directory, mock_error, mock_size
        )

    @Slot(str, str, bool, result=bool)
    def retryItemWithPassword(self, itemId: str, password: str, remember: bool = True) -> bool:
        p = str(password or "").strip()

        with self._prompt_lock:
            waiting_ev = self._prompt_events.get(itemId)

        # Locate target item
        target_item = None
        with self._items_lock:
            for it in self._items:
                if it.item_id == itemId:
                    target_item = it
                    break

        # ── Mock item special handling ────────────────────────────────────────
        if itemId == "mock_locked_archive":
            target_path = target_item.path if (target_item and target_item.path) else r"C:\Downloads\CloZzY [fanbox]\exclusive_art_pack.zip"
            if os.path.exists(target_path):
                is_valid = self.engine.test_password(target_path, p)
            else:
                is_valid = p.lower() in ("test123", "pawchive", "secret", "password")

            if not is_valid:
                self.passwordWrong.emit(itemId)
                return False

            if remember:
                self.addPassword(p)

            # If waiting in bulk extraction flow, wake up the worker
            if waiting_ev:
                with self._prompt_lock:
                    self._prompt_responses[itemId] = {
                        "action": "submit",
                        "password": p,
                        "remember": remember
                    }
                    waiting_ev.set()
                self.passwordPromptDismissed.emit(itemId)
                return True

            # Standalone mock extraction: if real file exists, extract it in background
            if target_item and os.path.exists(target_item.path):
                def _mock_worker():
                    target_item.password = p
                    target_item.status = "extracting"
                    target_item.progress = 0.0
                    target_item.error_message = ""
                    self.itemUpdated.emit(target_item.item_id, target_item.status, 0.0, "")
                    self.passwordPromptDismissed.emit(itemId)

                    last_cb_emit = [0.0]

                    def _cb(pct: float):
                        target_item.progress = pct
                        now = time.time()
                        if pct < 100.0 and (now - last_cb_emit[0] < 0.1):
                            return
                        last_cb_emit[0] = now
                        self.itemUpdated.emit(target_item.item_id, target_item.status, pct, "")

                    ok, err = self.engine.extract_single_archive(
                        item=target_item,
                        password=p,
                        threads_per_archive=self._threads_per_archive,
                        delete_after=False,
                        progress_callback=_cb
                    )
                    if ok:
                        target_item.status = "done"
                        target_item.progress = 100.0
                        target_item.error_message = ""
                        self.itemUpdated.emit(target_item.item_id, target_item.status, 100.0, "")
                        logger.success(f"✓ Extracted [{target_item.creator}] {target_item.filename} with password", category="decompressor")
                    else:
                        target_item.status = "error"
                        target_item.error_message = err
                        self.itemUpdated.emit(target_item.item_id, target_item.status, target_item.progress, err)
                    self.itemsChanged.emit()

                threading.Thread(target=_mock_worker, daemon=True).start()
                return True

            # Fallback if no file on disk
            with self._items_lock:
                for it in self._items:
                    if it.item_id == itemId:
                        it.status = "done"
                        it.progress = 100.0
                        it.password = p
                        it.error_message = ""
                        break
            self.itemUpdated.emit(itemId, "done", 100.0, "")
            self.itemsChanged.emit()
            self.passwordPromptDismissed.emit(itemId)
            return True

        # ── Real archive path ─────────────────────────────────────────────────
        if not target_item or not os.path.exists(target_item.path):
            return False

        # If waiting in bulk extraction flow, validate password and wake up worker
        if waiting_ev:
            if not self.engine.test_password(target_item.path, p):
                logger.debug(f"Wrong password for {target_item.filename}", category="decompressor")
                self.passwordWrong.emit(itemId)
                return False

            target_item.password = p
            if remember:
                _apm().record_archive_password(target_item.path, p)
                self.passwordBankChanged.emit()

            with self._prompt_lock:
                self._prompt_responses[itemId] = {
                    "action": "submit",
                    "password": p,
                    "remember": remember
                }
                waiting_ev.set()
            self.passwordPromptDismissed.emit(itemId)
            return True

        # Standalone retry (e.g. from an individual item row)
        def _single_worker():
            if not self.engine.test_password(target_item.path, p):
                logger.debug(f"Wrong password for {target_item.filename}", category="decompressor")
                self.passwordWrong.emit(itemId)
                return

            target_item.password = p
            if remember:
                _apm().record_archive_password(target_item.path, p)
                self.passwordBankChanged.emit()

            target_item.status = "extracting"
            target_item.progress = 0.0
            target_item.error_message = ""
            self.itemUpdated.emit(target_item.item_id, target_item.status, 0.0, "")
            self.passwordPromptDismissed.emit(itemId)

            last_cb_emit = [0.0]

            def _cb(pct: float):
                target_item.progress = pct
                now = time.time()
                if pct < 100.0 and (now - last_cb_emit[0] < 0.1):
                    return
                last_cb_emit[0] = now
                self.itemUpdated.emit(target_item.item_id, target_item.status, pct, "")

            ok, err = self.engine.extract_single_archive(
                item=target_item,
                password=p,
                threads_per_archive=self._threads_per_archive,
                delete_after=self._delete_after,
                progress_callback=_cb
            )
            if ok:
                target_item.status = "done"
                target_item.progress = 100.0
                target_item.error_message = ""
                self.itemUpdated.emit(target_item.item_id, target_item.status, 100.0, "")
                logger.success(f"✓ Extracted [{target_item.creator}] {target_item.filename} with password", category="decompressor")
            else:
                target_item.status = "error"
                target_item.error_message = err
                self.itemUpdated.emit(target_item.item_id, target_item.status, target_item.progress, err)
            self.itemsChanged.emit()

        threading.Thread(target=_single_worker, daemon=True).start()
        return True
