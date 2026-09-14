"""Простий REST API для управління задачами (tasks/todos).

Навчальний проєкт: Flask + зберігання даних у пам'яті (без бази даних).

Модель задачі:
    id         - integer, автоінкремент (генерується сервером)
    title      - string, обов'язкове поле
    done       - boolean, за замовчуванням False
    created_at - timestamp у форматі ISO 8601 (проставляється при створенні)

Запуск:
    python app.py
Сервер слухає на 0.0.0.0:8080 (щоб застосунок був доступний ззовні контейнера
у Docker / k3s).
"""

from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# За замовчуванням Flask екранує не-ASCII символи в JSON (кирилиця стає
# послідовностями виду Ку...). Це валідний JSON, але нечитабельний
# оком. Вимикаємо екранування, щоб відповіді API показували кирилицю "як є".
app.json.ensure_ascii = False

# ---------------------------------------------------------------------------
# "Сховище" даних
# ---------------------------------------------------------------------------
# Замість бази даних тримаємо задачі у звичайному списку Python у пам'яті.
# Це означає, що після перезапуску процесу всі дані зникають — для навчального
# проєкту цього достатньо.
tasks: list[dict] = []

# Лічильник для автоінкремента id. Кожна нова задача отримує _next_id,
# після чого лічильник збільшується на 1.
_next_id: int = 1


def _make_task(title: str, done: bool) -> dict:
    """Створити словник-задачу з усіма полями моделі та новим id.

    Використовує глобальний лічильник _next_id і після використання
    інкрементує його, щоб id ніколи не повторювались.
    """
    global _next_id
    task = {
        "id": _next_id,
        "title": title,
        "done": done,
        # ISO 8601, напр. "2026-09-06T12:34:56.789012+00:00"
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _next_id += 1
    tasks.append(task)
    return task


def _find_task(task_id: int) -> dict | None:
    """Знайти задачу за id у списку. Повертає словник або None, якщо немає."""
    return next((t for t in tasks if t["id"] == task_id), None)


# ---------------------------------------------------------------------------
# Обробники помилок
# ---------------------------------------------------------------------------
def _not_found():
    """Стандартна відповідь 404, коли задачі з указаним id не існує."""
    return jsonify({"error": "Task not found"}), 404


def _bad_request(message: str):
    """Стандартна відповідь 400 з людиночитабельним описом проблеми."""
    return jsonify({"error": message}), 400


# ---------------------------------------------------------------------------
# Ендпоінти
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    """Головна сторінка — простий візуальний інтерфейс до API.

    Віддає шаблон templates/index.html. Сам HTML нічого не знає про дані
    напряму — уся логіка на стороні клієнта (JavaScript у цьому файлі) ходить
    у вже існуючі ендпоінти /tasks через fetch(), так само, як міг би
    робити curl чи Postman. Бізнес-логіка ендпоінтів тут не дублюється.
    """
    return render_template("index.html")


@app.get("/health")
def health():
    """Healthcheck.

    Використовується оркестратором (Docker / k3s) та моніторингом, щоб
    перевірити, що застосунок живий. Завжди повертає 200 і {"status": "ok"}.
    """
    return jsonify({"status": "ok"})


@app.get("/tasks")
def list_tasks():
    """GET /tasks — повернути список усіх задач.

    Віддає JSON-масив усіх задач у тому порядку, в якому вони були створені.
    Якщо задач немає — повертає порожній масив [].
    """
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    """GET /tasks/<id> — повернути одну задачу за її id.

    <int:task_id> у маршруті гарантує, що Flask прийме тільки цілі числа.
    Якщо задачі з таким id немає — 404 {"error": "Task not found"}.
    """
    task = _find_task(task_id)
    if task is None:
        return _not_found()
    return jsonify(task)


@app.post("/tasks")
def create_task():
    """POST /tasks — створити нову задачу.

    Очікує тіло запиту у форматі JSON:
        {"title": "Купити молоко", "done": false}

    Правила:
        - title обов'язкове; якщо його немає або воно порожнє — 400.
        - done необов'язкове; якщо не передане — за замовчуванням False.
        - id та created_at генерує сервер, значення від клієнта ігноруються.

    У разі успіху повертає створену задачу і статус 201 (Created).
    """
    # silent=True -> якщо тіло не JSON, отримаємо None замість винятку.
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return _bad_request("Field 'title' is required and must be a non-empty string")

    # Приводимо done до bool: якщо поле відсутнє — False.
    done = bool(data.get("done", False))

    task = _make_task(title.strip(), done)
    return jsonify(task), 201


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    """PUT /tasks/<id> — оновити існуючу задачу.

    Приймає JSON, в якому можуть бути поля title та/або done — оновлюються
    тільки ті, що передані (часткове оновлення):
        {"title": "Новий текст"}
        {"done": true}
        {"title": "...", "done": true}

    Правила:
        - Якщо задачі з таким id немає — 404 {"error": "Task not found"}.
        - Якщо title передане, але порожнє / не рядок — 400.
        - id та created_at не змінюються ніколи.

    У разі успіху повертає оновлену задачу і статус 200.
    """
    task = _find_task(task_id)
    if task is None:
        return _not_found()

    data = request.get_json(silent=True) or {}

    # Оновлюємо title лише якщо клієнт його явно передав.
    if "title" in data:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return _bad_request("Field 'title' must be a non-empty string")
        task["title"] = title.strip()

    # Оновлюємо done лише якщо клієнт його явно передав.
    if "done" in data:
        task["done"] = bool(data.get("done"))

    return jsonify(task)


@app.delete("/tasks/<int:task_id>")
def delete_task(task_id: int):
    """DELETE /tasks/<id> — видалити задачу за id.

    Якщо задачі з таким id немає — 404 {"error": "Task not found"}.
    У разі успіху повертає видалену задачу і статус 200 (щоб клієнт бачив,
    що саме було видалено).
    """
    task = _find_task(task_id)
    if task is None:
        return _not_found()

    tasks.remove(task)
    return jsonify(task)


if __name__ == "__main__":
    # host="0.0.0.0" -> слухати на всіх мережевих інтерфейсах, а не лише
    # на localhost. Це критично для роботи всередині контейнера: інакше
    # запити ззовні (з host-машини чи іншого пода) не доходитимуть.
    # port=8080 -> порт, який далі буде прокинутий у Docker / k3s.
    app.run(host="0.0.0.0", port=8080, debug=True)
