"""Run Person 1's engine without a server or database."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from generate_demo_data import generate
from hex.pipeline import run_analysis

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['normal', 'surge'], default='surge')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    context, feeds = generate(args.seed)
    result = run_analysis(feeds[args.mode], **context)
    content = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
        print(f'Saved {args.output}')
    else:
        print(content, end='')

if __name__ == '__main__':
    main()
