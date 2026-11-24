from django import forms
from django.core.exceptions import ValidationError

from .models import Answer, Question
from .validators import validate_attachment


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["title", "body"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 200}),
            "body": forms.Textarea(attrs={"rows": 8}),
        }
        error_messages = {
            "title": {
                "required": "Введите заголовок вопроса.",
                "max_length": "Заголовок не должен превышать 200 символов.",
            },
            "body": {"required": "Введите текст вопроса."},
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise ValidationError("Введите заголовок вопроса.")
        return title

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise ValidationError("Введите текст вопроса.")
        return body


class AnswerForm(forms.ModelForm):
    body = forms.CharField(
        label="Текст ответа",
        max_length=10000,
        widget=forms.Textarea(attrs={"rows": 8}),
        error_messages={
            "required": "Введите текст ответа.",
            "max_length": "Ответ не должен превышать 10 000 символов.",
        },
    )

    class Meta:
        model = Answer
        fields = ["body"]

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise ValidationError("Введите текст ответа.")
        return body


class AttachmentForm(forms.Form):
    file = forms.FileField(label="Файл")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        try:
            self.content_type = validate_attachment(uploaded_file)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        return uploaded_file
