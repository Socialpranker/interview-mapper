"""Загрузка скриптов скилла по пути (у scripts/ нет __init__.py) + общие константы."""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIRS = {
    "ru": ROOT / "interview-mapper" / "scripts",
    "en": ROOT / "interview-mapper-en" / "scripts",
}
LANGS = ("ru", "en")

# Локализованные поля выходов — исключать при сравнении RU vs EN
LOCALIZED_KEYS = {"note", "caveats", "pipeline"}


def load_script(lang, name):
    """Импортирует scripts/<name>.py как модуль под уникальным именем."""
    path = SCRIPT_DIRS[lang] / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_{lang}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_script(lang, name, *args, check=False):
    """Запускает скрипт сабпроцессом, возвращает CompletedProcess (text=True)."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIRS[lang] / f"{name}.py"), *map(str, args)],
        capture_output=True, text=True, check=check,
    )


def strip_localized(obj):
    """Рекурсивно удаляет локализованные ключи из JSON-структуры."""
    if isinstance(obj, dict):
        return {k: strip_localized(v) for k, v in obj.items() if k not in LOCALIZED_KEYS}
    if isinstance(obj, list):
        return [strip_localized(x) for x in obj]
    return obj
