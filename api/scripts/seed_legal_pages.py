"""Crea les pàgines legals d'un tenant: avís legal, política de privacitat,
política de cookies, termes d'ús i condicions de venda.

Uso:
    docker compose exec api python -m scripts.seed_legal_pages --tenant recordstore
    ... --overwrite    # també reescriu les pàgines que ja existeixen

Por defecto es idempotente Y NO destructivo: si el slug ya existe, se deja tal
cual (el contenido puede estar curado a mano — p.ej. la cláusula de Spotify del
tenant `recordstore`, necesaria para el Extended Quota Mode). Solo `--overwrite`
sustituye el contenido existente por la plantilla.

Los textos son una PLANTILLA razonable para una tienda online española que
vende a consumidores (LSSI art. 10, RGPD art. 13, LSSI art. 22.2, TRLGDCU), pero
NO sustituyen la revisión de un abogado/gestor: hay que completar los datos que
falten (marcados como «[pendent]») y confirmar el tratamiento del IVA/REBU en
segunda mano. Los datos del titular salen de ConfiguracioBotiga (fiscal_name,
nif, address, contact_email, phone).
"""

import argparse
import html

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ConfiguracioBotiga, Pagina, Tenant
from app.tenancy import scoped_to

PENDENT = "[pendent]"


AVIS_LEGAL_TEMPLATE = """
<p>En compliment de l'article 10 de la Llei 34/2002, de serveis de la societat
de la informació i de comerç electrònic (LSSI-CE), s'informa que aquest web és
titularitat de:</p>

<ul>
  <li><strong>Titular:</strong> {nom}</li>
  <li><strong>NIF/CIF:</strong> {nif}</li>
  <li><strong>Domicili:</strong> {adreca}</li>
  <li><strong>Correu electrònic:</strong> <a href="mailto:{email}">{email}</a></li>
  <li><strong>Telèfon:</strong> {telefon}</li>
</ul>

<h2>Objecte</h2>
<p>Aquest web permet consultar el catàleg de {nom} i comprar-hi productes,
així com accedir a les seves notícies i activitats.</p>

<h2>Propietat intel·lectual</h2>
<p>Els textos, imatges, logotips i el disseny d'aquest web pertanyen a {nom} o
als seus autors i no es poden reproduir sense autorització. Les caràtules i
dades dels discos són propietat dels seus respectius titulars i s'hi mostren
només per identificar els productes a la venda.</p>

<h2>Responsabilitat</h2>
<p>Posem tot l'esforç perquè la informació sigui correcta i estigui al dia, però
no podem garantir que no hi hagi errors puntuals de preu o d'estoc. Si
detectem un error abans de servir la comanda, t'ho comunicarem i podràs
confirmar-la o cancel·lar-la sense cost. Els enllaços a webs de tercers són
només informatius.</p>

<h2>Legislació aplicable</h2>
<p>Aquest web es regeix per la legislació espanyola. Si ets consumidor,
qualsevol conflicte es pot sotmetre als jutjats i tribunals del teu domicili.</p>
""".strip()


