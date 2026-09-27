import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


COMMON = Path(__file__).resolve().parents[2] / "fuzzers/_shared/common.sh"


class VerifiedDownloadTests(unittest.TestCase):
    def download(self, source, destination, digest):
        return subprocess.run(
            [
                "bash", "-c",
                'source "$1"; download_verified "$2" "$3" "$4"',
                "bash", str(COMMON), source.as_uri(), str(destination), digest,
            ],
            capture_output=True,
            text=True,
        )

    def test_accepts_matching_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "download"
            source.write_bytes(b"verified release")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            result = self.download(source, destination, digest)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_rejects_modified_download(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_bytes(b"modified release")
            digest = hashlib.sha256(b"verified release").hexdigest()
            result = self.download(source, Path(directory) / "download", digest)
            self.assertNotEqual(result.returncode, 0)

    def test_rejects_missing_or_invalid_digest_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_bytes(b"unverified release")
            destination = Path(directory) / "download"
            for digest in ["", "not-a-digest", "0" * 63, "0" * 64 + "\n"]:
                with self.subTest(digest=digest):
                    result = self.download(source, destination, digest)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(destination.exists())
