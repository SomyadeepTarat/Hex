import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from src.hex.care_matching import interpret, match_care, explain_with_groq, ROOT
from src.hex import groq

class CareTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        profiles=json.loads((ROOT/'data/synthetic/hospital_capabilities.json').read_text())
        names=['Central Community Hospital','Riverside Medical Centre','North District Hospital']
        self.hospitals=[dict(hospital_id=hid,name=names[i],zone_id=['ZONE-03','ZONE-04','ZONE-05'][i],services=['general','respiratory'],staffed_general_beds=100,occupied_general_beds=50,accepting_patients=True,reported_at=self.now.isoformat(),capabilities_reported_at=self.now.isoformat(),**profile) for i,(hid,profile) in enumerate(profiles.items())]
    def match(self,message,selected=None):
        return match_care(interpret(message,selected or []),'ZONE-03',self.hospitals,self.now)
    def test_nearer_general_vs_farther_requested_specialist(self):
        result=self.match('I have a cough and want a pulmonologist.')
        self.assertEqual(result['suggested_hospital_id'],'HOSP-02')
        self.assertEqual(result['suggested_facility']['distance_km'],10)
        self.assertIn('closer at 5 km',result['explanation'])
        self.assertIn('pulmonology',result['explanation'])
        self.assertEqual(self.match('I have a cough')['suggested_hospital_id'],'HOSP-01')
    def test_resources_and_freshness(self):
        self.assertEqual(self.match('I need an x-ray for my knee pain')['suggested_hospital_id'],'HOSP-02')
        self.hospitals[1]['resources']['xray_slots']=0
        self.assertEqual(self.match('I need an x-ray for my knee pain')['suggested_hospital_id'],'HOSP-03')
        for h in self.hospitals:h['reported_at']='2020-01-01T00:00:00Z'
        self.assertIsNone(self.match('I have a cough')['suggested_hospital_id'])
    def test_no_diagnosis_or_resource_inference(self):
        needs=interpret('I have a cough and fever',[])
        self.assertEqual(needs['requested_resources'],[])
        self.assertIsNone(needs['requested_specialty'])
        result=self.match('I have an unusual sensation I cannot describe')
        self.assertIsNone(result['suggested_hospital_id'])
        self.assertTrue(result['explanation'])
    def test_emergency_negation_and_no_provider_wait(self):
        with patch.object(groq,'structured') as call:
            needs=interpret('I cannot breathe',[],True)
            self.assertTrue(needs['emergency']);call.assert_not_called()
        self.assertFalse(interpret('I have no severe chest pain, but a cough',[])['emergency'])
        self.assertTrue(interpret('No chest pain but I cannot breathe',[])['emergency'])
        self.assertFalse(interpret('I have a rash, no vomiting',[])['emergency'])
        self.assertNotIn('vomiting',interpret('I have a rash, no vomiting',[])['symptom_tags'])
    def test_groq_explanation_grounding_and_outage(self):
        result=self.match('I want a pulmonologist for my cough')
        original=copy.deepcopy(result)
        ids=[f['id'] for f in result['facts']]
        with patch.object(groq,'structured',return_value={'hospital_id':'HOSP-02','fact_ids':ids}):
            actual=explain_with_groq(result)
            self.assertIn('Groq-assisted',actual['explanation_source'])
            self.assertEqual(actual['explanation'],original['explanation'])
        for output in [{'hospital_id':'HOSP-01','fact_ids':ids},{'hospital_id':'HOSP-02','fact_ids':['invented']},{'hospital_id':'HOSP-02','fact_ids':[]}]:
            with patch.object(groq,'structured',return_value=output):
                actual=explain_with_groq(copy.deepcopy(original))
                self.assertEqual(actual['explanation'],original['explanation'])
                self.assertIn('unavailable',actual['provider_notice'])
        with patch.object(groq,'structured',side_effect=groq.ProviderUnavailable('offline')):
            self.assertTrue(interpret('a cough',[],True)['provider_notice'])
    def test_groq_cannot_invent_hard_resource_requirement(self):
        response=dict(is_health_concern=True,unmatched_requested_service=None,symptom_tags=['cough'],requested_specialty='pulmonology',requested_resources=['oxygen_stations'],emergency=False,clarification=None)
        with patch.object(groq,'structured',return_value=response):
            needs=interpret('a cough',[],True)
            self.assertEqual(needs['requested_resources'],[])
            self.assertIsNone(needs['requested_specialty'])
            self.assertTrue(needs['clarification'])
            confirmed=interpret('a cough',[],True,{'specialty':'pulmonology','resources':['oxygen_stations']})
            self.assertIsNone(confirmed['clarification'])
            self.assertEqual(confirmed['requested_resources'],['oxygen_stations'])

    def test_stomach_ache_aliases_and_best_available(self):
        for phrase in ['I have stomach ache','a stomachache','my tummy hurts; abdominal pain','my stomach hurts','stomach cramps']:
            needs=interpret(phrase,[])
            self.assertIn('stomach_pain',needs['symptom_tags'])
            self.assertIsNone(needs['clarification'])
            result=match_care(needs,'ZONE-04',self.hospitals,self.now)
            self.assertEqual(result['suggested_hospital_id'],'HOSP-02')
            self.assertEqual(result['outcome'],'recommended')
            self.assertIn('general-assessment',result['explanation'])
        self.hospitals[1]['accepting_patients']=False
        result=match_care(interpret('stomach ache',[]),'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['suggested_hospital_id'],'HOSP-03')
    def test_stomach_ache_works_during_provider_failure(self):
        with patch.object(groq,'structured',side_effect=groq.ProviderUnavailable('Groq unavailable')):
            needs=interpret('I have stomach ache',[],True)
        self.assertTrue(needs['provider_notice'])
        result=match_care(needs,'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['suggested_hospital_id'],'HOSP-02')
    def test_specific_failure_outcomes(self):
        needs=interpret('stomach ache',[])
        for h in self.hospitals:h['reported_at']='2020-01-01T00:00:00Z'
        result=match_care(needs,'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['outcome'],'no_current_reports')
        self.assertIn('out of date',result['title'])
        self.assertTrue(result['next_steps'])
        self.assertIsNone(result['suggested_hospital_id'])
        for h in self.hospitals:
            h['reported_at']=self.now.isoformat();h['accepting_patients']=False
        result=match_care(needs,'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['outcome'],'not_accepting_or_unknown')
        result=match_care(interpret('a completely unrecognized sensation',[]),'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['outcome'],'clarification_required')
        self.assertNotEqual(result['title'],'Hospital availability is out of date')
    def test_severe_abdominal_cues_bypass_normal_ranking(self):
        for phrase in ['severe stomach ache','sudden abdominal pain','my stomach pain is severe']:
            result=self.match(phrase)
            self.assertTrue(result['emergency_guidance_required'])
            self.assertIsNone(result['suggested_hospital_id'])
        self.assertFalse(interpret('No severe abdominal pain but a mild stomach ache',[])['emergency'])

    def test_open_ended_health_concern_gets_general_assessment(self):
        response=dict(is_health_concern=True,unmatched_requested_service=None,symptom_tags=[],requested_specialty=None,requested_resources=[],emergency=False,clarification='How long has this been happening?')
        with patch.object(groq,'structured',return_value=response):
            needs=interpret('I have tingling around my fingers and want to get checked',[],True)
        self.assertIsNone(needs['clarification'])
        self.assertEqual(needs['follow_up_question'],'How long has this been happening?')
        result=match_care(needs,'ZONE-04',self.hospitals,self.now)
        self.assertEqual(result['suggested_hospital_id'],'HOSP-02')
        self.assertIn('general-assessment',result['explanation'])
        self.assertIn('does not establish a diagnosis',result['explanation'])
    def test_unrelated_input_is_not_recommended(self):
        response=dict(is_health_concern=False,unmatched_requested_service=None,symptom_tags=[],requested_specialty=None,requested_resources=[],emergency=False,clarification=None)
        with patch.object(groq,'structured',return_value=response):
            needs=interpret('What is the weather today?',[],True)
        self.assertEqual(match_care(needs,'ZONE-04',self.hospitals,self.now)['outcome'],'clarification_required')
    def test_unavailable_explicit_specialist_is_not_invented(self):
        response=dict(is_health_concern=True,unmatched_requested_service='neurologist',symptom_tags=['general_concern'],requested_specialty=None,requested_resources=[],emergency=False,clarification=None)
        with patch.object(groq,'structured',return_value=response):
            needs=interpret('I was asked to see a neurologist',[],True)
        result=match_care(needs,'ZONE-04',self.hospitals,self.now)
        self.assertIsNone(result['suggested_hospital_id'])
        self.assertIn('neurologist',result['explanation'])
    def test_broad_local_concerns_during_outage(self):
        for message in ['I have a headache','My shoulder hurts','I need a medical checkup','I have a sore throat']:
            with patch.object(groq,'structured',side_effect=groq.ProviderUnavailable('offline')):
                needs=interpret(message,[],True)
            self.assertIn('general_concern',needs['symptom_tags'])
            self.assertEqual(match_care(needs,'ZONE-04',self.hospitals,self.now)['outcome'],'recommended')
