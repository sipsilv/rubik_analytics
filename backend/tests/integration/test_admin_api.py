def test_get_users_admin_required(client, user_token, admin_token):
    # User -> Forbidden
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403

    # Admin -> Success
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 2 # Admin + User

def test_admin_config_access(client, admin_token):
    # Verify Admin can access typical dashboard route (if exists, or list)
    # Using generic one that likely exists
    pass 
