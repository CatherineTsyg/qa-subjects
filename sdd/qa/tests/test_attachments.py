import io
import zipfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Attachment, Question, Subject
from qa.validators import validate_attachment


def jpeg_bytes():
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32


def png_bytes():
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def webp_bytes():
    return b"RIFF" + (36).to_bytes(4, "little") + b"WEBP" + b"\x00" * 32


def pdf_bytes():
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"


def doc_bytes():
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32


def docx_bytes(with_content_types=True):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if with_content_types:
            archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


def txt_bytes():
    return "Простой текст".encode("utf-8")


def upload(name, content):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class ValidatorTests(CacheMediaTestCase):
    def test_mime_table_is_applied(self):
        cases = [
            ("photo.jpg", jpeg_bytes(), "image/jpeg"),
            ("photo.jpeg", jpeg_bytes(), "image/jpeg"),
            ("image.png", png_bytes(), "image/png"),
            ("image.webp", webp_bytes(), "image/webp"),
            ("document.pdf", pdf_bytes(), "application/pdf"),
            ("notes.txt", txt_bytes(), "text/plain"),
            ("legacy.doc", doc_bytes(), "application/msword"),
            (
                "modern.docx",
                docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ]

        for name, content, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(validate_attachment(upload(name, content)), expected)

    def test_invalid_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_attachment(upload("virus.exe", b"MZ" + b"\x00" * 32))

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_attachment(upload("empty.txt", b""))

    def test_mismatched_content_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_attachment(upload("fake.png", b"not a png"))

    def test_txt_with_null_bytes_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_attachment(upload("bad.txt", b"hello\x00world"))

    def test_docx_must_be_zip_with_content_types(self):
        with self.assertRaises(ValidationError):
            validate_attachment(
                upload("bad.docx", docx_bytes(with_content_types=False))
            )

    def test_image_size_limit(self):
        content = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_attachment(upload("big.jpg", content))

    def test_document_size_limit(self):
        content = b"%PDF-" + b"\x00" * (10 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_attachment(upload("big.pdf", content))


class AttachmentViewTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )
        self.other = User.objects.create_user(
            "other", password="StrongPass123!"
        )
        self.subject = Subject.objects.create(name="Математика")
        self.question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )
        self.answer = Answer.objects.create(
            question=self.question, author=self.author, body="Ответ"
        )

    def test_author_can_attach_allowed_file(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": upload("photo.png", png_bytes())},
        )

        self.assertRedirects(
            response, reverse("question_detail", args=[self.question.pk])
        )
        attachment = Attachment.objects.get(answer=self.answer)
        self.assertEqual(attachment.original_name, "photo.png")
        self.assertEqual(attachment.content_type, "image/png")
        self.assertTrue(attachment.file.storage.exists(attachment.file.name))

    def test_other_user_cannot_attach_file(self):
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": upload("photo.png", png_bytes())},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_staff_cannot_attach_file_to_foreign_answer(self):
        staff = User.objects.create_user(
            "staff", password="StrongPass123!", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": upload("photo.png", png_bytes())},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_invalid_files_are_not_saved(self):
        self.client.force_login(self.author)

        cases = [
            ("virus.exe", b"MZ" + b"\x00" * 10),
            ("empty.txt", b""),
            ("fake.png", b"not a png"),
        ]
        for name, content in cases:
            with self.subTest(name=name):
                response = self.client.post(
                    reverse("attachment_create", args=[self.answer.pk]),
                    {"file": upload(name, content)},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Attachment.objects.count(), 0)

    def test_oversized_image_is_rejected(self):
        self.client.force_login(self.author)
        content = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024)

        response = self.client.post(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": upload("big.jpg", content)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_sixth_attachment_is_rejected(self):
        for index in range(5):
            Attachment.objects.create(
                answer=self.answer,
                file=upload(f"note{index}.txt", txt_bytes()),
                original_name=f"note{index}.txt",
                content_type="text/plain",
                size=len(txt_bytes()),
            )
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": upload("extra.txt", txt_bytes())},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не более 5")
        self.assertEqual(Attachment.objects.count(), 5)

    def test_download_uses_stored_content_type_and_disposition(self):
        image = Attachment.objects.create(
            answer=self.answer,
            file=upload("photo.png", png_bytes()),
            original_name="photo.png",
            content_type="image/png",
            size=len(png_bytes()),
        )
        document = Attachment.objects.create(
            answer=self.answer,
            file=upload("document.pdf", pdf_bytes()),
            original_name="document.pdf",
            content_type="application/pdf",
            size=len(pdf_bytes()),
        )

        image_response = self.client.get(
            reverse("attachment_download", args=[image.pk])
        )
        document_response = self.client.get(
            reverse("attachment_download", args=[document.pk])
        )

        self.assertEqual(image_response["Content-Type"], "image/png")
        self.assertIn("inline", image_response["Content-Disposition"])
        self.assertEqual(
            document_response["Content-Type"], "application/pdf"
        )
        self.assertIn("attachment", document_response["Content-Disposition"])

    def test_download_of_missing_attachment_returns_404(self):
        self.assertEqual(
            self.client.get(
                reverse("attachment_download", args=[999])
            ).status_code,
            404,
        )

    def test_author_and_staff_can_delete_attachment(self):
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=upload("note.txt", txt_bytes()),
            original_name="note.txt",
            content_type="text/plain",
            size=len(txt_bytes()),
        )
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("attachment_delete", args=[attachment.pk])
        )

        self.assertRedirects(
            response, reverse("question_detail", args=[self.question.pk])
        )
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())
