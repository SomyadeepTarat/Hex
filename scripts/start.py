"""One-process local demo launcher. Run: .venv/bin/python scripts/start.py"""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    from src.hex.ml import MODEL_PATH, train
    if not MODEL_PATH.exists():
        print('Training reproducible synthetic admission model…')
        train()
    if not (ROOT / 'data/synthetic/generated/cases_surge.csv').exists():
        import subprocess
        subprocess.run([sys.executable, str(ROOT / 'scripts/generate_demo_data.py')], check=True)
    import uvicorn
    print(f'Patient finder: http://localhost:{args.port}/find-care/')
    print(f'Hospital workspace: http://localhost:{args.port}/hospital/')
    uvicorn.run('src.hex.api:app', host='127.0.0.1', port=args.port)

if __name__ == '__main__':
    main()
