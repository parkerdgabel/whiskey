"""Tests for RouteMetadata class."""


from whiskey_asgi.extension import RouteMetadata


class TestRouteMetadata:
    """Test RouteMetadata functionality."""

    def test_simple_route(self):
        """Test matching a simple route without parameters."""
        route = RouteMetadata(func=lambda: None, path="/hello", methods=["GET"], name="hello")

        # Should match exact path with correct method
        params = route.match("/hello", "GET")
        assert params == {}

        # Should not match different path
        assert route.match("/world", "GET") is None

        # Should not match wrong method
        assert route.match("/hello", "POST") is None

    def test_parameterized_route(self):
        """Test matching routes with parameters."""
        route = RouteMetadata(
            func=lambda: None, path="/users/{id}", methods=["GET", "POST"], name="user"
        )

        # Should extract parameter
        params = route.match("/users/123", "GET")
        assert params == {"id": "123"}

        params = route.match("/users/abc", "POST")
        assert params == {"id": "abc"}

        # Should not match without parameter
        assert route.match("/users/", "GET") is None
        assert route.match("/users", "GET") is None

    def test_multiple_parameters(self):
        """Test routes with multiple parameters."""
        route = RouteMetadata(
            func=lambda: None,
            path="/projects/{project_id}/tasks/{task_id}",
            methods=["GET"],
            name="task",
        )

        params = route.match("/projects/proj1/tasks/task1", "GET")
        assert params == {"project_id": "proj1", "task_id": "task1"}

        # Missing parameters
        assert route.match("/projects/proj1/tasks", "GET") is None
        assert route.match("/projects/proj1", "GET") is None

    def test_path_to_pattern(self):
        """Test path to regex pattern conversion."""
        route = RouteMetadata(
            func=lambda: None, path="/api/{version}/users/{id}", methods=["GET"], name="api_user"
        )

        # Check param names extraction
        assert route.param_names == ["version", "id"]

        # Test pattern matching
        params = route.match("/api/v1/users/42", "GET")
        assert params == {"version": "v1", "id": "42"}

        # Special characters in non-param parts should be escaped
        route2 = RouteMetadata(
            func=lambda: None, path="/api.v2/users/{id}", methods=["GET"], name="api_v2"
        )
        params = route2.match("/api.v2/users/42", "GET")
        assert params == {"id": "42"}
        assert route2.match("/apiv2/users/42", "GET") is None

    def test_root_path(self):
        """Test handling of root path."""
        route = RouteMetadata(func=lambda: None, path="/", methods=["GET"], name="root")

        assert route.match("/", "GET") == {}
        assert route.match("", "GET") is None
        assert route.match("/anything", "GET") is None

    def test_method_matching(self):
        """Test HTTP method matching."""
        route = RouteMetadata(
            func=lambda: None, path="/resource", methods=["GET", "POST", "PUT"], name="resource"
        )

        # Should match allowed methods
        assert route.match("/resource", "GET") == {}
        assert route.match("/resource", "POST") == {}
        assert route.match("/resource", "PUT") == {}

        # Should not match disallowed methods
        assert route.match("/resource", "DELETE") is None
        assert route.match("/resource", "PATCH") is None
        assert route.match("/resource", "HEAD") is None

    def test_parameter_values(self):
        """Test different parameter value formats."""
        route = RouteMetadata(func=lambda: None, path="/items/{id}", methods=["GET"], name="item")

        # Should handle various formats
        test_cases = [
            ("123", {"id": "123"}),
            ("abc-def", {"id": "abc-def"}),
            ("test_123", {"id": "test_123"}),
            ("item.json", {"id": "item.json"}),
            ("with%20space", {"id": "with%20space"}),  # URL encoded
        ]

        for value, expected in test_cases:
            params = route.match(f"/items/{value}", "GET")
            assert params == expected
