import unittest
from src.hex.privacy.gate import redact_text, sanitize_case, sanitize_batch


class PrivacyGateTests(unittest.TestCase):
    def record(self, **changes):
        return dict(case_id='PATIENT-991', hospital_id='HOSP-01', zone_id='ZONE-03',
                    reported_at='2026-10-22T10:12:00Z', age=34,
                    symptoms='fever|cough', severity='mild', admitted='False', **changes)

    def test_allowlist_discards_identifiers_and_free_text(self):
        raw=self.record(patient_name='Alex Example',phone='202-555-0101',
                        notes='Unlabelled name Alex Example lives at 100 Example Street',
                        email='person@example.com',address='100 Example Street')
        safe=sanitize_case(raw)
        self.assertEqual(set(safe),{'case_id','hospital_id','zone_id','reported_at','age_band','symptoms','severity','admitted'})
        self.assertTrue(safe['case_id'].startswith('CASE-'))
        self.assertNotEqual(safe['case_id'],raw['case_id'])
        self.assertEqual(safe['age_band'],'30-39')
        self.assertEqual(safe['reported_at'],'2026-10-22T00:00:00+00:00')
        self.assertFalse(safe['admitted'])

    def test_redacts_common_text_patterns(self):
        value, counts=redact_text('Name: Alex Example; email person@example.com; Phone: +1 202-555-0101; MRN: ABC991; Address: 100 Example Street')
        for identifier in ('Alex Example','person@example.com','202-555-0101','ABC991','100 Example Street'):
            self.assertNotIn(identifier,value)
        self.assertTrue(counts)

    def test_pii_cannot_hide_in_symptom_field(self):
        raw=self.record()
        raw['symptoms']='fever|Alex Example|202-555-0101|person@example.com'
        self.assertEqual(sanitize_case(raw)['symptoms'],'fever')

    def test_rejects_identifying_location_and_unknown_hospital(self):
        raw=self.record();raw['zone_id']='100 Example Street'
        with self.assertRaises(ValueError):sanitize_case(raw)
        with self.assertRaises(ValueError):sanitize_case(self.record(),{'HOSP-02'},{'ZONE-03'})

    def test_batch_fails_before_storage(self):
        invalid=self.record();invalid['symptoms']='Alex Example'
        with self.assertRaises(ValueError):sanitize_batch([self.record(),invalid])

    def test_clean_records_remain_valid_on_repeat(self):
        safe=sanitize_case(self.record())
        self.assertEqual(sanitize_case(safe,preserve_case_id=True),safe)
        self.assertNotEqual(sanitize_case(safe)['case_id'],safe['case_id'])


if __name__=='__main__':unittest.main()
