import copy
import json
import unittest
from scripts.generate_demo_data import generate
from hex.facility_recommendation import recommend_facilities
from hex.constraint_parser import parse_constraint_message
from hex.detection import detect_surge
from hex.pipeline import run_analysis
from hex.simulation import generate_futures, simulate
from hex.strategies import compare_strategies

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.context, self.feeds = generate()
        self.c = self.context
        self.now = '2026-10-22T06:05:00Z'

    def recommend(self, symptoms=None):
        return recommend_facilities(symptoms or ['cough'], 'ZONE-03', self.c['hospitals'], self.c['statuses'], self.now)

    def test_accepting_and_unknown(self):
        self.assertEqual(self.recommend()['suggested_hospital_id'], 'HOSP-01')
        self.c['statuses'][0]['accepting_patients'] = False
        self.assertNotEqual(self.recommend()['suggested_hospital_id'], 'HOSP-01')
        for s in self.c['statuses']:
            s.pop('reported_at')
        result = self.recommend()
        self.assertIsNone(result['suggested_hospital_id'])
        self.assertTrue(all(a['freshness_state'] == 'unknown' for a in result['alternatives']))

    def test_stale_planned_and_missing_capacity(self):
        before = self.recommend()
        self.c['hospitals'][0]['planned_beds'] = 10000
        self.assertEqual(before, self.recommend())
        self.c['statuses'][0]['reported_at'] = '2026-10-21T06:00:00Z'
        item = next(x for x in self.recommend()['alternatives'] if x['hospital_id'] == 'HOSP-01')
        self.assertEqual(item['freshness_state'], 'stale')
        self.c['statuses'][0].pop('staffed_general_beds')
        item = next(x for x in self.recommend()['alternatives'] if x['hospital_id'] == 'HOSP-01')
        self.assertIsNone(item['available_staffed_beds'])

    def test_emergency(self):
        r = recommend_facilities(['severe_breathing_difficulty'], None, [], [], self.now)
        self.assertTrue(r['emergency_guidance_required'])
        self.assertEqual(r['alternatives'], [])

    def test_detection(self):
        self.assertFalse(detect_surge(self.feeds['normal'])['alert'])
        self.assertTrue(detect_surge(self.feeds['surge'])['alert'])
        self.assertFalse(detect_surge(self.feeds['surge'][-2:])['sufficient_history'])

    def test_seed_and_no_mutation(self):
        args = (self.feeds['surge'], self.c['hospitals'], self.c['settings'])
        self.assertEqual(generate_futures(*args), generate_futures(*args))
        before = copy.deepcopy(self.c)
        settings = dict(self.c['settings'], scenario_count=5)
        result = run_analysis(self.feeds['surge'], self.c['hospitals'], self.c['zones'], self.c['statuses'], self.c['constraints'], settings)
        json.dumps(result, allow_nan=False)
        self.assertEqual(self.c, before)
        self.assertEqual(result['status_version'], 1)

    def test_transfer_conservation(self):
        statuses = [dict(hospital_id='A', staffed_general_beds=10, occupied_general_beds=10), dict(hospital_id='B', staffed_general_beds=10, occupied_general_beds=0)]
        future = dict(length_of_stay_days=5, arrivals=[{'A': 10, 'B': 9}])
        r = simulate(future, statuses, transfer_limits={'A': 5})
        self.assertEqual(r['transferred_patients'], 1)
        self.assertEqual(r['daily'][0]['occupancy']['B'], 10)
        self.assertEqual(r['unmet_bed_days'], 7)
        future['arrivals'][0]['B'] = 0
        self.assertEqual(simulate(future, statuses, transfer_limits={'A': 2})['transferred_patients'], 2)

    def test_budget_and_constraints(self):
        statuses = [dict(hospital_id='A', staffed_general_beds=10, occupied_general_beds=10)]
        futures = [dict(length_of_stay_days=5, arrivals=[{'A': 20}] * 3)]
        constraints = [dict(hospital_id='A', max_additional_staffed_beds=5, transfer_out_limit_per_day=0)]
        plans = compare_strategies(futures, statuses, constraints, 20)
        flex = next(p for p in plans if p['strategy_id'] == 'flex_capacity')
        self.assertEqual(flex['additional_staffed_beds']['A'], 2)
        self.assertTrue(all(p['intervention_cost'] <= 20 for p in plans))
        constrained = compare_strategies(futures, statuses, constraints, 0)
        self.assertLess(flex['worst_case_unmet_bed_days'], constrained[0]['worst_case_unmet_bed_days'])

    def test_parser(self):
        context = dict(hospitals=[{**h, **c} for h, c in zip(self.c['hospitals'], self.c['constraints'])], settings=self.c['settings'])
        actor = dict(role='government')
        before = copy.deepcopy(context)
        r = parse_constraint_message('Set HOSP-02 transfer limit to 5 per day.', actor, context)
        self.assertEqual((r['action'], r['field'], r['new_value']), ('propose_change', 'transfer_out_limit_per_day', 5))
        self.assertEqual(parse_constraint_message('Set network budget to 100 units.', actor, context)['new_value'], 100)
        self.assertEqual(parse_constraint_message('Set scenario count to 100.', actor, context)['new_value'], 100)
        self.assertEqual(parse_constraint_message('Set HOSP-01 maximum additional staffed beds to 12.', actor, context)['new_value'], 12)
        self.assertEqual(parse_constraint_message('Set unknown transfer limit to 5.', actor, context)['action'], 'clarify')
        self.assertEqual(parse_constraint_message('Set scenario count to -1.', actor, context)['action'], 'clarify')
        self.assertEqual(parse_constraint_message('Drop table hospitals', actor, context)['action'], 'unsupported')
        self.assertEqual(parse_constraint_message('Show current constraints.', actor, context)['action'], 'show_constraints')
        self.assertEqual(parse_constraint_message('Set network budget to 20.', dict(role='hospital', hospital_id='HOSP-01'), context)['action'], 'unsupported')
        self.assertEqual(context, before)
        context['hospitals'].append(dict(context['hospitals'][0]))
        self.assertEqual(parse_constraint_message('Set HOSP-01 transfer limit to 5.', actor, context)['action'], 'clarify')

if __name__ == '__main__':
    unittest.main()
