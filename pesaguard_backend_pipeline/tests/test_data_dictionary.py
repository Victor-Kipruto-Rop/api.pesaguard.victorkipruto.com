import json

import pytest

from data_dictionary import DictionaryError, load_dictionary


def test_dictionary_exposes_field_level_contracts():
    dictionary = load_dictionary()
    amount = dictionary.field("transactions", "amount")
    assert amount.type == "DECIMAL(18,2)"
    assert amount.nullable is False
    assert amount.currency == "Defined by currency column."
    assert "Reconciliation" in amount.used_by


def test_dictionary_must_link_to_catalog(tmp_path):
    path = tmp_path / "dictionary.json"
    path.write_text(json.dumps({"datasets": {"missing": []}}), encoding="utf-8")
    with pytest.raises(DictionaryError):
        load_dictionary(str(path))