"""Simple routing system for ASGI."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

from .request import Request


class Route:
    """A single route definition."""

    def __init__(
        self,
        path: str,
        handler: Callable,
        methods: List[str] | None = None,
        name: str | None = None,
    ):
        self.path = path
        self.handler = handler
        self.methods = set(methods or ["GET"])
        self.name = name
        
        # Convert path to regex pattern
        self.pattern, self.param_names = self._path_to_pattern(path)

    def _path_to_pattern(self, path: str) -> Tuple[Pattern[str], List[str]]:
        """Convert a path with parameters to a regex pattern."""
        param_names = []
        pattern_parts = []
        
        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                # Parameter
                param_name = part[1:-1]
                param_names.append(param_name)
                pattern_parts.append(r"([^/]+)")
            else:
                # Literal
                pattern_parts.append(re.escape(part))
        
        pattern = "^" + "/".join(pattern_parts) + "$"
        return re.compile(pattern), param_names

    def match(self, path: str, method: str) -> Dict[str, str] | None:
        """Check if this route matches the given path and method."""
        if method not in self.methods:
            return None
        
        match = self.pattern.match(path)
        if not match:
            return None
        
        # Extract parameters
        params = {}
        for i, name in enumerate(self.param_names):
            params[name] = match.group(i + 1)
        
        return params


class Router:
    """Simple router for mapping paths to handlers."""

    def __init__(self):
        self._routes: List[Route] = []
        self._name_to_route: Dict[str, Route] = {}

    def add_route(
        self,
        path: str,
        handler: Callable,
        methods: List[str] | None = None,
        name: str | None = None,
    ) -> None:
        """Add a route to the router."""
        route = Route(path, handler, methods, name)
        self._routes.append(route)
        
        if name:
            self._name_to_route[name] = route

    async def resolve(self, request: Request) -> Callable | None:
        """Resolve a request to a handler."""
        for route in self._routes:
            params = route.match(request.path, request.method)
            if params is not None:
                # Store route params on request
                request.route_params = params  # type: ignore
                return route.handler
        
        return None

    def url_for(self, name: str, **params: Any) -> str:
        """Generate a URL for a named route."""
        route = self._name_to_route.get(name)
        if not route:
            raise ValueError(f"No route named {name}")
        
        path = route.path
        for param_name, param_value in params.items():
            path = path.replace(f"{{{param_name}}}", str(param_value))
        
        return path

    # Decorator methods
    def route(self, path: str, methods: List[str] | None = None, name: str | None = None):
        """Decorator to register a route."""
        def decorator(handler: Callable) -> Callable:
            self.add_route(path, handler, methods, name)
            return handler
        return decorator

    def get(self, path: str, name: str | None = None):
        """Register a GET route."""
        return self.route(path, ["GET"], name)

    def post(self, path: str, name: str | None = None):
        """Register a POST route."""
        return self.route(path, ["POST"], name)

    def put(self, path: str, name: str | None = None):
        """Register a PUT route."""
        return self.route(path, ["PUT"], name)

    def delete(self, path: str, name: str | None = None):
        """Register a DELETE route."""
        return self.route(path, ["DELETE"], name)

    def patch(self, path: str, name: str | None = None):
        """Register a PATCH route."""
        return self.route(path, ["PATCH"], name)