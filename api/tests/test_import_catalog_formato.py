"""El sheet és, en origen, un export de Discogs: la columna FORMAT sol portar
els mateixos tokens barrejats que la cerca de Discogs. Verifica que
scripts.import_catalog reutilitza el mateix mapeig que services.discogs
(veure test_discogs_formato.py) en lloc de desar el text lliure tal qual."""

from scripts.import_catalog import infer_formato_sheet


def test_normalitza_tokens_estil_discogs():
    assert infer_formato_sheet("Vinyl, LP, Album, Reissue") == "LP"
    assert infer_formato_sheet("Vinyl, 7\", 45 RPM, Single") == '7"'
    assert infer_formato_sheet("CD, Album") == "CD"


def test_cel·la_buida_retorna_none():
    assert infer_formato_sheet("") is None
    assert infer_formato_sheet(None) is None
    assert infer_formato_sheet("   ") is None


def test_text_sense_tokens_reconeguts_cau_a_altre():
    assert infer_formato_sheet("Picture Disc, Numbered") == "Altre"
