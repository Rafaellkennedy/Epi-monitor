import pytest
from database.models import Evento


def test_evento_composite_indexes_metadata():
    """Verifica se os índices compostos de alta performance estão mapeados no modelo Evento."""
    indexes = {idx.name: [col.name for col in idx.columns] for idx in Evento.__table__.indexes}

    # Verifica a existência dos dois índices compostos criados na Task 05
    assert "idx_evento_data_tipo" in indexes
    assert indexes["idx_evento_data_tipo"] == ["data_hora", "tipo_evento"]

    assert "idx_evento_camera_tipo_data" in indexes
    assert indexes["idx_evento_camera_tipo_data"] == ["camera_id", "tipo_evento", "data_hora"]
