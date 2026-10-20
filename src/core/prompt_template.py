"""Validazione e rendering dei prompt parametrizzati con colonne CSV."""

from __future__ import annotations

import math
from string import Formatter
from typing import Mapping, Sequence


class PromptTemplateError(ValueError):
    """Il prompt non può essere applicato in modo sicuro ai dati CSV."""


def extract_placeholders(prompt: str) -> list[str]:
    """Estrae placeholder semplici e univoci, preservandone l'ordine."""
    if not prompt or not prompt.strip():
        raise PromptTemplateError("Il prompt non può essere vuoto.")

    try:
        parsed = Formatter().parse(prompt)
        placeholders: list[str] = []
        for _, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if not field_name:
                raise PromptTemplateError("Placeholder vuoto non consentito.")
            if not field_name.isidentifier():
                raise PromptTemplateError(
                    f"Placeholder non valido '{{{field_name}}}': usa un nome "
                    "semplice, per esempio {review}."
                )
            if len(field_name) > 100:
                raise PromptTemplateError(
                    f"Placeholder '{{{field_name}}}' più lungo di 100 caratteri."
                )
            if format_spec or conversion:
                raise PromptTemplateError(
                    f"Formattazione avanzata non consentita per '{{{field_name}}}'."
                )
            if field_name not in placeholders:
                placeholders.append(field_name)
    except PromptTemplateError:
        raise
    except ValueError as error:
        raise PromptTemplateError(f"Sintassi delle graffe non valida: {error}") from error

    return placeholders


def _is_null(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def validate_prompt_data(
    prompt: str,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, str]:
    """Valida prompt e dati, restituendo il mapping identitario iniziale."""
    placeholders = extract_placeholders(prompt)
    available_columns = set(columns)
    missing_columns = [
        placeholder
        for placeholder in placeholders
        if placeholder not in available_columns
    ]
    if missing_columns:
        raise PromptTemplateError(
            "Colonne CSV mancanti per i placeholder: "
            + ", ".join(missing_columns)
        )

    null_values: list[str] = []
    for csv_row_number, row in enumerate(rows, start=2):
        for placeholder in placeholders:
            if _is_null(row.get(placeholder)):
                null_values.append(f"riga {csv_row_number}, colonna {placeholder}")
                if len(null_values) == 5:
                    break
        if len(null_values) == 5:
            break

    if null_values:
        raise PromptTemplateError(
            "Valori obbligatori mancanti: " + "; ".join(null_values)
        )

    return {placeholder: placeholder for placeholder in placeholders}


def render_prompt(
    prompt: str,
    row: Mapping[str, object],
    placeholder_mapping: Mapping[str, str] | None = None,
) -> str:
    """Sostituisce i placeholder usando il mapping persistito del task."""
    placeholders = extract_placeholders(prompt)
    mapping = (
        {placeholder: placeholder for placeholder in placeholders}
        if placeholder_mapping is None
        else placeholder_mapping
    )
    values: dict[str, str] = {}

    for placeholder in placeholders:
        column = mapping.get(placeholder)
        if not column:
            raise PromptTemplateError(
                f"Mapping mancante per il placeholder '{{{placeholder}}}'."
            )
        if column not in row:
            raise PromptTemplateError(
                f"Colonna '{column}' non presente nei dati della riga."
            )
        value = row[column]
        if _is_null(value):
            raise PromptTemplateError(
                f"Valore mancante per la colonna '{column}'."
            )
        values[placeholder] = str(value)

    try:
        return prompt.format_map(values)
    except (KeyError, ValueError) as error:
        raise PromptTemplateError(
            f"Impossibile applicare il prompt parametrico: {error}"
        ) from error
