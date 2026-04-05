"""Tests for endpoint factory."""

from deuscode.endpoints.factory import get_endpoint_provider
from deuscode.endpoints.serverless import ServerlessProvider
from deuscode.endpoints.pod import PodProvider


def test_returns_serverless_by_default():
    provider = get_endpoint_provider("serverless")
    assert isinstance(provider, ServerlessProvider)


def test_returns_pod_for_pod_type():
    provider = get_endpoint_provider("pod")
    assert isinstance(provider, PodProvider)


def test_returns_serverless_for_unknown():
    provider = get_endpoint_provider("unknown")
    assert isinstance(provider, ServerlessProvider)
