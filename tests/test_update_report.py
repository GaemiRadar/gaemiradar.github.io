import sys
import json
import unittest
from unittest.mock import MagicMock, patch
from types import ModuleType, SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_report as update


def fake_news():
    return {
        cat: [{
            'id': f'{cat}-{i}', 'title': f'가상 테스트 {cat} {i}',
            'publisher': '테스트', 'published_at': '2026-11-09T00:00:00Z',
            'summary': '테스트 입력 (실제 투자정보 아님)'
        } for i in range(2)] for cat in update.TOPICS
    }


def report(title):
    return {'headline': title, 'overview': '검증된 자료만 분석',
            'analysis': {cat: {'direction': '중립', 'confidence': '높음', 'horizon': '1주',
                                'summary': '자료상 혼재', 'bull_cases': ['조건 A'],
                                'bear_cases': ['조건 B'], 'watch': ['관찰 항목'],
                                'citation_ids': [f'{cat}-0', 'stocks-1', 'fake-99']}
                         for cat in update.TOPICS}}


def mocked_sdk(outputs):
    client = MagicMock()
    client.models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(x, ensure_ascii=False)) if isinstance(x, dict) else x
        for x in outputs
    ]
    fake_genai = ModuleType('google.genai')
    fake_types = ModuleType('google.genai.types')
    fake_types.GenerateContentConfig = lambda **kwargs: kwargs
    fake_genai.Client = lambda **kwargs: client
    fake_genai.types = fake_types
    fake_google = ModuleType('google')
    fake_google.genai = fake_genai
    return {'google': fake_google, 'google.genai': fake_genai, 'google.genai.types': fake_types}, client


class DataContractTests(unittest.TestCase):
    def test_rss_parser(self):
        rss = b'''<?xml version="1.0"?><rss><channel><item><title>Test - Example News</title>
          <link>https://news.google.com/rss/articles/abc</link>
          <pubDate>Sat, 07 Nov 2026 00:00:00 GMT</pubDate><source>Example News</source>
          <description>&lt;p&gt;summary&lt;/p&gt;</description></item></channel></rss>'''
        arts = update.parse_rss(rss, 'stocks', cutoff=datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual('Test', arts[0]['title'])
        self.assertEqual('summary', arts[0]['summary'])

    def test_fred_parser(self):
        rows = update.read_fred_csv(b'observation_date,DGS10\n2026-11-03,4.00\n2026-11-04,.\n2026-11-05,4.15\n', 'DGS10')
        self.assertEqual(2, len(rows))

    def test_no_key_stays_not_configured(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            out = update.analyze(fake_news(), [], [])
        self.assertEqual('not_configured', out['status'])
        self.assertEqual('not_run', out['review_status'])

    def test_two_stage_success(self):
        modules, client = mocked_sdk([report('Flash 초안'), report('Pro 검토본')])
        with patch.dict(sys.modules, modules), patch.dict('os.environ',
                {'GEMINI_API_KEY': 'dummy', 'GEMINI_FLASH_MODEL': 'gemini-3.6-flash',
                 'GEMINI_REVIEW_MODEL': 'gemini-2.5-pro', 'ENABLE_PRO_REVIEW': '1'}):
            out = update.analyze(fake_news(), [], [])
        self.assertEqual('ok', out['status'])
        self.assertEqual('completed', out['review_status'])
        self.assertEqual('Pro 검토본', out['headline'])
        self.assertEqual('gemini-3.6-flash → gemini-2.5-pro', out['model'])
        self.assertEqual('보통', out['analysis']['stocks']['confidence'])
        self.assertEqual(['housing-0'], out['analysis']['housing']['citation_ids'])
        self.assertEqual(2, client.models.generate_content.call_count)
        client.close.assert_called_once()

    def test_pro_failure_keeps_flash_and_marks_failure(self):
        modules, client = mocked_sdk([report('Flash 초안'), RuntimeError('quota')])
        errors = []
        with patch.dict(sys.modules, modules), patch.dict('os.environ',
                {'GEMINI_API_KEY': 'dummy', 'GEMINI_FLASH_MODEL': 'gemini-3.6-flash',
                 'ENABLE_PRO_REVIEW': '1'}):
            out = update.analyze(fake_news(), [], errors)
        self.assertEqual('ok', out['status'])
        self.assertEqual('failed', out['review_status'])
        self.assertEqual('Flash 초안', out['headline'])
        self.assertTrue(any('Pro 재검토 실패' in error for error in errors))

    def test_flash_fallback_then_pro_review(self):
        modules, client = mocked_sdk([RuntimeError('model unavailable'), report('Flash 대체'), report('Pro')])
        with patch.dict(sys.modules, modules), patch.dict('os.environ',
                {'GEMINI_API_KEY': 'dummy', 'GEMINI_FLASH_MODEL': 'gemini-3.6-flash',
                 'GEMINI_FLASH_FALLBACK': 'gemini-2.5-flash', 'ENABLE_PRO_REVIEW': '1'}):
            out = update.analyze(fake_news(), [], [])
        self.assertEqual('completed', out['review_status'])
        self.assertEqual('gemini-2.5-flash', out['draft_model'])
        self.assertEqual(3, client.models.generate_content.call_count)

    def test_review_disabled_one_call(self):
        modules, client = mocked_sdk([report('Flash 전용')])
        with patch.dict(sys.modules, modules), patch.dict('os.environ',
                {'GEMINI_API_KEY': 'dummy', 'ENABLE_PRO_REVIEW': '0'}):
            out = update.analyze(fake_news(), [], [])
        self.assertEqual('ok', out['status'])
        self.assertEqual('not_run', out['review_status'])
        self.assertEqual(1, client.models.generate_content.call_count)

    def test_all_flash_fail(self):
        modules, client = mocked_sdk([RuntimeError('fail'), RuntimeError('fail')])
        with patch.dict(sys.modules, modules), patch.dict('os.environ',
                {'GEMINI_API_KEY': 'dummy', 'GEMINI_FLASH_MODEL': 'gemini-3.6-flash',
                 'GEMINI_FLASH_FALLBACK': 'gemini-2.5-flash'}):
            out = update.analyze(fake_news(), [], [])
        self.assertEqual('error', out['status'])
        self.assertEqual('not_run', out['review_status'])
        self.assertEqual('판단 유보', out['analysis']['stocks']['direction'])

if __name__ == '__main__':
    unittest.main()
