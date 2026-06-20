"""Unit tests for copilot_agents.orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from models.skai_api.autogen import FilterOptions
from copilot_agents.orchestrator import OrchestratorSession, _format_numbered_list
from prompts.orchestrator.copilot import format_filter_context
from models.skai_api_v2.filters import FilterValuesResponse as FilterValuesResponseV2


@pytest.fixture
def mock_llm_service():
    return MagicMock()


@pytest.fixture
def mock_skai_service():
    return AsyncMock()


@pytest.fixture
def mock_version_config():
    return MagicMock()


@pytest.fixture
def orchestrator_session(mock_llm_service, mock_skai_service, mock_version_config):
    return OrchestratorSession(
        session_id="test-session",
        chat_history=[],
        llm_service=mock_llm_service,
        skai_service=mock_skai_service,
        version_config=mock_version_config,
    )


class TestSetFilterValues:
    """Tests for OrchestratorSession._set_filter_context."""

    @pytest.mark.asyncio
    async def test_set_filter_values_excludes_disallowed_values(
        self, orchestrator_session, mock_skai_service
    ):
        """Excluded filter values (e.g. NOT AVAILABLE for brands) are removed from context."""
        filters = FilterOptions(
            brands=["BrandA", "NOT AVAILABLE", "BrandB"],
            categories=["Cat1"],
        )
        mock_skai_service.get_filter_values.return_value = MagicMock(filters=filters)

        result = await orchestrator_session._set_filter_values()

        assert result is not None
        assert "NOT AVAILABLE" not in result.filters.brands
        assert set(result.filters.brands) == {"BrandA", "BrandB"}
        assert result.filters.categories == ["Cat1"]

    @pytest.mark.asyncio
    async def test_set_filter_values_returns_cached_result_on_second_call(
        self, orchestrator_session, mock_skai_service
    ):
        """Second call returns cached filter_context without calling API again."""
        filters = FilterOptions(brands=["BrandA"])
        mock_skai_service.get_filter_values.return_value = MagicMock(filters=filters)

        first = await orchestrator_session._set_filter_values()
        second = await orchestrator_session._set_filter_values()

        assert first is second
        assert mock_skai_service.get_filter_values.call_count == 1

    @pytest.mark.asyncio
    async def test_set_filter_values_ignores_missing_filter_attributes(
        self, orchestrator_session, mock_skai_service
    ):
        """If a key in EXCLUDED_FILTER_OPTIONS is not on filters, it is skipped."""
        filters = FilterOptions(brands=["BrandA"])
        mock_skai_service.get_filter_values.return_value = MagicMock(filters=filters)

        result = await orchestrator_session._set_filter_values()

        assert set(result.filters.brands) == {"BrandA"}
        assert mock_skai_service.get_filter_values.call_count == 1


class TestFormatNumberedList:
    """Regression tests for inline numbered list formatting."""

    def test_preserves_parenthesized_options_and_dates(self):
        """Do not split "(1)" style options or date fragments like "...-01), ...".

        These should remain untouched to avoid malformed markdown in chat bubbles.
        """
        text = (
            "Do you want the calendar for (1) the latest 20 weeks that are fully "
            "covered in the promo extract (ending ~2025-12-01), or (2) keep the "
            "last 20 weeks to 2025-12-22 but show it as incomplete/missing weeks "
            "where data isn't available?"
        )

        assert _format_numbered_list(text) == text

    def test_splits_plain_inline_numbered_markers(self):
        """Split compact inline numbered markers into multiline list format."""
        text = "Choose one: 1) latest fully covered weeks 2) keep last 20 weeks"
        expected = (
            "Choose one:\n" "1) latest fully covered weeks\n" "2) keep last 20 weeks"
        )

        assert _format_numbered_list(text) == expected


class TestFormatFilterContext:
    def test_supports_v2_filter_values_response(self):
        filter_values = FilterValuesResponseV2.model_validate(
            {
                "filters": {
                    "superCategories": ["Paint"],
                    "brands": ["Brand A"],
                    "categories": ["Category A"],
                    "subcategories": ["Subcategory A"],
                    "retailers": ["Retailer A"],
                    "channels": ["Online"],
                    "priceTiers": ["Premium"],
                },
                "metadata": {
                    "tenantId": 42,
                    "lastUpdated": "2026-06-04T09:15:00Z",
                    "dataRange": {
                        "minDate": "2025-01-01",
                        "maxDate": "2026-05-31",
                    },
                },
            }
        )

        context = format_filter_context(filter_values)

        assert "**Super Categories**: Paint" in context
        assert "**Brands** (1 total): Brand A" in context
        assert "**Retailers**: Retailer A" in context
