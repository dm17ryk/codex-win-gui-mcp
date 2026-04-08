Посмотрел. Репо уже хорошее как **starter kit**: в нем есть тонкий MCP‑слой, отдельный desktop harness, локальный Computer Use loop, PowerShell‑скрипты и пример Codex‑конфига. README уже описывает базовый сценарий установки и текущий набор инструментов вроде `launch_app`, `wait_main_window`, `get_uia_tree`, `click_element`, `click_xy`, `drag_mouse`, `capture_screenshot`, `tail_log` и `collect_recent_logs`. ([GitHub][1])

Самый важный вывод: **P0 у тебя сейчас не “мало тулов”, а проблема с пространством координат в `openai_loop.py`**. В текущем коде действия модели исполняются через `pyautogui` по прямым `x/y`, при этом loop умеет работать как по всему экрану, так и по одному окну через `--window-title` и `--full-screen`. Для window-only capture это почти наверняка приведет к misclick/misdrag, потому что модель видит координаты в пространстве изображения окна, а клик уходит в desktop space. OpenAI отдельно предупреждает, что когда геометрия/область изображения отличается от целевой среды, координаты нужно переводить обратно перед исполнением. ([GitHub][2])

Еще две практические вещи, которые стоит поправить сразу: в README сейчас ставится Python 3.14, но venv создается через `py -3.11`; а `user_config.toml.example` все еще ссылается на старый путь `codex-win-gui-starter`. Плюс `run-app.ps1` уже поддерживает `APP_ARGS`, но README это не документирует. ([GitHub][1])

Что надо добавить по LLD.

1. **Session + viewport layer**
   Введи явные сущности `TargetSession` и `Viewport`. `capture_screenshot()` должен возвращать не только PNG/base64, но и `left`, `top`, `width`, `height`, `hwnd`, `pid`, `capture_mode`, `coord_space`, `scale_x`, `scale_y`. Все coordinate actions должны идти через один переводчик, например `image_to_desktop_point()`. Это ключевой слой для Computer Use, потому что OpenAI описывает custom harness именно как связку screenshots + actions, которые исполняет твой код. ([OpenAI Developers][3])

2. **Wait/assert/oracle layer**
   Сейчас репо умеет “действовать”, но еще слабо умеет “проверять”. Добавь `wait_for_element`, `wait_for_window_title`, `wait_for_process_idle`, `assert_element`, `assert_window_title`, `assert_status_text`, `assert_log_contains`, `assert_no_modal_dialog`. Это сильнее приблизит MCP к человеческому тестированию: не просто кликнуть, а понять, случилось ли ожидаемое состояние.

3. **Artifact/session trace layer**
   Нужен один tool уровня `collect_artifact_bundle`, который собирает: последний screenshot, session trace JSONL, свежие логи, optional dump/minidump, Event Viewer excerpt, UI tree snapshot, текущий viewport metadata. `collect-logs.ps1` я бы тоже усилил: не сваливать все в одну папку с риском перезаписи, а сохранять относительную структуру путей. Текущий скрипт уже собирает файлы из `APP_LOG_DIR`, так что сюда удобно нарастить bundle‑механику. ([GitHub][4])

4. **UIA/event/control-pattern layer**
   Сейчас фокус в основном на click/drag/tree. Добавь event‑driven наблюдение и более “человеческие” операции поверх UIA: `invoke`, `expand_collapse`, `select`, `set_value`, `toggle`, `get_selection`. У Microsoft control view специально ближе к UI, как его воспринимает пользователь, а control patterns и UI Automation events позволяют работать не только через координаты, но и через поведение элемента. ([Microsoft Learn][5])

5. **Qt/klogg adapter layer**
   Для `klogg` я бы не ограничивался generic Windows tools. Добавь `adapters/qt_adapter.py` и `adapters/klogg.py`, где будут objectName‑first операции: `click_qt_object`, `find_qt_object`, `dump_qt_state`, `klogg_open_log`, `klogg_search`, `klogg_get_active_tab`, `klogg_toggle_follow`, `klogg_get_visible_range`. Для Qt это очень естественно: `QObject` имеет `objectName`, `findChild()`/`findChildren()` опираются на него, а `QWidget` поддерживает `accessibleName`, `accessibleDescription`, а с Qt 6.9 — еще и `accessibleIdentifier`, который Qt прямо упоминает как полезный для automated tests. Для кастомных виджетов стоит предусмотреть `QAccessibleInterface`/`QAccessibleWidget`. ([Qt Documentation][6])

