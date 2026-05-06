import json
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from typing import Any
from tkcalendar import Calendar
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from uuid import uuid4


APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = APP_DIR / "tasks.json"
SETTINGS_FILE = APP_DIR / "settings.json"
APP_ICON_FILE = APP_DIR / "assets" / "app-icon.png"
APP_ICON_ICO_FILE = APP_DIR / "assets" / "app-icon.ico"
TOOLBOX_ICON_DIR = APP_DIR / "assets" / "toolbox"
BUILD_TIMESTAMP = datetime.fromtimestamp(APP_DIR.joinpath("app.py").stat().st_mtime).strftime("%d/%m/%Y %H:%M")
DEFAULT_TAG_COLOR = "#2563EB"
DEFAULT_RESPONSIBLE_COLOR = "#0F766E"
DEFAULT_SECTION_COLOR = "#B45309"
PRIMARY_BUTTON_BG = "#2563EB"
PRIMARY_BUTTON_HOVER = "#1D4ED8"
SECONDARY_BUTTON_BG = "#DBEAFE"
SECONDARY_BUTTON_HOVER = "#BFDBFE"
SECONDARY_BUTTON_FG = "#1E3A8A"
TOOLBOX_BUTTON_BG = "#31506B"
TOOLBOX_BUTTON_HOVER = "#3C6283"


class NoteHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.spans: list[dict[str, Any]] = []
        self.active_counts = {tag: 0 for tag in ("bold", "italic", "underline")}
        self.tag_map = {
            "b": "bold",
            "strong": "bold",
            "i": "italic",
            "em": "italic",
            "u": "underline",
        }

    def current_offset(self) -> int:
        return len("".join(self.text_parts))

    def handle_starttag(self, tag: str, attrs) -> None:
        mapped = self.tag_map.get(tag.lower())
        if mapped:
            self.active_counts[mapped] += 1

    def handle_endtag(self, tag: str) -> None:
        mapped = self.tag_map.get(tag.lower())
        if mapped and self.active_counts[mapped] > 0:
            self.active_counts[mapped] -= 1

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag.lower() == "br":
            self.handle_data("\n")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        start = self.current_offset()
        self.text_parts.append(data)
        end = self.current_offset()
        for tag_name, count in self.active_counts.items():
            if count > 0:
                self.spans.append({"tag": tag_name, "start": start, "end": end})

    def result(self) -> dict[str, Any] | None:
        text = "".join(self.text_parts)
        if not text.strip():
            return None
        return {"text": text, "spans": self.merge_spans(self.spans)}

    def merge_spans(self, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for span in sorted(spans, key=lambda item: (str(item["tag"]), int(item["start"]), int(item["end"]))):
            if not merged:
                merged.append(dict(span))
                continue
            previous = merged[-1]
            if previous["tag"] == span["tag"] and previous["end"] >= span["start"]:
                previous["end"] = max(int(previous["end"]), int(span["end"]))
                continue
            merged.append(dict(span))
        return merged


class AppSettings:
    def __init__(self) -> None:
        self.data = self.load()

    def load(self) -> dict:
        if not SETTINGS_FILE.exists():
            return {}
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def tasks_path(self) -> Path | None:
        raw_path = self.data.get("tasks_file", "").strip()
        if not raw_path:
            legacy_dir = self.data.get("storage_dir", "").strip()
            if not legacy_dir:
                return None
            return Path(legacy_dir) / "tasks.json"
        return Path(raw_path)

    def set_tasks_path(self, file_path: str) -> None:
        self.data["tasks_file"] = file_path
        self.save()

    def tasks_file(self) -> Path:
        custom_path = self.tasks_path()
        if custom_path:
            return custom_path
        return DEFAULT_DATA_FILE

    def layout_mode(self) -> str:
        raw_value = str(self.data.get("layout_mode", "compact")).strip().lower()
        if raw_value in {"compact", "normal"}:
            return raw_value
        return "compact"

    def set_layout_mode(self, mode: str) -> None:
        self.data["layout_mode"] = "normal" if mode == "normal" else "compact"
        self.save()

    def responsible_color(self) -> str:
        raw_value = str(self.data.get("responsible_color", DEFAULT_RESPONSIBLE_COLOR)).strip()
        if isinstance(raw_value, str) and len(raw_value) == 7 and raw_value.startswith("#"):
            hex_part = raw_value[1:]
            if all(char in "0123456789abcdefABCDEF" for char in hex_part):
                return f"#{hex_part.upper()}"
        return DEFAULT_RESPONSIBLE_COLOR

    def set_responsible_color(self, color: str) -> None:
        self.data["responsible_color"] = color
        self.save()


@dataclass
class Task:
    id: str
    title: str
    item_type: str = "task"
    section_color: str = DEFAULT_SECTION_COLOR
    completed: bool = False
    important: bool = False
    due_date: str = ""
    notes: str = ""
    notes_rich: dict[str, Any] | None = None
    responsible: str = ""
    tags: list[str] = field(default_factory=list)


class TaskManagerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.geometry("920x620")
        self.root.minsize(720, 500)
        self.root.configure(bg="#eef3f8")
        self.app_icon_image: tk.PhotoImage | None = None

        self.settings = AppSettings()
        self.tasks_file = self.settings.tasks_file()
        self.layout_mode = self.settings.layout_mode()
        self.responsible_color = self.settings.responsible_color()
        self.file_title = self.load_file_title()
        self.tag_catalog = self.load_tag_catalog()
        self.tasks: list[Task] = self.load_tasks()
        self.sync_tag_catalog_with_tasks()
        self.normalize_task_tags()
        self.save_tag_catalog()
        self.editing_task_id: str | None = None
        self.inline_title_var: tk.StringVar | None = None
        self.inline_title_entry: tk.Entry | None = None
        self.editing_file_title = False
        self.inline_file_title_var: tk.StringVar | None = None
        self.inline_file_title_entry: tk.Entry | None = None
        self.task_rows: dict[str, tk.Frame] = {}
        self.drag_data = {"task_id": None, "active": False, "target_index": None}
        self.drop_indicator: tk.Frame | None = None
        self.tag_drag_data = {"key": None, "active": False, "target_index": None}

        self.responsible_filter_var = tk.StringVar(value="Todos")
        self.tag_filter_var = tk.StringVar(value="Todas")
        self.important_filter_var = tk.StringVar(value="Todas")
        self.storage_status_var = tk.StringVar(value=self.storage_status_text())

        self.apply_app_icon()
        self.build_ui()
        self.update_window_title()
        self.render_tasks()
        self.root.bind_all("<Button-1>", self.handle_global_left_click, add="+")

    def storage_status_text(self) -> str:
        return f"Arquivo de dados: {self.tasks_file}"

    def display_file_name(self) -> str:
        return self.tasks_file.name

    def default_file_title(self) -> str:
        return self.tasks_file.name

    def update_window_title(self) -> None:
        self.root.title(f"UltraTask - {self.file_title}")

    def task_layout_metrics(self) -> dict[str, object]:
        if self.layout_mode == "normal":
            return {
                "row_padx": 10,
                "row_pady": 6,
                "row_pack_pady": 3,
                "grip_font": ("Segoe UI Semibold", 11),
                "grip_padx": (0, 8),
                "content_padx": (2, 8),
                "tag_font": ("Segoe UI", 9),
                "tag_padx": 8,
                "tag_pady": 2,
                "tag_pack_padx": (0, 6),
                "title_font": ("Segoe UI", 11),
                "title_entry_font": ("Segoe UI", 11),
                "title_entry_ipady": 2,
                "action_font": ("Segoe UI Semibold", 11),
                "action_padx": 6,
                "action_pady": 2,
                "action_pack_padx": 2,
            }

        return {
            "row_padx": 8,
            "row_pady": 4,
            "row_pack_pady": 2,
            "grip_font": ("Segoe UI Semibold", 10),
            "grip_padx": (0, 6),
            "content_padx": (2, 6),
            "tag_font": ("Segoe UI", 8),
            "tag_padx": 7,
            "tag_pady": 1,
            "tag_pack_padx": (0, 5),
            "title_font": ("Segoe UI", 10),
            "title_entry_font": ("Segoe UI", 10),
            "title_entry_ipady": 1,
            "action_font": ("Segoe UI Semibold", 10),
            "action_padx": 5,
            "action_pady": 1,
            "action_pack_padx": 1,
        }

    def apply_app_icon(self) -> None:
        try:
            if APP_ICON_ICO_FILE.exists():
                self.root.iconbitmap(str(APP_ICON_ICO_FILE))
        except tk.TclError:
            pass

        if not APP_ICON_FILE.exists():
            return

        try:
            self.app_icon_image = tk.PhotoImage(file=str(APP_ICON_FILE))
            self.root.iconphoto(True, self.app_icon_image)
        except tk.TclError:
            self.app_icon_image = None

    def build_ui(self) -> None:
        header = tk.Frame(self.root, bg="#1f2937", padx=24, pady=10)
        header.pack(fill="x")

        header_top = tk.Frame(header, bg="#1f2937")
        header_top.pack(fill="x")

        title_block = tk.Frame(header_top, bg="#1f2937")
        title_block.pack(side="left", fill="both", expand=True)

        self.header_title_block = title_block
        self.render_header_title()

        header_meta = tk.Frame(header, bg="#1f2937")
        header_meta.pack(fill="x", pady=(6, 0))

        tk.Label(
            header_meta,
            text=f"Build: {BUILD_TIMESTAMP}",
            font=("Segoe UI", 8),
            bg="#1f2937",
            fg="#94a3b8",
        ).pack(side="right")

        body_shell = tk.Frame(self.root, bg="#eef3f8")
        body_shell.pack(fill="both", expand=True)

        toolbox = tk.Frame(
            body_shell,
            bg="#f8fbff",
            highlightthickness=1,
            highlightbackground="#d7e3f4",
            width=56,
        )
        toolbox.pack(side="left", fill="y")
        toolbox.pack_propagate(False)

        content_area = tk.Frame(body_shell, bg="#eef3f8")
        content_area.pack(side="left", fill="both", expand=True, padx=(24, 24), pady=(14, 12))

        toolbox_inner = tk.Frame(toolbox, bg="#f8fbff", padx=6, pady=14)
        toolbox_inner.pack(fill="both", expand=True)

        controls = tk.Frame(content_area, bg="#eef3f8")
        controls.pack(fill="x")

        # Filter panel kept isolated in one block to make rollback easy if needed.
        filter_shell = tk.Frame(controls, bg="#eef3f8")
        filter_shell.pack(fill="x")

        filter_panel = tk.Frame(
            filter_shell,
            bg="#f8fbff",
            highlightthickness=1,
            highlightbackground="#d7e3f4",
            padx=10,
            pady=7,
        )
        filter_panel.pack(side="right")

        tk.Label(
            filter_panel,
            text="Filtrar:",
            font=("Segoe UI Semibold", 9),
            bg="#f8fbff",
            fg="#1e3a8a",
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            filter_panel,
            text="Responsável",
            font=("Segoe UI", 9),
            bg="#f8fbff",
            fg="#334155",
        ).pack(side="left", padx=(0, 6))

        self.responsible_filter_menu = tk.OptionMenu(
            filter_panel,
            self.responsible_filter_var,
            "Todos",
            command=lambda _value: self.render_tasks(),
        )
        self.responsible_filter_menu.config(
            font=("Segoe UI", 9),
            relief="flat",
            bg="white",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            activebackground="white",
            width=10,
            anchor="w",
        )
        self.responsible_filter_menu["menu"].config(font=("Segoe UI", 9))
        self.responsible_filter_menu.pack(side="left", padx=(0, 12))

        tk.Label(
            filter_panel,
            text="Importância",
            font=("Segoe UI", 9),
            bg="#f8fbff",
            fg="#334155",
        ).pack(side="left", padx=(0, 6))

        self.important_filter_menu = tk.OptionMenu(
            filter_panel,
            self.important_filter_var,
            "Todas",
            command=lambda _value: self.render_tasks(),
        )
        self.important_filter_menu.config(
            font=("Segoe UI", 9),
            relief="flat",
            bg="white",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            activebackground="white",
            width=9,
            anchor="w",
        )
        self.important_filter_menu["menu"].config(font=("Segoe UI", 9))
        self.important_filter_menu.pack(side="left", padx=(0, 12))

        tk.Label(
            filter_panel,
            text="Tag",
            font=("Segoe UI", 9),
            bg="#f8fbff",
            fg="#334155",
        ).pack(side="left", padx=(0, 6))

        self.tag_filter_menu = tk.OptionMenu(
            filter_panel,
            self.tag_filter_var,
            "Todas",
            command=lambda _value: self.render_tasks(),
        )
        self.tag_filter_menu.config(
            font=("Segoe UI", 9),
            relief="flat",
            bg="white",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            activebackground="white",
            width=8,
            anchor="w",
        )
        self.tag_filter_menu["menu"].config(font=("Segoe UI", 9))
        self.tag_filter_menu.pack(side="left")

        tk.Button(
            filter_panel,
            text="Limpar filtros",
            command=self.clear_filters,
            font=("Segoe UI Semibold", 9),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=(12, 0))
        self.refresh_filter_options()

        toolbox_fallback_patterns = {
            "add": [
                "0001000",
                "0001000",
                "0001000",
                "1111111",
                "0001000",
                "0001000",
                "0001000",
            ],
            "section": [
                "1111111",
                "0000000",
                "1111111",
                "0000000",
                "1111111",
                "0000000",
                "1111111",
            ],
            "reload": [
                "0011110",
                "0100001",
                "1000111",
                "1000100",
                "1000100",
                "0100001",
                "0011100",
            ],
            "tags": [
                "1111110",
                "1000010",
                "1111110",
                "0010000",
                "0111000",
                "0010000",
                "0000000",
            ],
            "settings": [
                "0011100",
                "0111110",
                "1110111",
                "1100011",
                "1110111",
                "0111110",
                "0011100",
            ],
            "about": [
                "0011100",
                "0100010",
                "0000010",
                "0001100",
                "0001000",
                "0000000",
                "0001000",
            ],
        }
        self.toolbox_icons = {
            icon_name: self.load_toolbox_icon(icon_name, fallback_pattern, TOOLBOX_BUTTON_BG)
            for icon_name, fallback_pattern in toolbox_fallback_patterns.items()
        }

        for icon_key, tooltip_text, command in (
            ("add", "Nova tarefa", self.add_task),
            ("section", "Nova seção", self.add_section),
            ("reload", "Recarregar", self.reload_tasks_from_disk),
        ):
            button_slot = tk.Frame(toolbox_inner, bg="#f8fbff", width=40, height=40)
            button_slot.pack(pady=(0, 8))
            button_slot.pack_propagate(False)

            action_button = tk.Button(
                button_slot,
                image=self.toolbox_icons[icon_key],
                command=command,
                bg=TOOLBOX_BUTTON_BG,
                fg="white",
                activebackground=TOOLBOX_BUTTON_HOVER,
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=0,
                pady=0,
                cursor="hand2",
            )
            action_button.pack(fill="both", expand=True)
            self.bind_action_button_hover(action_button, TOOLBOX_BUTTON_BG, TOOLBOX_BUTTON_HOVER)
            self.attach_tooltip(action_button, tooltip_text)

        for index, (icon_key, tooltip_text, command) in enumerate((
            ("tags", "Gerenciar tags", self.open_tag_manager),
            ("settings", "Configurações", self.open_settings_window),
            ("about", "Sobre", self.open_about_window),
        )):
            if index != 1:
                separator = tk.Frame(toolbox_inner, bg="#d7e3f4", height=1)
                separator.pack(fill="x", padx=2, pady=(2, 8))

            button_slot = tk.Frame(toolbox_inner, bg="#f8fbff", width=40, height=40)
            button_slot.pack(pady=(0, 8))
            button_slot.pack_propagate(False)

            action_button = tk.Button(
                button_slot,
                image=self.toolbox_icons[icon_key],
                command=command,
                bg=TOOLBOX_BUTTON_BG,
                fg="white",
                activebackground=TOOLBOX_BUTTON_HOVER,
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=0,
                pady=0,
                cursor="hand2",
            )
            action_button.pack(fill="both", expand=True)
            self.bind_action_button_hover(action_button, TOOLBOX_BUTTON_BG, TOOLBOX_BUTTON_HOVER)
            self.attach_tooltip(action_button, tooltip_text)

        container = tk.Frame(content_area, bg="#eef3f8")
        container.pack(fill="both", expand=True, pady=(12, 0))

        self.canvas = tk.Canvas(
            container,
            bg="#eef3f8",
            highlightthickness=0,
            bd=0,
        )
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg="#eef3f8")
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")

        self.list_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def bind_header_button_hover(self, button: tk.Button) -> None:
        def on_enter(_event) -> None:
            button.configure(
                bg="#334155",
                activebackground="#334155",
            )

        def on_leave(_event) -> None:
            button.configure(
                bg="#1f2937",
                activebackground="#334155",
            )

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def bind_action_button_hover(self, button: tk.Button, base_bg: str, hover_bg: str) -> None:
        def on_enter(_event) -> None:
            button.configure(
                bg=hover_bg,
                activebackground=hover_bg,
            )

        def on_leave(_event) -> None:
            button.configure(
                bg=base_bg,
                activebackground=hover_bg,
            )

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        tooltip_window: tk.Toplevel | None = None

        def show_tooltip(_event=None) -> None:
            nonlocal tooltip_window
            if tooltip_window is not None:
                return

            tooltip_window = tk.Toplevel(self.root)
            tooltip_window.wm_overrideredirect(True)
            tooltip_window.configure(bg="#0f172a")

            label = tk.Label(
                tooltip_window,
                text=text,
                font=("Segoe UI", 9),
                bg="#0f172a",
                fg="white",
                padx=8,
                pady=4,
            )
            label.pack()

            x_root = widget.winfo_rootx() + widget.winfo_width() + 10
            y_root = widget.winfo_rooty() + max((widget.winfo_height() // 2) - 12, 0)
            tooltip_window.geometry(f"+{x_root}+{y_root}")

        def hide_tooltip(_event=None) -> None:
            nonlocal tooltip_window
            if tooltip_window is not None:
                tooltip_window.destroy()
                tooltip_window = None

        widget.bind("<Enter>", show_tooltip, add="+")
        widget.bind("<Leave>", hide_tooltip, add="+")
        widget.bind("<ButtonPress-1>", hide_tooltip, add="+")

    def create_toolbox_icon(
        self,
        pattern: list[str],
        background: str,
        foreground: str = "white",
        scale: int = 2,
    ) -> tk.PhotoImage:
        rows = len(pattern)
        cols = max((len(row) for row in pattern), default=0)
        image = tk.PhotoImage(width=cols * scale, height=rows * scale)
        image.put(background, to=(0, 0, cols * scale, rows * scale))

        for y, row in enumerate(pattern):
            for x, cell in enumerate(row):
                if cell == "1":
                    image.put(
                        foreground,
                        to=(x * scale, y * scale, (x + 1) * scale, (y + 1) * scale),
                    )
        return image

    def load_toolbox_icon(
        self,
        icon_name: str,
        fallback_pattern: list[str],
        background: str,
        foreground: str = "white",
    ) -> tk.PhotoImage:
        icon_path = TOOLBOX_ICON_DIR / f"{icon_name}.png"
        if icon_path.exists():
            return tk.PhotoImage(file=str(icon_path))
        return self.create_toolbox_icon(fallback_pattern, background, foreground)

    def render_header_title(self) -> None:
        for child in self.header_title_block.winfo_children():
            child.destroy()

        if self.editing_file_title:
            self.inline_file_title_var = tk.StringVar(value=self.file_title)
            self.inline_file_title_entry = tk.Entry(
                self.header_title_block,
                textvariable=self.inline_file_title_var,
                font=("Segoe UI Semibold", 20),
                relief="flat",
                highlightthickness=1,
                highlightbackground="#475569",
                highlightcolor="#93c5fd",
                bg="#1f2937",
                fg="white",
                insertbackground="white",
            )
            self.inline_file_title_entry.pack(anchor="w", fill="x", ipady=2, pady=(4, 0))
            self.inline_file_title_entry.bind("<Return>", lambda _event: self.save_inline_file_title())
            self.inline_file_title_entry.bind("<Escape>", lambda _event: self.cancel_inline_file_title())
            self.inline_file_title_entry.bind("<FocusOut>", lambda _event: self.save_inline_file_title())
            self.inline_file_title_entry.focus_set()
            self.inline_file_title_entry.select_range(0, "end")
            return

        self.app_title_label = tk.Label(
            self.header_title_block,
            text=f"UltraTask - {self.file_title}",
            font=("Segoe UI Semibold", 22),
            fg="white",
            bg="#1f2937",
            cursor="xterm",
        )
        self.app_title_label.pack(anchor="w", pady=(4, 0))
        self.app_title_label.bind("<Button-1>", lambda _event: self.edit_file_title())

    def on_frame_configure(self, _event=None) -> None:
        scrollregion = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=scrollregion)

        if not scrollregion:
            return

        content_height = scrollregion[3] - scrollregion[1]
        if content_height <= self.canvas.winfo_height():
            self.canvas.yview_moveto(0)

    def on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.list_window, width=event.width)

    def current_scroll_fraction(self) -> float:
        yview = self.canvas.yview()
        if not yview:
            return 0.0
        return float(yview[0])

    def restore_scroll_fraction(self, fraction: float) -> None:
        self.root.update_idletasks()
        scrollregion = self.canvas.bbox("all")
        if not scrollregion:
            return

        content_height = scrollregion[3] - scrollregion[1]
        if content_height <= self.canvas.winfo_height():
            self.canvas.yview_moveto(0)
            return

        self.canvas.yview_moveto(max(0.0, min(fraction, 1.0)))

    def on_mousewheel(self, event) -> None:
        if not self.pointer_over_scroll_area():
            return

        scrollregion = self.canvas.bbox("all")
        if not scrollregion:
            return

        content_height = scrollregion[3] - scrollregion[1]
        if content_height <= self.canvas.winfo_height():
            return

        delta = int(-event.delta / 120)
        if delta != 0:
            self.canvas.yview_scroll(delta, "units")

    def pointer_over_scroll_area(self) -> bool:
        widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        while widget is not None:
            if widget == self.canvas or widget == self.list_frame:
                return True
            widget = widget.master
        return False

    def center_window(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        pos_x = root_x + max((root_width - width) // 2, 0)
        pos_y = root_y + max((root_height - height) // 2, 0)
        window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def widget_is_descendant_of(self, widget: tk.Widget | None, ancestor: tk.Widget | None) -> bool:
        while widget is not None:
            if widget == ancestor:
                return True
            widget = widget.master
        return False

    def handle_global_left_click(self, event) -> None:
        if not self.editing_task_id or not self.inline_title_entry or not self.inline_title_var:
            if self.editing_file_title and self.inline_file_title_entry and self.inline_file_title_var:
                if self.widget_is_descendant_of(event.widget, self.inline_file_title_entry):
                    return
                self.save_inline_file_title()
            return

        if not self.widget_is_descendant_of(event.widget, self.inline_title_entry):
            self.save_inline_task_title(self.editing_task_id, self.inline_title_var.get())

        if self.editing_file_title and self.inline_file_title_entry and self.inline_file_title_var:
            if self.widget_is_descendant_of(event.widget, self.inline_file_title_entry):
                return
            self.save_inline_file_title()

    def load_tag_catalog(self) -> dict[str, dict]:
        catalog: dict[str, dict] = {}
        source_items: list[dict] = []

        if self.tasks_file.exists():
            try:
                raw_data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
                if isinstance(raw_data, dict):
                    raw_items = raw_data.get("tag_catalog", [])
                    if isinstance(raw_items, list):
                        source_items = [item for item in raw_items if isinstance(item, dict)]
            except json.JSONDecodeError:
                source_items = []

        for item in source_items:
            name = self.clean_tag_name(item.get("name", ""))
            if not name:
                continue
            key = name.lower()
            if key in catalog:
                continue
            catalog[key] = {
                "name": name,
                "color": self.normalize_color(item.get("color")),
                "order": int(item.get("order", len(catalog))),
            }
        self.reindex_tag_catalog(catalog)
        return catalog

    def save_tag_catalog(self) -> None:
        self.save_tasks()

    def sorted_tag_catalog(self) -> list[dict]:
        return sorted(
            self.tag_catalog.values(),
            key=lambda item: (int(item.get("order", 0)), item["name"].lower()),
        )

    def tag_order_keys(self) -> list[str]:
        return [item["name"].lower() for item in self.sorted_tag_catalog()]

    def next_tag_order(self) -> int:
        if not self.tag_catalog:
            return 0
        return max(int(item.get("order", index)) for index, item in enumerate(self.tag_catalog.values())) + 1

    def reindex_tag_catalog(self, catalog: dict[str, dict] | None = None) -> None:
        target = catalog if catalog is not None else self.tag_catalog
        ordered_items = sorted(
            target.items(),
            key=lambda pair: (int(pair[1].get("order", 0)), pair[1]["name"].lower()),
        )
        for index, (_key, item) in enumerate(ordered_items):
            item["order"] = index

    def reorder_tag_catalog(self, ordered_keys: list[str]) -> None:
        remaining = [key for key in self.tag_catalog if key not in ordered_keys]
        final_keys = [*ordered_keys, *remaining]
        for index, key in enumerate(final_keys):
            item = self.tag_catalog.get(key)
            if item is not None:
                item["order"] = index

    def move_tag_order(self, key: str, direction: int) -> bool:
        current_order = self.tag_order_keys()
        if key not in current_order:
            return False

        current_index = current_order.index(key)
        target_index = current_index + direction
        if target_index < 0 or target_index >= len(current_order):
            return False

        current_order[current_index], current_order[target_index] = current_order[target_index], current_order[current_index]
        self.reorder_tag_catalog(current_order)
        return True

    def ordered_task_tags(self, tags: list[str]) -> list[str]:
        unique_tags: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            key = self.clean_tag_name(tag).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique_tags.append(self.tag_catalog.get(key, {"name": self.clean_tag_name(tag)})["name"])

        return sorted(
            unique_tags,
            key=lambda tag: (
                int(self.tag_catalog.get(tag.lower(), {}).get("order", 10**9)),
                tag.lower(),
            ),
        )

    def clean_tag_name(self, name: str) -> str:
        return str(name).strip()

    def normalize_color(self, value: str | None) -> str:
        if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
            hex_part = value[1:]
            if all(char in "0123456789abcdefABCDEF" for char in hex_part):
                return f"#{hex_part.upper()}"
        return DEFAULT_TAG_COLOR

    def register_tag(self, name: str, color: str | None = None) -> str | None:
        cleaned = self.clean_tag_name(name)
        if not cleaned:
            return None

        key = cleaned.lower()
        existing = self.tag_catalog.get(key)
        if existing:
            if color is not None:
                existing["color"] = self.normalize_color(color)
                self.save_tag_catalog()
            return existing["name"]

        self.tag_catalog[key] = {
            "name": cleaned,
            "color": self.normalize_color(color),
            "order": self.next_tag_order(),
        }
        self.save_tag_catalog()
        return cleaned

    def sync_tag_catalog_with_tasks(self) -> None:
        changed = False
        for task in self.tasks:
            if self.is_section(task):
                continue
            for tag in task.tags:
                cleaned = self.clean_tag_name(tag)
                if not cleaned:
                    continue
                key = cleaned.lower()
                if key not in self.tag_catalog:
                    self.tag_catalog[key] = {
                        "name": cleaned,
                        "color": DEFAULT_TAG_COLOR,
                        "order": self.next_tag_order(),
                    }
                    changed = True

        if changed:
            self.save_tag_catalog()

    def normalize_task_tags(self) -> None:
        changed = False
        for task in self.tasks:
            if task.item_type not in {"task", "section"}:
                task.item_type = "task"
                changed = True
            normalized_section_color = self.normalize_color(task.section_color)
            if task.section_color != normalized_section_color:
                task.section_color = normalized_section_color
                changed = True
            if self.is_section(task):
                if task.tags or task.completed or task.important or task.due_date or task.notes.strip() or task.notes_rich or task.responsible:
                    task.tags = []
                    task.completed = False
                    task.important = False
                    task.due_date = ""
                    task.notes = ""
                    task.notes_rich = None
                    task.responsible = ""
                    changed = True
                continue
            normalized: list[str] = []
            seen: set[str] = set()
            for tag in task.tags:
                cleaned = self.clean_tag_name(tag)
                if not cleaned:
                    continue
                key = cleaned.lower()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(self.tag_catalog.get(key, {"name": cleaned})["name"])

            ordered_normalized = self.ordered_task_tags(normalized)
            if ordered_normalized != task.tags:
                task.tags = ordered_normalized
                changed = True

        if changed:
            self.save_tasks()

    def get_tag_entry(self, name: str) -> dict | None:
        return self.tag_catalog.get(self.clean_tag_name(name).lower())

    def get_tag_color(self, name: str) -> str:
        entry = self.get_tag_entry(name)
        if not entry:
            return DEFAULT_TAG_COLOR
        return entry["color"]

    def contrast_text_color(self, background: str) -> str:
        color = self.normalize_color(background)
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return "#0F172A" if luminance > 186 else "white"

    def draw_rounded_rectangle(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        fill: str,
    ) -> None:
        radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        canvas.create_polygon(points, smooth=True, fill=fill, outline=fill)

    def create_responsible_chip(self, parent: tk.Widget, text: str, metrics: dict[str, object]) -> tk.Canvas:
        display_text = f"@ {text}"
        chip_font = tkfont.Font(family=metrics["tag_font"][0], size=metrics["tag_font"][1])
        text_width = chip_font.measure(display_text)
        text_height = chip_font.metrics("linespace")
        pad_x = int(metrics["tag_padx"])
        pad_y = int(metrics["tag_pady"])
        width = text_width + (pad_x * 2)
        height = text_height + (pad_y * 2) + 2

        canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.draw_rounded_rectangle(
            canvas,
            1,
            1,
            width - 1,
            height - 1,
            radius=max(8, height // 2),
            fill=self.responsible_color,
        )
        canvas.create_text(
            width // 2,
            height // 2,
            text=display_text,
            fill=self.contrast_text_color(self.responsible_color),
            font=chip_font,
        )
        return canvas

    def parse_due_date(self, value: str) -> date | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            year_text, month_text, day_text = cleaned.split("-")
            return date(int(year_text), int(month_text), int(day_text))
        except (TypeError, ValueError):
            return None

    def format_due_date(self, value: str) -> str:
        parsed = self.parse_due_date(value)
        if not parsed:
            return "Sem data"
        return parsed.strftime("%d/%m/%Y")

    def due_date_text_color(self, value: str) -> str:
        parsed = self.parse_due_date(value)
        if not parsed:
            return "#94a3b8"
        if parsed < date.today():
            return "#DC2626"
        return "#334155"

    def open_due_date_dialog(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or self.is_section(task):
            return

        current_date = self.parse_due_date(task.due_date) or date.today()
        result: dict[str, str | None] = {"value": None}

        window = tk.Toplevel(self.root)
        window.title("Selecionar data")
        window.geometry("360x420")
        window.resizable(False, False)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        tk.Label(
            window,
            text="Data de previsão",
            font=("Segoe UI Semibold", 15),
            bg="#eef3f8",
            fg="#0f172a",
        ).pack(anchor="w", padx=24, pady=(20, 6))

        tk.Label(
            window,
            text="Escolha a data prevista para esta tarefa.",
            font=("Segoe UI", 10),
            bg="#eef3f8",
            fg="#475569",
        ).pack(anchor="w", padx=24)

        calendar_frame = tk.Frame(window, bg="#eef3f8")
        calendar_frame.pack(fill="both", expand=True, padx=24, pady=18)

        calendar = Calendar(
            calendar_frame,
            selectmode="day",
            year=current_date.year,
            month=current_date.month,
            day=current_date.day,
            date_pattern="yyyy-mm-dd",
            locale="pt_BR",
            background="#2563eb",
            foreground="white",
            headersbackground="#1d4ed8",
            headersforeground="white",
            selectbackground="#0f766e",
            selectforeground="white",
            normalbackground="white",
            normalforeground="#0f172a",
            weekendbackground="white",
            weekendforeground="#0f172a",
            othermonthbackground="#f8fafc",
            othermonthforeground="#94a3b8",
            othermonthwebackground="#f8fafc",
            othermonthweforeground="#94a3b8",
            bordercolor="#dbe3ec",
        )
        calendar.pack(fill="both", expand=True)

        buttons = tk.Frame(window, bg="#eef3f8")
        buttons.pack(fill="x", padx=24, pady=(8, 20))

        def apply_date() -> None:
            result["value"] = str(calendar.get_date())
            window.destroy()

        def clear_date() -> None:
            result["value"] = ""
            window.destroy()

        tk.Button(
            buttons,
            text="Limpar",
            command=clear_date,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            buttons,
            text="Cancelar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            buttons,
            text="Salvar",
            command=apply_date,
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        window.wait_window()
        if result["value"] is None:
            return

        task.due_date = str(result["value"])
        self.persist_and_refresh()

    def open_notes_dialog(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or self.is_section(task):
            return

        window = tk.Toplevel(self.root)
        window.title("Notas")
        window.geometry("620x500")
        window.minsize(520, 420)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        tk.Label(
            window,
            text="Notas da tarefa",
            font=("Segoe UI Semibold", 15),
            bg="#eef3f8",
            fg="#0f172a",
        ).pack(anchor="w", padx=24, pady=(20, 6))

        toolbar = tk.Frame(window, bg="#eef3f8")
        toolbar.pack(fill="x", padx=24, pady=(8, 0))

        footer = tk.Frame(window, bg="#eef3f8")
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 20))

        content = tk.Frame(window, bg="#eef3f8")
        content.pack(fill="both", expand=True)

        text_box = tk.Text(
            content,
            font=("Segoe UI", 10),
            relief="flat",
            wrap="word",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
            padx=10,
            pady=10,
        )
        text_box.pack(fill="both", expand=True, padx=24, pady=(12, 18))
        self.configure_note_text_tags(text_box)
        self.load_task_notes_into_textbox(task, text_box)

        for label, tag_name, shortcut in (
            ("B", "bold", "Ctrl+B"),
            ("I", "italic", "Ctrl+I"),
            ("U", "underline", "Ctrl+U"),
        ):
            tk.Button(
                toolbar,
                text=label,
                command=lambda name=tag_name: self.toggle_note_format(text_box, name),
                font=("Segoe UI Semibold", 10),
                relief="flat",
                bg=SECONDARY_BUTTON_BG,
                fg=SECONDARY_BUTTON_FG,
                activebackground=SECONDARY_BUTTON_HOVER,
                padx=12,
                pady=6,
                cursor="hand2",
            ).pack(side="left", padx=(0, 8))

            tk.Label(
                toolbar,
                text=shortcut,
                font=("Segoe UI", 9),
                bg="#eef3f8",
                fg="#64748b",
            ).pack(side="left", padx=(0, 14))

        def save_notes() -> None:
            note_text = text_box.get("1.0", "end-1c")
            task.notes = note_text.strip()
            task.notes_rich = self.serialize_note_text(text_box)
            window.destroy()
            self.persist_and_refresh()

        tk.Button(
            footer,
            text="Limpar",
            command=lambda: self.clear_note_text(text_box),
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            footer,
            text="Cancelar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer,
            text="Salvar",
            command=save_notes,
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        window.bind("<Control-b>", lambda _event: self.handle_note_shortcut(text_box, "bold"))
        window.bind("<Control-i>", lambda _event: self.handle_note_shortcut(text_box, "italic"))
        window.bind("<Control-u>", lambda _event: self.handle_note_shortcut(text_box, "underline"))
        text_box.focus_set()

    def note_tag_names(self) -> tuple[str, ...]:
        return ("bold", "italic", "underline")

    def configure_note_text_tags(self, text_box: tk.Text) -> None:
        base_font = tkfont.Font(font=text_box.cget("font"))
        bold_font = base_font.copy()
        bold_font.configure(weight="bold")
        italic_font = base_font.copy()
        italic_font.configure(slant="italic")
        underline_font = base_font.copy()
        underline_font.configure(underline=1)

        text_box.tag_configure("bold", font=bold_font)
        text_box.tag_configure("italic", font=italic_font)
        text_box.tag_configure("underline", font=underline_font)

    def load_task_notes_into_textbox(self, task: Task, text_box: tk.Text) -> None:
        payload = self.normalize_notes_rich_payload(task.notes_rich)
        if payload:
            note_text = str(payload.get("text", ""))
            text_box.insert("1.0", note_text)
            for span in payload.get("spans", []):
                if not isinstance(span, dict):
                    continue

                tag_name = str(span.get("tag", ""))
                if tag_name not in self.note_tag_names():
                    continue

                start = span.get("start")
                end = span.get("end")
                if not isinstance(start, int) or not isinstance(end, int) or end <= start:
                    continue

                text_box.tag_add(tag_name, f"1.0+{start}c", f"1.0+{end}c")
            return

        if task.notes:
            text_box.insert("1.0", task.notes)

    def normalize_notes_rich_payload(self, payload: Any) -> dict[str, Any] | None:
        if self.is_valid_rich_note_payload(payload):
            return payload
        if isinstance(payload, str) and payload.strip():
            return self.parse_note_html(payload)
        return None

    def is_valid_rich_note_payload(self, payload: Any) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("text", ""), str) and isinstance(
            payload.get("spans", []), list
        )

    def parse_note_html(self, html_text: str) -> dict[str, Any] | None:
        parser = NoteHTMLParser()
        try:
            parser.feed(html_text)
            parser.close()
        except Exception:
            return None
        return parser.result()

    def toggle_note_format(self, text_box: tk.Text, tag_name: str) -> None:
        try:
            start = text_box.index("sel.first")
            end = text_box.index("sel.last")
        except tk.TclError:
            return

        if text_box.tag_nextrange(tag_name, start, end):
            text_box.tag_remove(tag_name, start, end)
        else:
            text_box.tag_add(tag_name, start, end)

        text_box.focus_set()

    def handle_note_shortcut(self, text_box: tk.Text, tag_name: str) -> str:
        self.toggle_note_format(text_box, tag_name)
        return "break"

    def clear_note_text(self, text_box: tk.Text) -> None:
        text_box.delete("1.0", "end")
        for tag_name in self.note_tag_names():
            text_box.tag_remove(tag_name, "1.0", "end")

    def serialize_note_text(self, text_box: tk.Text) -> str | None:
        plain_text = text_box.get("1.0", "end-1c")
        if not plain_text.strip():
            return None

        intervals: dict[str, list[tuple[int, int]]] = {tag_name: [] for tag_name in self.note_tag_names()}
        boundaries = {0, len(plain_text)}

        for tag_name in self.note_tag_names():
            ranges = text_box.tag_ranges(tag_name)
            for index in range(0, len(ranges), 2):
                start_index = str(ranges[index])
                end_index = str(ranges[index + 1])
                start_offset = self.text_index_to_offset(text_box, start_index)
                end_offset = self.text_index_to_offset(text_box, end_index)
                if end_offset > start_offset:
                    intervals[tag_name].append((start_offset, end_offset))
                    boundaries.add(start_offset)
                    boundaries.add(end_offset)

        tag_html = {"bold": "b", "italic": "i", "underline": "u"}
        ordered_boundaries = sorted(boundaries)
        html_parts: list[str] = []
        open_tags: list[str] = []

        for start_offset, end_offset in zip(ordered_boundaries, ordered_boundaries[1:]):
            if end_offset <= start_offset:
                continue
            segment_text = plain_text[start_offset:end_offset]
            if not segment_text:
                continue

            active_tags = [
                tag_name
                for tag_name in self.note_tag_names()
                if any(start <= start_offset and end_offset <= end for start, end in intervals[tag_name])
            ]

            shared_prefix = 0
            while (
                shared_prefix < len(open_tags)
                and shared_prefix < len(active_tags)
                and open_tags[shared_prefix] == active_tags[shared_prefix]
            ):
                shared_prefix += 1

            for tag_name in reversed(open_tags[shared_prefix:]):
                html_parts.append(f"</{tag_html[tag_name]}>")
            open_tags = open_tags[:shared_prefix]

            for tag_name in active_tags[shared_prefix:]:
                html_parts.append(f"<{tag_html[tag_name]}>")
                open_tags.append(tag_name)

            html_parts.append(escape(segment_text))

        for tag_name in reversed(open_tags):
            html_parts.append(f"</{tag_html[tag_name]}>")

        return "".join(html_parts)

    def text_index_to_offset(self, text_box: tk.Text, text_index: str) -> int:
        return len(text_box.get("1.0", text_index))

    def load_file_title(self) -> str:
        if not self.tasks_file.exists():
            return self.default_file_title()

        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                raw_title = str(data.get("title", "")).strip()
                if raw_title:
                    return raw_title
        except json.JSONDecodeError:
            pass

        return self.default_file_title()

    def load_tasks(self) -> list[Task]:
        if not self.tasks_file.exists():
            sample = [
                Task(id=str(uuid4()), title="Planejar a semana", tags=["rotina", "prioridade"]),
                Task(id=str(uuid4()), title="Revisar contas do mês", tags=["financeiro"]),
                Task(id=str(uuid4()), title="Preparar reunião de sexta", tags=["trabalho"]),
            ]
            self.save_tasks(sample)
            return sample

        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [Task(**item) for item in data]

            if isinstance(data, dict):
                raw_tasks = data.get("tasks", [])
                if isinstance(raw_tasks, list):
                    return [Task(**item) for item in raw_tasks]

            raise TypeError
        except (json.JSONDecodeError, TypeError):
            messagebox.showwarning(
                "Arquivo inválido",
                "Não foi possível carregar tasks.json. Um novo arquivo será criado.",
            )
            self.save_tasks([])
            return []

    def save_tasks(self, tasks: list[Task] | None = None) -> None:
        current = tasks if tasks is not None else self.tasks
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": self.file_title.strip() or self.default_file_title(),
            "tasks": [asdict(task) for task in current],
            "tag_catalog": [
                {"name": item["name"], "color": item["color"], "order": int(item.get("order", 0))}
                for item in self.sorted_tag_catalog()
            ],
        }
        self.tasks_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def refresh_filter_options(self) -> None:
        responsible_menu = self.responsible_filter_menu["menu"]
        responsible_menu.delete(0, "end")

        responsible_options = ["Todos", *sorted(self.collect_responsibles())]
        for option in responsible_options:
            responsible_menu.add_command(
                label=option,
                command=lambda value=option: self.set_responsible_filter(value),
            )

        if self.responsible_filter_var.get() not in responsible_options:
            self.responsible_filter_var.set("Todos")

        important_menu = self.important_filter_menu["menu"]
        important_menu.delete(0, "end")

        important_options = ["Todas", "Importantes", "Não importantes"]
        for option in important_options:
            important_menu.add_command(
                label=option,
                command=lambda value=option: self.set_important_filter(value),
            )

        if self.important_filter_var.get() not in important_options:
            self.important_filter_var.set("Todas")

        tag_menu = self.tag_filter_menu["menu"]
        tag_menu.delete(0, "end")

        catalog_tag_names = [item["name"] for item in self.sorted_tag_catalog()]
        catalog_tag_name_set = set(catalog_tag_names)
        extra_tags = sorted(tag for tag in self.collect_tags() if tag not in catalog_tag_name_set)
        tag_options = ["Todas", *catalog_tag_names, *extra_tags]
        for option in tag_options:
            tag_menu.add_command(
                label=option,
                command=lambda value=option: self.set_tag_filter(value),
            )

        if self.tag_filter_var.get() not in tag_options:
            self.tag_filter_var.set("Todas")

    def set_responsible_filter(self, value: str) -> None:
        self.responsible_filter_var.set(value)
        self.render_tasks()

    def set_tag_filter(self, value: str) -> None:
        self.tag_filter_var.set(value)
        self.render_tasks()

    def set_important_filter(self, value: str) -> None:
        self.important_filter_var.set(value)
        self.render_tasks()

    def apply_chip_filters(self, responsible: str | None = None, tag: str | None = None) -> None:
        if responsible is not None:
            self.responsible_filter_var.set(responsible)
        if tag is not None:
            self.tag_filter_var.set(tag)
        self.render_tasks()

    def clear_filters(self) -> None:
        self.responsible_filter_var.set("Todos")
        self.important_filter_var.set("Todas")
        self.tag_filter_var.set("Todas")
        self.render_tasks()

    def collect_tags(self) -> set[str]:
        tags: set[str] = {item["name"] for item in self.tag_catalog.values()}
        for task in self.tasks:
            if self.is_section(task):
                continue
            tags.update(tag for tag in task.tags if tag.strip())
        return tags

    def collect_responsibles(self) -> set[str]:
        responsibles: dict[str, str] = {}
        for task in self.tasks:
            if self.is_section(task):
                continue
            cleaned = task.responsible.strip()
            if cleaned:
                responsibles.setdefault(cleaned.lower(), cleaned)
        return set(responsibles.values())

    def is_section(self, task: Task | None) -> bool:
        return bool(task and task.item_type == "section")

    def section_color(self, task: Task | None) -> str:
        if not task:
            return DEFAULT_SECTION_COLOR
        return self.normalize_color(task.section_color)

    def task_row_colors(self, task: Task | None) -> tuple[str, str]:
        if self.is_section(task):
            return "#eef3f8", "#eef3f8"
        if task and task.important:
            return "#FEE2E2", "#F87171"
        return "white", "#dbe3ec"

    def filtered_tasks(self) -> list[Task]:
        selected_responsible = self.responsible_filter_var.get()
        selected_important = self.important_filter_var.get()
        selected_tag = self.tag_filter_var.get()
        if selected_responsible == "Todos" and selected_important == "Todas" and selected_tag == "Todas":
            return self.tasks

        visible: list[Task] = []
        current_section: Task | None = None
        section_added = False
        selected_responsible_key = selected_responsible.lower()

        for task in self.tasks:
            if self.is_section(task):
                current_section = task
                section_added = False
                continue

            if selected_responsible != "Todos" and task.responsible.strip().lower() != selected_responsible_key:
                continue

            if selected_important == "Importantes" and not task.important:
                continue

            if selected_important == "Não importantes" and task.important:
                continue

            if selected_tag != "Todas" and selected_tag not in task.tags:
                continue

            if current_section and not section_added:
                visible.append(current_section)
                section_added = True
            visible.append(task)

        return visible

    def prompt_item_title(self, item_label: str, dialog_title: str) -> str | None:
        result: dict[str, str | None] = {"value": None}

        window = tk.Toplevel(self.root)
        window.title(dialog_title)
        window.geometry("460x270")
        window.resizable(False, False)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        content = tk.Frame(
            window,
            bg="white",
            highlightthickness=1,
            highlightbackground="#dbe3ec",
        )
        content.pack(fill="both", expand=True, padx=20, pady=20)

        footer = tk.Frame(content, bg="white")
        footer.pack(side="bottom", fill="x", padx=22, pady=(0, 20))

        tk.Label(
            content,
            text=dialog_title,
            font=("Segoe UI Semibold", 16),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=22, pady=(18, 6))

        tk.Label(
            content,
            text=f"Digite o nome da {item_label} para adicionar a lista.",
            font=("Segoe UI", 10),
            bg="white",
            fg="#475569",
        ).pack(anchor="w", padx=22)

        value_var = tk.StringVar()
        entry = tk.Entry(
            content,
            textvariable=value_var,
            font=("Segoe UI", 12),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
            fg="#0f172a",
        )
        entry.pack(fill="x", padx=22, pady=(18, 14), ipady=10)

        def submit() -> None:
            cleaned = value_var.get().strip()
            if not cleaned:
                messagebox.showinfo("Campo vazio", f"Digite um nome para criar a {item_label}.", parent=window)
                entry.focus_set()
                return
            result["value"] = cleaned
            window.destroy()

        tk.Button(
            footer,
            text="Cancelar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(10, 0))

        tk.Button(
            footer,
            text="Salvar",
            command=submit,
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        entry.bind("<Return>", lambda _event: submit())
        entry.bind("<Escape>", lambda _event: window.destroy())
        entry.focus_set()

        window.wait_window()
        if result["value"] is None:
            return None

        return result["value"]

    def add_task(self) -> None:
        title = self.prompt_item_title("tarefa", "Nova tarefa")
        if title is None:
            return

        self.tasks.append(Task(id=str(uuid4()), title=title))
        self.persist_and_refresh()

    def add_section(self) -> None:
        title = self.prompt_item_title("seção", "Nova seção")
        if title is None:
            return

        self.tasks.append(Task(id=str(uuid4()), title=title, item_type="section"))
        self.persist_and_refresh()

    def toggle_task(self, task_id: str, completed: bool) -> None:
        task = self.find_task(task_id)
        if task and not self.is_section(task):
            task.completed = completed
            self.persist_and_refresh()

    def toggle_task_important(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or self.is_section(task):
            return

        task.important = not task.important
        self.persist_and_refresh()

    def edit_task_title(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task:
            return

        self.inline_title_entry = None
        self.inline_title_var = None
        self.editing_task_id = task_id
        self.render_tasks(preserve_scroll=True)

    def edit_file_title(self) -> None:
        self.editing_file_title = True
        self.render_header_title()

    def save_inline_file_title(self) -> None:
        if not self.editing_file_title or not self.inline_file_title_var:
            return

        cleaned = self.inline_file_title_var.get().strip()
        if not cleaned:
            messagebox.showinfo("Título inválido", "O arquivo precisa ter um título.")
            return

        self.editing_file_title = False
        self.inline_file_title_entry = None
        self.inline_file_title_var = None
        if cleaned != self.file_title:
            self.file_title = cleaned
            self.save_tasks()
            self.update_window_title()
        self.render_header_title()

    def cancel_inline_file_title(self) -> None:
        self.editing_file_title = False
        self.inline_file_title_entry = None
        self.inline_file_title_var = None
        self.render_header_title()

    def save_inline_task_title(self, task_id: str, raw_value: str) -> None:
        task = self.find_task(task_id)
        if not task:
            self.editing_task_id = None
            self.render_tasks()
            return

        cleaned = raw_value.strip()
        if not cleaned:
            messagebox.showinfo("Título inválido", "A tarefa precisa ter um título.")
            return

        self.editing_task_id = None
        self.inline_title_entry = None
        self.inline_title_var = None
        if cleaned != task.title:
            task.title = cleaned
            self.persist_and_refresh(preserve_scroll=True)
            return

        self.render_tasks(preserve_scroll=True)

    def cancel_inline_task_title(self) -> None:
        self.editing_task_id = None
        self.inline_title_entry = None
        self.inline_title_var = None
        self.render_tasks(preserve_scroll=True)

    def edit_task_tags(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or self.is_section(task):
            return

        if not self.tag_catalog:
            self.open_tag_manager()
            if not self.tag_catalog:
                return

        window = tk.Toplevel(self.root)
        window.title("Associar tags")
        window.geometry("420x420")
        window.minsize(380, 340)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        tk.Label(
            window,
            text=f"Tags da tarefa: {task.title}",
            font=("Segoe UI Semibold", 14),
            bg="#eef3f8",
            fg="#0f172a",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            window,
            text="Selecione as tags cadastradas para esta tarefa.",
            font=("Segoe UI", 10),
            bg="#eef3f8",
            fg="#475569",
        ).pack(anchor="w", padx=20)

        list_panel = tk.Frame(window, bg="white", highlightthickness=1, highlightbackground="#dbe3ec")
        list_panel.pack(fill="both", expand=True, padx=20, pady=16)
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        list_canvas = tk.Canvas(list_panel, bg="white", highlightthickness=0, bd=0, height=210)
        list_scrollbar = tk.Scrollbar(
            list_panel,
            orient="vertical",
            command=list_canvas.yview,
            bg="#e2e8f0",
            activebackground="#cbd5e1",
            troughcolor="#f8fafc",
            width=12,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        list_canvas.configure(yscrollcommand=list_scrollbar.set)
        list_canvas.grid(row=0, column=0, sticky="nsew")
        list_scrollbar.grid(row=0, column=1, sticky="ns")

        selected: dict[str, tk.BooleanVar] = {}
        tags_container = tk.Frame(list_canvas, bg="white")
        tags_container_window = list_canvas.create_window((0, 0), window=tags_container, anchor="nw")

        def sync_task_tag_list_width(_event=None) -> None:
            list_canvas.itemconfigure(tags_container_window, width=list_canvas.winfo_width())

        def refresh_task_tag_scrollregion(_event=None) -> None:
            list_canvas.configure(scrollregion=list_canvas.bbox("all"))

        def task_tag_list_on_mousewheel(event) -> str | None:
            scrollregion = list_canvas.bbox("all")
            if not scrollregion:
                return None

            content_height = scrollregion[3] - scrollregion[1]
            if content_height <= list_canvas.winfo_height():
                return "break"

            delta = int(-event.delta / 120)
            if delta != 0:
                list_canvas.yview_scroll(delta, "units")
                return "break"
            return None

        def bind_task_tag_mousewheel(widget: tk.Widget) -> None:
            widget.bind("<MouseWheel>", task_tag_list_on_mousewheel, add="+")

        tags_container.bind("<Configure>", refresh_task_tag_scrollregion)
        list_canvas.bind("<Configure>", sync_task_tag_list_width)
        bind_task_tag_mousewheel(list_canvas)
        bind_task_tag_mousewheel(tags_container)

        def render_tag_options() -> None:
            for child in tags_container.winfo_children():
                child.destroy()
            selected.clear()

            if not self.tag_catalog:
                tk.Label(
                    tags_container,
                    text="Nenhuma tag cadastrada.",
                    font=("Segoe UI", 10),
                    bg="white",
                    fg="#64748b",
                ).pack(anchor="w")
                return

            current = {tag.lower() for tag in task.tags}
            for item in self.sorted_tag_catalog():
                key = item["name"].lower()
                row = tk.Frame(tags_container, bg="white")
                row.pack(fill="x", padx=14, pady=4)
                bind_task_tag_mousewheel(row)

                var = tk.BooleanVar(value=key in current)
                selected[key] = var

                checkbox = tk.Checkbutton(
                    row,
                    variable=var,
                    bg="white",
                    activebackground="white",
                )
                checkbox.pack(side="left", padx=(0, 10))
                bind_task_tag_mousewheel(checkbox)

                chip = tk.Label(
                    row,
                    text=item["name"],
                    font=("Segoe UI", 9),
                    bg=item["color"],
                    fg=self.contrast_text_color(item["color"]),
                    padx=9,
                    pady=3,
                    cursor="hand2",
                )
                chip.pack(side="left")
                chip.bind("<Button-1>", lambda _event, value=var: value.set(not value.get()))
                bind_task_tag_mousewheel(chip)

        render_tag_options()

        footer = tk.Frame(window, bg="#eef3f8")
        footer.pack(fill="x", padx=20, pady=(0, 20))

        tk.Button(
            footer,
            text="Gerenciar tags",
            command=lambda: self.open_tag_manager(on_close=render_tag_options),
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            footer,
            text="Salvar",
            command=lambda: self.save_task_tags(window, task_id, selected),
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        tk.Button(
            footer,
            text="Cancelar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(0, 10))

    def normalize_tags(self, raw_tags: str) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []

        for piece in raw_tags.split(","):
            tag = piece.strip()
            key = tag.lower()
            if tag and key not in seen:
                seen.add(key)
                normalized.append(tag)

        return normalized

    def save_task_tags(self, window: tk.Toplevel, task_id: str, selected: dict[str, tk.BooleanVar]) -> None:
        task = self.find_task(task_id)
        if not task:
            window.destroy()
            return

        task.tags = [
            item["name"]
            for item in self.sorted_tag_catalog()
            if selected.get(item["name"].lower()) and selected[item["name"].lower()].get()
        ]
        task.tags = self.ordered_task_tags(task.tags)
        window.destroy()
        self.persist_and_refresh()

    def delete_task(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task:
            return

        item_label = "seção" if self.is_section(task) else "tarefa"
        if not messagebox.askyesno(f"Excluir {item_label}", f"Deseja remover '{task.title}'?"):
            return

        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.persist_and_refresh()

    def duplicate_task(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task:
            return

        current_index = self.index_of_task(task_id)
        copied_task = Task(
            id=str(uuid4()),
            title=f"{task.title} (copia)",
            item_type=task.item_type,
            section_color=task.section_color,
            completed=task.completed,
            important=task.important,
            due_date=task.due_date,
            notes=task.notes,
            notes_rich=json.loads(json.dumps(task.notes_rich)) if task.notes_rich is not None else None,
            tags=list(task.tags),
            responsible=task.responsible,
        )
        insert_at = current_index + 1 if current_index != -1 else len(self.tasks)
        self.tasks.insert(insert_at, copied_task)
        self.persist_and_refresh()

    def set_task_responsible(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or self.is_section(task):
            return

        answer = simpledialog.askstring(
            "Definir responsável",
            "Informe o responsável da tarefa:",
            initialvalue=task.responsible,
            parent=self.root,
        )
        if answer is None:
            return

        task.responsible = answer.strip()
        self.persist_and_refresh()

    def set_section_color(self, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task or not self.is_section(task):
            return

        chosen = colorchooser.askcolor(
            color=self.section_color(task),
            parent=self.root,
            title="Escolher cor da seção",
        )[1]
        if not chosen:
            return

        task.section_color = self.normalize_color(chosen)
        self.persist_and_refresh()

    def show_task_context_menu(self, event, task_id: str) -> None:
        task = self.find_task(task_id)
        if not task:
            return

        menu = tk.Menu(self.root, tearoff=0)
        menu.configure(font=("Segoe UI", 10))
        menu.add_command(label="Editar", command=lambda tid=task_id: self.edit_task_title(tid))
        if not self.is_section(task):
            menu.add_separator()
            menu.add_command(
                label="Desmarcar como importante" if task.important else "Marcar como importante",
                command=lambda tid=task_id: self.toggle_task_important(tid),
            )
            menu.add_command(label="Alterar tags", command=lambda tid=task_id: self.edit_task_tags(tid))
            menu.add_command(label="Definir responsável", command=lambda tid=task_id: self.set_task_responsible(tid))
            menu.add_command(label="Definir data", command=lambda tid=task_id: self.open_due_date_dialog(tid))
            menu.add_command(label="Adicionar notas", command=lambda tid=task_id: self.open_notes_dialog(tid))
            menu.add_separator()
        else:
            menu.add_separator()
            menu.add_command(label="Definir cor", command=lambda tid=task_id: self.set_section_color(tid))
            menu.add_separator()
        menu.add_command(label="Duplicar", command=lambda tid=task_id: self.duplicate_task(tid))
        menu.add_command(label="Excluir", command=lambda tid=task_id: self.delete_task(tid))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def show_tag_chip_context_menu(self, event, tag_name: str) -> str:
        menu = tk.Menu(self.root, tearoff=0)
        menu.configure(font=("Segoe UI", 10))
        menu.add_command(
            label=f"Filtrar por tag {tag_name}",
            command=lambda value=tag_name: self.apply_chip_filters(tag=value),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()
        return "break"

    def show_responsible_chip_context_menu(self, event, responsible_name: str) -> str:
        menu = tk.Menu(self.root, tearoff=0)
        menu.configure(font=("Segoe UI", 10))
        menu.add_command(
            label=f"Filtrar por responsável {responsible_name}",
            command=lambda value=responsible_name: self.apply_chip_filters(responsible=value),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()
        return "break"

    def bind_task_context_menu(self, widget: tk.Widget, task_id: str) -> None:
        widget.bind("<Button-3>", lambda event, tid=task_id: self.show_task_context_menu(event, tid), add="+")
        for child in widget.winfo_children():
            self.bind_task_context_menu(child, task_id)

    def find_task(self, task_id: str) -> Task | None:
        return next((task for task in self.tasks if task.id == task_id), None)

    def persist_and_refresh(self, preserve_scroll: bool = False) -> None:
        self.save_tasks()
        self.storage_status_var.set(self.storage_status_text())
        self.refresh_filter_options()
        self.render_tasks(preserve_scroll=preserve_scroll)

    def reload_tasks_from_disk(self) -> None:
        self.tasks = self.load_tasks()
        self.sync_tag_catalog_with_tasks()
        self.normalize_task_tags()
        self.storage_status_var.set(self.storage_status_text())
        self.refresh_filter_options()
        self.render_tasks()

    def open_settings_window(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Configurações")
        window.geometry("680x580")
        window.minsize(620, 540)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        tk.Label(
            window,
            text="Configurações",
            font=("Segoe UI Semibold", 18),
            bg="#eef3f8",
            fg="#0f172a",
        ).pack(anchor="w", padx=24, pady=(20, 8))

        tk.Label(
            window,
            text="Escolha o arquivo onde as tarefas serão armazenadas.",
            font=("Segoe UI", 10),
            bg="#eef3f8",
            fg="#475569",
        ).pack(anchor="w", padx=24)

        panel = tk.Frame(window, bg="white", highlightthickness=1, highlightbackground="#dbe3ec")
        panel.pack(fill="both", expand=True, padx=24, pady=(20, 12))

        file_path_var = tk.StringVar(value=str(self.tasks_file))
        layout_var = tk.StringVar(value="Compacto" if self.layout_mode == "compact" else "Normal")
        responsible_color_var = tk.StringVar(value=self.responsible_color)

        tk.Label(
            panel,
            text="Arquivo de tarefas",
            font=("Segoe UI Semibold", 10),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        row = tk.Frame(panel, bg="white")
        row.pack(fill="x", padx=16, pady=(0, 16))

        entry = tk.Entry(
            row,
            textvariable=file_path_var,
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=8)

        tk.Button(
            row,
            text="Selecionar",
            command=lambda: self.choose_tasks_file(file_path_var),
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            panel,
            text="Layout da lista",
            font=("Segoe UI Semibold", 10),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(4, 8))

        layout_row = tk.Frame(panel, bg="white")
        layout_row.pack(fill="x", padx=16, pady=(0, 16))

        tk.Radiobutton(
            layout_row,
            text="Compacto",
            variable=layout_var,
            value="Compacto",
            font=("Segoe UI", 10),
            bg="white",
            activebackground="white",
            cursor="hand2",
        ).pack(side="left")

        tk.Radiobutton(
            layout_row,
            text="Normal",
            variable=layout_var,
            value="Normal",
            font=("Segoe UI", 10),
            bg="white",
            activebackground="white",
            cursor="hand2",
        ).pack(side="left", padx=(16, 0))

        tk.Label(
            panel,
            text="Cor do responsável",
            font=("Segoe UI Semibold", 10),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(4, 8))

        responsible_row = tk.Frame(panel, bg="white")
        responsible_row.pack(fill="x", padx=16, pady=(0, 16))

        responsible_preview = tk.Label(
            responsible_row,
            text="Responsável",
            font=("Segoe UI", 9),
            bg=responsible_color_var.get(),
            fg=self.contrast_text_color(responsible_color_var.get()),
            padx=10,
            pady=4,
        )
        responsible_preview.pack(side="left")

        tk.Button(
            responsible_row,
            text="Escolher cor",
            command=lambda: self.choose_responsible_color(responsible_color_var, responsible_preview),
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            panel,
            text="Tags",
            font=("Segoe UI Semibold", 10),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(4, 8))

        tags_row = tk.Frame(panel, bg="white")
        tags_row.pack(fill="x", padx=16, pady=(0, 16))

        tk.Label(
            tags_row,
            text="Abra o cadastro para criar, editar e reorganizar tags.",
            font=("Segoe UI", 10),
            bg="white",
            fg="#475569",
        ).pack(side="left")

        tk.Button(
            tags_row,
            text="Gerenciar tags",
            command=self.open_tag_manager,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        footer = tk.Frame(window, bg="#eef3f8")
        footer.pack(fill="x", padx=24, pady=(0, 24))

        tk.Button(
            footer,
            text="Salvar",
            command=lambda: self.save_settings(window, file_path_var.get(), layout_var.get(), responsible_color_var.get()),
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=14,
            pady=9,
            cursor="hand2",
        ).pack(side="right")

        tk.Button(
            footer,
            text="Cancelar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=14,
            pady=9,
            cursor="hand2",
        ).pack(side="right", padx=(0, 10))

    def choose_tasks_file(self, file_path_var: tk.StringVar) -> None:
        current_path = Path(file_path_var.get()).expanduser() if file_path_var.get().strip() else self.tasks_file
        initial_dir = str(current_path.parent if current_path.parent.exists() else APP_DIR)
        selected = filedialog.asksaveasfilename(
            title="Selecionar arquivo de tarefas",
            initialdir=initial_dir,
            initialfile=current_path.name or "tasks.json",
            defaultextension=".json",
            filetypes=[("Arquivo JSON", "*.json")],
            confirmoverwrite=False,
            parent=self.root,
        )
        if selected:
            file_path_var.set(selected)

    def choose_responsible_color(self, color_var: tk.StringVar, preview: tk.Label) -> None:
        chosen = colorchooser.askcolor(color=color_var.get(), parent=self.root, title="Escolher cor do responsável")[1]
        if not chosen:
            return

        normalized = self.normalize_color(chosen)
        color_var.set(normalized)
        preview.configure(
            bg=normalized,
            fg=self.contrast_text_color(normalized),
        )

    def save_settings(self, window: tk.Toplevel, file_path: str, layout_label: str, responsible_color: str) -> None:
        cleaned_path = file_path.strip()
        if not cleaned_path:
            messagebox.showerror("Configurações", "Escolha um arquivo válido.")
            return

        new_file = Path(cleaned_path).expanduser()
        selected_dir = new_file.parent
        cleaned_name = new_file.name
        invalid_chars = set('<>:"/\\|?*')
        if any(char in invalid_chars for char in cleaned_name):
            messagebox.showerror("Configurações", "O nome do arquivo contém caracteres inválidos.")
            return

        if not cleaned_name.lower().endswith(".json"):
            new_file = new_file.with_name(f"{cleaned_name}.json")

        try:
            selected_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            messagebox.showerror("Configurações", "Não foi possível acessar a pasta selecionada.")
            return

        if not new_file.exists():
            should_create = messagebox.askyesno(
                "Criar novo arquivo",
                "O arquivo selecionado não existe. Deseja criar um novo arquivo de tarefas vazio?",
                parent=window,
            )
            if not should_create:
                return

            self.tasks_file = new_file
            self.settings.set_tasks_path(str(new_file))
            self.file_title = self.default_file_title()
            self.tasks = []
            self.tag_catalog = {}
            self.save_tasks([])
        else:
            self.tasks_file = new_file
            self.settings.set_tasks_path(str(new_file))
            self.file_title = self.load_file_title()
            self.tag_catalog = self.load_tag_catalog()
            self.tasks = self.load_tasks()
            self.sync_tag_catalog_with_tasks()
            self.normalize_task_tags()

        self.layout_mode = "compact" if layout_label == "Compacto" else "normal"
        self.settings.set_layout_mode(self.layout_mode)
        self.responsible_color = self.normalize_color(responsible_color)
        self.settings.set_responsible_color(self.responsible_color)
        self.storage_status_var.set(self.storage_status_text())
        self.update_window_title()
        self.render_header_title()
        self.refresh_filter_options()
        self.render_tasks()
        window.destroy()
        messagebox.showinfo("Configurações", "Configurações atualizadas com sucesso.")

    def open_about_window(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Sobre")
        window.geometry("420x235")
        window.minsize(380, 220)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)

        panel = tk.Frame(window, bg="white", highlightthickness=1, highlightbackground="#dbe3ec")
        panel.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(
            panel,
            text="UltraTask",
            font=("Segoe UI Semibold", 16),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(18, 10))

        tk.Label(
            panel,
            text="Autores: Marcus Siqueira e ChatGPT Codex",
            font=("Segoe UI", 10),
            bg="white",
            fg="#334155",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        tk.Label(
            panel,
            text=f"Build: {BUILD_TIMESTAMP}",
            font=("Segoe UI", 9),
            bg="white",
            fg="#64748b",
        ).pack(anchor="w", padx=16, pady=(0, 18))

        tk.Button(
            panel,
            text="Fechar",
            command=window.destroy,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(anchor="e", padx=16, pady=(0, 18))

    def open_tag_manager(self, on_close=None) -> None:
        window = tk.Toplevel(self.root)
        window.title("Gerenciar tags")
        window.geometry("560x560")
        window.minsize(500, 520)
        window.configure(bg="#eef3f8")
        window.transient(self.root)
        window.grab_set()
        self.center_window(window)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(0, weight=1)

        if on_close is not None:
            def handle_close() -> None:
                self.refresh_filter_options()
                self.render_tasks()
                window.destroy()
                on_close()

            window.protocol("WM_DELETE_WINDOW", handle_close)
        else:
            def handle_close() -> None:
                self.refresh_filter_options()
                self.render_tasks()
                window.destroy()

            window.protocol("WM_DELETE_WINDOW", handle_close)

        content = tk.Frame(window, bg="#eef3f8")
        content.grid(row=0, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        tk.Label(
            content,
            text="Cadastro de tags",
            font=("Segoe UI Semibold", 18),
            bg="#eef3f8",
            fg="#0f172a",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))

        tk.Label(
            content,
            text="Cadastre tags globais, escolha uma cor e reutilize essas tags nas tarefas.",
            font=("Segoe UI", 10),
            bg="#eef3f8",
            fg="#475569",
        ).grid(row=1, column=0, sticky="w", padx=24)

        form = tk.Frame(content, bg="white", highlightthickness=1, highlightbackground="#dbe3ec")
        form.grid(row=2, column=0, sticky="ew", padx=24, pady=18)

        name_var = tk.StringVar()
        color_var = tk.StringVar(value=DEFAULT_TAG_COLOR)

        tk.Label(
            form,
            text="Nova tag",
            font=("Segoe UI Semibold", 10),
            bg="white",
            fg="#0f172a",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        form_row = tk.Frame(form, bg="white")
        form_row.pack(fill="x", padx=16, pady=(0, 16))

        tk.Entry(
            form_row,
            textvariable=name_var,
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            highlightcolor="#2563eb",
        ).pack(side="left", fill="x", expand=True, ipady=8)

        color_button = tk.Button(
            form_row,
            text="Cor",
            command=lambda: self.choose_tag_color(color_var, color_button),
            font=("Segoe UI", 10),
            relief="flat",
            bg=color_var.get(),
            fg=self.contrast_text_color(color_var.get()),
            activebackground=color_var.get(),
            activeforeground=self.contrast_text_color(color_var.get()),
            padx=12,
            pady=8,
            cursor="hand2",
        )
        color_button.pack(side="left", padx=(10, 0))

        list_panel = tk.Frame(content, bg="white", highlightthickness=1, highlightbackground="#dbe3ec")
        list_panel.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 16))
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)

        list_canvas = tk.Canvas(list_panel, bg="white", highlightthickness=0, bd=0, height=200)
        list_scrollbar = ttk.Scrollbar(list_panel, orient="vertical", command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scrollbar.set)
        list_canvas.grid(row=0, column=0, sticky="nsew")
        list_scrollbar.grid(row=0, column=1, sticky="ns")

        list_body = tk.Frame(list_canvas, bg="white")
        list_body_window = list_canvas.create_window((0, 0), window=list_body, anchor="nw")

        def sync_tag_list_width(_event=None) -> None:
            list_canvas.itemconfigure(list_body_window, width=list_canvas.winfo_width())

        def refresh_tag_list_scrollregion(_event=None) -> None:
            list_canvas.configure(scrollregion=list_canvas.bbox("all"))

        def tag_list_on_mousewheel(event) -> str | None:
            scrollregion = list_canvas.bbox("all")
            if not scrollregion:
                return None

            content_height = scrollregion[3] - scrollregion[1]
            if content_height <= list_canvas.winfo_height():
                return "break"

            delta = int(-event.delta / 120)
            if delta != 0:
                list_canvas.yview_scroll(delta, "units")
                return "break"
            return None

        def bind_tag_list_mousewheel(widget: tk.Widget) -> None:
            widget.bind("<MouseWheel>", tag_list_on_mousewheel, add="+")

        list_body.bind("<Configure>", refresh_tag_list_scrollregion)
        list_canvas.bind("<Configure>", sync_tag_list_width)
        bind_tag_list_mousewheel(list_canvas)
        bind_tag_list_mousewheel(list_body)

        def move_tag_and_refresh(key: str, direction: int) -> None:
            if not self.move_tag_order(key, direction):
                return
            self.save_tag_catalog()
            refresh_tags()

        def refresh_tags() -> None:
            for child in list_body.winfo_children():
                child.destroy()

            if not self.tag_catalog:
                tk.Label(
                    list_body,
                    text="Nenhuma tag cadastrada ainda.",
                    font=("Segoe UI", 10),
                    bg="white",
                    fg="#64748b",
                ).pack(anchor="w", padx=16, pady=16)
                return

            ordered_items = self.sorted_tag_catalog()
            for index, item in enumerate(ordered_items):
                tag_key = item["name"].lower()
                row = tk.Frame(list_body, bg="white")
                row.pack(fill="x", padx=12, pady=3)
                bind_tag_list_mousewheel(row)

                order_panel = tk.Frame(
                    row,
                    bg="#f8fbff",
                    highlightthickness=1,
                    highlightbackground="#dbe7f5",
                    padx=3,
                    pady=3,
                )
                order_panel.pack(side="left", padx=(0, 10))
                bind_tag_list_mousewheel(order_panel)

                move_up_button = tk.Button(
                    order_panel,
                    text="▲",
                    command=lambda key=tag_key: move_tag_and_refresh(key, -1),
                    font=("Segoe UI", 7),
                    relief="flat",
                    bg="#f8fbff",
                    fg="#64748b",
                    activebackground="#e2e8f0",
                    activeforeground="#334155",
                    bd=0,
                    width=2,
                    padx=0,
                    pady=0,
                    cursor="hand2",
                    state="normal" if index > 0 else "disabled",
                    disabledforeground="#cbd5e1",
                )
                move_up_button.pack()
                bind_tag_list_mousewheel(move_up_button)

                move_down_button = tk.Button(
                    order_panel,
                    text="▼",
                    command=lambda key=tag_key: move_tag_and_refresh(key, 1),
                    font=("Segoe UI", 7),
                    relief="flat",
                    bg="#f8fbff",
                    fg="#64748b",
                    activebackground="#e2e8f0",
                    activeforeground="#334155",
                    bd=0,
                    width=2,
                    padx=0,
                    pady=0,
                    cursor="hand2",
                    state="normal" if index < len(ordered_items) - 1 else "disabled",
                    disabledforeground="#cbd5e1",
                )
                move_down_button.pack(pady=(2, 0))
                bind_tag_list_mousewheel(move_down_button)

                name_label = tk.Label(
                    row,
                    text=item["name"],
                    font=("Segoe UI Semibold", 10),
                    bg=item["color"],
                    fg=self.contrast_text_color(item["color"]),
                    padx=10,
                    pady=4,
                )
                name_label.pack(side="left")
                bind_tag_list_mousewheel(name_label)

                color_label = tk.Label(
                    row,
                    text=item["color"],
                    font=("Consolas", 9),
                    bg="white",
                    fg="#475569",
                )
                color_label.pack(side="left", padx=(10, 0))
                bind_tag_list_mousewheel(color_label)

                color_action = tk.Button(
                    row,
                    text="Cor",
                    command=lambda name=item["name"]: self.update_tag_color(name, refresh_tags, refresh_main=False),
                    font=("Segoe UI", 9),
                    relief="flat",
                    bg=SECONDARY_BUTTON_BG,
                    fg=SECONDARY_BUTTON_FG,
                    activebackground=SECONDARY_BUTTON_HOVER,
                    padx=10,
                    pady=6,
                    cursor="hand2",
                )
                color_action.pack(side="right")
                bind_tag_list_mousewheel(color_action)

                delete_action = tk.Button(
                    row,
                    text="Excluir",
                    command=lambda name=item["name"]: self.delete_tag(name, refresh_tags, refresh_main=False),
                    font=("Segoe UI", 9),
                    relief="flat",
                    bg=SECONDARY_BUTTON_BG,
                    fg=SECONDARY_BUTTON_FG,
                    activebackground=SECONDARY_BUTTON_HOVER,
                    padx=10,
                    pady=6,
                    cursor="hand2",
                )
                delete_action.pack(side="right", padx=(0, 8))
                bind_tag_list_mousewheel(delete_action)

                rename_action = tk.Button(
                    row,
                    text="Renomear",
                    command=lambda name=item["name"]: self.rename_tag(name, refresh_tags, refresh_main=False),
                    font=("Segoe UI", 9),
                    relief="flat",
                    bg=SECONDARY_BUTTON_BG,
                    fg=SECONDARY_BUTTON_FG,
                    activebackground=SECONDARY_BUTTON_HOVER,
                    padx=10,
                    pady=6,
                    cursor="hand2",
                )
                rename_action.pack(side="right", padx=(0, 8))
                bind_tag_list_mousewheel(rename_action)

        refresh_tags()

        footer = tk.Frame(content, bg="#eef3f8")
        footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 20))

        tk.Button(
            footer,
            text="Adicionar tag",
            command=lambda: self.create_tag(name_var, color_var, color_button, refresh_tags, refresh_main=False),
            font=("Segoe UI Semibold", 10),
            relief="flat",
            bg=PRIMARY_BUTTON_BG,
            fg="white",
            activebackground=PRIMARY_BUTTON_HOVER,
            activeforeground="white",
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        tk.Button(
            footer,
            text="Fechar",
            command=handle_close,
            font=("Segoe UI", 10),
            relief="flat",
            bg=SECONDARY_BUTTON_BG,
            fg=SECONDARY_BUTTON_FG,
            activebackground=SECONDARY_BUTTON_HOVER,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(0, 10))

    def choose_tag_color(self, color_var: tk.StringVar, button: tk.Button) -> None:
        chosen = colorchooser.askcolor(color=color_var.get(), parent=self.root, title="Escolher cor da tag")[1]
        if not chosen:
            return

        normalized = self.normalize_color(chosen)
        color_var.set(normalized)
        button.configure(
            bg=normalized,
            fg=self.contrast_text_color(normalized),
            activebackground=normalized,
            activeforeground=self.contrast_text_color(normalized),
        )

    def create_tag(
        self,
        name_var: tk.StringVar,
        color_var: tk.StringVar,
        color_button: tk.Button,
        refresh_callback,
        refresh_main: bool = True,
    ) -> None:
        cleaned = self.clean_tag_name(name_var.get())
        if not cleaned:
            messagebox.showinfo("Tags", "Digite um nome para a tag.")
            return

        if cleaned.lower() in self.tag_catalog:
            messagebox.showinfo("Tags", "Essa tag já está cadastrada.")
            return

        self.tag_catalog[cleaned.lower()] = {
            "name": cleaned,
            "color": self.normalize_color(color_var.get()),
            "order": self.next_tag_order(),
        }
        self.save_tag_catalog()
        name_var.set("")
        color_var.set(DEFAULT_TAG_COLOR)
        color_button.configure(
            bg=DEFAULT_TAG_COLOR,
            fg=self.contrast_text_color(DEFAULT_TAG_COLOR),
            activebackground=DEFAULT_TAG_COLOR,
            activeforeground=self.contrast_text_color(DEFAULT_TAG_COLOR),
        )
        if refresh_main:
            self.refresh_filter_options()
            self.render_tasks()
        refresh_callback()

    def rename_tag(self, current_name: str, refresh_callback, refresh_main: bool = True) -> None:
        answer = simpledialog.askstring(
            "Renomear tag",
            "Novo nome da tag:",
            initialvalue=current_name,
            parent=self.root,
        )
        if answer is None:
            return

        cleaned = self.clean_tag_name(answer)
        if not cleaned:
            messagebox.showinfo("Tags", "Digite um nome válido para a tag.")
            return

        current_key = current_name.lower()
        new_key = cleaned.lower()
        if new_key != current_key and new_key in self.tag_catalog:
            messagebox.showinfo("Tags", "Já existe outra tag com esse nome.")
            return

        item = self.tag_catalog.pop(current_key, None)
        if not item:
            return

        item["name"] = cleaned
        self.tag_catalog[new_key] = item

        for task in self.tasks:
            task.tags = [cleaned if tag.lower() == current_key else tag for tag in task.tags]

        self.save_tag_catalog()
        self.save_tasks()
        if refresh_main:
            self.refresh_filter_options()
            self.render_tasks()
        refresh_callback()

    def update_tag_color(self, name: str, refresh_callback, refresh_main: bool = True) -> None:
        item = self.get_tag_entry(name)
        if not item:
            return

        chosen = colorchooser.askcolor(color=item["color"], parent=self.root, title="Escolher cor da tag")[1]
        if not chosen:
            return

        item["color"] = self.normalize_color(chosen)
        self.save_tag_catalog()
        if refresh_main:
            self.render_tasks()
        refresh_callback()

    def delete_tag(self, name: str, refresh_callback, refresh_main: bool = True) -> None:
        task_count = sum(1 for task in self.tasks if name in task.tags)
        message = f"Deseja excluir a tag '{name}'?"
        if task_count:
            message = (
                f"Deseja excluir a tag '{name}'? "
                f"Ela será removida de {task_count} tarefa(s)."
            )

        if not messagebox.askyesno("Excluir tag", message, parent=self.root):
            return

        self.tag_catalog.pop(name.lower(), None)
        self.reindex_tag_catalog()
        for task in self.tasks:
            task.tags = [tag for tag in task.tags if tag.lower() != name.lower()]

        self.save_tag_catalog()
        self.save_tasks()
        if refresh_main:
            self.refresh_filter_options()
            self.render_tasks()
        refresh_callback()

    def render_tasks(self, preserve_scroll: bool = False) -> None:
        scroll_fraction = self.current_scroll_fraction() if preserve_scroll else 0.0
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.task_rows.clear()
        self.drop_indicator = tk.Frame(self.list_frame, bg="#2563eb", height=4)

        tasks = self.filtered_tasks()
        if not tasks:
            empty = tk.Label(
                self.list_frame,
                text="Nenhuma tarefa encontrada para o filtro atual.",
                font=("Segoe UI", 11),
                bg="#eef3f8",
                fg="#64748b",
                pady=32,
            )
            empty.pack(fill="x")
            if preserve_scroll:
                self.restore_scroll_fraction(scroll_fraction)
            return

        for task in tasks:
            self.create_task_row(task)

        if preserve_scroll:
            self.restore_scroll_fraction(scroll_fraction)

    def create_task_row(self, task: Task) -> None:
        if self.is_section(task):
            self.create_section_row(task)
            return

        metrics = self.task_layout_metrics()
        row_bg = "#FEE2E2" if task.important else "white"
        border_color = "#F87171" if task.important else "#dbe3ec"
        row = tk.Frame(
            self.list_frame,
            bg=row_bg,
            highlightthickness=1,
            highlightbackground=border_color,
            padx=metrics["row_padx"],
            pady=metrics["row_pady"],
        )
        row.pack(fill="x", pady=metrics["row_pack_pady"])
        self.task_rows[task.id] = row

        grip = tk.Label(
            row,
            text="::",
            font=metrics["grip_font"],
            fg="#94a3b8",
            bg=row_bg,
            cursor="fleur",
            width=2,
        )
        grip.pack(side="left", padx=metrics["grip_padx"])
        grip.bind("<ButtonPress-1>", lambda event, tid=task.id: self.start_drag(event, tid))

        content = tk.Frame(row, bg=row_bg)
        content.pack(side="left", fill="x", expand=True, padx=metrics["content_padx"])

        title_line = tk.Frame(content, bg=row_bg)
        title_line.pack(fill="x")

        title_font = tkfont.Font(family="Segoe UI", size=11)
        title_font.configure(overstrike=1 if task.completed else 0)
        title_color = "#94a3b8" if task.completed else "#0f172a"

        ordered_tags = self.ordered_task_tags(task.tags)
        if ordered_tags:
            for tag in ordered_tags:
                color = self.get_tag_color(tag)
                pill = tk.Label(
                    title_line,
                    text=tag,
                    font=metrics["tag_font"],
                    bg=color,
                    fg=self.contrast_text_color(color),
                    padx=metrics["tag_padx"],
                    pady=metrics["tag_pady"],
                    cursor="hand2",
                )
                pill.pack(side="left", padx=metrics["tag_pack_padx"])
                pill.bind("<Button-1>", lambda _event, tid=task.id: self.edit_task_tags(tid))
                pill.bind("<Button-3>", lambda event, value=tag: self.show_tag_chip_context_menu(event, value))

        if task.responsible:
            responsible_pill = self.create_responsible_chip(title_line, task.responsible, metrics)
            responsible_pill.pack(side="left", padx=metrics["tag_pack_padx"])
            responsible_pill.bind("<Button-1>", lambda _event, tid=task.id: self.set_task_responsible(tid))
            responsible_pill.bind(
                "<Button-3>",
                lambda event, value=task.responsible: self.show_responsible_chip_context_menu(event, value),
            )

        if self.editing_task_id == task.id:
            edit_var = tk.StringVar(value=task.title)
            title_entry = tk.Entry(
                title_line,
                textvariable=edit_var,
                font=metrics["title_entry_font"],
                relief="flat",
                highlightthickness=1,
                highlightbackground="#93c5fd",
                highlightcolor="#2563eb",
            )
            self.inline_title_var = edit_var
            self.inline_title_entry = title_entry
            title_entry.pack(side="left", fill="x", expand=True, ipady=metrics["title_entry_ipady"])
            title_entry.bind(
                "<Return>",
                lambda _event, tid=task.id, var=edit_var: self.save_inline_task_title(tid, var.get()),
            )
            title_entry.bind("<Escape>", lambda _event: self.cancel_inline_task_title())
            title_entry.bind(
                "<FocusOut>",
                lambda _event, tid=task.id, var=edit_var: self.save_inline_task_title(tid, var.get()),
            )
            title_entry.focus_set()
            title_entry.select_range(0, "end")
        else:
            title_label = tk.Label(
                title_line,
                text=task.title,
                font=metrics["title_font"],
                fg=title_color,
                bg=row_bg,
                anchor="w",
                cursor="xterm",
            )
            title_label.pack(side="left", fill="x", expand=True)
            title_label.bind("<Button-1>", lambda _event, tid=task.id: self.edit_task_title(tid))

        actions = tk.Frame(row, bg=row_bg)
        actions.pack(side="right")

        for label, command, button_bg, active_bg, font_name, fg_color, active_fg_color in [
            (
                "!",
                lambda tid=task.id: self.toggle_task_important(tid),
                "#BFDBFE" if task.important else SECONDARY_BUTTON_BG,
                "#93C5FD" if task.important else SECONDARY_BUTTON_HOVER,
                metrics["action_font"],
                "#1E40AF" if task.important else SECONDARY_BUTTON_FG,
                "#1E40AF" if task.important else SECONDARY_BUTTON_FG,
            ),
            ("×", lambda tid=task.id: self.delete_task(tid), SECONDARY_BUTTON_BG, SECONDARY_BUTTON_HOVER, metrics["action_font"], SECONDARY_BUTTON_FG, SECONDARY_BUTTON_FG),
        ]:
            tk.Button(
                actions,
                text=label,
                command=command,
                font=font_name,
                relief="sunken" if label == "!" and task.important else "flat",
                bg=button_bg,
                fg=fg_color,
                activebackground=active_bg,
                activeforeground=active_fg_color,
                cursor="hand2",
                width=2,
                padx=metrics["action_padx"],
                pady=metrics["action_pady"],
                bd=1 if label == "!" and task.important else 0,
            ).pack(side="left", padx=metrics["action_pack_padx"])

        due_date_label = tk.Label(
            row,
            text=self.format_due_date(task.due_date),
            font=("Segoe UI", 9 if self.layout_mode == "compact" else 10),
            fg=self.due_date_text_color(task.due_date),
            bg=row_bg,
            cursor="hand2",
            width=10,
            anchor="e",
            justify="right",
            padx=8,
        )
        due_date_label.pack(side="right", padx=(8, 6))
        due_date_label.bind("<Button-1>", lambda _event, tid=task.id: self.open_due_date_dialog(tid))

        if task.notes.strip():
            notes_indicator = tk.Label(
                row,
                text="nota",
                font=("Segoe UI", 8 if self.layout_mode == "compact" else 9),
                bg="#E0F2FE",
                fg="#075985",
                padx=7,
                pady=1,
                cursor="hand2",
            )
            notes_indicator.pack(side="right", padx=(8, 2))
            notes_indicator.bind("<Button-1>", lambda _event, tid=task.id: self.open_notes_dialog(tid))

        self.bind_task_context_menu(row, task.id)

    def create_section_row(self, task: Task) -> None:
        metrics = self.task_layout_metrics()
        section_color = self.section_color(task)
        row = tk.Frame(
            self.list_frame,
            bg="#eef3f8",
            highlightthickness=0,
            padx=metrics["row_padx"],
            pady=0,
        )
        row.pack(fill="x", pady=(8, max(1, int(metrics["row_pack_pady"]))))
        self.task_rows[task.id] = row

        grip = tk.Label(
            row,
            text="::",
            font=metrics["grip_font"],
            fg="#cbd5e1",
            bg="#eef3f8",
            cursor="fleur",
            width=2,
        )
        grip.pack(side="left", padx=metrics["grip_padx"])
        grip.bind("<ButtonPress-1>", lambda event, tid=task.id: self.start_drag(event, tid))

        section_line = tk.Frame(row, bg="#eef3f8")
        section_line.pack(side="left", fill="x", expand=True, pady=(8, 2))

        lead_line = tk.Frame(section_line, bg=section_color, height=1, width=28)
        lead_line.pack(side="left", padx=(0, 6), pady=(7, 0))
        lead_line.pack_propagate(False)

        if self.editing_task_id == task.id:
            edit_var = tk.StringVar(value=task.title)
            title_entry = tk.Entry(
                section_line,
                textvariable=edit_var,
                font=("Segoe UI Semibold", 10),
                relief="flat",
                justify="left",
                highlightthickness=1,
                highlightbackground=section_color,
                highlightcolor=section_color,
            )
            self.inline_title_var = edit_var
            self.inline_title_entry = title_entry
            title_entry.pack(side="left", ipadx=10, ipady=2, pady=(0, 0))
            title_entry.bind(
                "<Return>",
                lambda _event, tid=task.id, var=edit_var: self.save_inline_task_title(tid, var.get()),
            )
            title_entry.bind("<Escape>", lambda _event: self.cancel_inline_task_title())
            title_entry.bind(
                "<FocusOut>",
                lambda _event, tid=task.id, var=edit_var: self.save_inline_task_title(tid, var.get()),
            )
            title_entry.focus_set()
            title_entry.select_range(0, "end")
        else:
            title_label = tk.Label(
                section_line,
                text=task.title.upper(),
                font=("Segoe UI Semibold", 10),
                fg=section_color,
                bg="#eef3f8",
                padx=2,
                cursor="xterm",
                anchor="s",
            )
            title_label.pack(side="left", pady=(6, 0))
            title_label.bind("<Button-1>", lambda _event, tid=task.id: self.edit_task_title(tid))

        line_right = tk.Frame(section_line, bg=section_color, height=1)
        line_right.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=(7, 0))

        self.bind_task_context_menu(row, task.id)

    def start_drag(self, event, task_id: str) -> None:
        if (
            self.tag_filter_var.get() != "Todas"
            or self.responsible_filter_var.get() != "Todos"
            or self.important_filter_var.get() != "Todas"
        ):
            messagebox.showinfo(
                "Reordenação desativada",
                "Limpe os filtros para reorganizar a lista completa.",
            )
            return

        self.drag_data["task_id"] = task_id
        self.drag_data["active"] = True
        self.drag_data["target_index"] = self.index_of_task(task_id)
        self.highlight_dragged_row(task_id)
        self.show_drop_indicator(self.drag_data["target_index"])
        self.root.bind_all("<B1-Motion>", self.drag_task)
        self.root.bind_all("<ButtonRelease-1>", self.finish_drag)

    def drag_task(self, event) -> None:
        task_id = self.drag_data["task_id"]
        if not task_id or not self.drag_data["active"]:
            return

        target_index = self.target_index_from_pointer(event.y_root)
        if target_index is None:
            self.auto_scroll(event.y_root)
            return

        self.drag_data["target_index"] = target_index
        self.show_drop_indicator(target_index)
        self.auto_scroll(event.y_root)

    def finish_drag(self, _event) -> None:
        task_id = self.drag_data["task_id"]
        target_index = self.drag_data["target_index"]
        if task_id:
            self.clear_drag_highlight(task_id)
            current_index = self.index_of_task(task_id)
            if current_index != -1 and target_index is not None:
                dragged_task = self.tasks.pop(current_index)
                if current_index < target_index:
                    target_index -= 1
                self.tasks.insert(target_index, dragged_task)
                self.save_tasks()
                self.render_tasks()
        self.hide_drop_indicator()
        self.root.unbind_all("<B1-Motion>")
        self.root.unbind_all("<ButtonRelease-1>")
        self.drag_data = {"task_id": None, "active": False, "target_index": None}

    def index_of_task(self, task_id: str) -> int:
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                return index
        return -1

    def reorder_target_from_pointer(
        self,
        ordered_keys: list[str],
        row_widgets: dict[str, tk.Widget],
        y_root: int,
    ) -> int | None:
        self.root.update_idletasks()
        for index, key in enumerate(ordered_keys):
            row = row_widgets.get(key)
            if not row or not row.winfo_exists():
                continue

            top = row.winfo_rooty()
            bottom = top + row.winfo_height()
            midpoint = top + (row.winfo_height() / 2)

            if top <= y_root <= bottom:
                return index if y_root <= midpoint else index + 1

        if not ordered_keys:
            return 0

        first_row = row_widgets.get(ordered_keys[0])
        last_row = row_widgets.get(ordered_keys[-1])
        if first_row and y_root < first_row.winfo_rooty():
            return 0
        if last_row and y_root > last_row.winfo_rooty() + last_row.winfo_height():
            return len(ordered_keys)
        return None

    def show_reorder_indicator(
        self,
        indicator: tk.Frame | None,
        container: tk.Widget,
        ordered_keys: list[str],
        row_widgets: dict[str, tk.Widget],
        target_index: int,
        edge_pady: tuple[int, int] = (4, 0),
        leading_pady: tuple[int, int] = (0, 4),
        middle_pady: int = 2,
    ) -> None:
        if not indicator:
            return

        indicator.pack_forget()
        visible_rows = [row_widgets[key] for key in ordered_keys if key in row_widgets and row_widgets[key].winfo_exists()]
        if not visible_rows:
            return

        if target_index <= 0:
            indicator.pack(in_=container, before=visible_rows[0], fill="x", pady=leading_pady)
            return

        if target_index >= len(visible_rows):
            indicator.pack(in_=container, after=visible_rows[-1], fill="x", pady=edge_pady)
            return

        indicator.pack(in_=container, before=visible_rows[target_index], fill="x", pady=middle_pady)

    def auto_scroll_canvas(self, canvas: tk.Canvas, y_root: int) -> None:
        scrollregion = canvas.bbox("all")
        if not scrollregion:
            return

        content_height = scrollregion[3] - scrollregion[1]
        canvas_height = canvas.winfo_height()
        if content_height <= canvas_height:
            canvas.yview_moveto(0)
            return

        canvas_top = canvas.winfo_rooty()
        canvas_bottom = canvas_top + canvas_height
        top_fraction, bottom_fraction = canvas.yview()

        if y_root < canvas_top + 40 and top_fraction > 0:
            canvas.yview_scroll(-1, "units")
        elif y_root > canvas_bottom - 40 and bottom_fraction < 1:
            canvas.yview_scroll(1, "units")

    def target_index_from_pointer(self, y_root: int) -> int | None:
        return self.reorder_target_from_pointer([task.id for task in self.tasks], self.task_rows, y_root)

    def show_drop_indicator(self, target_index: int) -> None:
        self.show_reorder_indicator(
            self.drop_indicator,
            self.list_frame,
            [task.id for task in self.tasks],
            self.task_rows,
            target_index,
            edge_pady=(4, 0),
            leading_pady=(0, 4),
            middle_pady=2,
        )

    def hide_drop_indicator(self) -> None:
        if self.drop_indicator:
            self.drop_indicator.pack_forget()

    def highlight_dragged_row(self, task_id: str) -> None:
        for tid, row in self.task_rows.items():
            if not row.winfo_exists():
                continue
            if tid == task_id:
                row.configure(bg="#eff6ff", highlightbackground="#60a5fa")
                for child in row.winfo_children():
                    self.tint_widget_tree(child, "#eff6ff")
            else:
                base_bg, base_border = self.task_row_colors(self.find_task(tid))
                row.configure(bg=base_bg, highlightbackground=base_border)
                for child in row.winfo_children():
                    self.tint_widget_tree(child, base_bg)

    def clear_drag_highlight(self, task_id: str) -> None:
        row = self.task_rows.get(task_id)
        if not row or not row.winfo_exists():
            return
        task = self.find_task(task_id)
        base_bg, base_border = self.task_row_colors(task)
        row.configure(bg=base_bg, highlightbackground=base_border)
        for child in row.winfo_children():
            self.tint_widget_tree(child, base_bg)

    def tint_widget_tree(self, widget: tk.Widget, bg: str) -> None:
        try:
            current_bg = widget.cget("bg")
            if current_bg in {"white", "#eff6ff", "#FEF2F2", "#FEE2E2", "#eef3f8"}:
                widget.configure(bg=bg)
            if widget.winfo_class() == "Checkbutton":
                widget.configure(activebackground=bg)
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self.tint_widget_tree(child, bg)

    def auto_scroll(self, y_root: int) -> None:
        self.auto_scroll_canvas(self.canvas, y_root)


def main() -> None:
    root = tk.Tk()
    app = TaskManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
