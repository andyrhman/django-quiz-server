from rest_framework import serializers

from core.models import User

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'fullName', 'email', 'username', 'password', 'is_user', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }    
          
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        
        # Convert email and username to lowercase
        email = validated_data.get('email', '').lower()
        username = validated_data.get('username', '').lower()
        
        # Update the dictionary with lowercase values
        validated_data['email'] = email
        validated_data['username'] = username

        instance = self.Meta.model(**validated_data)
        
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("fullName", "email", "username", "password", "confirm_password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        # Emit signal here if you prefer
        # user_registered.send(sender=self.__class__, user=user)
        return user