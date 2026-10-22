import unittest
from src.hex.ml import generate_dataset, fit, evaluate, forecast_cases
from scripts.generate_demo_data import generate

class MLTests(unittest.TestCase):
    def test_reproducible_training_and_holdout(self):
        rows=generate_dataset(cities=3, days=365)
        self.assertEqual(rows,generate_dataset(cities=3,days=365))
        training=[r for r in rows if r['city_id']<2 and r['day']<250]
        test=[r for r in rows if r['city_id']==2 and r['day']>=250]
        model=fit(training,10)
        self.assertEqual(model,fit(training,10))
        score=evaluate(model,test)
        self.assertLess(score['mae'],score['persistence_mae'])
    def test_runtime_forecast(self):
        context,feeds=generate()
        info,rates=forecast_cases(feeds['surge'],context['hospitals'])
        self.assertTrue(info['available'])
        self.assertEqual(set(rates),{'HOSP-01','HOSP-02','HOSP-03'})
        self.assertTrue(all(v>=0 for v in rates.values()))
