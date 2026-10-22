"""Transparent respiratory-count baseline on complete daily reporting windows."""
from collections import Counter
from datetime import timedelta
from math import sqrt
from .facility_recommendation import timestamp

def detect_surge(cases, baseline_days=14, recent_days=3):
    if baseline_days < 7 or recent_days < 1:
        raise ValueError('Use at least seven baseline days and one recent day')
    daily = Counter()
    dates = []
    for case in cases:
        day = timestamp(case['reported_at']).date()
        dates.append(day)
        symptoms = case['symptoms'].split('|') if isinstance(case['symptoms'], str) else case['symptoms']
        if {'cough', 'shortness_of_breath'} & set(symptoms):
            daily[day] += 1
    if not dates:
        return dict(alert=False, sufficient_history=False, daily_counts=[], explanation='No hospital case signals')
    end = max(dates)
    start = end - timedelta(days=baseline_days + recent_days - 1)
    sufficient = min(dates) <= start
    baseline = [daily[start + timedelta(days=i)] for i in range(baseline_days)]
    recent = [daily[end - timedelta(days=i)] for i in range(recent_days)]
    mean = sum(baseline) / baseline_days
    threshold = mean + 3 * sqrt(max(mean, 1))
    recent_mean = sum(recent) / recent_days
    return dict(alert=sufficient and recent_mean > threshold, sufficient_history=sufficient,
                baseline_daily_mean=mean, recent_daily_mean=recent_mean, threshold=threshold,
                daily_counts=[dict(date=(start + timedelta(days=i)).isoformat(), count=daily[start + timedelta(days=i)]) for i in range(baseline_days + recent_days)],
                explanation='Recent respiratory count mean compared with baseline mean plus three Poisson standard deviations; assumes complete daily reporting.')
