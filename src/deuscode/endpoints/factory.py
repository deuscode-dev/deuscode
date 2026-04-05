def get_endpoint_provider(endpoint_type: str):
    """Return the correct provider for the given endpoint type."""
    if endpoint_type == "pod":
        from deuscode.endpoints.pod import PodProvider
        return PodProvider()
    from deuscode.endpoints.serverless import ServerlessProvider
    return ServerlessProvider()
