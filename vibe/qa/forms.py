import os

from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator

from .models import Answer, Attachment, Question
from .validators import (
    ALLOWED_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    validate_file_size,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            items = data
        elif data:
            items = [data]
        else:
            items = []
        return [single_file_clean(item, initial) for item in items]


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("subject", "title", "body")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-input")


class AnswerForm(forms.ModelForm):
    files = MultipleFileField(
        label="Фото и документы",
        required=False,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS),
            validate_file_size,
        ],
        help_text=(
            "Можно прикрепить несколько файлов. "
            f"Не более {settings.MAX_FILES_PER_ANSWER} файлов на ответ. "
            f"Фото: {', '.join(IMAGE_EXTENSIONS)}. "
            f"Документы: {', '.join(DOCUMENT_EXTENSIONS)}. "
            f"Размер каждого файла — до "
            f"{settings.MAX_UPLOAD_SIZE_MB} МБ."
        ),
    )

    class Meta:
        model = Answer
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Напишите ответ по существу вопроса…",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs.setdefault("class", "form-input")

    def clean(self):
        cleaned_data = super().clean()
        files = cleaned_data.get("files") or []
        max_files = settings.MAX_FILES_PER_ANSWER
        existing = (
            self.instance.attachments.count() if self.instance.pk else 0
        )
        if existing + len(files) > max_files:
            self.add_error(
                "files",
                f"К ответу можно прикрепить не более {max_files} файлов. "
                f"Уже прикреплено: {existing}, выбрано: {len(files)}.",
            )
        return cleaned_data

    def save_attachments(self, answer):
        attachments = []
        for uploaded_file in self.cleaned_data.get("files", []):
            original_name = os.path.basename(uploaded_file.name)[:255]
            attachments.append(
                Attachment.objects.create(
                    answer=answer,
                    file=uploaded_file,
                    original_name=original_name,
                )
            )
        return attachments
