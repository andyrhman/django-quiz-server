def scope_from_path(path: str):
    path = (path or '').lower()
    if path.startswith('/api/admin/'):
        return 'admin'
    if path.startswith('/api/user/'):
        return 'user'
    return None
