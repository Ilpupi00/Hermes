"""Test del parser e renderer dei prompt parametrizzati."""

import pytest

from src.core.prompt_template import (
    PromptTemplateError,
    extract_placeholders,
    render_prompt,
    validate_prompt_data,
)


class TestExtractPlaceholders:
    def test_extracts_unique_placeholders_in_order(self):
        assert extract_placeholders(
            "Confronta {review} del {date} con {review}."
        ) == ["review", "date"]

    def test_accepts_literal_braces(self):
        assert extract_placeholders(
            'Restituisci {{"sentiment": "x"}} per {review}.'
        ) == ["review"]

    @pytest.mark.parametrize(
        "prompt",
        ["", "Testo {", "Testo }", "Valore {}", "Valore {review.name}"],
    )
    def test_rejects_invalid_templates(self, prompt):
        with pytest.raises(PromptTemplateError):
            extract_placeholders(prompt)

    @pytest.mark.parametrize("prompt", ["{review!r}", "{review:>10}"])
    def test_rejects_advanced_formatting(self, prompt):
        with pytest.raises(PromptTemplateError, match="avanzata"):
            extract_placeholders(prompt)


class TestValidatePromptData:
    def test_returns_identity_mapping(self):
        mapping = validate_prompt_data(
            "Classifica {review} del {date}.",
            ["review", "date"],
            [{"review": "Ottimo", "date": "2026-10-19"}],
        )

        assert mapping == {"review": "review", "date": "date"}

    def test_rejects_missing_columns(self):
        with pytest.raises(PromptTemplateError, match="date"):
            validate_prompt_data(
                "Classifica {review} del {date}.",
                ["review"],
                [{"review": "Ottimo"}],
            )

    @pytest.mark.parametrize("missing_value", [None, "", "   "])
    def test_rejects_null_values(self, missing_value):
        with pytest.raises(PromptTemplateError, match="riga 2, colonna review"):
            validate_prompt_data(
                "Classifica {review}.",
                ["review"],
                [{"review": missing_value}],
            )

    def test_plain_prompt_does_not_require_columns(self):
        assert validate_prompt_data(
            "Riassumi i dati forniti.",
            ["review"],
            [{"review": ""}],
        ) == {}


class TestRenderPrompt:
    def test_substitutes_values_and_unescapes_literal_braces(self):
        result = render_prompt(
            'Recensione: {review}. Formato: {{"sentiment": "valore"}}.',
            {"review": "Prodotto ottimo"},
            {"review": "review"},
        )

        assert result == (
            'Recensione: Prodotto ottimo. '
            'Formato: {"sentiment": "valore"}.'
        )

    def test_supports_explicit_column_mapping(self):
        assert render_prompt(
            "Testo: {contenuto}",
            {"review": "Ottimo"},
            {"contenuto": "review"},
        ) == "Testo: Ottimo"

    def test_rejects_missing_mapping(self):
        with pytest.raises(PromptTemplateError, match="Mapping mancante"):
            render_prompt(
                "Testo: {review}",
                {"review": "Ottimo"},
                {"altro": "review"},
            )

    def test_rejects_null_runtime_value(self):
        with pytest.raises(PromptTemplateError, match="Valore mancante"):
            render_prompt(
                "Testo: {review}",
                {"review": float("nan")},
                {"review": "review"},
            )
