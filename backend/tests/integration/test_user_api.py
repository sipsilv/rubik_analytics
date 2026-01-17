def test_update_user_me(client, user_token):
    # Update Theme
    response = client.put(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"theme_preference": "light"}
    )
    assert response.status_code == 200
    assert response.json()["theme_preference"] == "light"

    # Verify Persistence
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.json()["theme_preference"] == "light"

# TODO add admin user management tests in test_admin_api
