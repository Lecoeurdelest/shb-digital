"""REST API routers (T1-3): conversations + chat + SSE. CONTRACT §2/§4.

Router = tầng HTTP: gọi store/orch, KHÔNG business trực tiếp. Success = resource trần (§0);
error = ApiError 4-field. Auth qua require_user (cookie JWT — T1-1).
"""
