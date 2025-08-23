from rest_framework.permissions import BasePermission

class ScopePermission(BasePermission):
    """
    Check token claim 'scope' against request path.
    - /api/admin/ -> scope must be 'admin'
    - /api/user/  -> scope must be 'user'
    - /api/       -> scope must be 'user' or 'admin'
    """

    def has_permission(self, request, view):
        # if no token available, let normal auth/IsAuthenticated handle it
        token = getattr(request, 'auth', None)
        if token is None:
            return False

        # token behaves like a mapping for claims
        scope = token.get('scope') if hasattr(token, 'get') else None
        path = (request.path or '').lower()

        if path.startswith('/api/admin/'):
            return scope == 'admin'
        elif path.startswith('/api/user/'):
            return scope == 'user'
        elif path.startswith('/api/'):
            return scope in ('user', 'admin')
        # not an API route we care about -> deny here so other auth flows can't bypass
        return False
