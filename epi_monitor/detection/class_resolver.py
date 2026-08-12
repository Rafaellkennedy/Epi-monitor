"""
detection/class_resolver.py
---------------------------
Função PURA e testável para resolução de nomes de classe YOLO,
sem dependências pesadas (torch, ultralytics).

Resolução de classes (model-aware):
    a. Nome nativo do modelo no mapa de equivalência -> nome interno EPI
    b. Classes fora do domínio EPI (ex: machinery, vehicle) -> descartadas
    c. Fallback legado via dict class_names por id quando o mapa não bate
"""

from __future__ import annotations

from typing import Optional


def resolver_nome_classe(
    cls_id: int,
    native_names: dict,
    equivalence_map: dict[str, str],
    discard_classes: set[str],
    class_names_fallback: dict[int, str],
    is_fallback_model: bool = False,
) -> Optional[str]:
    """
    Função PURA e testável: resolve o nome da classe a partir do id
    retornado pelo modelo YOLO.

    Regras (em ordem):
      a. Se for modelo fallback COCO (yolo11n.pt), usa nomes nativos --
         sem aplicar mapeamentos EPI (evita falsos positivos).
      b. Se o nome nativo estiver no mapa de equivalência, retorna o
         nome interno EPI correspondente.
      c. Se o nome nativo estiver no conjunto de classes a descartar,
         retorna None (detecção ignorada).
      d. Fallback legado: usa dict `class_names` por id (para modelos
         customizados como `epi_best.pt`).
    """
    if is_fallback_model:
        return native_names.get(cls_id, f"classe_{cls_id}")

    native_name = native_names.get(cls_id, "")

    if native_name in equivalence_map:
        return equivalence_map[native_name]

    if native_name in discard_classes:
        return None  # descartar detecção

    # Fallback legado: dict id -> nome (modelo customizado treinado)
    return class_names_fallback.get(cls_id, native_name or f"classe_{cls_id}")