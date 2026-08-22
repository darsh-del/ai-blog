"""
Shared pytest fixtures and configurations.
"""
from typing import Generator
from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture(name="mock_genai_client")
def fixture_mock_genai_client() -> Generator[MagicMock, None, None]:
    """Fixture to mock the Google GenAI Client singleton manager."""
    with patch('src.llm_client.ClientManager.get_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client
