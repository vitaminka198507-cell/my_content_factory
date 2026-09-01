#!/usr/bin/env python3

import json
import os
import re
import subprocess
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from openai import OpenAI

from scripts.generate_image import generate_image
from scripts.render_carousel import render_carousel


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_ROOT / "output" / "web"
KNOWLEDGE_FILES = [
    "knowledge/about-me.md",
    "knowledge/audience.md",
    "knowledge/content-guide.md",
    "knowledge/tone-of-voice.md",
    "knowledge/examples-posts.md",
]
HUMAN_WORDS = {
    "человек",
    "девушка",
    "женщина",
    "автор",
    "эксперт",
    "пользователь",
    "персонаж",
    "лицо",
    "портрет",
    "силуэт",
    "фигура",
    "рука",
    "сидит",
    "стоит",
    "держит",
    "смотрит",
    "работает",
}


def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        os.environ.setdefault(key.strip(), value)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", text.lower()).strip("-")
    return slug[:70] or "content"


def read_knowledge() -> str:
    blocks = []
    for relative_path in KNOWLEDGE_FILES:
        path = PROJECT_ROOT / relative_path
        if path.is_file():
            blocks.append(f"# {relative_path}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(blocks)


def build_prompt(user_request: str, knowledge: str) -> str:
    return f"""
Ты — локальный Content Factory Виолетты.

Задача: по запросу пользователя подготовить контент на русском языке для Telegram, VK и Instagram.

Используй базу знаний ниже: позиционирование, аудиторию, tone of voice, правила контента и примеры.
Не публикуй ничего в соцсети. Только подготовь тексты и структуру файлов.

Верни строго валидный JSON без markdown-обертки по схеме:
{{
  "title": "короткое название материала",
  "telegram": "готовый текст Telegram-поста",
  "vk": "готовый текст VK-поста",
  "instagram": {{
    "schema_version": "instagram-carousel/v1",
    "format": "carousel",
    "slides": [
      {{
        "slide": 1,
        "role": "hook",
        "headline": "текст слайда",
        "body": "текст слайда"
      }}
    ],
    "caption": "готовая подпись к Instagram"
  }},
  "visual": {{
    "topic": "тема визуала",
    "concept": "конкретная сцена или визуальная метафора",
    "key_object": "главный объект",
    "mood": "настроение",
    "cover_text": "короткий текст на обложке или null"
  }}
}}

Запрос пользователя:
{user_request}

База знаний:
{knowledge}
""".strip()


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def save_result(user_request: str, data: dict) -> dict:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp}_{slugify(data.get('title') or user_request)}"
    output_dir = OUTPUT_ROOT / folder_name
    posts_dir = output_dir / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    (posts_dir / "telegram.md").write_text(data["telegram"], encoding="utf-8")
    (posts_dir / "vk.md").write_text(data["vk"], encoding="utf-8")
    (posts_dir / "instagram.json").write_text(
        json.dumps(data["instagram"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (posts_dir / "visual_brief.json").write_text(
        json.dumps({"visual": data["visual"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "result.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "output_dir": str(output_dir),
        "instagram_json": str(posts_dir / "instagram.json"),
        "files": [
            str(posts_dir / "telegram.md"),
            str(posts_dir / "vk.md"),
            str(posts_dir / "instagram.json"),
            str(posts_dir / "visual_brief.json"),
            str(output_dir / "result.json"),
        ],
    }


def visual_text(visual: dict) -> str:
    return " ".join(str(visual.get(key) or "") for key in ("topic", "concept", "key_object", "mood"))


def has_human(visual: dict) -> bool:
    text = visual_text(visual).lower()
    return any(word in text for word in HUMAN_WORDS)


def build_image_prompt(visual: dict, human_detected: bool) -> str:
    cover_text = visual.get("cover_text")
    cover_instruction = (
        f'Add exactly this cover text: "{cover_text}". Do not add any other text.'
        if cover_text
        else "Do not add any text to the image."
    )
    person_instruction = ""
    if human_detected:
        person_instruction = (
            "If a person is shown, the person is a Slavic-looking woman with light hair and a bob haircut. "
            "The person must preserve identity from the reference photos: same facial structure, face proportions, "
            "hairstyle, light bob haircut, hair color, age impression, and overall recognizable likeness. "
            "This is the same woman from the reference photos in a new scene, not a similar generic woman."
        )

    return f"""
Create a vertical 1024x1536 branded cover image for a Russian social media post.

Topic: {visual.get("topic", "")}
Scene concept: {visual.get("concept", "")}
Key object: {visual.get("key_object", "")}
Mood: {visual.get("mood", "")}

Style: modern minimalist digital surrealism, clean light-gray neutral background, generous negative space, ordered composition, subtle futuristic digital details, thin glowing lavender lines in #C5C7FF, monochrome gray/black/white palette with one soft lavender accent. Avoid clutter and secondary objects. Main object or character should sit mostly in the lower or side area, often bottom-right, leaving readable space for cover text.

{person_instruction}
{cover_instruction}
""".strip()


def create_cover_image(output_dir: Path, visual: dict) -> dict:
    output_dir = output_dir.resolve()
    if not visual.get("topic") or not visual.get("concept"):
        raise RuntimeError("Visual Brief неполный: нужны поля topic и concept.")

    human_detected = has_human(visual)
    image_prompt = build_image_prompt(visual, human_detected)
    output_name = str(output_dir.relative_to(PROJECT_ROOT / "output") / "cover.png")
    reference_dir = "assets/me" if human_detected else None

    if human_detected and not (PROJECT_ROOT / "assets" / "me").is_dir():
        raise RuntimeError("Для визуала с человеком нужна папка assets/me с референсами.")

    image_path = generate_image(
        prompt=image_prompt,
        output_name=output_name,
        reference_dir=reference_dir,
    )
    absolute_image_path = PROJECT_ROOT / image_path
    result = {
        "status": "ok",
        "local_image_path": str(absolute_image_path),
        "image_prompt": image_prompt,
        "human_detected": human_detected,
        "used_reference_dir": reference_dir,
        "notes": [],
    }
    (output_dir / "image_generation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def create_carousel(output_dir: Path, instagram_json: Path) -> dict:
    output_dir = output_dir.resolve()
    instagram_json = instagram_json.resolve()
    carousel_dir = output_dir / "instagram_carousel"
    manifest = render_carousel(instagram_json, carousel_dir)
    manifest_path = carousel_dir / "manifest.json"
    return {
        "status": "ok",
        "source_json": str(instagram_json),
        "output_dir": str(carousel_dir),
        "slides": [str(PROJECT_ROOT / path) for path in manifest.get("slides", [])],
        "caption": str(PROJECT_ROOT / manifest.get("caption", "")),
        "manifest": str(manifest_path),
        "notes": manifest.get("warnings", []),
    }


def update_result_manifest(result: dict, image_result: dict, carousel_result: dict) -> dict:
    output_dir = Path(result["output_dir"])
    result["cover_image"] = image_result.get("local_image_path")
    result["carousel_dir"] = carousel_result.get("output_dir")
    result["carousel_slides"] = carousel_result.get("slides", [])
    result["files"].extend(
        [
            image_result.get("local_image_path"),
            str(output_dir / "image_generation.json"),
            carousel_result.get("manifest"),
            carousel_result.get("caption"),
            *carousel_result.get("slides", []),
        ]
    )
    (output_dir / "web_result_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def generate_content(user_request: str):
    load_project_env()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не найден. Добавь ключ в .env или переменные окружения.")

    yield {"type": "log", "message": "Приняла запрос. Читаю базу знаний проекта..."}
    knowledge = read_knowledge()
    yield {"type": "log", "message": "База знаний загружена: позиционирование, аудитория, стиль и примеры."}
    yield {"type": "log", "message": "Передаю задачу модели и жду готовые материалы для трех площадок..."}

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5.4-mini",
        input=build_prompt(user_request, knowledge),
    )

    yield {"type": "log", "message": "Ответ получен. Проверяю JSON и раскладываю результат по файлам..."}
    data = extract_json(response.output_text)
    result = save_result(user_request, data)
    output_dir = Path(result["output_dir"])
    instagram_json = Path(result["instagram_json"])

    yield {"type": "log", "message": "Запускаю Image Generator: готовлю фирменный промпт и создаю обложку..."}
    image_result = create_cover_image(output_dir, data["visual"])
    yield {
        "type": "log",
        "message": f"Обложка готова: {image_result['local_image_path']}",
    }

    yield {"type": "log", "message": "Запускаю Carousel Renderer: рендерю Instagram JSON в PNG-слайды..."}
    carousel_result = create_carousel(output_dir, instagram_json)
    yield {
        "type": "log",
        "message": f"Слайды карусели готовы: {carousel_result['output_dir']}",
    }

    result = update_result_manifest(result, image_result, carousel_result)

    yield {"type": "log", "message": "Готово. Тексты, visual brief, обложка и слайды сохранены в одну папку."}
    yield {"type": "done", "result": result}


class ContentFactoryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            html = (PROJECT_ROOT / "web" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/open-folder":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            folder = Path(payload.get("path", "")).resolve()
            if not str(folder).startswith(str(PROJECT_ROOT.resolve())) or not folder.is_dir():
                self.send_json(400, {"error": "Папка не найдена или находится вне проекта."})
                return
            subprocess.Popen(["open", str(folder)])
            self.send_json(200, {"status": "ok"})
            return

        if self.path != "/api/generate":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        user_request = str(payload.get("request", "")).strip()
        if not user_request:
            self.send_json(400, {"error": "Введите запрос для Content Factory."})
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        try:
            for event in generate_content(user_request):
                self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.15)
        except Exception as error:
            event = {"type": "error", "message": str(error)}
            self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()


def main() -> None:
    os.chdir(PROJECT_ROOT)
    host = "127.0.0.1"
    port = int(os.getenv("CONTENT_FACTORY_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ContentFactoryHandler)
    print(f"Content Factory web UI: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
