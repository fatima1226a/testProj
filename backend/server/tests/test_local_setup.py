from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import SimpleTestCase
from server import setup_local
from server import docs


class LocalSetupTests(SimpleTestCase):
    def test_swagger_files_are_published_after_all_downloads_complete(self):
        with TemporaryDirectory() as directory, patch.object(setup_local, 'urlopen', side_effect=lambda *a, **kw: BytesIO(b'official-file')):
            destination = Path(directory)
            setup_local.download_swagger(destination)
            self.assertEqual({f.name for f in destination.iterdir()}, {'swagger-ui-bundle.js','swagger-ui.css','LICENSE','NOTICE'})

    def test_failed_download_preserves_previous_files(self):
        with TemporaryDirectory() as directory, patch.object(setup_local, 'urlopen', side_effect=[BytesIO(b'new-bundle'), OSError('offline')]):
            destination = Path(directory)
            (destination / 'swagger-ui-bundle.js').write_bytes(b'old-bundle')
            with self.assertRaises(OSError):
                setup_local.download_swagger(destination)
            self.assertEqual((destination / 'swagger-ui-bundle.js').read_bytes(), b'old-bundle')
            self.assertEqual(len(list(destination.iterdir())), 1)

    def test_html_error_page_is_not_saved_as_javascript(self):
        with TemporaryDirectory() as directory, patch.object(setup_local, 'urlopen', return_value=BytesIO(b'<!doctype html>failure')):
            with self.assertRaises(ValueError):
                setup_local.download_swagger(Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_installed_swagger_uses_same_origin_assets_without_cdn(self):
        with TemporaryDirectory() as directory, patch.object(docs, 'VENDOR_DIR', Path(directory)):
            for filename in ('swagger-ui-bundle.js', 'swagger-ui.css'):
                (Path(directory) / filename).write_bytes(b'local-asset')
            page = self.client.get('/swagger/')
            self.assertContains(page, 'data-swagger-js-url="/api/docs/assets/swagger-ui-bundle.js"')
            self.assertNotContains(page, 'unpkg.com')
            asset = self.client.get('/api/docs/assets/swagger-ui-bundle.js')
            self.assertEqual(b''.join(asset.streaming_content), b'local-asset')
            asset.close()

    def test_missing_swagger_asset_returns_404_instead_of_500(self):
        with TemporaryDirectory() as directory, patch.object(docs, 'VENDOR_DIR', Path(directory)):
            self.assertEqual(self.client.get('/api/docs/assets/swagger-ui.css').status_code, 404)
