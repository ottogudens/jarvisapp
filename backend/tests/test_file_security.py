import unittest

from fastapi import HTTPException

from backend.file_security import validate_upload


class FileSecurityTests(unittest.TestCase):
    def test_accepts_valid_pdf(self):
        self.assertEqual(
            validate_upload("informe.pdf", "application/pdf", b"%PDF-1.7\ncontenido"),
            "informe.pdf",
        )

    def test_rejects_pdf_without_signature(self):
        with self.assertRaises(HTTPException) as error:
            validate_upload("informe.pdf", "application/pdf", b"texto plano")
        self.assertEqual(error.exception.status_code, 400)

    def test_strips_path_from_filename(self):
        self.assertEqual(
            validate_upload("../../notas.txt", "text/plain", b"contenido"),
            "notas.txt",
        )

    def test_rejects_unknown_extension(self):
        with self.assertRaises(HTTPException):
            validate_upload("programa.exe", "application/octet-stream", b"MZ")


if __name__ == "__main__":
    unittest.main()
