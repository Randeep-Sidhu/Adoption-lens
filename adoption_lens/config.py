from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = Path(__file__).resolve().parent / "sql"
DATA_RAW = ROOT / "data" / "raw"
DATA_REF = ROOT / "data" / "reference"
ARTIFACTS = ROOT / "artifacts"

HF_REVISION = "7fc50b03e2bd9fc2a011794a96c2ac69e666fd40"
_HF = f"https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/{HF_REVISION}/release_2026_03_24/data"

SOURCES = {
    "claude_ai": {
        "file": "aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv",
        "url": f"{_HF}/aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv",
        "sha256": "9c53320b8732ac2e88fc2c95fbdefa02222f04333a41d4f4e947861409798cf1",
        "bytes": 96018130,
    },
    "api": {
        "file": "aei_raw_1p_api_2026-02-05_to_2026-02-12.csv",
        "url": f"{_HF}/aei_raw_1p_api_2026-02-05_to_2026-02-12.csv",
        "sha256": "b3bcd68e7f6d820ffbb50a3c53d71ec2a122556fc2a38226cd86951a054bd4c8",
        "bytes": 43957174,
    },
}

AEI_COLUMNS = ["geo_id", "geography", "date_start", "date_end", "platform_and_product", "facet", "level",
               "variable", "cluster_name", "value"]

FOCUS_COUNTRY = "CA"
MIN_CONVERSATIONS = 200
MIN_CATEGORY_COUNT = 30
Z = 1.96

USE_CASES = ("work", "personal", "coursework")
AUTOMATION = ("directive", "feedback loop")
AUGMENTATION = ("learning", "task iteration", "validation")
SUCCESS = ("yes", "no")

