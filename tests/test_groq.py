import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from src.hex import groq, config

class GroqTransportTests(unittest.TestCase):
    def setUp(self):
        self.saved=list(groq._calls);groq._calls.clear()
    def tearDown(self):
        groq._calls[:]=self.saved
    def test_valid_response_and_bounded_private_request(self):
        output={'status':'ok'}
        raw=json.dumps(dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(output)))])).encode()
        fake=io.BytesIO(raw)
        with patch.object(groq,'provider_config',return_value=('test-credential','test-model')),patch.object(groq,'urlopen',return_value=fake) as call:
            actual=groq.structured('Return status.',{}, {'status':{'type':'string'}})
        self.assertEqual(actual,output)
        request=call.call_args.args[0]
        payload=json.loads(request.data)
        self.assertEqual(request.full_url,'https://api.groq.com/openai/v1/chat/completions')
        self.assertNotIn('input',payload)
        self.assertEqual(len(payload['messages']),2)
        self.assertEqual(payload['max_completion_tokens'],1000)
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertEqual(call.call_args.kwargs['timeout'],12)
    def test_sanitized_failure_and_schema_errors(self):
        failure=HTTPError('https://api.groq.com/openai/v1/chat/completions',403,'contains-private-content',{},io.BytesIO(b'contains-private-content'))
        with patch.object(groq,'provider_config',return_value=('test-credential','test-model')),patch.object(groq,'urlopen',side_effect=failure):
            with self.assertRaises(groq.ProviderUnavailable) as caught:
                groq.structured('task',{}, {'status':{'type':'string'}})
        self.assertNotIn('test-credential',str(caught.exception))
        self.assertNotIn('contains-private-content',str(caught.exception))
        self.assertIn('403',str(caught.exception))
        with patch.object(groq,'provider_config',return_value=('test-credential','test-model')),patch.object(groq,'urlopen',return_value=io.BytesIO(b'{"status":"incomplete"}')):
            with self.assertRaises(groq.ProviderUnavailable):groq.structured('task',{}, {'status':{'type':'string'}})
    def test_missing_key_never_calls_network(self):
        with patch.object(groq,'provider_config',return_value=('','test-model')),patch.object(groq,'urlopen') as call:
            with self.assertRaises(groq.ProviderUnavailable):groq.structured('task',{}, {'status':{'type':'string'}})
            call.assert_not_called()

class GroqConfigTests(unittest.TestCase):
    def test_uses_groq_key_and_default_model(self):
        with patch.object(config, 'load_env'), patch.dict(config.os.environ, {'GROQ_API_KEY':'test-groq', 'XAI_API_KEY':'obsolete-key'}, clear=True):
            self.assertEqual(config.provider_config(), ('test-groq', 'openai/gpt-oss-20b'))
    def test_old_xai_key_is_never_used(self):
        with patch.object(config, 'load_env'), patch.dict(config.os.environ, {'XAI_API_KEY':'obsolete-key'}, clear=True):
            self.assertEqual(config.provider_config()[0], '')