PRIVACITAT_TEMPLATE = """
<p>Aquesta política explica com {nom} tracta les teves dades personals, d'acord
amb el Reglament (UE) 2016/679 (RGPD) i la Llei Orgànica 3/2018 (LOPDGDD).</p>

<h2>Responsable del tractament</h2>
<ul>
  <li><strong>Responsable:</strong> {nom} (NIF {nif})</li>
  <li><strong>Domicili:</strong> {adreca}</li>
  <li><strong>Contacte per a qüestions de privacitat:</strong> <a href="mailto:{email}">{email}</a></li>
</ul>

<h2>Quines dades tractem, per a què i amb quina base legal</h2>
<table>
  <thead><tr><th>Finalitat</th><th>Dades</th><th>Base legal</th></tr></thead>
  <tbody>
    <tr><td>Crear i gestionar el teu compte i les teves sessions</td>
        <td>Email, nom, telèfon, contrasenya (només el seu <em>hash</em>), identificador d'accés amb Google</td>
        <td>Execució del contracte (art. 6.1.b RGPD)</td></tr>
    <tr><td>Gestionar les teves compres, peticions de discos i, si t'hi apuntes, el club del disc: cobrament, enviament, atenció postvenda i garantia</td>
        <td>Dades de contacte, adreça d'entrega, comandes, imports. No guardem dades de la targeta: les tracta directament la passarel·la de pagament.</td>
        <td>Execució del contracte (art. 6.1.b)</td></tr>
    <tr><td>Complir obligacions fiscals, comptables i mercantils</td>
        <td>Comandes, factures i dades de facturació</td>
        <td>Obligació legal (art. 6.1.c)</td></tr>
    <tr><td>Enviar-te la newsletter amb novetats i activitats</td>
        <td>Email, nom, idioma</td>
        <td>Consentiment (art. 6.1.a). Pots retirar-lo en qualsevol moment des de «El meu compte → Perfil» o amb l'enllaç de baixa de cada correu.</td></tr>
    <tr><td>Respondre consultes que ens facis</td>
        <td>Les que ens facilitis</td>
        <td>Interès legítim i/o execució de mesures precontractuals (art. 6.1.f i 6.1.b)</td></tr>
    <tr><td>Seguretat del servei i prevenció del frau i els abusos (límits de peticions, registres tècnics)</td>
        <td>Adreça IP i dades tècniques de la connexió</td>
        <td>Interès legítim (art. 6.1.f)</td></tr>
  </tbody>
</table>
<p>Si connectes el teu compte de Spotify per rebre recomanacions, només usem les
dades de gust musical que autoritzes en aquell moment; pots desconnectar-lo
quan vulguis. No prenem decisions automatitzades amb efectes jurídics sobre tu.</p>

<h2>Amb qui compartim les dades</h2>
<p>No venem ni cedim les teves dades amb finalitats comercials. Només hi accedeixen
proveïdors que ens presten serveis i actuen com a encarregats del tractament
sota contracte:</p>
<ul>
  <li>Allotjament i infraestructura tècnica del web.</li>
  <li>Passarel·la de pagament amb targeta (Redsys i l'entitat financera corresponent).</li>
  <li>Servei d'enviament de correu electrònic transaccional i de newsletter.</li>
  <li>Empreses de transport, perquè puguin lliurar-te la comanda.</li>
  <li>La nostra gestoria, per a la comptabilitat i les obligacions fiscals.</li>
</ul>
<p>També poden rebre dades les administracions públiques quan una llei ho exigeixi.
No transferim dades fora de l'Espai Econòmic Europeu llevat que el proveïdor ho
faci amb garanties adequades (clàusules contractuals tipus de la Comissió Europea
o decisió d'adequació).</p>

<h2>Quant de temps les conservem</h2>
<ul>
  <li><strong>Compte:</strong> mentre el mantinguis. Si l'esborres, eliminem les dades personals (perfil, adreces, sessions, vincles).</li>
  <li><strong>Comandes i factures:</strong> el temps que exigeix la llei (mínim 6 anys, art. 30 del Codi de Comerç, i el termini de prescripció tributària). Un cop esborrat el compte, es conserven sense el teu email.</li>
  <li><strong>Newsletter:</strong> fins que et donis de baixa.</li>
  <li><strong>Consultes:</strong> el temps necessari per atendre-les i, després, durant els terminis de prescripció de possibles responsabilitats.</li>
</ul>

<h2>Els teus drets</h2>
<p>Pots exercir els drets d'accés, rectificació, supressió, oposició, limitació del
tractament i portabilitat, i retirar el consentiment que hagis donat:</p>
<ul>
  <li><strong>Pel teu compte:</strong> a «El meu compte → Perfil» pots descarregar totes les teves dades i esborrar el compte tu mateix/a.</li>
  <li><strong>Per correu:</strong> escrivint a <a href="mailto:{email}">{email}</a>. Respondrem en un màxim d'un mes.</li>
</ul>
<p>Si consideres que no hem tractat bé les teves dades, pots reclamar davant
l'<a href="https://www.aepd.es" rel="noopener">Agència Espanyola de Protecció de Dades</a>
o l'<a href="https://apdcat.gencat.cat" rel="noopener">Autoritat Catalana de Protecció de Dades</a>.</p>

<h2>Menors</h2>
<p>Aquest web no s'adreça a menors de 14 anys. Si ets menor d'aquesta edat, no
creïs un compte sense el consentiment dels teus pares o tutors.</p>
""".strip()


