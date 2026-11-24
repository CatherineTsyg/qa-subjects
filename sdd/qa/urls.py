from django.urls import path

from . import views

urlpatterns = [
    path("", views.subject_list, name="subject_list"),
    path("healthz/", views.healthz, name="healthz"),
    path("subjects/<int:pk>/", views.subject_detail, name="subject_detail"),
    path(
        "subjects/<int:pk>/questions/new/",
        views.question_create,
        name="question_create",
    ),
    path(
        "questions/<int:pk>/",
        views.question_detail,
        name="question_detail",
    ),
    path(
        "questions/<int:pk>/edit/",
        views.question_edit,
        name="question_edit",
    ),
    path(
        "questions/<int:pk>/delete/",
        views.question_delete,
        name="question_delete",
    ),
    path(
        "questions/<int:pk>/answers/new/",
        views.answer_create,
        name="answer_create",
    ),
    path("answers/<int:pk>/edit/", views.answer_edit, name="answer_edit"),
    path(
        "answers/<int:pk>/delete/",
        views.answer_delete,
        name="answer_delete",
    ),
    path("answers/<int:pk>/vote/", views.answer_vote, name="answer_vote"),
    path(
        "answers/<int:pk>/attachments/new/",
        views.attachment_create,
        name="attachment_create",
    ),
    path(
        "attachments/<int:pk>/download/",
        views.attachment_download,
        name="attachment_download",
    ),
    path(
        "attachments/<int:pk>/delete/",
        views.attachment_delete,
        name="attachment_delete",
    ),
]
