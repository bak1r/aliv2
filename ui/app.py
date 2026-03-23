"""Ali v2 — Ana UI penceresi (CustomTkinter)."""

from __future__ import annotations

import threading
from datetime import datetime

import customtkinter as ctk

from ui.theme import *
from ui.components.setup_dialog import SetupDialog
from core.config import is_configured, SETTINGS
from core.brain import think, get_cost_summary


class AliApp(ctk.CTk):
    """Ana uygulama penceresi."""

    def __init__(self):
        super().__init__()

        ui_cfg = SETTINGS.get("ui", {})
        self.title("Ali v2 — Avukat AI Asistani")
        self.geometry(f"{ui_cfg.get('window_width', 1200)}x{ui_cfg.get('window_height', 750)}")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._status = "disconnected"
        self._voice_engine = None

        self._build_ui()

        # Ilk kurulum kontrolu
        if not is_configured():
            self.after(500, self._show_setup)

    def _build_ui(self):
        """UI bilesenleri olustur."""
        # ── Ust bar ──────────────────────────────────────────────────
        top_bar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=50)
        top_bar.pack(fill="x", padx=5, pady=(5, 0))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar, text="ALI",
            font=(FONT_FAMILY, 20, "bold"),
            text_color=ACCENT_GOLD,
        ).pack(side="left", padx=15)

        ctk.CTkLabel(
            top_bar, text="Avukat AI v2.0",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            top_bar, text="● Baglanti bekleniyor",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=ACCENT_RED,
        )
        self.status_label.pack(side="right", padx=15)

        self.cost_label = ctk.CTkLabel(
            top_bar, text="$0.00",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
        )
        self.cost_label.pack(side="right", padx=10)

        # ── Ana icerik ───────────────────────────────────────────────
        main_frame = ctk.CTkFrame(self, fg_color=BG_DARK)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Sol panel — Arac durumu
        left_panel = ctk.CTkFrame(main_frame, fg_color=BG_PANEL, width=220)
        left_panel.pack(side="left", fill="y", padx=(0, 5))
        left_panel.pack_propagate(False)

        ctk.CTkLabel(
            left_panel, text="Araclar",
            font=(FONT_FAMILY, FONT_SIZE_LARGE, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=10)

        self.tool_frame = ctk.CTkScrollableFrame(
            left_panel, fg_color=BG_PANEL,
        )
        self.tool_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self._populate_tools()

        # Orta — Chat log
        center_frame = ctk.CTkFrame(main_frame, fg_color=BG_PANEL)
        center_frame.pack(side="left", fill="both", expand=True)

        self.chat_log = ctk.CTkTextbox(
            center_frame, fg_color=BG_DARK,
            text_color=TEXT_PRIMARY,
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            wrap="word", state="disabled",
        )
        self.chat_log.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        # Giris alani
        input_frame = ctk.CTkFrame(center_frame, fg_color=BG_PANEL, height=50)
        input_frame.pack(fill="x", padx=10, pady=(0, 10))
        input_frame.pack_propagate(False)

        self.input_entry = ctk.CTkEntry(
            input_frame, fg_color=BG_INPUT,
            placeholder_text="Mesajinizi yazin...",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            height=40,
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(5, 5), pady=5)
        self.input_entry.bind("<Return>", self._on_send)

        ctk.CTkButton(
            input_frame, text="Gonder",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            fg_color=ACCENT_BLUE, hover_color="#3a7bc8",
            width=80, height=40,
            command=self._on_send,
        ).pack(side="right", padx=5, pady=5)

        # Mikrofon butonu
        self.mic_btn = ctk.CTkButton(
            input_frame, text="🎤",
            font=(FONT_FAMILY, 18),
            fg_color=ACCENT_GREEN, hover_color="#16a34a",
            width=40, height=40,
            command=self._toggle_voice,
        )
        self.mic_btn.pack(side="right", padx=(0, 5), pady=5)

    def _populate_tools(self):
        """Arac listesini doldur."""
        try:
            from tools import get_registry
            registry = get_registry()
        except Exception:
            registry = {}

        categories = {
            "legal": ("Hukuk", []),
            "computer": ("Bilgisayar", []),
            "general": ("Genel", []),
        }

        for name, tool in registry.items():
            module = tool.__class__.__module__
            if "legal" in module:
                categories["legal"][1].append(name)
            elif "computer" in module:
                categories["computer"][1].append(name)
            else:
                categories["general"][1].append(name)

        for cat_key, (cat_name, tools) in categories.items():
            if not tools:
                continue
            color = TOOL_COLORS.get(cat_key, ACCENT_BLUE)

            ctk.CTkLabel(
                self.tool_frame, text=cat_name,
                font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                text_color=color,
            ).pack(anchor="w", pady=(8, 2))

            for tool_name in sorted(tools):
                ctk.CTkLabel(
                    self.tool_frame, text=f"  ● {tool_name}",
                    font=(FONT_FAMILY, FONT_SIZE_SMALL),
                    text_color=TEXT_SECONDARY,
                ).pack(anchor="w")

    def _on_send(self, event=None):
        """Mesaj gonderme."""
        message = self.input_entry.get().strip()
        if not message:
            return

        self.input_entry.delete(0, "end")
        self._write_chat(f"Sen: {message}", TEXT_PRIMARY)

        # Claude'a gonder (ayri thread)
        threading.Thread(
            target=self._process_message,
            args=(message,),
            daemon=True,
        ).start()

    def _process_message(self, message: str):
        """Mesaji Claude'a gonder, sonucu goster."""
        self._write_chat("Ali dusunuyor...", TEXT_MUTED)

        try:
            response = think(user_message=message)
            # "Ali dusunuyor..." satirini sil
            self.chat_log.configure(state="normal")
            content = self.chat_log.get("1.0", "end")
            lines = content.split("\n")
            # Son "dusunuyor" satirini bul ve sil
            new_lines = [l for l in lines if "Ali dusunuyor" not in l]
            self.chat_log.delete("1.0", "end")
            self.chat_log.insert("1.0", "\n".join(new_lines))
            self.chat_log.configure(state="disabled")

            self._write_chat(f"Ali: {response}", ACCENT_GOLD)

            # Maliyet guncelle
            cost = get_cost_summary()
            total = (cost["input_tokens"] * 3 + cost["output_tokens"] * 15) / 1_000_000
            self.cost_label.configure(text=f"${total:.3f}")

        except Exception as e:
            self._write_chat(f"Hata: {e}", ACCENT_RED)

    def _write_chat(self, text: str, color: str = TEXT_PRIMARY):
        """Chat log'a yaz."""
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"\n{text}\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def _toggle_voice(self):
        """Sesli modu ac/kapat."""
        if self._voice_engine and self._voice_engine._running:
            self._voice_engine.stop()
            self.mic_btn.configure(fg_color=ACCENT_GREEN, text="🎤")
            self.set_status("disconnected")
        else:
            self.mic_btn.configure(fg_color=ACCENT_RED, text="⏹")
            threading.Thread(target=self._start_voice, daemon=True).start()

    def _start_voice(self):
        """Ses motorunu baslat."""
        import asyncio
        from core.voice import VoiceEngine

        self._voice_engine = VoiceEngine(ui=self)
        self.set_status("connected")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._voice_engine.start())

    def set_status(self, status: str):
        """Durum guncelle."""
        self._status = status
        status_map = {
            "connected": ("● Bagli", ACCENT_GREEN),
            "disconnected": ("● Bagli degil", ACCENT_RED),
            "reconnecting": ("● Yeniden baglaniyor...", ACCENT_GOLD),
            "thinking": ("● Dusunuyor...", ACCENT_BLUE),
        }
        text, color = status_map.get(status, ("● ?", TEXT_MUTED))
        try:
            self.status_label.configure(text=text, text_color=color)
        except Exception:
            pass

    def _show_setup(self):
        """Ilk kurulum dialog'unu goster."""
        SetupDialog(self, on_complete=lambda: self._write_chat(
            "API anahtarlari kaydedildi. Ali hazir!", ACCENT_GREEN
        ))

    def write_log(self, text: str):
        """Tool'lardan gelen log mesajlari."""
        self._write_chat(f"  [{text}]", TEXT_MUTED)
