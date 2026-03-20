"""Módulo CRUD de Acuerdos del Área — almacenados en acuerdos/acuerdos_{slug}.json"""
import json
import uuid
from pathlib import Path
from datetime import datetime

ACUERDOS_DIR = Path(__file__).parent.parent / "acuerdos"


def _acuerdos_path(slug: str) -> Path:
    ACUERDOS_DIR.mkdir(exist_ok=True)
    return ACUERDOS_DIR / f"acuerdos_{slug}.json"


def get_acuerdos(slug: str) -> list:
    """Lee y retorna la lista de acuerdos para el sitio."""
    path = _acuerdos_path(slug)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("acuerdos", [])


def save_acuerdo(slug: str, data: dict) -> dict:
    """Crea o actualiza un acuerdo. Si no tiene id, asigna uno nuevo."""
    acuerdos = get_acuerdos(slug)
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        data["fecha"] = datetime.now().strftime("%Y-%m-%d")
        acuerdos.append(data)
    else:
        acuerdos = [data if a["id"] == data["id"] else a for a in acuerdos]
    _write(slug, acuerdos)
    return data


def delete_acuerdo(slug: str, acuerdo_id: str) -> None:
    """Elimina un acuerdo por id."""
    acuerdos = [a for a in get_acuerdos(slug) if a["id"] != acuerdo_id]
    _write(slug, acuerdos)


def _write(slug: str, acuerdos: list) -> None:
    with open(_acuerdos_path(slug), "w", encoding="utf-8") as f:
        json.dump({"acuerdos": acuerdos}, f, ensure_ascii=False, indent=2)