6. **Repo/layout cleanup**
   `win_gui_core.py` стоит разрезать хотя бы на `core/session.py`, `core/screenshots.py`, `core/input.py`, `core/uia.py`, `core/logs.py`, `core/artifacts.py`, `adapters/qt_adapter.py`, `loops/computer_use.py`. Иначе дальше будет больно тестировать и наращивать app‑specific behavior.

7. **Tests**
   Минимум нужны unit‑tests на coordinate translation, viewport metadata, action validation и path handling. Для smoke‑tests хватит headful integration на простом окне. Для `klogg` отдельно стоит готовить репродукцию багов так, чтобы Codex находил проблему интерактивно, а потом ты фиксировал ее уже нормальным regression test’ом в app repo.

Что добавить именно в README.

README должен не просто объяснять “как поднять сервер”, а задавать **правильную модель использования**. Я бы обязательно добавил туда:

* явное разделение режимов `full-screen` vs `single-window`, с предупреждением про coordinate spaces;
* рекомендуемый flow: `launch -> wait -> inspect UIA -> try semantic action -> fallback to screenshot/coords -> assert -> bundle artifacts`;
* требования к target app, особенно для Qt: `objectName`, `accessibleName`, optional `accessibleIdentifier`, debug/automation mode;
* guidance по Local environments и `.codex/config.toml`;
* пояснение, когда держать MCP в user config, а когда в project config;
* безопасность: isolated test session/VM, allowlist действий, human‑in‑the‑loop для destructive действий. OpenAI прямо рекомендует изолированную среду и человека в цикле для рискованных шагов. ([OpenAI Developers][7])

Еще один README‑совет: явно описать модельный выбор. `gpt-5.4` годится как default, а `computer-use-preview` OpenAI описывает как специализированную модель именно для computer use tool. Для vision‑heavy GUI сценариев это стоит упомянуть рядом с `OPENAI_COMPUTER_MODEL`. ([OpenAI Developers][8])

Я не пушил изменения прямо в GitHub из этой среды, но подготовил готовые материалы:

[Подробный review + LLD](./codex-win-gui-mcp_review.md)

[Полностью переписанный README](./codex-win-gui-mcp_README_new.md)

[Готовый diff-патч для README](./codex-win-gui-mcp_README_patch.diff)

Из всего этого я бы начал с одного шага: **починить viewport/session layer в `openai_loop.py`**, потому что без него остальная “человечность” GUI‑агента будет упираться в неверные клики и нестабильный drag.

[1]: https://github.com/dm17ryk/codex-win-gui-mcp "https://github.com/dm17ryk/codex-win-gui-mcp"
[2]: https://github.com/dm17ryk/codex-win-gui-mcp/raw/refs/heads/master/openai_loop.py "https://github.com/dm17ryk/codex-win-gui-mcp/raw/refs/heads/master/openai_loop.py"
[3]: https://developers.openai.com/api/docs/guides/tools-computer-use "https://developers.openai.com/api/docs/guides/tools-computer-use"
[4]: https://github.com/dm17ryk/codex-win-gui-mcp/blob/master/scripts/collect-logs.ps1 "https://github.com/dm17ryk/codex-win-gui-mcp/blob/master/scripts/collect-logs.ps1"
[5]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-treeoverview "https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-treeoverview"
[6]: https://doc.qt.io/qt-6/qobject.html "https://doc.qt.io/qt-6/qobject.html"
[7]: https://developers.openai.com/codex/config-reference "https://developers.openai.com/codex/config-reference"
[8]: https://developers.openai.com/api/docs/models/computer-use-preview "https://developers.openai.com/api/docs/models/computer-use-preview"
