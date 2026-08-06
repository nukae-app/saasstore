"""Tests de la deducció de format canònic a partir dels tokens de Discogs
(veure services/discogs.infer_formato, usat per l'alta assistida per
omplir Release.formato de manera fiable — sense això, cauria a text lliure
com "Vinyl, LP, Album, Reissue" que mai fa match amb PesFormat)."""

from app.services.discogs import infer_formato


def test_lp_estandard():
    assert infer_formato(["Vinyl", "LP", "Album", "Reissue"]) == "LP"
    assert infer_formato(["Vinyl", "12\"", "33 ⅓ RPM", "Album"]) == "LP"


def test_single_12_polzades_no_es_confon_amb_lp():
    assert infer_formato(["Vinyl", "12\"", "45 RPM", "Maxi-Single"]) == '12"'
    assert infer_formato(["Vinyl", "12\"", "45 RPM", "Single"]) == '12"'


def test_single_7_polzades():
    assert infer_formato(["Vinyl", "7\"", "45 RPM", "Single"]) == '7"'


def test_cd():
    assert infer_formato(["CD", "Album"]) == "CD"


def test_cassette():
    assert infer_formato(["Cassette", "Album"]) == "Cassette"


def test_ep_sense_mida_explicita():
    assert infer_formato(["Vinyl", "EP"]) == "EP"


def test_vinil_sense_mes_detall_cau_a_lp():
    assert infer_formato(["Vinyl"]) == "LP"


def test_sense_tokens_retorna_none():
    assert infer_formato([]) is None
    assert infer_formato([None, ""]) is None


def test_format_desconegut_cau_a_altre():
    assert infer_formato(["File", "MP3", "320 kbps"]) == "Altre"


def test_discogs_formats_detallat_name_i_descriptions_barrejats():
    """Simula com get_release() aplana formats[].name + .descriptions."""
    tokens = ["Vinyl"] + ["12\"", "45 RPM", "EP"]
    assert infer_formato(tokens) == '12"'
