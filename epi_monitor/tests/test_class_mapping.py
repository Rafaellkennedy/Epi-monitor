"""
Testes do resolvedor de nomes de classe (model-aware).
Cobre o remapeamento por nome, descarte de classes irrelevantes
e fallback COCO seguro.
"""

import pytest
from detection.yolo_detector import resolver_nome_classe


# Mapa de equivalência do construction model (Roboflow)
EQUIV_MAP = {
    "Hardhat": "capacete",
    "NO-Hardhat": "sem_capacete",
    "Mask": "mascara",
    "NO-Mask": "sem_mascara",
    "Safety Vest": "colete",
    "NO-Safety Vest": "sem_colete",
    "Person": "pessoa",
}
DISCARD = {"Safety Cone", "machinery", "vehicle"}
CLASS_NAMES_FALLBACK = {0: "capacete", 1: "sem_capacete", 10: "pessoa"}

# native_names simulando o retorno de result.names do modelo construction
NATIVE_NAMES = {
    0: "Hardhat",
    1: "NO-Hardhat",
    2: "Mask",
    3: "NO-Mask",
    4: "Safety Vest",
    5: "NO-Safety Vest",
    6: "Person",
    7: "Safety Cone",
    8: "machinery",
    9: "vehicle",
}


class TestResolverNomeClasse:
    """Testa a função pura resolver_nome_classe."""

    def test_remap_hardhat_para_capacete(self):
        nome = resolver_nome_classe(
            cls_id=0,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "capacete"

    def test_remap_no_hardhat_para_sem_capacete(self):
        nome = resolver_nome_classe(
            cls_id=1,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "sem_capacete"

    def test_remap_mask_para_mascara(self):
        nome = resolver_nome_classe(
            cls_id=2,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "mascara"

    def test_remap_no_mask_para_sem_mascara(self):
        nome = resolver_nome_classe(
            cls_id=3,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "sem_mascara"

    def test_remap_safety_vest_para_colete(self):
        nome = resolver_nome_classe(
            cls_id=4,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "colete"

    def test_remap_no_safety_vest_para_sem_colete(self):
        nome = resolver_nome_classe(
            cls_id=5,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "sem_colete"

    def test_remap_person_para_pessoa(self):
        nome = resolver_nome_classe(
            cls_id=6,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "pessoa"

    def test_descarta_safety_cone(self):
        nome = resolver_nome_classe(
            cls_id=7,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome is None  # deve ser descartado

    def test_descarta_machinery(self):
        nome = resolver_nome_classe(
            cls_id=8,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome is None  # deve ser descartado

    def test_descarta_vehicle(self):
        nome = resolver_nome_classe(
            cls_id=9,
            native_names=NATIVE_NAMES,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome is None  # deve ser descartado

    def test_fallback_legado_por_id(self):
        """Quando o nome nativo não está no mapa de equivalência nem no discard,
        usa o dict class_names por id como fallback."""
        # id=0 no fallback dict mapeia para "capacete"
        native_without_map = {0: "UnknownClass", 7: "Safety Cone"}
        nome = resolver_nome_classe(
            cls_id=0,
            native_names=native_without_map,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "capacete"  # veio do class_names por id

    def test_nome_nativo_quando_sem_fallback(self):
        """Se o id não estiver nem no fallback dict, retorna nome nativo."""
        native_small = {99: "classe_exotica"}
        nome = resolver_nome_classe(
            cls_id=99,
            native_names=native_small,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
        )
        assert nome == "classe_exotica"

    def test_fallback_coco_sem_mapeamento_epi(self):
        """No modo fallback COCO, usa APENAS nomes nativos (sem EPI mapping)."""
        coco_names = {0: "person", 1: "bicycle", 2: "car", 67: "cell phone"}
        nome = resolver_nome_classe(
            cls_id=0,
            native_names=coco_names,
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
            is_fallback_model=True,
        )
        # Deve retornar o nome nativo do COCO, NÃO mapear para EPI
        assert nome == "person"

    def test_fallback_coco_id_inexistente(self):
        """No fallback COCO, id inexistente retorna 'classe_{id}'."""
        nome = resolver_nome_classe(
            cls_id=999,
            native_names={0: "person"},
            equivalence_map=EQUIV_MAP,
            discard_classes=DISCARD,
            class_names_fallback=CLASS_NAMES_FALLBACK,
            is_fallback_model=True,
        )
        assert nome == "classe_999"