from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from rest_framework import serializers

from .models import Category, Comment, Genre, Review, Title

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name',
                  'username', 'bio', 'role', 'email')

    def validate_username(self, value):
        if value == 'me':
            raise serializers.ValidationError("This user already exist")
        return value

    def validate_role(self, value):
        user = self.context['request'].user
        if not user.is_admin:
            return user.role
        return value


class AuthSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, write_only=True)
    confirmation_code = serializers.CharField(
        required=True, max_length=36, write_only=True
    )


class CustomSlugRelatedField(serializers.SlugRelatedField):
    def __init__(self, slug_field=None, serializer_for_object=None, **kwargs):
        super().__init__(slug_field, **kwargs)
        self.serializer_for_object = serializer_for_object

    def to_representation(self, obj):
        serializer = self.serializer_for_object(instance=obj)
        return serializer.to_representation(obj)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('name', 'slug')


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ('name', 'slug')


class TitleSerializer(serializers.ModelSerializer):
    category = CustomSlugRelatedField(
        slug_field='slug',
        serializer_for_object=CategorySerializer,
        queryset=Category.objects.all(),
    )
    genre = CustomSlugRelatedField(
        slug_field='slug',
        serializer_for_object=GenreSerializer,
        queryset=Genre.objects.all(),
        many=True
    )
    rating = serializers.IntegerField(required=False)

    class Meta:
        model = Title
        fields = '__all__'
        read_only_fields = ('rating',)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True,
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model = Comment
        fields = ('id', 'text', 'author', 'pub_date')


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True,
        default=serializers.CurrentUserDefault()
    )
    score = serializers.IntegerField(min_value=1, max_value=10)

    class Meta:
        model = Review
        fields = ('id', 'text', 'author', 'score', 'pub_date')

    def validate(self, attrs):
        if self.context['request'].method != 'POST':
            return attrs
        author = self.context['request'].user
        title_id = self.context['view'].kwargs['title_id']

        title = get_object_or_404(Title, pk=title_id)
        if Review.objects.filter(title=title, author=author).exists():
            mes = (f'Review from author {author.username}'
                   f'on title {title.name} already exists')
            raise serializers.ValidationError(mes)
        return attrs
