"""Unit tests for TemplateService update behavior."""

from uuid import uuid4

import pytest

from services.template_service import TemplateService


class TestTemplateServiceUpdate:
    """Test template update semantics."""

    @pytest.mark.asyncio
    async def test_updates_only_provided_fields(self, mocker):
        """Omitted fields should not be modified."""
        service = TemplateService()
        mock_db = mocker.AsyncMock()

        template = mocker.Mock()
        template.name = "Legacy template"
        template.description = "Legacy description that should remain untouched"
        template.content = "Original content"
        template.is_default = False

        mocker.patch.object(service, "get_template", return_value=template)
        mocker.patch.object(service, "_clear_defaults", new=mocker.AsyncMock())

        result = await service.update_template(
            template_id=uuid4(),
            user_id=uuid4(),
            db=mock_db,
            name="Renamed template",
        )

        assert result == template
        assert template.name == "Renamed template"
        assert template.description == "Legacy description that should remain untouched"
        assert template.content == "Original content"
        assert template.is_default is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(template)

    @pytest.mark.asyncio
    async def test_allows_clearing_description(self, mocker):
        """Explicit null should clear description."""
        service = TemplateService()
        mock_db = mocker.AsyncMock()

        template = mocker.Mock()
        template.name = "Template"
        template.description = "Will be cleared"
        template.content = "Content"
        template.is_default = False

        mocker.patch.object(service, "get_template", return_value=template)
        mocker.patch.object(service, "_clear_defaults", new=mocker.AsyncMock())

        await service.update_template(
            template_id=uuid4(),
            user_id=uuid4(),
            db=mock_db,
            description=None,
        )

        assert template.description is None
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(template)

    @pytest.mark.asyncio
    async def test_clears_other_defaults_when_marked_default(self, mocker):
        """When setting default true, other defaults should be cleared first."""
        service = TemplateService()
        mock_db = mocker.AsyncMock()

        template = mocker.Mock()
        template.name = "Template"
        template.description = None
        template.content = "Content"
        template.is_default = False

        clear_defaults = mocker.AsyncMock()
        mocker.patch.object(service, "get_template", return_value=template)
        mocker.patch.object(service, "_clear_defaults", new=clear_defaults)

        await service.update_template(
            template_id=uuid4(),
            user_id=uuid4(),
            db=mock_db,
            is_default=True,
        )

        clear_defaults.assert_called_once()
        assert template.is_default is True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(template)
