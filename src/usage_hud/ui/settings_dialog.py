"""Settings dialog — general knobs plus per-service enable/detect/credentials.

Reached from the tray menu ("Settings…"). Two tabs: General (refresh
interval, opacity, display mode, alert thresholds) and Services (one box per
provider — enable/disable, a plain-language detected/not-detected line, and
the one credential field that's actually needed: GitHub's token, since
Actions/storage billing has no local file to auto-detect a subscription
from the way Cursor/Copilot/OpenCode Go/OpenAI/Claude do).

Claude/Anthropic deliberately gets no credential field here — see
AnthropicProvider: it is local-files-only by design, zero network calls,
and this dialog must not grow a way around that.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from usage_hud.branding import APP_NAME
from usage_hud.config import Settings, save_user_settings
from usage_hud.providers.anthropic import claude_present_locally
from usage_hud.providers.opencode_auth import auth_block, load_opencode_auth
from usage_hud.providers_pref import KNOWN_PROVIDERS, ProviderPrefs


def _detect_status(provider_id: str, auth: dict) -> tuple[bool, str]:
    """(detected, plain-language line) — everything checkable without a
    network call, so opening the dialog never blocks on I/O."""
    if provider_id == "cursor":
        return True, "always on (local editor session)"
    if provider_id == "copilot":
        ok = auth_block(auth, "github-copilot", "github_copilot") is not None
        return ok, "signed in via OpenCode" if ok else "not signed in — run `opencode auth login`"
    if provider_id == "opencode-go":
        ok = auth_block(auth, "opencode-go", "opencode") is not None
        return ok, "signed in via OpenCode" if ok else "not signed in — run `opencode auth login`"
    if provider_id == "openai":
        ok = auth_block(auth, "openai", "chatgpt", "openai-codex") is not None
        return ok, "signed in via OpenCode" if ok else "not signed in — run `opencode auth login`"
    if provider_id == "anthropic":
        ok = claude_present_locally()
        return ok, "Claude Desktop data found locally" if ok else "no local Claude Desktop data found"
    if provider_id == "cloud":
        return False, "experimental stub — off unless enabled below"
    if provider_id == "github":
        return False, "needs a token below, or a `gh auth login` session"
    return False, ""


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Settings — {APP_NAME}")
        self.setMinimumWidth(480)
        self._settings = settings
        self._prefs = ProviderPrefs(settings.state_dir / "providers.json")
        self._auth = load_opencode_auth()
        self._enabled_checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_services_tab(), "Services")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._refresh = QSpinBox()
        self._refresh.setRange(30, 3600)
        self._refresh.setSuffix(" s")
        self._refresh.setValue(self._settings.refresh_seconds)
        form.addRow("Refresh interval", self._refresh)

        self._opacity = QSpinBox()
        self._opacity.setRange(35, 100)
        self._opacity.setSuffix(" %")
        self._opacity.setValue(round(self._settings.opacity * 100))
        form.addRow("Chip opacity", self._opacity)

        self._popup = QSpinBox()
        self._popup.setRange(4, 120)
        self._popup.setSuffix(" s")
        self._popup.setValue(self._settings.popup_seconds)
        form.addRow("Flyout popup duration", self._popup)

        self._mode = QComboBox()
        self._mode.addItem("Always-visible chip", "chip")
        self._mode.addItem("Tray only (quiet)", "quiet")
        self._mode.setCurrentIndex(0 if self._settings.ui_mode == "chip" else 1)
        form.addRow("Display mode", self._mode)

        form.addRow(QLabel("<b>Alerts</b>"))

        self._burn_mult = QDoubleSpinBox()
        self._burn_mult.setRange(1.1, 10.0)
        self._burn_mult.setSingleStep(0.1)
        self._burn_mult.setValue(self._settings.alert_burn_multiplier)
        form.addRow("Burn-rate spike multiplier", self._burn_mult)

        self._included_pct = QDoubleSpinBox()
        self._included_pct.setRange(1.0, 100.0)
        self._included_pct.setValue(self._settings.alert_included_pct)
        form.addRow("Included-quota alert threshold (%)", self._included_pct)

        self._ondemand_pct = QDoubleSpinBox()
        self._ondemand_pct.setRange(1.0, 100.0)
        self._ondemand_pct.setValue(self._settings.alert_ondemand_pct)
        form.addRow("On-demand alert threshold (%)", self._ondemand_pct)

        return w

    def _build_services_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        note = QLabel(
            "Cursor, Copilot, OpenCode Go, OpenAI and Claude are all read from local "
            "files already on this PC — nothing to enter here for them. GitHub needs "
            "a token because Actions/storage billing has no local file to read."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #6f7686; font-size: 11px;")
        outer.addWidget(note)

        self._github_token: QLineEdit | None = None
        self._github_login: QLineEdit | None = None
        self._cloud_stub: QCheckBox | None = None

        for pid, label in KNOWN_PROVIDERS:
            detected, detail = _detect_status(pid, self._auth)
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)

            head = QHBoxLayout()
            chk = QCheckBox("Enabled")
            chk.setChecked(self._prefs.is_enabled(pid))
            self._enabled_checks[pid] = chk
            head.addWidget(chk)
            status = QLabel(("✓ " if detected else "— ") + detail)
            status.setStyleSheet(f"color: {'#2f9e5c' if detected else '#8a93a6'};")
            head.addWidget(status, 1)
            box_layout.addLayout(head)

            if pid == "github":
                form = QFormLayout()
                self._github_token = QLineEdit(self._settings.github_token)
                self._github_token.setEchoMode(QLineEdit.EchoMode.Password)
                self._github_token.setPlaceholderText(
                    "ghp_… (actions/packages scope) — blank uses `gh` CLI if available"
                )
                form.addRow("Token", self._github_token)
                self._github_login = QLineEdit(self._settings.github_login)
                self._github_login.setPlaceholderText("auto-detected from the token if left blank")
                form.addRow("Login", self._github_login)
                box_layout.addLayout(form)

            if pid == "cloud":
                self._cloud_stub = QCheckBox("Enable experimental cloud stub")
                self._cloud_stub.setChecked(self._settings.enable_cloud_stub)
                box_layout.addWidget(self._cloud_stub)

            outer.addWidget(box)

        outer.addStretch(1)
        return w

    def _save(self) -> None:
        for pid, chk in self._enabled_checks.items():
            self._prefs.set_enabled(pid, chk.isChecked())

        values = {
            "refresh_seconds": self._refresh.value(),
            "opacity": self._opacity.value() / 100.0,
            "popup_seconds": self._popup.value(),
            "ui_mode": self._mode.currentData(),
            "alert_burn_multiplier": self._burn_mult.value(),
            "alert_included_pct": self._included_pct.value(),
            "alert_ondemand_pct": self._ondemand_pct.value(),
        }
        if self._github_token is not None:
            values["github_token"] = self._github_token.text().strip()
        if self._github_login is not None:
            values["github_login"] = self._github_login.text().strip()
        if self._cloud_stub is not None:
            values["enable_cloud_stub"] = self._cloud_stub.isChecked()

        save_user_settings(self._settings.state_dir, values)
        self.accept()
