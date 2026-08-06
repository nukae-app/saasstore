"""Parser de fitxers bancaris: format N43 (AEB 43, estàndard espanyol) i CSV genèric.

N43: cada línia comença pel tipus de registre (11=capçalera, 22=moviment, 33=peu).
CSV genèric: columnes data_operacio,data_valor,concepte,import,saldo (saldo opcional).
"""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class MovimentParsejat:
    data_operacio: date
    data_valor: date | None
    concepte: str
    import_moviment: Decimal   # positiu = ingrés, negatiu = despesa
    saldo: Decimal | None


def _parse_date_n43(s: str) -> date:
    """AAMMDD → date."""
    year = 2000 + int(s[0:2])
    month = int(s[2:4])
    day = int(s[4:6])
    return date(year, month, day)


def _parse_amount_n43(sign_char: str, amount_str: str) -> Decimal:
    """
    sign_char: '1'=credit (ingrés +), '2'=debit (despesa -)
    amount_str: 14 dígits sense separador, 2 decimals implícits.
    """
    value = Decimal(amount_str.strip()) / 100
    return value if sign_char == "1" else -value


def parse_n43(content: str) -> list[MovimentParsejat]:
    """Parseja un fitxer N43 (AEB 43) i retorna la llista de moviments."""
    moviments: list[MovimentParsejat] = []
    current: dict | None = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\r\n")
        if len(line) < 2:
            continue
        record_type = line[0:2]

        if record_type == "22":
            # Guardem el moviment anterior si hi havia concepte pendent
            if current is not None:
                moviments.append(MovimentParsejat(**current))
            # Registre de moviment:
            # [0:2]=tipus [2:8]=data_op [8:14]=data_val [14:18]=codi_op
            # [18]=signe(1=credit,2=debit) [19:33]=import14dig [33:53]=concepte1 [53:80]=ref
            data_op = _parse_date_n43(line[2:8])
            data_val = _parse_date_n43(line[8:14]) if len(line) >= 14 else None
            sign = line[18] if len(line) > 18 else "1"
            amount_str = line[19:33].strip() if len(line) >= 33 else "0"
            concepte_part1 = line[33:53].strip() if len(line) >= 53 else ""
            current = {
                "data_operacio": data_op,
                "data_valor": data_val,
                "concepte": concepte_part1,
                "import_moviment": _parse_amount_n43(sign, amount_str.zfill(14)),
                "saldo": None,
            }

        elif record_type == "23" and current is not None:
            # Registre de concepte ampliat: afegim la descripció
            extra = line[2:42].strip()
            if extra:
                sep = " — " if current["concepte"] else ""
                current["concepte"] = current["concepte"] + sep + extra

        elif record_type == "33":
            if current is not None:
                moviments.append(MovimentParsejat(**current))
                current = None
            # Saldo final al peu: [20:34]=saldo, [18]= signe
            if len(line) >= 34:
                sign = line[18] if len(line) > 18 else "1"
                saldo_str = line[20:34].strip().zfill(14)
                saldo = _parse_amount_n43(sign, saldo_str)
                if moviments:
                    moviments[-1].saldo = saldo

    if current is not None:
        moviments.append(MovimentParsejat(**current))

    return moviments


def parse_csv_generic(content: str) -> list[MovimentParsejat]:
    """
    CSV genèric amb les columnes (amb o sense capçalera):
        data_operacio, data_valor (opcional), concepte, import, saldo (opcional)

    L'import ha de ser numèric: positiu = ingrés, negatiu = despesa.
    Accepta separadors de coma o punt i coma.
    """
    # Detecta separador
    sep = ";" if content.count(";") > content.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=sep)

    # Normalitza noms de columna (minúscules, sense espais)
    def norm(k: str) -> str:
        return k.strip().lower().replace(" ", "_").replace("-", "_")

    moviments: list[MovimentParsejat] = []
    for row in reader:
        nrow = {norm(k): v.strip() for k, v in row.items() if k}

        # data_operacio: accepta YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
        raw_date = nrow.get("data_operacio") or nrow.get("data") or nrow.get("fecha") or ""
        data_op = _parse_date_flexible(raw_date)
        if data_op is None:
            continue

        raw_val = nrow.get("data_valor") or nrow.get("valor") or ""
        data_val = _parse_date_flexible(raw_val) if raw_val else None

        concepte = nrow.get("concepte") or nrow.get("concepto") or nrow.get("descripcion") or ""
        import_str = nrow.get("import") or nrow.get("importe") or nrow.get("amount") or "0"
        saldo_str = nrow.get("saldo") or nrow.get("balance") or ""

        try:
            import_val = Decimal(import_str.replace(",", ".").replace(" ", ""))
        except Exception:
            continue

        saldo = None
        if saldo_str:
            try:
                saldo = Decimal(saldo_str.replace(",", ".").replace(" ", ""))
            except Exception:
                pass

        moviments.append(MovimentParsejat(
            data_operacio=data_op,
            data_valor=data_val,
            concepte=concepte,
            import_moviment=import_val,
            saldo=saldo,
        ))

    return moviments


def _parse_date_flexible(s: str) -> date | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y%m%d"):
        try:
            from datetime import datetime as dt
            return dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
