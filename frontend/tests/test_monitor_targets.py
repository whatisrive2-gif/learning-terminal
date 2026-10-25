import tempfile
import unittest
from pathlib import Path
import json
from hub.workspace import monitor_targets

class MonitorTargetsTests(unittest.TestCase):
    def test_allowlisted_display_fields_only(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'artifacts') as folder:
            root=Path(folder);state=root/'course'/'.learning-terminal';(state/'tools').mkdir(parents=True)
            (state/'tools'/'homework_crawler.py').write_text("ORIGIN='https://example.test'\nTOKEN='public-share'\nraise RuntimeError('must never execute')",encoding='utf-8')
            (root/'协议').mkdir()
            (root/'协议'/'config.json').write_text(json.dumps({'token':'secret-auth','homework':{'downloadDir':'downloads','password':'secret-password'},'tools':{'dirwatch':{'watchDir':'watch'}}}),encoding='utf-8')
            result=monitor_targets(state)
            self.assertEqual(result['homework-crawler']['target'],'https://example.test/d/public-share/')
            self.assertEqual(result['dirwatch']['target'],'watch')
            self.assertNotIn('secret',json.dumps(result))
            self.assertEqual(monitor_targets(root/'missing'),{})
