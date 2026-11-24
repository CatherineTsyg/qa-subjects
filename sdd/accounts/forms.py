from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Имя пользователя"
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Подтверждение пароля"
        self.fields["username"].error_messages["unique"] = (
            "Пользователь с таким именем уже существует."
        )
        self.fields["username"].error_messages["required"] = (
            "Введите имя пользователя."
        )
        self.fields["password1"].error_messages["required"] = "Введите пароль."
        self.fields["password2"].error_messages["required"] = (
            "Подтвердите пароль."
        )
        self.fields["password2"].error_messages["password_mismatch"] = (
            "Пароли не совпадают."
        )


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Имя пользователя")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Неверное имя пользователя или пароль.",
        "inactive": "Эта учётная запись отключена.",
    }
