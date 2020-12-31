import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Avg
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from rest_framework_simplejwt.tokens import RefreshToken

from .filters import TitleFilter
from .models import Category, Genre, Review, Title
from .permissions import (IsAdmin, IsAdminOrReadOnly,
                          IsAuthorOrAdminOrModeratorOrReadOnly)
from .serializers import (AuthSerializer,
                          CategorySerializer, CommentSerializer,
                          GenreSerializer, ReviewSerializer, TitleSerializer,
                          UserSerializer)

User = get_user_model()


class CreateListDestroyViewSet(mixins.CreateModelMixin,
                               mixins.ListModelMixin,
                               mixins.DestroyModelMixin,
                               viewsets.GenericViewSet):
    pass


class UserAuthView(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(url_path='email', methods=['post'], detail=False)
    def user_auth_view(self, request):
        email = request.data.get('email', None)
        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"message": "Поле 'email' отсутствует либо некорректно"},
                status=status.HTTP_400_BAD_REQUEST
            )
        user, created = User.objects.get_or_create(
            email=email, username=email
        )
        confirmation_code = uuid.uuid4()
        user.confirmation_code = confirmation_code
        user.confirmation_code_active = True
        user.save()
        user.email_user(
            subject='Registration',
            message=f'Your confirmation_code: {confirmation_code}',
        )
        return Response(
            {"message": "На ваш email направлен код подтверждения"},
            status=status.HTTP_200_OK
        )

    @action(url_path='token', methods=['post'], detail=False)
    def user_token_view(self, request):
        serializer = AuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        email = data.get('email', None)
        confirmation_code = data.get('confirmation_code', None)

        message_incorrect = "Введенный email или confirmation_code не корректен"
        message_unactive = ("Ваш код недействителен. Вы можете "
                            "получить новый код по адресу: '/auth/email/'")
        try:
            user = User.objects.get(email=email)
            if user.confirmation_code != confirmation_code:
                raise ValueError()
        except (User.DoesNotExist, ValueError):
            return Response({"message": message_incorrect},
                            status=status.HTTP_400_BAD_REQUEST)
        if not user.confirmation_code_active:
            return Response({"message": message_unactive},
                            status=status.HTTP_400_BAD_REQUEST)
        user.confirmation_code_active = False
        user.save()
        refresh = RefreshToken.for_user(user)
        return Response({"token": str(refresh.access_token)},
                        status=status.HTTP_200_OK)


class UsersViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    lookup_field = 'username'
    serializer_class = UserSerializer
    filter_backends = [SearchFilter]
    search_fields = ['username']
    pagination_class = PageNumberPagination
    permission_classes = [IsAdmin]

    @action(url_path='me', methods=['get', 'patch'], detail=False,
            permission_classes=[permissions.IsAuthenticated])
    def retrieve_update_user(self, request):
        self.kwargs['username'] = request.user.username
        if request.method == 'GET':
            return self.retrieve(request)
        if request.method == 'PATCH':
            return self.update(request, partial=True)


class CategoryViewSet(CreateListDestroyViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    lookup_field = 'slug'
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name']


class GenreViewSet(CreateListDestroyViewSet):
    serializer_class = GenreSerializer
    queryset = Genre.objects.all()
    lookup_field = 'slug'
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name']


class TitleViewSet(viewsets.ModelViewSet):
    serializer_class = TitleSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsAdminOrReadOnly]
    queryset = Title.objects.annotate(rating=Avg('reviews__score'))
    filter_backends = [DjangoFilterBackend]
    filterset_class = TitleFilter


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsAuthorOrAdminOrModeratorOrReadOnly]

    def perform_create(self, serializer):
        title = get_object_or_404(Title, pk=self.kwargs.get('title_id'))
        serializer.save(author=self.request.user, title=title)

    def get_queryset(self):
        title = get_object_or_404(Title, pk=self.kwargs.get('title_id'))
        return title.reviews.all()


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']
    permission_classes = [IsAuthorOrAdminOrModeratorOrReadOnly]

    def get_review(self):
        title_id = self.kwargs.get('title_id')
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, pk=review_id, title__pk=title_id)
        return review

    def perform_create(self, serializer):
        review = self.get_review()
        serializer.save(author=self.request.user, review=review)

    def get_queryset(self):
        review = self.get_review()
        return review.comments.all()
