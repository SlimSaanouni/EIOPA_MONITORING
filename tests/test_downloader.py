from unittest.mock import MagicMock

from eiopa_rfr.downloader import EIOPADownloader


def _fake_response(content: bytes = b"nouveau-contenu"):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.headers.get.return_value = "0"
    response.iter_content.return_value = [content]
    return response


class TestDownloadFile:
    def test_skips_existing_file_by_default(self, tmp_path):
        output_path = tmp_path / "EIOPA_RFR_20241231.zip"
        output_path.write_bytes(b"ancien-contenu")

        downloader = EIOPADownloader()
        downloader.session.get = MagicMock(side_effect=AssertionError("ne doit pas être appelé"))

        result = downloader.download_file("https://example.org/x.zip", output_path.name, output_dir=tmp_path)

        assert result == output_path
        assert output_path.read_bytes() == b"ancien-contenu"
        downloader.session.get.assert_not_called()

    def test_force_redownloads_existing_file(self, tmp_path):
        output_path = tmp_path / "EIOPA_RFR_20241231.zip"
        output_path.write_bytes(b"ancien-contenu")

        downloader = EIOPADownloader()
        downloader.session.get = MagicMock(return_value=_fake_response(b"nouveau-contenu"))

        result = downloader.download_file(
            "https://example.org/x.zip", output_path.name, output_dir=tmp_path, force=True
        )

        assert result == output_path
        assert output_path.read_bytes() == b"nouveau-contenu"
        downloader.session.get.assert_called_once()
