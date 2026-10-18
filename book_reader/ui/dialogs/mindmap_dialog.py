"""Mind maps for a book: several maps per book, created blank, from notes, or from an outline."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from book_reader.services.journal import ref_text
from book_reader.services.mindmap import MindMap
from book_reader.ui.dialogs.notes_to_map_dialog import NotesToMapDialog
from book_reader.ui.widgets.mindmap_view import MindMapView


class MindMapDialog(QDialog):
    jumpRequested = Signal(int, float)  # go to a node's source in the open book

    def __init__(self, parent, library, builder, theme: dict, location=None, can_jump=True):
        super().__init__(parent)
        self.lib, self.b, self.t = library, builder, theme
        self.book_id, self.fmt, self.location = builder.book_id, builder.fmt, location
        self.map_id: int | None = None
        self.mm: MindMap | None = None
        self.setWindowTitle(f"Mind maps — {builder.title}")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(1120, 740)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMinimumWidth(240)
        top.addWidget(self.combo)
        new_btn = QPushButton("＋  New")
        new_btn.setObjectName("tonal")
        menu = QMenu(new_btn)
        menu.addAction("Blank map").triggered.connect(lambda: self.new_blank())
        menu.addAction("From my notes…").triggered.connect(lambda: self.generate_from_notes())
        menu.addAction("From an outline…").triggered.connect(lambda: self.new_from_outline())
        new_btn.setMenu(menu)
        top.addWidget(new_btn)
        for text, slot in (("Rename", self.rename_map), ("Delete map", self.delete_map)):
            b = QPushButton(text)
            b.setObjectName("link")
            b.clicked.connect(lambda _=False, s=slot: s())
            top.addWidget(b)
        top.addStretch()
        export = QPushButton("Export")
        export.setObjectName("tonal")
        em = QMenu(export)
        for text, kind in (("PNG image…", "png"), ("PDF…", "pdf"), ("SVG…", "svg"),
                           ("Markdown outline…", "md")):
            em.addAction(text).triggered.connect(lambda _=False, k=kind: self.export(k))
        em.addSeparator()
        em.addAction("Copy outline").triggered.connect(self.copy_outline)
        export.setMenu(em)
        top.addWidget(export)
        lay.addLayout(top)

        tools = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, text, tip in (("child", "＋ Idea", "Add a sub-idea (Tab)"),
                               ("sibling", "＋ Sibling", "Add a sibling idea (Enter)"),
                               ("edit", "Edit", "Edit text (F2 or double-click)"),
                               ("details", "Details…", "Longer note shown as a tooltip"),
                               ("source", "Go to source ↗", "Jump to where this idea came from"),
                               ("delete", "Delete", "Delete the idea and its sub-ideas")):
            b = QPushButton(text)
            b.setObjectName("link")
            b.setToolTip(tip)
            self.buttons[key] = b
            tools.addWidget(b)
        self.buttons["source"].setVisible(can_jump)
        tools.addStretch()
        for text, slot, tip in (("Auto layout", lambda: self.view.relayout(), "Re-arrange all ideas"),
                                ("Fit", lambda: self.view.fit(), "Fit the whole map in the window"),
                                ("−", lambda: self.view.zoom_by(1 / 1.2), "Zoom out"),
                                ("＋", lambda: self.view.zoom_by(1.2), "Zoom in")):
            b = QPushButton(text)
            b.setObjectName("link")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=slot: s())
            tools.addWidget(b)
        lay.addLayout(tools)

        self.view = MindMapView()
        self.view.set_theme(theme)
        self.view.pin = self._pin
        lay.addWidget(self.view, 1)
        hint = QLabel("Tab: new sub-idea  ·  Enter: new sibling  ·  F2 / double-click: edit  ·  "
                      "Space: collapse  ·  drag an idea (its branch follows)  ·  "
                      "Ctrl + wheel: zoom  ·  right-click for more")
        hint.setObjectName("muted")
        lay.addWidget(hint)

        b = self.buttons
        b["child"].clicked.connect(lambda: self.view.add_child())
        b["sibling"].clicked.connect(lambda: self.view.add_sibling())
        b["edit"].clicked.connect(lambda: self.view.edit_node())
        b["details"].clicked.connect(lambda: self.view.edit_details())
        b["source"].clicked.connect(lambda: self.view.jump_to_source())
        b["delete"].clicked.connect(lambda: self.view.delete_selected())
        self.view.jumpRequested.connect(self.jumpRequested.emit)
        self.view.canvas.selectionChanged.connect(self._sync_buttons)

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self._save)
        self.view.changed.connect(self._save_timer.start)
        self.combo.currentIndexChanged.connect(self._on_combo)
        self._load_list()

    # -- maps ------------------------------------------------------------------------ #

    def _pin(self):
        """Location + label for new ideas: where the reader is right now."""
        loc = self.location() if self.location else None
        if not loc:
            return None, ""
        return (dict(i=loc["spine_index"], r=loc["ratio"]),
                ref_text(loc["chapter"], loc["page"], loc["total"], self.fmt))

    def _load_list(self, select: int | None = None):
        maps = self.lib.mindmaps(self.book_id)
        if not maps:  # first time: start with a map that has the book at its centre
            select = self.lib.add_mindmap(self.book_id, "Mind map", MindMap(self.b.title).to_json())
            maps = self.lib.mindmaps(self.book_id)
        self.combo.blockSignals(True)
        self.combo.clear()
        for m in maps:
            self.combo.addItem(m["title"], m["id"])
        index = max(0, self.combo.findData(select)) if select is not None else 0
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._open_selected()

    def _open_selected(self):
        self.map_id = self.combo.currentData()
        row = self.lib.mindmap(self.map_id) if self.map_id is not None else None
        self.mm = MindMap.from_json(row["data"], self.b.title) if row else MindMap(self.b.title)
        self.view.set_map(self.mm)
        self._sync_buttons()

    def _on_combo(self, _index):
        self._save_now()
        self._open_selected()

    def _save(self):
        if self.map_id is not None and self.mm is not None:
            self.lib.save_mindmap(self.map_id, self.mm.to_json())

    def _save_now(self):
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._save()

    def _create(self, title: str, mm: MindMap):
        self._save_now()
        new_id = self.lib.add_mindmap(self.book_id, title, mm.to_json())
        self._load_list(new_id)

    def new_blank(self):
        n = self.combo.count() + 1
        title, ok = QInputDialog.getText(self, "New mind map", "Name:", QLineEdit.EchoMode.Normal,
                                         f"Mind map {n}")
        if ok and title.strip():
            self._create(title.strip(), MindMap(self.b.title))

    def generate_from_notes(self):
        """Notes and highlights -> a new mind map."""
        if not self.b.entries():
            QMessageBox.information(self, "No notes yet", "Add some book notes or highlights "
                                    "first; they will become the branches of the map.")
            return
        dlg = NotesToMapDialog(self, self.b, f"Notes map — {datetime.now():%d %b}")
        if dlg.exec():
            o = dlg.options()
            entries = self.b.entries("", o["notes"], o["highlights"])
            if not entries:
                QMessageBox.information(self, "Nothing selected", "Tick book notes or highlights.")
                return
            mm = MindMap.from_entries(self.b.title, entries, o["mode"], self.fmt, o["split"])
            self._create(o["title"], mm)

    def new_from_outline(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "From an outline", "Paste an outline. Indent lines to nest them "
            "(spaces or tabs; “-” bullets are fine):", "Main idea\n  Sub idea\n  Another\n")
        if ok and text.strip():
            mm = MindMap.from_outline(self.b.title, text)
            self._create(f"Outline — {datetime.now():%d %b}", mm)

    def rename_map(self):
        if self.map_id is None:
            return
        title, ok = QInputDialog.getText(self, "Rename mind map", "Name:",
                                         QLineEdit.EchoMode.Normal, self.combo.currentText())
        if ok and title.strip():
            self.lib.rename_mindmap(self.map_id, title.strip())
            self._save_now()
            self._load_list(self.map_id)

    def delete_map(self):
        if self.map_id is None:
            return
        if QMessageBox.question(self, "Delete mind map",
                                f"Delete “{self.combo.currentText()}”?") != QMessageBox.StandardButton.Yes:
            return
        self._save_timer.stop()
        self.lib.delete_mindmap(self.map_id)
        self.map_id = None
        self._load_list()

    # -- export ---------------------------------------------------------------------------- #

    def export(self, kind: str):
        self._save_now()
        safe = "".join(c for c in self.combo.currentText() if c.isalnum() or c in " -_").strip() or "mind map"
        filters = {"png": "PNG image (*.png)", "pdf": "PDF document (*.pdf)",
                   "svg": "SVG image (*.svg)", "md": "Markdown (*.md)"}
        path, _ = QFileDialog.getSaveFileName(self, "Export mind map",
                                              str(Path.home() / f"{safe}.{kind}"), filters[kind])
        if not path:
            return
        if not path.lower().endswith(f".{kind}"):
            path += f".{kind}"
        try:
            if kind == "md":
                Path(path).write_text(self.mm.to_markdown(), encoding="utf-8")
            else:
                getattr(self.view, f"export_{kind}")(path)
        except ImportError:
            QMessageBox.warning(self, "SVG not available", "This Qt install has no SVG module. "
                                "Use PNG or PDF instead.")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def copy_outline(self):
        QApplication.clipboard().setText(self.mm.to_outline())

    # -- misc -------------------------------------------------------------------------------- #

    def _sync_buttons(self):
        nid = self.view.selected_id()
        node = self.mm.nodes.get(nid) if (self.mm and nid is not None) else None
        has = node is not None
        for key in ("child", "edit", "details"):
            self.buttons[key].setEnabled(has)
        self.buttons["sibling"].setEnabled(has and node.parent is not None)
        self.buttons["delete"].setEnabled(has and node.parent is not None)
        self.buttons["source"].setEnabled(bool(has and node.loc))

    def done(self, result):
        self._save_now()
        super().done(result)
