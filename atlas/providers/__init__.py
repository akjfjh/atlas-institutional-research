"""Read-only real-data providers and optional explicit offline fixtures."""
from .provider_registry import DataService
from .common import ProviderError
__all__=['DataService','ProviderError']
