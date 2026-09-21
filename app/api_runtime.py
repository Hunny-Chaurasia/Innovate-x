import reflex as rx

import inspect
import json
import logging
import re
import secrets
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Annotated, get_args, get_origin, get_type_hints
from urllib.parse import parse_qs

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

Query = Field
MISSING = inspect.Parameter.empty


class HTTPException(Exception):
    def __init__(self, status_code, detail, headers=None):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}


class RequestValidationError(Exception):
    def __init__(self, errors):
        self.details = errors


@dataclass(frozen=True)
class Depends:
    dependency: object


@dataclass
class HTTPAuthorizationCredentials:
    scheme: str
    credentials: str


class HTTPBearer:
    def __init__(self, auto_error=False):
        self.auto_error = auto_error

    async def __call__(self, request):
        parts = request.headers.get("authorization", "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return HTTPAuthorizationCredentials(*parts)


class Request:
    def __init__(self, scope, receive):
        self.scope = scope
        self.receive = receive
        self.headers = {
            k.decode("latin1").lower(): v.decode("latin1")
            for k, v in scope.get("headers", [])
        }
        self.url = SimpleNamespace(path=scope.get("path", "/"))
        client = scope.get("client")
        self.client = (
            SimpleNamespace(host=client[0], port=client[1]) if client else None
        )
        self.state = SimpleNamespace(request_id=secrets.token_hex(12))
        self.query = parse_qs(
            scope.get("query_string", b"").decode("utf-8", errors="replace"),
            keep_blank_values=True,
        )
        self.maximum = (
            104857600 if self.url.path.endswith("/proofs/upload") else 1048576
        )
        self.consumed = False
        self.body_value = MISSING

    def check_length(self):
        raw = self.headers.get("content-length")
        if raw is not None:
            if not re.fullmatch(r"[0-9]+", raw):
                raise HTTPException(
                    400,
                    {
                        "code": "invalid_request",
                        "message": "Invalid content length",
                    },
                )
            if len(raw) > 12 or int(raw) > self.maximum:
                raise HTTPException(
                    413,
                    {
                        "code": "body_too_large",
                        "message": "Request body exceeds the supported size",
                    },
                )

    async def stream(self):
        if self.consumed:
            raise RuntimeError("Request stream already consumed")
        self.consumed = True
        size = 0
        while True:
            message = await self.receive()
            if message["type"] == "http.disconnect":
                raise HTTPException(
                    400,
                    {
                        "code": "client_disconnected",
                        "message": "Request body was interrupted",
                    },
                )
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.maximum:
                raise HTTPException(
                    413,
                    {
                        "code": "body_too_large",
                        "message": "Request body exceeds the supported size",
                    },
                )
            yield chunk
            if not message.get("more_body", False):
                break

    async def json(self):
        if self.body_value is MISSING:
            content_type = (
                self.headers.get("content-type", "application/json")
                .split(";")[0]
                .strip()
                .lower()
            )
            if content_type != "application/json" and not (
                content_type.startswith("application/")
                and content_type.endswith("+json")
            ):
                raise HTTPException(
                    415,
                    {
                        "code": "unsupported_media",
                        "message": "Use application/json for this endpoint",
                    },
                )
            chunks = bytearray()
            async for chunk in self.stream():
                chunks.extend(chunk)
            try:
                self.body_value = json.loads(chunks)
            except (ValueError, UnicodeError) as e:
                logging.exception(f"Error: {type(e).__name__}")
                raise RequestValidationError(
                    [
                        {
                            "path": ["body"],
                            "message": "Invalid JSON body",
                            "type": "json_invalid",
                        }
                    ]
                ) from e
        return self.body_value


def parameter_info(parameter, annotation):
    metadata = (
        get_args(annotation)[1:] if get_origin(annotation) is Annotated else ()
    )
    base = get_args(annotation)[0] if metadata else annotation
    dependency = next(
        (m.dependency for m in metadata if isinstance(m, Depends)), None
    )
    field = next((m for m in metadata if isinstance(m, FieldInfo)), None)
    default = parameter.default
    if isinstance(default, Depends):
        dependency = default.dependency
        default = MISSING
    if isinstance(default, FieldInfo):
        field = default
        default = MISSING if default.is_required() else default.default
    validation = Annotated[base, field] if field is not None else base
    return base, dependency, default, validation


def parameters(endpoint):
    target = endpoint if inspect.isfunction(endpoint) else endpoint.__call__
    hints = get_type_hints(target, include_extras=True)
    return [
        (name, parameter_info(p, hints.get(name, p.annotation)))
        for name, p in inspect.signature(target).parameters.items()
    ]


@dataclass
class Route:
    path: str
    method: str
    endpoint: object
    response_model: object
    status_code: int
    tags: list[str]

    def __post_init__(self):
        segments = self.path.split("/")
        self.pattern = re.compile(
            "/".join(
                f"(?P<{s[1:-1]}>[^/]+)" if s.startswith("{") else re.escape(s)
                for s in segments
            )
        )
        self.specificity = sum(not s.startswith("{") for s in segments)


class APIRouter:
    def __init__(self, prefix="", tags=None):
        self.prefix = prefix
        self.tags = tags or []
        self.routes = []

    def route(self, method, path, response_model=None, status_code=200):
        def register(endpoint):
            self.routes.append(
                Route(
                    f"{self.prefix}{path}",
                    method,
                    endpoint,
                    response_model,
                    status_code,
                    self.tags,
                )
            )
            return endpoint

        return register

    def get(self, path, **kwargs):
        return self.route("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.route("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.route("PUT", path, **kwargs)

    def patch(self, path, **kwargs):
        return self.route("PATCH", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.route("DELETE", path, **kwargs)


class Resolver:
    def __init__(self, app, request, path, stack):
        self.app, self.request, self.path, self.stack = (
            app,
            request,
            path,
            stack,
        )
        self.cache = {}

    async def resolve(self, endpoint):
        original = endpoint
        if original in self.cache:
            return self.cache[original]
        endpoint = self.app.dependency_overrides.get(original, original)
        values = {}
        dependencies = []
        errors = []
        for name, (base, dependency, default, validation) in parameters(
            endpoint
        ):
            if dependency is not None:
                dependencies.append((name, dependency))
                continue
            if base is Request or (
                isinstance(endpoint, HTTPBearer) and name == "request"
            ):
                values[name] = self.request
                continue
            is_body = inspect.isclass(base) and issubclass(base, BaseModel)
            location = (
                "body" if is_body else "path" if name in self.path else "query"
            )
            prefix = [location] if is_body else [location, name]
            if is_body:
                value = await self.request.json()
            elif name in self.path:
                value = self.path[name]
            elif name in self.request.query:
                value = self.request.query[name][-1]
            elif default is not MISSING:
                value = default
            else:
                errors.append(
                    {
                        "path": prefix,
                        "message": "Field required",
                        "type": "missing",
                    }
                )
                continue
            try:
                values[name] = TypeAdapter(validation).validate_python(value)
            except ValidationError as e:
                # Do not include submitted values or validator exception contexts.
                logging.exception("Unexpected error")
                errors.extend(
                    {
                        "path": [*prefix, *issue["loc"]],
                        "message": issue["msg"],
                        "type": issue["type"],
                    }
                    for issue in e.errors()
                )
        if errors:
            raise RequestValidationError(errors)
        for name, dependency in dependencies:
            values[name] = await self.resolve(dependency)
        if inspect.isasyncgenfunction(endpoint):
            value = await self.stack.enter_async_context(
                asynccontextmanager(endpoint)(**values)
            )
        else:
            value = endpoint(**values)
            if inspect.isawaitable(value):
                value = await value
        self.cache[original] = value
        return value


class API(APIRouter):
    """ASGI application and synchronous Reflex callable transformer."""

    def __init__(self, title, version, allow_origins):
        super().__init__()
        self.title, self.version = title, version
        self.allow_origins = frozenset(allow_origins)
        self.dependency_overrides = {}
        self.fallback = None

    def include_router(self, router):
        self.routes.extend(router.routes)
        self.routes.sort(key=lambda route: route.specificity, reverse=True)

    def __call__(self, scope, receive=None, send=None):
        if receive is None and send is None:
            # Reflex invokes callable transformers once with its original ASGI app.
            wrapped = API(self.title, self.version, self.allow_origins)
            wrapped.routes = self.routes
            wrapped.dependency_overrides = self.dependency_overrides
            wrapped.fallback = scope
            return wrapped
        return self.serve(scope, receive, send)

    def openapi(self):
        paths, schemas = {}, {}

        def schema_for(annotation):
            schema = TypeAdapter(annotation).json_schema(
                ref_template="#/components/schemas/{model}"
            )
            schemas.update(schema.pop("$defs", {}))
            return schema

        def describe(endpoint, path, seen):
            params, body, secured = [], None, False
            if endpoint in seen:
                return params, body, secured
            seen.add(endpoint)
            for name, (base, dependency, default, validation) in parameters(
                endpoint
            ):
                if dependency is not None:
                    if isinstance(dependency, HTTPBearer):
                        secured = True
                    else:
                        nested, nested_body, nested_secured = describe(
                            dependency, path, seen
                        )
                        params.extend(nested)
                        body = nested_body or body
                        secured = secured or nested_secured
                elif base is Request:
                    continue
                elif inspect.isclass(base) and issubclass(base, BaseModel):
                    body = {
                        "required": True,
                        "content": {
                            "application/json": {"schema": schema_for(base)}
                        },
                    }
                else:
                    location = "path" if f"{{{name}}}" in path else "query"
                    schema = schema_for(validation)
                    if default is not MISSING:
                        schema["default"] = default
                    params.append(
                        {
                            "name": name,
                            "in": location,
                            "required": location == "path"
                            or default is MISSING,
                            "schema": schema,
                        }
                    )
            return params, body, secured

        for route in self.routes:
            params, body, secured = describe(route.endpoint, route.path, set())
            operation = {
                "operationId": route.endpoint.__name__,
                "tags": route.tags,
                "parameters": params,
                "responses": {
                    str(route.status_code): {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": schema_for(route.response_model)
                            }
                        },
                    },
                    "422": {"description": "Request validation failed"},
                },
            }
            if route.path.endswith("/proofs/upload"):
                body = {
                    "required": True,
                    "content": {
                        mime: {"schema": {"type": "string", "format": "binary"}}
                        for mime in (
                            "image/jpeg",
                            "image/png",
                            "image/gif",
                            "image/webp",
                            "video/mp4",
                            "video/quicktime",
                            "video/webm",
                            "video/ogg",
                        )
                    },
                }
            if body:
                operation["requestBody"] = body
            if secured:
                operation["security"] = [{"HTTPBearer": []}]
            paths.setdefault(route.path, {})[route.method.lower()] = operation
        return {
            "openapi": "3.1.0",
            "info": {"title": self.title, "version": self.version},
            "paths": paths,
            "components": {
                "schemas": schemas,
                "securitySchemes": {
                    "HTTPBearer": {"type": "http", "scheme": "bearer"}
                },
            },
        }

    async def dispatch(self, request):
        path, method = request.url.path, request.scope["method"]
        if path in ("/api/openapi.json", "/api/docs"):
            if method != "GET":
                raise HTTPException(405, "Method not allowed", {"Allow": "GET"})
            if path.endswith(".json"):
                return 200, self.openapi(), "application/json"
            return (
                200,
                '<!doctype html><html><head><title>InnovateX API</title></head><body><h1>InnovateX API</h1><p><a href="/api/openapi.json">OpenAPI request and response catalog</a></p><pre id="catalog"></pre><script>fetch("/api/openapi.json").then(r=>r.json()).then(s=>{document.getElementById("catalog").textContent=JSON.stringify(s,null,2)})</script></body></html>',
                "text/html; charset=utf-8",
            )
        matches = [(r, r.pattern.fullmatch(path)) for r in self.routes]
        matches = [(r, m) for r, m in matches if m]
        if not matches:
            raise HTTPException(404, "Not found")
        for route, match in matches:
            if route.method == method:
                async with AsyncExitStack() as stack:
                    value = await Resolver(
                        self, request, match.groupdict(), stack
                    ).resolve(route.endpoint)
                    if route.response_model:
                        value = (
                            TypeAdapter(route.response_model)
                            .validate_python(value)
                            .model_dump(mode="json")
                        )
                    # Encode before commit so serialization failures roll back too.
                    encoded = json.dumps(
                        value, ensure_ascii=False, allow_nan=False
                    ).encode("utf-8")
                return route.status_code, encoded, "application/json"
        raise HTTPException(
            405,
            "Method not allowed",
            {"Allow": ", ".join(sorted({r.method for r, _ in matches}))},
        )

    async def serve(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith(
            "/api/"
        ):
            if self.fallback is not None:
                return await self.fallback(scope, receive, send)
            if scope["type"] == "lifespan":
                while True:
                    event = await receive()
                    if event["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif event["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1000})
            if scope["type"] != "http":
                return
        request = Request(scope, receive)
        headers = {
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "x-request-id": request.state.request_id,
        }
        origin = request.headers.get("origin")
        if origin:
            headers["vary"] = "Origin"
        if origin in self.allow_origins:
            headers["access-control-allow-origin"] = origin
            headers["access-control-expose-headers"] = (
                "X-Request-ID, Retry-After"
            )
        try:
            request.check_length()
            if (
                scope["method"] == "OPTIONS"
                and "access-control-request-method" in request.headers
            ):
                methods = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                requested = {
                    h.strip().lower()
                    for h in request.headers.get(
                        "access-control-request-headers", ""
                    ).split(",")
                    if h.strip()
                }
                if (
                    origin not in self.allow_origins
                    or request.headers["access-control-request-method"]
                    not in methods.split(", ")
                    or not requested.issubset({"authorization", "content-type"})
                ):
                    raise HTTPException(
                        400,
                        {
                            "code": "cors_denied",
                            "message": "CORS preflight is not allowed",
                        },
                    )
                headers.update(
                    {
                        "access-control-allow-methods": methods,
                        "access-control-allow-headers": "Authorization, Content-Type",
                        "access-control-max-age": "600",
                    }
                )
                status, value, media = 200, {}, "application/json"
            else:
                status, value, media = await self.dispatch(request)
        except Exception as e:
            details = []
            if isinstance(e, HTTPException):
                status = e.status_code
                detail = (
                    e.detail
                    if isinstance(e.detail, dict)
                    else {"code": "http_error", "message": str(e.detail)}
                )
                code, message = (
                    detail.get("code", "http_error"),
                    detail.get("message", "Request failed"),
                )
                headers.update({k.lower(): v for k, v in e.headers.items()})
            elif isinstance(e, RequestValidationError):
                status, code, message, details = (
                    422,
                    "validation_error",
                    "Request validation failed",
                    e.details,
                )
            else:
                logging.exception(f"Error: {type(e).__name__}")
                status, code, message = (
                    500,
                    "internal_error",
                    "The request could not be completed",
                )
            if status == 401:
                headers["www-authenticate"] = "Bearer"
            if status == 429:
                headers["retry-after"] = "900"
            value = {
                "error": {"code": code, "message": message, "details": details},
                "request_id": request.state.request_id,
            }
            media = "application/json"
        body = (
            value
            if isinstance(value, bytes)
            else (
                json.dumps(value, ensure_ascii=False).encode("utf-8")
                if media == "application/json"
                else value.encode("utf-8")
            )
        )
        headers.update(
            {"content-type": media, "content-length": str(len(body))}
        )
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (k.encode("latin1"), v.encode("latin1"))
                    for k, v in headers.items()
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
