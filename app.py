import sys
import os
import json
import subprocess
import requests
import ctypes
import re

def get_data_dir():
    """Возвращает папку, где лежит EXE файл"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

# Прячем окно консоли Windows при прямом запуске
if sys.platform == "win32":
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    # Устанавливаем AppUserModelID для корректного отображения иконки в панели задач Windows
    try:
        myappid = 'gguf2ollama.converter.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QCheckBox, QSpinBox, QDoubleSpinBox, QTextEdit, 
                               QComboBox, QTabWidget, QGroupBox, QFileDialog, QMessageBox, QScrollArea)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer
from PySide6.QtGui import QIcon

# Пытаемся импортировать движок для браузера (требует pip install PySide6[webengine])
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

SETTINGS_FILE = os.path.join(get_data_dir(), "settings.json")
LOCALES_FILE = os.path.join(get_data_dir(), "locales.json")
OLLAMA_API_URL = "http://localhost:11434/api"

class PullThread(QThread):
    """Фоновый поток для скачивания моделей, чтобы не зависал интерфейс"""
    finished = Signal(bool, str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            # Скрываем окно консоли у процесса ollama
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(["ollama", "pull", self.model_name], 
                                    capture_output=True, text=True, encoding='utf-8',
                                    startupinfo=startupinfo)
            if result.returncode == 0:
                self.finished.emit(True, "Установка завершена успешно.")
            else:
                self.finished.emit(False, result.stderr or result.stdout)
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelfileGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("icon.ico")) # Устанавливаем иконку окна
        self.resize(800, 900)
        
        # Таймер для анимации кнопки загрузки
        self.pull_timer = QTimer(self)
        self.pull_timer.timeout.connect(self.update_pull_animation)
        self.pull_animation_step = 0

        self.settings = self.load_settings()
        self.ensure_locales_file()
        
        self.init_ui()
        self.apply_theme()
        self.apply_loaded_settings()
        
        # Инициализация заголовка (выполняется после retranslate_ui)
        self.setWindowTitle(self.t("window_title"))

    def get_theme_stylesheet(self, theme):
        if theme == "light":
            return """
                QWidget { background-color: #f3f3f3; color: #333333; font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
                QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #ffffff; border: 1px solid #cccccc; padding: 5px; border-radius: 4px; }
                QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: #e0e0e0; color: #999999; border: 1px solid #cccccc; }
                QPushButton { background-color: #007acc; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #0098ff; }
                QPushButton:disabled { background-color: #cccccc; color: #888888; }
                QPushButton#primaryBtn { background-color: #238636; color: white; }
                QPushButton#primaryBtn:hover { background-color: #2ea043; }
                QPushButton#dangerBtn { background-color: #d32f2f; color: white; }
                QPushButton#dangerBtn:hover { background-color: #f44336; }
                QGroupBox { border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; padding-top: 15px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #007acc; }
                QTabWidget::pane { border: 1px solid #cccccc; }
                QTabBar::tab { background: #e0e0e0; padding: 8px 20px; border: 1px solid #cccccc; }
                QTabBar::tab:selected { background: #f3f3f3; border-bottom-color: #f3f3f3; color: #007acc; }
                QScrollArea { border: none; background-color: #f3f3f3; }
                QCheckBox { spacing: 8px; }
                QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #666666; border-radius: 3px; background: white; }
                QCheckBox::indicator:checked { background-color: #007acc; border: 2px solid #005a9e; }
            """
        elif theme == "blue":
            return """
                QWidget { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
                QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #161b22; border: 1px solid #30363d; padding: 5px; border-radius: 4px; }
                QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: #0d1117; color: #6e7681; border: 1px solid #21262d; }
                QPushButton { background-color: #1f6feb; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #388bfd; }
                QPushButton:disabled { background-color: #21262d; color: #6e7681; }
                QPushButton#primaryBtn { background-color: #238636; color: white; }
                QPushButton#primaryBtn:hover { background-color: #2ea043; }
                QPushButton#dangerBtn { background-color: #da3633; color: white; }
                QPushButton#dangerBtn:hover { background-color: #f85149; }
                QGroupBox { border: 1px solid #30363d; border-radius: 6px; margin-top: 10px; padding-top: 15px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #58a6ff; }
                QTabWidget::pane { border: 1px solid #30363d; }
                QTabBar::tab { background: #161b22; padding: 8px 20px; border: 1px solid #30363d; }
                QTabBar::tab:selected { background: #0d1117; border-bottom-color: #0d1117; color: #58a6ff; }
                QScrollArea { border: none; background-color: #0d1117; }
            """
        elif theme == "hacker":
            return """
                QWidget { background-color: #0a0a0c; color: #00ff00; font-family: 'Courier New', monospace; font-size: 10pt; }
                QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #111116; border: 1px solid #005500; color: #00ff00; padding: 5px; border-radius: 0px; }
                QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: #0a0a0c; color: #005500; border: 1px solid #002200; }
                QPushButton { background-color: #004400; color: #00ff00; border: 1px solid #00ff00; padding: 8px 15px; border-radius: 0px; font-weight: bold; }
                QPushButton:hover { background-color: #007700; color: #ffffff; }
                QPushButton:disabled { background-color: #111116; color: #005500; border: 1px solid #002200; }
                QPushButton#primaryBtn { background-color: #007700; color: #00ff00; border: 1px solid #00ff00; }
                QPushButton#primaryBtn:hover { background-color: #00aa00; color: #ffffff; }
                QPushButton#dangerBtn { background-color: #770000; color: #ff0000; border: 1px solid #ff0000; }
                QPushButton#dangerBtn:hover { background-color: #aa0000; color: #ffffff; }
                QGroupBox { border: 1px solid #005500; border-radius: 0px; margin-top: 10px; padding-top: 15px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #00ff00; }
                QTabWidget::pane { border: 1px solid #005500; }
                QTabBar::tab { background: #111116; padding: 8px 20px; border: 1px solid #005500; color: #00aa00; }
                QTabBar::tab:selected { background: #0a0a0c; border-bottom-color: #0a0a0c; color: #00ff00; }
                QScrollArea { border: none; background-color: #0a0a0c; }
            """
        else: # dark
            return """
                QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
                QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #2d2d2d; border: 1px solid #3c3c3c; padding: 5px; border-radius: 4px; }
                QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: #1e1e1e; color: #666666; border: 1px solid #2a2a2a; }
                QPushButton { background-color: #0e639c; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #1177bb; }
                QPushButton:disabled { background-color: #4d4d4d; color: #888888; }
                QPushButton#primaryBtn { background-color: #238636; color: white; }
                QPushButton#primaryBtn:hover { background-color: #2ea043; }
                QPushButton#dangerBtn { background-color: #da3633; color: white; }
                QPushButton#dangerBtn:hover { background-color: #f85149; }
                QGroupBox { border: 1px solid #3c3c3c; border-radius: 6px; margin-top: 10px; padding-top: 15px; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #569cd6; }
                QTabWidget::pane { border: 1px solid #3c3c3c; }
                QTabBar::tab { background: #2d2d2d; padding: 8px 20px; border: 1px solid #3c3c3c; }
                QTabBar::tab:selected { background: #1e1e1e; border-bottom-color: #1e1e1e; color: #569cd6; }
                QScrollArea { border: none; background-color: #1e1e1e; }
            """

    def apply_theme(self):
        theme = self.settings.get("theme", "dark")
        self.setStyleSheet(self.get_theme_stylesheet(theme))

    def ensure_locales_file(self):
        """Гарантирует, что файл переводов существует, обновляя его новыми ключами (сохраняя пользовательские)"""
        default_locales = {
            "en": {
                "window_title": "Ollama Manager by OreX",
                "tab_gguf": "Convert GGUF",
                "tab_manage": "Manage Ollama",
                "tab_store": "Ollama Store",
                "gguf_path_placeholder": "Drag and drop GGUF file here or browse...",
                "btn_browse": "Browse",
                "gguf_name_placeholder": "New model name in Ollama (e.g. my-model:q4)",
                "btn_create": "Create model in Ollama",
                "btn_refresh": "Find models",
                "meta_placeholder": "Model metadata...",
                "btn_update": "Update model parameters",
                "btn_delete": "Delete model",
                "btn_back": "⬅ Back",
                "btn_home": "🏠 Home",
                "store_search_placeholder": "Search model (e.g. qwen)...",
                "btn_search": "🔍 Search",
                "lbl_model": "Model:",
                "store_pull_placeholder": "Command (e.g. qwen:0.5b)",
                "btn_pull": "⬇ Install",
                "params_group": "Inference Parameters (Modelfile)",
                "cb_ctx": "Context Size",
                "vram_lbl": "VRAM (KV Cache): ~{0} MB",
                "cb_stop": "Stop Tokens (comma-separated)",
                "cb_sys": "System Prompt",
                "cb_tpl": "Chat Template",
                "jinja_placeholder": "Paste Jinja from LM Studio here for auto-conversion...",
                "tpl_placeholder": "Ollama (Go) template will appear here...",
                "tab_jinja": "Template Jinja",
                "tab_go": "Ollama (Go)",
                "msg_success": "Success",
                "msg_warning": "Warning",
                "msg_error": "Error",
                "msg_no_file": "Specify file path and model name.",
                "msg_created": "Model {0} successfully created!",
                "msg_pull_empty": "Enter model name to install.",
                "msg_pull_success": "Successfully!\n{0}",
                "msg_pull_error": "Failed to download model:\n{0}",
                "msg_del_confirm_title": "Confirm deletion",
                "msg_del_confirm_text": "Are you sure you want to delete model '{0}'?\nThis action cannot be undone.",
                "msg_del_success": "Model '{0}' successfully deleted.",
                "msg_del_error": "Failed to delete model.\nAPI responded: {0}",
                "browser_unavailable": "Browser unavailable.\n\nTo use this tab, install the WebEngine library:\n\nRun in console: pip install PySide6[webengine]",
                "loading": "⏳ Loading",
                "msg_process_error": "Process exited with error.\n{0}",
                "msg_ollama_not_found": "Ollama executable not found. Make sure Ollama is installed and added to PATH.",
                "msg_unknown_error": "Unknown error: {0}",
                "msg_api_error": "Failed to contact Ollama: {0}",
                "msg_meta_error": "Error loading metadata: {0}",
                "theme_dark": "Dark Theme",
                "theme_light": "Light Theme",
                "theme_blue": "Dark Blue Theme",
                "theme_hacker": "Hacker Theme"
            },
            "ru": {
                "window_title": "Ollama Manager by OreX",
                "tab_gguf": "Конвертация GGUF",
                "tab_manage": "Управление Ollama",
                "tab_store": "Магазин Ollama",
                "gguf_path_placeholder": "Перетащи GGUF файл сюда или выбери через проводник...",
                "btn_browse": "Обзор",
                "gguf_name_placeholder": "Имя новой модели в Ollama (например: my-model:q4)",
                "btn_create": "Создать модель в Ollama",
                "btn_refresh": "Найти модели",
                "meta_placeholder": "Метаданные модели...",
                "btn_update": "Обновить параметры модели",
                "btn_delete": "Удалить модель",
                "btn_back": "⬅ Назад",
                "btn_home": "🏠 Главная",
                "store_search_placeholder": "Поиск модели (например: qwen)...",
                "btn_search": "🔍 Искать",
                "lbl_model": "Модель:",
                "store_pull_placeholder": "Команда (например: qwen:0.5b)",
                "btn_pull": "⬇ Установить",
                "params_group": "Параметры инференса (Modelfile)",
                "cb_ctx": "Context Size",
                "vram_lbl": "VRAM (KV Cache): ~{0} MB",
                "cb_stop": "Stop Tokens (разделитель - запятая)",
                "cb_sys": "System Prompt",
                "cb_tpl": "Chat Template",
                "jinja_placeholder": "Вставьте Jinja из LM Studio сюда для авто-конвертации...",
                "tpl_placeholder": "Здесь появится Ollama (Go) шаблон...",
                "tab_jinja": "Template Jinja",
                "tab_go": "Ollama (Go)",
                "msg_success": "Успех",
                "msg_warning": "Внимание",
                "msg_error": "Ошибка",
                "msg_no_file": "Укажите путь к файлу и имя модели.",
                "msg_created": "Модель {0} успешно создана!",
                "msg_pull_empty": "Введите имя модели для установки.",
                "msg_pull_success": "Успешно!\n{0}",
                "msg_pull_error": "Не удалось скачать модель:\n{0}",
                "msg_del_confirm_title": "Подтверждение удаления",
                "msg_del_confirm_text": "Вы уверены, что хотите удалить модель '{0}'?\nЭто действие нельзя отменить.",
                "msg_del_success": "Модель '{0}' успешно удалена.",
                "msg_del_error": "Не удалось удалить модель.\nAPI ответил: {0}",
                "browser_unavailable": "Браузер недоступен.\n\nДля работы этой вкладки установите библиотеку WebEngine:\n\nВыполните в консоли: pip install PySide6[webengine]",
                "loading": "⏳ Загрузка",
                "msg_process_error": "Процесс завершился с ошибкой.\n{0}",
                "msg_ollama_not_found": "Не найден исполняемый файл ollama. Убедитесь, что Ollama установлена и добавлена в PATH.",
                "msg_unknown_error": "Неизвестная ошибка: {0}",
                "msg_api_error": "Не удалось связаться с Ollama: {0}",
                "msg_meta_error": "Ошибка загрузки метаданных: {0}",
                "theme_dark": "Темная тема",
                "theme_light": "Светлая тема",
                "theme_blue": "Темно-синяя тема",
                "theme_hacker": "Хакерская тема"
            }
        }
        
        user_locales = {}
        if os.path.exists(LOCALES_FILE):
            try:
                with open(LOCALES_FILE, "r", encoding="utf-8") as f:
                    user_locales = json.load(f)
            except Exception:
                pass

        # Умное слияние - обновляем ключи, которых не было
        changed = False
        for lang, strings in default_locales.items():
            if lang not in user_locales:
                user_locales[lang] = strings
                changed = True
            else:
                for k, v in strings.items():
                    if k not in user_locales[lang]:
                        user_locales[lang][k] = v
                        changed = True

        if changed or not os.path.exists(LOCALES_FILE):
            with open(LOCALES_FILE, "w", encoding="utf-8") as f:
                json.dump(user_locales, f, indent=4, ensure_ascii=False)
                
        self.locales = user_locales

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "theme": "dark",
            "language": "en",
            "last_path": "", 
            "system_prompt": "You are a professional and accurate translator...",
            "jinja_template": "",
            "template": "{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n{{ end }}{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n{{ end }}<|im_start|>assistant\n",
            "stop_tokens": "<|im_end|>,<|im_start|>"
        }

    def save_settings(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4)

    def t(self, key):
        """Метод для получения переведенной строки по ключу"""
        lang = self.settings.get("language", "en")
        # Пытаемся получить ключ из выбранного языка, иначе фоллбэк на 'en', иначе сам ключ
        return self.locales.get(lang, {}).get(key, self.locales.get("en", {}).get(key, key))

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Выбор темы и языка (в правом верхнем углу)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch()

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.t("theme_dark"), "dark")
        self.theme_combo.addItem(self.t("theme_light"), "light")
        self.theme_combo.addItem(self.t("theme_blue"), "blue")
        self.theme_combo.addItem(self.t("theme_hacker"), "hacker")
        
        current_theme = self.settings.get("theme", "dark")
        theme_index = self.theme_combo.findData(current_theme)
        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)
            
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        top_bar_layout.addWidget(self.theme_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Русский", "ru")
        self.lang_combo.addItem("Français", "fr")
        self.lang_combo.addItem("Español", "es")
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("Deutsch", "de")
        self.lang_combo.addItem("हिन्दी", "hi")
        
        current_lang = self.settings.get("language", "en")
        index = self.lang_combo.findData(current_lang)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)
            
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        top_bar_layout.addWidget(self.lang_combo)
        
        main_layout.addLayout(top_bar_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1
        self.tab_gguf = QWidget()
        self.tabs.addTab(self.tab_gguf, "")
        self.setup_gguf_tab()

        # Tab 2
        self.tab_ollama = QWidget()
        self.tabs.addTab(self.tab_ollama, "")
        self.setup_ollama_tab()

        # Tab 3 (Магазин)
        self.tab_store = QWidget()
        self.tabs.addTab(self.tab_store, "")
        self.setup_store_tab()

        # Параметры (общие)
        self.setup_parameters_group(main_layout)

        # Устанавливаем высоту для первой вкладки по умолчанию, чтобы убить пустое место
        self.tabs.setMaximumHeight(180)

        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Применяем переводы ко всем созданным элементам
        self.retranslate_ui()

    def change_theme(self):
        self.settings["theme"] = self.theme_combo.currentData()
        self.apply_theme()

    def change_language(self):
        self.settings["language"] = self.lang_combo.currentData()
        self.retranslate_ui()

    def retranslate_ui(self):
        """Обновляет все текстовые поля в интерфейсе при смене языка"""
        self.setWindowTitle(self.t("window_title"))
        self.tabs.setTabText(0, self.t("tab_gguf"))
        self.tabs.setTabText(1, self.t("tab_manage"))
        self.tabs.setTabText(2, self.t("tab_store"))
        
        # Обновляем названия тем без вызова события смены
        self.theme_combo.blockSignals(True)
        self.theme_combo.setItemText(0, self.t("theme_dark"))
        self.theme_combo.setItemText(1, self.t("theme_light"))
        self.theme_combo.setItemText(2, self.t("theme_blue"))
        self.theme_combo.setItemText(3, self.t("theme_hacker"))
        self.theme_combo.blockSignals(False)

        # Вкладка GGUF
        self.path_input.setPlaceholderText(self.t("gguf_path_placeholder"))
        self.btn_browse.setText(self.t("btn_browse"))
        self.model_name_input.setPlaceholderText(self.t("gguf_name_placeholder"))
        self.btn_create.setText(self.t("btn_create"))
        
        # Вкладка Управления
        self.btn_refresh.setText(self.t("btn_refresh"))
        self.meta_display.setPlaceholderText(self.t("meta_placeholder"))
        self.btn_update.setText(self.t("btn_update"))
        self.btn_delete.setText(self.t("btn_delete"))
        
        # Вкладка Магазина
        if hasattr(self, 'btn_back'):
            self.btn_back.setText(self.t("btn_back"))
            self.btn_home.setText(self.t("btn_home"))
            self.store_search_input.setPlaceholderText(self.t("store_search_placeholder"))
            self.btn_search.setText(self.t("btn_search"))
            self.lbl_model.setText(self.t("lbl_model"))
            self.store_pull_input.setPlaceholderText(self.t("store_pull_placeholder"))
            if not self.btn_pull.text().startswith("⏳"):
                self.btn_pull.setText(self.t("btn_pull"))
            if hasattr(self, 'fallback_label'):
                self.fallback_label.setText(self.t("browser_unavailable"))

        # Группа параметров
        if hasattr(self, 'params_group'):
            self.params_group.setTitle(self.t("params_group"))
            self.cb_ctx.setText(self.t("cb_ctx"))
            self.update_vram_estimation() # Обновит VRAM label с переводом
            self.cb_stop.setText(self.t("cb_stop"))
            self.cb_sys.setText(self.t("cb_sys"))
            self.cb_tpl.setText(self.t("cb_tpl"))
            
            self.jinja_edit.setPlaceholderText(self.t("jinja_placeholder"))
            self.tpl_edit.setPlaceholderText(self.t("tpl_placeholder"))
            self.tpl_tabs.setTabText(0, self.t("tab_jinja"))
            self.tpl_tabs.setTabText(1, self.t("tab_go"))

    def setup_gguf_tab(self):
        layout = QVBoxLayout(self.tab_gguf)
        
        self.tab_gguf.setAcceptDrops(True)
        self.tab_gguf.dragEnterEvent = self.dragEnterEvent
        self.tab_gguf.dropEvent = self.dropEvent

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.btn_browse = QPushButton()
        self.btn_browse.clicked.connect(self.browse_file)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.btn_browse)
        layout.addLayout(path_layout)

        self.model_name_input = QLineEdit()
        layout.addWidget(self.model_name_input)

        self.btn_create = QPushButton()
        self.btn_create.setObjectName("primaryBtn") # Используем класс для стилизации цвета
        self.btn_create.clicked.connect(self.create_gguf_model)
        layout.addWidget(self.btn_create)
        
        layout.addStretch()

    def setup_ollama_tab(self):
        layout = QVBoxLayout(self.tab_ollama)
        
        top_layout = QHBoxLayout()
        self.combo_models = QComboBox()
        self.combo_models.currentIndexChanged.connect(self.load_model_metadata)
        self.btn_refresh = QPushButton()
        self.btn_refresh.clicked.connect(self.refresh_ollama_models)
        
        top_layout.addWidget(self.combo_models, stretch=1)
        top_layout.addWidget(self.btn_refresh)
        layout.addLayout(top_layout)

        self.meta_display = QTextEdit()
        self.meta_display.setReadOnly(True)
        layout.addWidget(self.meta_display)

        actions_layout = QHBoxLayout()
        self.btn_update = QPushButton()
        self.btn_update.clicked.connect(self.update_ollama_model)
        
        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("dangerBtn") # Используем класс для стилизации
        self.btn_delete.clicked.connect(self.delete_ollama_model)
        
        actions_layout.addWidget(self.btn_update)
        actions_layout.addWidget(self.btn_delete)
        
        layout.addLayout(actions_layout)

    def setup_store_tab(self):
        layout = QVBoxLayout(self.tab_store)
        
        # Навигационная панель
        nav_layout = QHBoxLayout()
        
        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(self.store_go_back)
        nav_layout.addWidget(self.btn_back)

        self.btn_home = QPushButton()
        self.btn_home.clicked.connect(self.store_go_home)
        nav_layout.addWidget(self.btn_home)
        
        self.store_search_input = QLineEdit()
        self.store_search_input.returnPressed.connect(self.store_search)
        nav_layout.addWidget(self.store_search_input)
        
        self.btn_search = QPushButton()
        self.btn_search.clicked.connect(self.store_search)
        nav_layout.addWidget(self.btn_search)
        
        nav_layout.addSpacing(20)
        
        self.lbl_model = QLabel()
        nav_layout.addWidget(self.lbl_model)
        
        self.store_pull_input = QLineEdit()
        nav_layout.addWidget(self.store_pull_input)
        
        self.btn_pull = QPushButton()
        self.btn_pull.setObjectName("primaryBtn") # Используем класс
        self.btn_pull.clicked.connect(self.store_pull_model)
        nav_layout.addWidget(self.btn_pull)
        
        layout.addLayout(nav_layout)
        
        # Встроенный браузер
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            
            # Разрешаем JS доступ к буферу обмена
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
            
            # Авто-одобрение запросов прав (например, на копирование в буфер)
            self.web_view.page().featurePermissionRequested.connect(self.on_feature_permission_requested)
            
            self.store_go_home()
            layout.addWidget(self.web_view)
        else:
            self.fallback_label = QLabel()
            self.fallback_label.setAlignment(Qt.AlignCenter)
            self.fallback_label.setStyleSheet("font-size: 14pt; color: #888888;")
            layout.addWidget(self.fallback_label)

    def store_go_back(self):
        if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
            self.web_view.back()

    def store_go_home(self):
        if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
            self.web_view.setUrl(QUrl("https://ollama.com/search"))
            self.store_search_input.clear()

    def store_search(self):
        if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
            query = self.store_search_input.text().strip()
            if query:
                self.web_view.setUrl(QUrl(f"https://ollama.com/search?q={query}"))
            else:
                self.store_go_home()

    def on_feature_permission_requested(self, url, feature):
        # Одобряем права (нужно для работы кнопок 'Копировать' на сайте)
        if WEBENGINE_AVAILABLE and hasattr(self, 'web_view'):
            self.web_view.page().setFeaturePermission(url, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)

    def update_pull_animation(self):
        """Анимирует текст на кнопке во время загрузки"""
        dots = "." * (self.pull_animation_step % 4)
        loading_text = self.t("loading")
        self.btn_pull.setText(f"{loading_text}{dots}")
        self.pull_animation_step += 1

    def store_pull_model(self):
        model_cmd = self.store_pull_input.text().strip()
        
        # Очистка если пользователь скопировал вместе с "ollama pull/run"
        if model_cmd.startswith("ollama pull "):
            model_cmd = model_cmd.replace("ollama pull ", "")
        elif model_cmd.startswith("ollama run "):
            model_cmd = model_cmd.replace("ollama run ", "")
            
        if not model_cmd:
            QMessageBox.warning(self, self.t("msg_warning"), self.t("msg_pull_empty"))
            return

        # Настраиваем UI под состояние загрузки (применяем цвет на месте)
        self.btn_pull.setEnabled(False)
        self.btn_pull.setStyleSheet("background-color: #d97706; color: white;") # Оранжевый цвет во время загрузки
        self.pull_animation_step = 0
        self.update_pull_animation()
        self.pull_timer.start(500)
        
        self.pull_thread = PullThread(model_cmd)
        self.pull_thread.finished.connect(self.on_pull_finished)
        self.pull_thread.start()

    def on_pull_finished(self, success, msg):
        # Возвращаем UI в нормальное состояние (восстанавливаем CSS класс)
        self.pull_timer.stop()
        self.btn_pull.setEnabled(True)
        self.btn_pull.setText(self.t("btn_pull"))
        self.btn_pull.setStyleSheet("") # Сбрасываем инлайн стиль, чтобы работал primaryBtn

        if success:
            QMessageBox.information(self, self.t("msg_success"), self.t("msg_pull_success").format(msg))
            self.refresh_ollama_models()  # Обновляем список моделей
        else:
            QMessageBox.critical(self, self.t("msg_error"), self.t("msg_pull_error").format(msg))

    def setup_parameters_group(self, parent_layout):
        self.params_group = QGroupBox()
        layout = QVBoxLayout(self.params_group)

        # Делаем группу скроллируемой на случай маленьких экранов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.params = {}
        def add_param(name, label_text, widget, default_val):
            row = QHBoxLayout()
            cb = QCheckBox(label_text) # Оставляем стандартные названия LLM без перевода
            cb.toggled.connect(widget.setEnabled)
            
            widget.setValue(default_val)
            widget.setEnabled(False)
            
            row.addWidget(cb)
            row.addWidget(widget)
            scroll_layout.addLayout(row)
            self.params[name] = {'cb': cb, 'widget': widget}

        temp_spin = QDoubleSpinBox(); temp_spin.setRange(0.0, 2.0); temp_spin.setSingleStep(0.1)
        add_param("temperature", "Temperature", temp_spin, 0.8)

        top_k_spin = QSpinBox(); top_k_spin.setRange(1, 100)
        add_param("top_k", "Top-K", top_k_spin, 40)

        top_p_spin = QDoubleSpinBox(); top_p_spin.setRange(0.0, 1.0); top_p_spin.setSingleStep(0.05)
        add_param("top_p", "Top-P", top_p_spin, 0.9)

        rep_pen_spin = QDoubleSpinBox(); rep_pen_spin.setRange(1.0, 2.0); rep_pen_spin.setSingleStep(0.05)
        add_param("repeat_penalty", "Repeat Penalty", rep_pen_spin, 1.1)

        # --- Context Size ---
        ctx_row = QHBoxLayout()
        self.cb_ctx = QCheckBox()
        self.spin_ctx = QSpinBox()
        self.spin_ctx.setRange(512, 128000)
        self.spin_ctx.setValue(4096)
        self.spin_ctx.setSingleStep(1024)
        self.spin_ctx.setEnabled(False)
        self.cb_ctx.toggled.connect(self.spin_ctx.setEnabled)
        self.spin_ctx.valueChanged.connect(self.update_vram_estimation)
        
        self.lbl_vram = QLabel()
        self.lbl_vram.setStyleSheet("color: #888888;")
        
        ctx_row.addWidget(self.cb_ctx)
        ctx_row.addWidget(self.spin_ctx)
        ctx_row.addWidget(self.lbl_vram)
        scroll_layout.addLayout(ctx_row)

        # --- Stop Tokens ---
        stop_row = QHBoxLayout()
        self.cb_stop = QCheckBox()
        self.stop_edit = QLineEdit()
        self.stop_edit.setEnabled(False)
        self.cb_stop.toggled.connect(self.stop_edit.setEnabled)
        stop_row.addWidget(self.cb_stop)
        stop_row.addWidget(self.stop_edit)
        scroll_layout.addLayout(stop_row)

        # --- System Prompt ---
        sys_row = QVBoxLayout()
        sys_header = QHBoxLayout()
        self.cb_sys = QCheckBox()
        sys_header.addWidget(self.cb_sys)
        sys_header.addStretch()
        
        self.sys_prompt_edit = QTextEdit()
        self.sys_prompt_edit.setMaximumHeight(80)
        self.sys_prompt_edit.setEnabled(False)
        self.cb_sys.toggled.connect(self.sys_prompt_edit.setEnabled)
        
        # Кнопки сохранения и очистки промпта УДАЛЕНЫ согласно запросу
        
        sys_row.addLayout(sys_header)
        sys_row.addWidget(self.sys_prompt_edit)
        scroll_layout.addLayout(sys_row)

        # --- Chat Template ---
        tpl_row = QVBoxLayout()
        tpl_header = QHBoxLayout()
        self.cb_tpl = QCheckBox()
        tpl_header.addWidget(self.cb_tpl)
        tpl_header.addStretch()
        
        self.tpl_tabs = QTabWidget()
        self.tpl_tabs.setMaximumHeight(120)
        self.tpl_tabs.setEnabled(False)
        self.cb_tpl.toggled.connect(self.tpl_tabs.setEnabled)
        
        self.jinja_edit = QTextEdit()
        self.jinja_edit.textChanged.connect(self.auto_convert_jinja)
        
        self.tpl_edit = QTextEdit()
        
        self.tpl_tabs.addTab(self.jinja_edit, "")
        self.tpl_tabs.addTab(self.tpl_edit, "")
        
        tpl_row.addLayout(tpl_header)
        tpl_row.addWidget(self.tpl_tabs)
        scroll_layout.addLayout(tpl_row)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        parent_layout.addWidget(self.params_group)

    def apply_loaded_settings(self):
        last_path = self.settings.get("last_path", "")
        self.path_input.setText(last_path)
        self.sys_prompt_edit.setText(self.settings.get("system_prompt", ""))
        self.jinja_edit.setText(self.settings.get("jinja_template", ""))
        self.tpl_edit.setText(self.settings.get("template", ""))
        self.stop_edit.setText(self.settings.get("stop_tokens", ""))
        self.update_vram_estimation()

    def on_tab_changed(self, index):
        # Жестко ограничиваем высоту верхнего блока вкладок, чтобы убить пустое место
        if index == 0:
            self.tabs.setMaximumHeight(180) # Компактная высота для GGUF
            if hasattr(self, 'params_group'):
                self.params_group.setVisible(True)
        elif index == 1:
            self.refresh_ollama_models()
            self.tabs.setMaximumHeight(300) # Чуть больше для логов метаданных
            if hasattr(self, 'params_group'):
                self.params_group.setVisible(True)
        elif index == 2:
            self.tabs.setMaximumHeight(16777215) # Убираем лимит для браузера (Магазин)
            if hasattr(self, 'params_group'):
                self.params_group.setVisible(False)

    def auto_convert_jinja(self):
        jinja_text = self.jinja_edit.toPlainText()
        if not jinja_text.strip():
            return

        sys_pre, sys_post = "", ""
        user_pre, user_post = "", ""
        asst_pre, asst_post = "", ""

        def extract(role):
            pattern = r"['\"]" + role + r"['\"].*?%}(.*?)\{\{\s*(?:message\['content'\]|system_message)\s*\}\}(.*?)(?:\{%|$)"
            match = re.search(pattern, jinja_text, re.DOTALL)
            if match:
                return match.group(1).strip(), match.group(2).strip()
            return None, None

        s_pre, s_post = extract("system")
        if s_pre is not None: sys_pre, sys_post = s_pre, s_post
        
        u_pre, u_post = extract("user")
        if u_pre is not None: user_pre, user_post = u_pre, u_post
        
        a_pre, a_post = extract("assistant")
        if a_pre is not None: asst_pre, asst_post = a_pre, a_post

        if not user_pre:
            if "im_start" in jinja_text:
                sys_pre, sys_post = "<|im_start|>system\\n", "<|im_end|>\\n"
                user_pre, user_post = "<|im_start|>user\\n", "<|im_end|>\\n"
                asst_pre = "<|im_start|>assistant\\n"
            elif "start_header_id" in jinja_text:
                sys_pre, sys_post = "<|start_header_id|>system<|end_header_id|>\\n\\n", "<|eot_id|>"
                user_pre, user_post = "<|start_header_id|>user<|end_header_id|>\\n\\n", "<|eot_id|>"
                asst_pre = "<|start_header_id|>assistant<|end_header_id|>\\n\\n"
            elif "[INST]" in jinja_text:
                sys_pre, sys_post = "<<SYS>>\\n", "\\n<</SYS>>\\n\\n"
                user_pre, user_post = "[INST] ", " [/INST]"
                asst_pre = ""

        gen_match = re.search(r"add_generation_prompt.*?%}(.*?)(?:\{%|$)", jinja_text, re.DOTALL)
        if gen_match and gen_match.group(1).strip():
            asst_pre = gen_match.group(1).strip()

        out = ""
        if sys_pre or sys_post:
            out += f"{{{{ if .System }}}}{sys_pre}{{{{ .System }}}}{sys_post}{{{{ end }}}}"
        if user_pre or user_post:
            out += f"{{{{ if .Prompt }}}}{user_pre}{{{{ .Prompt }}}}{user_post}{{{{ end }}}}"
        if asst_pre:
            out += f"{asst_pre}"

        out = out.replace("\\n", "\n")
        
        if out.strip():
            self.tpl_edit.setPlainText(out)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith(".gguf"):
                self.path_input.setText(file_path)
                self.settings["last_path"] = file_path
                self.save_settings()
                
                name = os.path.basename(file_path).replace(".gguf", "")
                self.model_name_input.setText(name)
                break

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, self.t("btn_browse"), "", "GGUF Models (*.gguf);;All Files (*)")
        if file_path:
            self.path_input.setText(file_path)
            self.settings["last_path"] = file_path
            self.save_settings()

    def update_vram_estimation(self):
        ctx_size = self.spin_ctx.value()
        vram_mb = (ctx_size / 1024) * 100 
        self.lbl_vram.setText(self.t("vram_lbl").format(int(vram_mb)))

    def generate_modelfile(self, base_model_path_or_name, is_file=True):
        lines = []
        if is_file:
            path = base_model_path_or_name.replace('\\', '/')
            lines.append(f'FROM "{path}"')
        else:
            lines.append(f'FROM {base_model_path_or_name}')

        if self.params["temperature"]['cb'].isChecked():
            lines.append(f'PARAMETER temperature {self.params["temperature"]["widget"].value()}')
        if self.params["top_k"]['cb'].isChecked():
            lines.append(f'PARAMETER top_k {self.params["top_k"]["widget"].value()}')
        if self.params["top_p"]['cb'].isChecked():
            lines.append(f'PARAMETER top_p {self.params["top_p"]["widget"].value()}')
        if self.params["repeat_penalty"]['cb'].isChecked():
            lines.append(f'PARAMETER repeat_penalty {self.params["repeat_penalty"]["widget"].value()}')
        
        if self.cb_ctx.isChecked():
            lines.append(f'PARAMETER num_ctx {self.spin_ctx.value()}')
            
        if self.cb_stop.isChecked():
            stops = self.stop_edit.text().split(",")
            for s in stops:
                s = s.strip()
                if s:
                    lines.append(f'PARAMETER stop "{s}"')

        if self.cb_tpl.isChecked():
            tpl = self.tpl_edit.toPlainText().strip()
            if tpl:
                lines.append(f'TEMPLATE """{tpl}"""')

        if self.cb_sys.isChecked():
            sys_prompt = self.sys_prompt_edit.toPlainText().strip()
            if sys_prompt:
                lines.append(f'SYSTEM """{sys_prompt}"""')

        return "\n".join(lines)

    def execute_ollama_create(self, model_name, modelfile_content):
        modelfile_path = "temp_Modelfile"
        with open(modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)

        try:
            subprocess.run(["ollama", "create", model_name, "-f", modelfile_path], check=True)
            QMessageBox.information(self, self.t("msg_success"), self.t("msg_created").format(model_name))
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, self.t("msg_error"), self.t("msg_process_error").format(e))
        except FileNotFoundError:
            QMessageBox.critical(self, self.t("msg_error"), self.t("msg_ollama_not_found"))
        except Exception as e:
            QMessageBox.critical(self, self.t("msg_error"), self.t("msg_unknown_error").format(e))
        finally:
            if os.path.exists(modelfile_path):
                os.remove(modelfile_path)

    def create_gguf_model(self):
        file_path = self.path_input.text().strip()
        model_name = self.model_name_input.text().strip()
        if not file_path or not model_name:
            QMessageBox.warning(self, self.t("msg_warning"), self.t("msg_no_file"))
            return

        modelfile = self.generate_modelfile(file_path, is_file=True)
        self.execute_ollama_create(model_name, modelfile)

    def refresh_ollama_models(self):
        self.combo_models.clear()
        try:
            response = requests.get(f"{OLLAMA_API_URL}/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                for m in models:
                    self.combo_models.addItem(m["name"])
        except Exception as e:
            pass # Игнорируем ошибку при авто-обновлении, чтобы не спамить окна

    def load_model_metadata(self):
        model_name = self.combo_models.currentText()
        if not model_name:
            return
        try:
            response = requests.post(f"{OLLAMA_API_URL}/show", json={"name": model_name})
            if response.status_code == 200:
                data = response.json()
                details = data.get("details", {})
                info = (f"Family: {details.get('family')}\n"
                        f"Parameter Size: {details.get('parameter_size')}\n"
                        f"Quantization: {details.get('quantization_level')}\n"
                        f"\n--- Modelfile ---\n{data.get('modelfile', '')}")
                self.meta_display.setText(info)
        except Exception as e:
            self.meta_display.setText(self.t("msg_meta_error").format(e))

    def update_ollama_model(self):
        model_name = self.combo_models.currentText()
        if not model_name:
            return
        modelfile = self.generate_modelfile(model_name, is_file=False)
        self.execute_ollama_create(model_name, modelfile)

    def delete_ollama_model(self):
        model_name = self.combo_models.currentText()
        if not model_name:
            return
            
        reply = QMessageBox.question(self, self.t("msg_del_confirm_title"), 
                                     self.t("msg_del_confirm_text").format(model_name),
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                response = requests.delete(f"{OLLAMA_API_URL}/delete", json={"name": model_name})
                if response.status_code == 200:
                    QMessageBox.information(self, self.t("msg_success"), self.t("msg_del_success").format(model_name))
                    self.meta_display.clear()
                    self.refresh_ollama_models()
                else:
                    QMessageBox.warning(self, self.t("msg_error"), self.t("msg_del_error").format(response.text))
            except Exception as e:
                QMessageBox.critical(self, self.t("msg_error"), f"{e}")

    def closeEvent(self, event):
        # Сохраняем язык, тему и все текстовые поля при закрытии программы!
        self.settings["theme"] = self.theme_combo.currentData()
        self.settings["language"] = self.lang_combo.currentData()
        self.settings["system_prompt"] = self.sys_prompt_edit.toPlainText()
        self.settings["jinja_template"] = self.jinja_edit.toPlainText()
        self.settings["template"] = self.tpl_edit.toPlainText()
        self.settings["stop_tokens"] = self.stop_edit.text()
        self.save_settings()
        sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico")) # Устанавливаем иконку для всего приложения и панели задач
    window = ModelfileGenerator()
    window.show()
    sys.exit(app.exec())