COOKIES_TEMPLATE = """
<p>Aquest web fa servir només els emmagatzematges <strong>estrictament necessaris</strong>
perquè funcioni. No fem servir cookies d'analítica, publicitat ni seguiment, i per això
no et mostrem un bàner de cookies. El contingut de tercers (vídeos, reproductors de
música) <strong>no es carrega fins que tu ho demanes</strong>.</p>

<h2>Emmagatzematge tècnic (exempt de consentiment)</h2>
<table>
  <thead><tr><th>Nom</th><th>Finalitat</th><th>Durada</th></tr></thead>
  <tbody>
    <tr><td><code>ulr_refresh</code> (cookie)</td><td>Mantenir la teva sessió iniciada de forma segura (httpOnly)</td><td>30 dies o fins que tanquis sessió</td></tr>
    <tr><td><code>ulr_cart</code> (cookie)</td><td>Recordar el teu carret si no has iniciat sessió</td><td>30 dies</td></tr>
    <tr><td><code>ulr_token</code> (emmagatzematge local)</td><td>Credencial d'accés de curta durada de la teva sessió</td><td>Fins que tanquis sessió</td></tr>
    <tr><td><code>ulr_lang</code> (emmagatzematge local)</td><td>Recordar l'idioma triat</td><td>Persistent</td></tr>
    <tr><td><code>embed_consent_hosts</code> (emmagatzematge local)</td><td>Recordar de quins proveïdors has acceptat carregar contingut</td><td>Fins que l'esborris</td></tr>
  </tbody>
</table>

<h2>Contingut de tercers (només amb el teu clic)</h2>
<p>Algunes pàgines poden incloure reproductors de YouTube, Vimeo, Spotify, Mixcloud,
Bandcamp o SoundCloud. Fins que premis «Carregar contingut» no es connecta amb aquests
serveis. Un cop carregat, el tercer pot veure la teva adreça IP i instal·lar les seves
pròpies cookies, sota la seva política de privacitat. Si marques «Recorda'm», ho
desem al teu navegador; pots esborrar-ho en qualsevol moment amb l'enllaç
«Esborrar permisos de contingut de tercers» del peu de pàgina.</p>

<h2>Com gestionar o eliminar cookies</h2>
<p>Pots bloquejar o esborrar cookies des de la configuració del teu navegador. Si
bloqueges les tècniques, no podràs iniciar sessió ni fer servir el carret.</p>

<p>Per a qualsevol dubte, escriu-nos a <a href="mailto:{email}">{email}</a>.</p>
""".strip()


TERMES_TEMPLATE = """
<p>L'accés i ús d'aquest web, propietat de {nom}, implica l'acceptació d'aquests termes.
Les compres es regeixen a més per les <a href="/condicions-venda">condicions de venda</a>.</p>

<h2>Ús del web</h2>
<p>Et compromets a fer-ne un ús lícit i a no intentar accedir a àrees restringides,
alterar-ne el funcionament ni usar-lo per a finalitats fraudulentes.</p>

<h2>Compte d'usuari</h2>
<p>Ets responsable de mantenir confidencials les teves credencials. Si sospites que
algú hi ha accedit, avisa'ns a <a href="mailto:{email}">{email}</a>. Podem suspendre
comptes que incompleixin aquests termes o la llei.</p>

<h2>Contingut i propietat intel·lectual</h2>
<p>Vegeu l'<a href="/avis-legal">avís legal</a>.</p>

<h2>Dades personals i cookies</h2>
<p>Vegeu la <a href="/privacitat">política de privacitat</a> i la
<a href="/cookies">política de cookies</a>.</p>

<h2>Modificacions</h2>
<p>Podem actualitzar aquests termes; la versió vigent és sempre la publicada en aquesta pàgina.</p>

<h2>Contacte</h2>
<p><a href="mailto:{email}">{email}</a></p>
""".strip()


