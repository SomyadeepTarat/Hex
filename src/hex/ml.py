"""Small trained ridge autoregressor for synthetic next-day admission demand."""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / 'models/admission_model.json'
FEATURES = ['lag_1', 'lag_7', 'mean_7', 'trend_3', 'respiratory_share', 'weekday_sin', 'weekday_cos']

def features(history, respiratory_share, weekday):
    values = list(history)[-7:]
    values = [values[0] if values else 0] * (7 - len(values)) + values
    return [values[-1], values[0], sum(values) / 7, (sum(values[-3:]) - sum(values[:3])) / 3,
            respiratory_share, math.sin(2 * math.pi * weekday / 7), math.cos(2 * math.pi * weekday / 7)]

def generate_dataset(seed=42, cities=12, days=730):
    rng = random.Random(seed)
    rows = []
    for city in range(cities):
        for hospital in range(3):
            history = [10.] * 7
            share, latent = .4, 0.
            scale = rng.uniform(.7, 1.5)
            for day in range(days):
                surge = 12 * max(0, math.sin((day + city * 13) / 31)) ** 6
                latent = .85 * latent + rng.gauss(0, .8)
                previous_share = share
                share = min(.95, max(.1, .35 + surge / 35 + rng.gauss(0, .04)))
                demand = max(0, round(scale * (9 + surge + 3 * math.sin(2 * math.pi * day / 7)) + latent + rng.gauss(0, 1.5)))
                if day >= 7:
                    rows.append(dict(city_id=city, hospital_id=hospital, day=day, features=features(history, previous_share, day % 7), target=demand, baseline=history[-1]))
                history.append(demand)
    return rows

def solve(matrix, target):
    a = [list(row) + [value] for row, value in zip(matrix, target)]
    size = len(a)
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        if abs(divisor) < 1e-12:
            raise ValueError('Singular training matrix')
        a[col] = [v / divisor for v in a[col]]
        for row in range(size):
            if row != col:
                ratio = a[row][col]
                a[row] = [x - ratio * y for x, y in zip(a[row], a[col])]
    return [row[-1] for row in a]

def fit(rows, alpha):
    n, dim = len(rows), len(FEATURES)
    means = [sum(r['features'][j] for r in rows) / n for j in range(dim)]
    scales = [max(1e-6, (sum((r['features'][j] - means[j]) ** 2 for r in rows) / n) ** .5) for j in range(dim)]
    matrix, target = [[0.] * (dim + 1) for _ in range(dim + 1)], [0.] * (dim + 1)
    for row in rows:
        x = [1.] + [(v - m) / s for v, m, s in zip(row['features'], means, scales)]
        for j in range(dim + 1):
            target[j] += x[j] * row['target']
            for k in range(dim + 1):
                matrix[j][k] += x[j] * x[k]
    for j in range(1, dim + 1):
        matrix[j][j] += alpha
    return dict(coefficients=solve(matrix, target), means=means, scales=scales, alpha=alpha, features=FEATURES)

def predict(model, values):
    x = [1.] + [(v - m) / s for v, m, s in zip(values, model['means'], model['scales'])]
    return max(0., sum(a * b for a, b in zip(x, model['coefficients'])))

def evaluate(model, rows):
    errors = [predict(model, r['features']) - r['target'] for r in rows]
    base = [r['baseline'] - r['target'] for r in rows]
    return dict(rows=len(rows), mae=sum(abs(e) for e in errors) / len(rows), rmse=(sum(e * e for e in errors) / len(rows)) ** .5,
                persistence_mae=sum(abs(e) for e in base) / len(rows), persistence_rmse=(sum(e * e for e in base) / len(rows)) ** .5)

def train(output=MODEL_PATH):
    import csv
    rows = generate_dataset()
    train_rows = [r for r in rows if r['city_id'] < 10 and r['day'] < 510]
    validation = [r for r in rows if r['city_id'] < 10 and 510 <= r['day'] < 620]
    candidates = [fit(train_rows, a) for a in [1., 10., 100.]]
    model = min(candidates, key=lambda m: evaluate(m, validation)['mae'])
    test = [r for r in rows if r['city_id'] < 10 and r['day'] >= 620]
    unseen = [r for r in rows if r['city_id'] >= 10 and r['day'] >= 620]
    metrics = dict(seed=42, synthetic=True, dataset_rows=len(rows), training_rows=len(train_rows), validation=evaluate(model, validation), temporal_test=evaluate(model, test), unseen_city_test=evaluate(model, unseen),
                   split='Train cities 0..9 days 7..509; tune days 510..619; test days 620..729. Cities 10..11 are never used to fit or select the model.',
                   limitation='Synthetic benchmark only. These results do not establish real hospital forecasting performance.')
    model['residual_std'] = metrics['validation']['rmse']
    model['evaluation'] = metrics
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, indent=2) + '\n')
    dataset = ROOT / 'data/synthetic/ml_hospital_days.csv'
    with dataset.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['city_id', 'hospital_id', 'day', *FEATURES, 'next_day_admissions', 'persistence_prediction'])
        for r in rows:
            writer.writerow([r['city_id'], r['hospital_id'], r['day'], *r['features'], r['target'], r['baseline']])
    (output.parent / 'evaluation.json').write_text(json.dumps(metrics, indent=2) + '\n')
    return metrics

def forecast_cases(cases, hospitals):
    from datetime import date, timedelta
    if not MODEL_PATH.exists():
        return dict(available=False, explanation='Train the admission model first.'), {}
    model = json.loads(MODEL_PATH.read_text())
    if not cases:
        return dict(available=False, explanation='No hospital case history.'), {}
    end = max(date.fromisoformat(str(c['reported_at'])[:10]) for c in cases)
    predictions = {}
    for h in hospitals:
        own = [c for c in cases if c['hospital_id'] == h['hospital_id']]
        history = [sum(str(c['reported_at'])[:10] == (end - timedelta(days=d)).isoformat() and str(c['admitted']).lower() == 'true' for c in own) for d in range(6, -1, -1)]
        recent = [c for c in own if str(c['reported_at'])[:10] == end.isoformat()]
        share = sum('cough' in c['symptoms'] or 'shortness_of_breath' in c['symptoms'] for c in recent) / max(1, len(recent))
        predictions[h['hospital_id']] = predict(model, features(history, share, (end + timedelta(days=1)).weekday()))
    return dict(available=True, model='Ridge autoregression', next_day_admissions=predictions, evaluation=model['evaluation'], residual_std=model['residual_std']), predictions

if __name__ == '__main__':
    print(json.dumps(train(), indent=2))
