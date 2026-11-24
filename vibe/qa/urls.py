from django.urls import path

from . import views

app_name = "qa"

urlpatterns = [
    path("", views.SubjectListView.as_view(), name="subject_list"),
    path(
        "subjects/<slug:slug>/",
        views.SubjectDetailView.as_view(),
        name="subject_detail",
    ),
    path(
        "questions/new/",
        views.QuestionCreateView.as_view(),
        name="question_create",
    ),
    path(
        "questions/<int:pk>/",
        views.QuestionDetailView.as_view(),
        name="question_detail",
    ),
    path(
        "questions/<int:pk>/edit/",
        views.QuestionUpdateView.as_view(),
        name="question_update",
    ),
    path(
        "questions/<int:pk>/delete/",
        views.QuestionDeleteView.as_view(),
        name="question_delete",
    ),
    path(
        "questions/<int:pk>/answers/new/",
        views.AnswerCreateView.as_view(),
        name="answer_create",
    ),
    path(
        "answers/<int:pk>/edit/",
        views.AnswerUpdateView.as_view(),
        name="answer_update",
    ),
    path(
        "answers/<int:pk>/delete/",
        views.AnswerDeleteView.as_view(),
        name="answer_delete",
    ),
    path(
        "answers/<int:pk>/vote/",
        views.answer_vote,
        name="answer_vote",
    ),
    path(
        "attachments/<int:pk>/delete/",
        views.attachment_delete,
        name="attachment_delete",
    ),
]