CONDICIONS_VENDA_TEMPLATE = """
<p>Aquestes condicions regulen les compres fetes a través d'aquest web a
<strong>{nom}</strong> (NIF {nif}, {adreca}; <a href="mailto:{email}">{email}</a>),
d'acord amb el Reial decret legislatiu 1/2007 (Llei general per a la defensa dels
consumidors i usuaris).</p>

<h2>Productes</h2>
<p>Venem discos nous i de segona mà. Els articles de segona mà són exemplars únics:
indiquem l'estat del disc i de la funda (graduació) a la fitxa, i la compra
d'un exemplar l'esgota. Les imatges són orientatives; per als exemplars únics, la
descripció i l'estat indicats són els que prevalen.</p>

<h2>Preus i impostos</h2>
<p>Tots els preus s'expressen en euros. Els productes nous inclouen l'IVA. Els
articles de segona mà es poden vendre sota el règim especial de béns usats (REBU),
en què l'IVA no es desglossa a la factura. Els costos d'enviament, si n'hi ha,
s'indiquen i se sumen al total abans de confirmar el pagament.</p>

<h2>Procés de compra i contracte</h2>
<p>Afegeixes els productes al carret, indiques les dades i l'adreça i confirmes la
comanda prement el botó de pagament, que implica una obligació de pagar. Els
exemplars del carret es reserven durant uns minuts mentre completes el pagament.
Un cop pagada, rebràs un correu de confirmació. Podem cancel·lar una comanda i
reemborsar-te si un article no està realment disponible.</p>

<h2>Pagament</h2>
<p>El pagament amb targeta es processa a través de la passarel·la segura de Redsys.
{nom} no té accés ni guarda les dades de la teva targeta. També es pot pagar a
botiga quan hagis triat recollida a botiga i aquesta opció estigui disponible.</p>

<h2>Lliurament</h2>
<p>Enviem a l'adreça que indiquis o pots recollir a botiga quan aquesta opció estigui
disponible. Salvat que s'indiqui un altre termini, el lliurament es fa en un màxim
de 30 dies des de la confirmació. T'avisarem quan la comanda surti o estigui
preparada per recollir.</p>

<h2>Dret de desistiment (14 dies)</h2>
<p>Tens dret a desistir de la compra, sense justificar-ho, en un termini de
<strong>14 dies naturals</strong> des que tu (o la persona que triïs) rep els productes.
Per exercir-lo, comunica'ns la decisió de forma inequívoca per correu electrònic a
<a href="mailto:{email}">{email}</a> (pots fer servir el formulari següent). Has de
tornar els productes en un màxim de 14 dies des de la comunicació; el cost directe de
la devolució és a càrrec teu, llevat que s'indiqui el contrari. Et reemborsarem tots els
pagaments, incloent-hi les despeses d'enviament estàndard, en un màxim de 14 dies des
que rebem la teva comunicació, i podem retenir el reemborsament fins que rebem els
productes o en demostris la devolució. Respondràs de la disminució de valor del bé
causada per una manipulació diferent de la necessària per comprovar-ne la naturalesa i el funcionament.</p>
<p><strong>Excepcions:</strong> no hi ha dret de desistiment en els enregistraments
sonors precintats que hagis desprecintat després del lliurament, ni en béns
confeccionats segons les teves especificacions.</p>
<p><em>Formulari de desistiment (a enviar a {email}):</em> «Pel present us comunico que desisteixo del
contracte de venda dels productes següents: [productes]. Comanda núm.: [número].
Rebuda el: [data]. Nom: [nom]. Adreça: [adreça]. Data: [data].»</p>

<h2>Garantia legal</h2>
<p>Els productes tenen la garantia legal de conformitat: <strong>3 anys</strong> per als
nous i <strong>1 any</strong> per als de segona mà, des del lliurament. Si el producte no és
conforme, tens dret a la reparació o substitució i, si no és possible, a la rebaixa del preu
o a la resolució del contracte. Un exemplar de segona mà no es considera no conforme per
desgastos propis de l'ús que ja constin en l'estat indicat a la fitxa. Contacta'ns a
<a href="mailto:{email}">{email}</a> indicant el número de comanda.</p>

<h2>Reclamacions</h2>
<p>Disposem de fulls de reclamacions a la botiga. També pots adreçar-te a l'Agència
Catalana del Consum o als mecanismes de resolució alternativa de conflictes de consum.
Per a qualsevol queixa, escriu-nos primer a <a href="mailto:{email}">{email}</a>.</p>

<h2>Protecció de dades</h2>
<p>Vegeu la <a href="/privacitat">política de privacitat</a>.</p>
""".strip()


PAGES = (
    ("avis-legal", "Avís legal", AVIS_LEGAL_TEMPLATE, 89),
    ("privacitat", "Política de privacitat", PRIVACITAT_TEMPLATE, 90),
    ("termes", "Termes d'ús", TERMES_TEMPLATE, 91),
    ("cookies", "Política de cookies", COOKIES_TEMPLATE, 92),
    ("condicions-venda", "Condicions de venda", CONDICIONS_VENDA_TEMPLATE, 93),
)


def _val(value: str | None) -> str:
    return html.escape(value.strip()) if value and value.strip() else PENDENT


def seed(db, tenant_id, overwrite: bool = False) -> list[str]:
    """Importable desde routers/superadmin.py (alta de tenant) además del
    CLI de abajo. Sin `overwrite`, las páginas que ya existen no se tocan."""
    config = db.scalar(select(ConfiguracioBotiga))
    ctx = dict(
        nom=_val(config.fiscal_name if config else None),
        nif=_val(config.nif if config else None),
        adreca=_val(config.address.replace("\n", ", ") if config and config.address else None),
        email=_val(config.contact_email if config else None),
        telefon=_val(config.phone if config else None),
    )

    result = []
    for slug, name, template, position in PAGES:
        data = dict(
            slug=slug, name=name, type="estatica", position=position, menu_visible=False,
            content=template.format(**ctx),
        )
        pagina = db.scalar(select(Pagina).where(Pagina.slug == slug))
        if pagina is None:
            db.add(Pagina(**data))
            result.append(f"Creada: /{slug}")
        elif overwrite:
            for k, v in data.items():
                setattr(pagina, k, v)
            result.append(f"Reescrita: /{slug}")
        else:
            result.append(f"Ja existeix (no es toca): /{slug}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", required=True, help="Slug del tenant (ver tabla tenants)")
    parser.add_argument("--overwrite", action="store_true", help="Reescriu també les pàgines que ja existeixen")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant))
        if tenant is None:
            raise SystemExit(f"No existe ningún tenant con slug '{args.tenant}'")
        with scoped_to(db, tenant.id):
            for line in seed(db, tenant.id, overwrite=args.overwrite):
                print(line)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
