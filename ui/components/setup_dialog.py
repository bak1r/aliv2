"""Ilk kurulum dialog'u — API key girisi."""

from __future__ import annotations

import customtkinter as ctk
from ui.theme import *


class SetupDialog(ctk.CTkToplevel):
    """API key giris penceresi."""

    def __init__(self, parent, on_complete=None):
        super().__init__(parent)
        self.on_complete = on_complete
        self.title("Ali v2 — Ilk Kurulum")
        self.geometry("450x350")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)

        # Baslik
        ctk.CTkLabel(
            self, text="Ali v2 — Avukat AI",
            font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
            text_color=ACCENT_GOLD,
        ).pack(pady=(30, 5))

        ctk.CTkLabel(
            self, text="API anahtarlarinizi girin",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 20))

        # Gemini key
        ctk.CTkLabel(
            self, text="Google Gemini API Key:",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=40)

        self.gemini_entry = ctk.CTkEntry(
            self, width=370, height=35, show="*",
            fg_color=BG_INPUT, border_color=ACCENT_BLUE,
        )
        self.gemini_entry.pack(padx=40, pady=(2, 10))

        # Anthropic key
        ctk.CTkLabel(
            self, text="Anthropic API Key:",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=40)

        self.anthropic_entry = ctk.CTkEntry(
            self, width=370, height=35, show="*",
            fg_color=BG_INPUT, border_color=ACCENT_BLUE,
        )
        self.anthropic_entry.pack(padx=40, pady=(2, 20))

        # Kaydet butonu
        ctk.CTkButton(
            self, text="Kaydet ve Baslat",
            font=(FONT_FAMILY, FONT_SIZE_NORMAL, "bold"),
            fg_color=ACCENT_BLUE, hover_color="#3a7bc8",
            height=40, width=200,
            command=self._save,
        ).pack(pady=10)

        # Status
        self.status_label = ctk.CTkLabel(
            self, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=ACCENT_RED,
        )
        self.status_label.pack(pady=5)

        self.grab_set()

    def _save(self):
        gemini = self.gemini_entry.get().strip()
        anthropic = self.anthropic_entry.get().strip()

        if not gemini or len(gemini) < 10:
            self.status_label.configure(text="Gecerli bir Gemini API key girin.")
            return
        if not anthropic or len(anthropic) < 10:
            self.status_label.configure(text="Gecerli bir Anthropic API key girin.")
            return

        from core.config import save_api_keys
        save_api_keys(gemini_key=gemini, anthropic_key=anthropic)

        self.status_label.configure(text="Kaydedildi!", text_color=ACCENT_GREEN)

        if self.on_complete:
            self.after(500, self.on_complete)

        self.after(800, self.destroy)
