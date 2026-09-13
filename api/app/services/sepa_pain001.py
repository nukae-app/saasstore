"""Generador del fitxer SEPA pain.001.001.03 (transferència/crèdit — per
PAGAR a proveïdors, no confondre amb el pain.008 de domiciliació que
quedaria per COBRAR quotes, ver docs/PLAN_COBRAMENTS_PAGAMENTS.md).

NOMÉS genera el XML — mai el puja ni l'envia a cap banc (això seria un
servei PISP, mateixa paret regulatòria que l'AISP descartat per a la
conciliació automàtica). L'estàndard ISO 20022 en si és un format
internacional fix, no una interpretació legal com el Model 200 o VeriFactu
— però NO s'ha pogut verificar aquesta implementació contra un banc real:
prova-la amb un fitxer real al portal del teu banc abans de confiar-hi en
producció, com amb qualsevol integració nova d'aquest projecte.
"""

import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

PAIN001_NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"

# Charset SEPA (EPC): lletres sense accent, dígits, espai, i aquests signes.
# Qualsevol altre caràcter (accents, ñ, &, %...) es transllitera o es treu —
# molts bancs rebutgen el fitxer sencer si hi troben un caràcter fora d'això.
_SEPA_ALLOWED_EXTRA = set("/-?:().,'+ ")


def _sepa_text(value: str, max_len: int) -> str:
    """Transllitera a ASCII (NFKD + descartar diacrítics) i filtra qualsevol
    caràcter fora del charset SEPA, retallant a `max_len`."""
    normalitzat = unicodedata.normalize("NFKD", value)
    ascii_ = normalitzat.encode("ascii", "ignore").decode("ascii")
    net = "".join(c for c in ascii_ if c.isalnum() or c in _SEPA_ALLOWED_EXTRA)
    net = " ".join(net.split())  # col·lapsa espais múltiples que hagi deixat el filtrat
    return net[:max_len] or "NA"


def generate_end_to_end_id(remesa_number: str, position: int) -> str:
    """Identificador de la transacció SEPA (Max35Text, charset SEPA) —
    únic dins de la remesa, prou curt per no passar-se dels 35 caràcters
    encara amb remeses de número alt."""
    return _sepa_text(f"REM{remesa_number}-{position:04d}", 35)


@dataclass(frozen=True)
class Pain001Linia:
    end_to_end_id: str
    amount: Decimal
    creditor_name: str
    creditor_iban: str
    remittance_info: str


def build_pain001_xml(
    *,
    remesa_number: str,
    execution_date: date,
    created_at: datetime,
    debtor_name: str,
    debtor_iban: str,
    debtor_bic: str | None,
    lines: list[Pain001Linia],
) -> str:
    """`lines` no pot ser buida (una remesa sense línies no té sentit crear-
    la, ver validació a l'endpoint). El BIC (`debtor_bic`) és opcional des
    de 2016 per a transferències SEPA dins la UE/EEE — si no es coneix
    s'informa `NOTPROVIDED`, tal com permet l'esquema (`Othr/Id`)."""
    if not lines:
        raise ValueError("Una remesa de pagament ha de tenir com a mínim una línia")

    msg_id = _sepa_text(f"MSG-{remesa_number}-{uuid.uuid4().hex[:8]}", 35)
    pmt_inf_id = _sepa_text(f"PMT-{remesa_number}", 35)
    ctrl_sum = sum((l.amount for l in lines), Decimal("0.00"))

    doc = Element("Document", {
        "xmlns": PAIN001_NAMESPACE,
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    })
    cstmr = SubElement(doc, "CstmrCdtTrfInitn")

    grp_hdr = SubElement(cstmr, "GrpHdr")
    SubElement(grp_hdr, "MsgId").text = msg_id
    SubElement(grp_hdr, "CreDtTm").text = created_at.strftime("%Y-%m-%dT%H:%M:%S")
    SubElement(grp_hdr, "NbOfTxs").text = str(len(lines))
    SubElement(grp_hdr, "CtrlSum").text = f"{ctrl_sum:.2f}"
    initg_pty = SubElement(grp_hdr, "InitgPty")
    SubElement(initg_pty, "Nm").text = _sepa_text(debtor_name, 70)

    pmt_inf = SubElement(cstmr, "PmtInf")
    SubElement(pmt_inf, "PmtInfId").text = pmt_inf_id
    SubElement(pmt_inf, "PmtMtd").text = "TRF"
    SubElement(pmt_inf, "BtchBookg").text = "true"
    SubElement(pmt_inf, "NbOfTxs").text = str(len(lines))
    SubElement(pmt_inf, "CtrlSum").text = f"{ctrl_sum:.2f}"
    pmt_tp_inf = SubElement(pmt_inf, "PmtTpInf")
    SubElement(SubElement(pmt_tp_inf, "SvcLvl"), "Cd").text = "SEPA"
    SubElement(pmt_inf, "ReqdExctnDt").text = execution_date.isoformat()

    dbtr = SubElement(pmt_inf, "Dbtr")
    SubElement(dbtr, "Nm").text = _sepa_text(debtor_name, 70)
    dbtr_acct = SubElement(pmt_inf, "DbtrAcct")
    SubElement(SubElement(dbtr_acct, "Id"), "IBAN").text = debtor_iban.replace(" ", "")
    dbtr_agt = SubElement(pmt_inf, "DbtrAgt")
    fin_instn_dbtr = SubElement(dbtr_agt, "FinInstnId")
    if debtor_bic:
        SubElement(fin_instn_dbtr, "BIC").text = debtor_bic.replace(" ", "")
    else:
        SubElement(SubElement(fin_instn_dbtr, "Othr"), "Id").text = "NOTPROVIDED"
    SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    for linia in lines:
        tx = SubElement(pmt_inf, "CdtTrfTxInf")
        pmt_id = SubElement(tx, "PmtId")
        SubElement(pmt_id, "EndToEndId").text = linia.end_to_end_id
        amt = SubElement(tx, "Amt")
        SubElement(amt, "InstdAmt", {"Ccy": "EUR"}).text = f"{linia.amount:.2f}"
        cdtr_agt = SubElement(tx, "CdtrAgt")
        SubElement(SubElement(SubElement(cdtr_agt, "FinInstnId"), "Othr"), "Id").text = "NOTPROVIDED"
        cdtr = SubElement(tx, "Cdtr")
        SubElement(cdtr, "Nm").text = _sepa_text(linia.creditor_name, 70)
        cdtr_acct = SubElement(tx, "CdtrAcct")
        SubElement(SubElement(cdtr_acct, "Id"), "IBAN").text = linia.creditor_iban.replace(" ", "")
        rmt_inf = SubElement(tx, "RmtInf")
        SubElement(rmt_inf, "Ustrd").text = _sepa_text(linia.remittance_info, 140)

    xml_bytes = tostring(doc, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
