"""Crea (o actualitza) les pàgines estàtiques de política de privacitat i
termes d'ús, necessàries per sol·licitar l'Extended Quota Mode de Spotify
(el formulari exigeix URLs públiques d'ambdues).

Ús:
    python -m scripts.seed_legal_pages

Idempotent: si l'slug ja existeix, actualitza el contingut en lloc de duplicar.
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Pagina

PRIVACITAT_HTML = """
<p>Ultra-Local Records ("nosaltres") tracta les teves dades personals amb la
finalitat de gestionar la teva compra, el teu compte d'usuari i, si hi
consenteixes expressament, connectar el teu compte de Spotify per
oferir-te recomanacions del catàleg.</p>

<h2>Quines dades recollim</h2>
<ul>
  <li>Dades de compte: nom, email, adreces d'enviament.</li>
  <li>Dades de comanda: articles comprats, historial de comandes.</li>
  <li>Si connectes Spotify: el teu identificador d'usuari de Spotify i els
  teus artistes/cançons més escoltats (només amb el teu consentiment
  explícit, revocable en qualsevol moment des del teu compte).</li>
</ul>

<h2>Amb qui compartim les dades</h2>
<p>No venem ni cedim les teves dades a tercers amb finalitats comercials.
Utilitzem proveïdors de servei (allotjament, processament de pagaments,
enviament d'emails) únicament per prestar el servei.</p>

<h2>Spotify</h2>
<p>Quan connectes el teu compte de Spotify, utilitzem l'API oficial de
Spotify (àmbit <code>user-top-read</code>) exclusivament per comparar els
teus artistes escoltats amb el nostre catàleg de vinils i suggerir-te
discos. Pots desconnectar Spotify en qualsevol moment des del teu compte;
això elimina el token d'accés emmagatzemat.</p>

<h2>Els teus drets</h2>
<p>Pots exercir els drets d'accés, rectificació, supressió i portabilitat
escrivint a <a href="mailto:info@ultralocalrecords.com">info@ultralocalrecords.com</a>.</p>
""".strip()

TERMES_HTML = """
<p>L'ús d'aquesta web i la compra a Ultra-Local Records implica l'acceptació
d'aquests termes.</p>

<h2>Productes</h2>
<p>Els articles en venda són exemplars físics únics (vinils nous o de
segona mà); el grading de cada exemplar es descriu a la fitxa del producte.</p>

<h2>Comandes i pagament</h2>
<p>Una comanda es confirma un cop rebut el pagament. Els preus inclouen IVA.</p>

<h2>Compte i connexió amb Spotify</h2>
<p>Connectar el teu compte de Spotify és opcional i es fa sota la teva
responsabilitat, acceptant les <a href="https://www.spotify.com/legal/end-user-agreement/" target="_blank" rel="noopener">condicions d'ús de Spotify</a>.
Nosaltres només utilitzem aquesta connexió per a recomanacions dins del
nostre catàleg.</p>

<h2>Contacte</h2>
<p><a href="mailto:info@ultralocalrecords.com">info@ultralocalrecords.com</a></p>
""".strip()

PAGES = [
    dict(slug="privacitat", nom="Política de privacitat", tipus="estatica",
         posicio=90, visible_menu=False, contingut=PRIVACITAT_HTML),
    dict(slug="termes", nom="Termes d'ús", tipus="estatica",
         posicio=91, visible_menu=False, contingut=TERMES_HTML),
]


def main():
    db = SessionLocal()
    try:
        for data in PAGES:
            pagina = db.scalar(select(Pagina).where(Pagina.slug == data["slug"]))
            if pagina:
                for k, v in data.items():
                    setattr(pagina, k, v)
                print(f"Actualitzada: /{data['slug']}")
            else:
                db.add(Pagina(**data))
                print(f"Creada: /{data['slug']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
