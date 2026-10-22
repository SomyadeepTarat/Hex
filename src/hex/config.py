"""Server-only environment configuration. Never return or log credential values."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip().strip('\"').strip("'")
            if key in {'GROQ_API_KEY', 'GROQ_MODEL'} and value:
                os.environ.setdefault(key, value)

def provider_config():
    load_env()
    return os.getenv('GROQ_API_KEY', ''), os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')
