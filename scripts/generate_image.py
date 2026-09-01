# scripts/generate_image.py

import argparse
import base64
import os
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from openai import OpenAI


MODEL = "gpt-image-2"
IMAGE_SIZE = "1024x1536"
IMAGE_QUALITY = "low"
OUTPUT_DIR = Path("output")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_REFERENCE_LIMIT = 6


def load_project_env() -> None:
    """Load simple KEY=VALUE entries from the project's .env file."""
    env_path = PROJECT_ROOT / ".env"

    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value[:1] == value[-1:] and value.startswith(("\"", "'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def collect_reference_paths(
    reference_paths: list[str] | None = None,
    reference_dir: str | None = None,
    limit: int = DEFAULT_REFERENCE_LIMIT,
) -> list[Path]:
    paths: list[Path] = []

    if reference_paths:
        paths.extend(Path(path) for path in reference_paths)

    if reference_dir:
        directory = Path(reference_dir)
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory

        if not directory.is_dir():
            raise RuntimeError(f"Папка с референсами не найдена: {directory}")

        paths.extend(
            sorted(
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in REFERENCE_EXTENSIONS
            )
        )

    resolved_paths: list[Path] = []

    for path in paths:
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        if path.suffix.lower() not in REFERENCE_EXTENSIONS:
            raise RuntimeError(f"Неподдерживаемый формат референса: {path}")

        if not path.is_file():
            raise RuntimeError(f"Файл референса не найден: {path}")

        if path not in resolved_paths:
            resolved_paths.append(path)

    return resolved_paths[:limit]


def generate_image(
    prompt: str,
    output_name: str | None = None,
    reference_paths: list[str] | None = None,
    reference_dir: str | None = None,
) -> Path:
    load_project_env()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY не найден. Добавь ключ в переменные окружения."
        )

    client = OpenAI(api_key=api_key)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_name:
        filename = output_name
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_image.png"

    if not filename.endswith(".png"):
        filename += ".png"

    output_path = OUTPUT_DIR / filename

    # Не перезаписываем существующий файл
    if output_path.exists():
        stem = output_path.stem
        suffix = output_path.suffix
        counter = 2

        while output_path.exists():
            output_path = OUTPUT_DIR / f"{stem}-{counter}{suffix}"
            counter += 1

    references = collect_reference_paths(
        reference_paths=reference_paths,
        reference_dir=reference_dir,
    )

    if references:
        with ExitStack() as stack:
            image_files = [
                stack.enter_context(reference.open("rb")) for reference in references
            ]

            result = client.images.edit(
                model=MODEL,
                image=image_files,
                prompt=prompt,
                size=IMAGE_SIZE,
                quality=IMAGE_QUALITY,
                output_format="png",
            )
    else:
        result = client.images.generate(
            model=MODEL,
            prompt=prompt,
            size=IMAGE_SIZE,
            quality=IMAGE_QUALITY,
            output_format="png",
        )

    image_base64 = result.data[0].b64_json

    if not image_base64:
        raise RuntimeError("OpenAI не вернул изображение.")

    image_bytes = base64.b64decode(image_base64)

    output_path.write_bytes(image_bytes)

    if output_path.stat().st_size == 0:
        raise RuntimeError("Создан пустой файл изображения.")

    print(str(output_path))

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate image using OpenAI Image API"
    )

    parser.add_argument(
        "--prompt",
        required=True,
        help="Готовый prompt для генерации изображения",
    )

    parser.add_argument(
        "--output",
        required=False,
        help="Имя выходного PNG-файла",
    )

    parser.add_argument(
        "--reference",
        action="append",
        required=False,
        help="Путь к изображению-референсу. Можно передать несколько раз.",
    )

    parser.add_argument(
        "--reference-dir",
        required=False,
        help="Папка с изображениями-референсами. Используются первые 6 файлов.",
    )

    args = parser.parse_args()

    generate_image(
        prompt=args.prompt,
        output_name=args.output,
        reference_paths=args.reference,
        reference_dir=args.reference_dir,
    )


if __name__ == "__main__":
    main()
