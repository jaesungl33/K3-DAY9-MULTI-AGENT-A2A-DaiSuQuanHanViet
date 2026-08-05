"""Runtime configuration. Model name is declared here (not in .env) for grading."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
LOGGING_DIR = ROOT / "logging"

# Each agent uses the same <=10B model when LLM deliberation is enabled.
MODEL_NAME = "llama-3.1-8b-instant"
MODEL_PARAMETER_SIZE = "8B"
FRAMEWORK = "custom-a2a-multi-agent"
RUNTIME = "python-pandas-deterministic-policy"

PAYMENT_MATCH_TOLERANCE_BRL = 0.10
MONEY_ROUND = 2

MAX_ENTITY_IDS = 5
MAX_EVIDENCE_IDS = 10
MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_ACTIONS = 5
