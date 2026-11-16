#!/usr/bin/env python3
"""Auditoria de CBS/IBS (Reforma Tributária do Consumo - LC 214/2025).

Reproduz as regras das calculadoras oficiais da Receita Federal
(calculadora-rtc-regime-regular e calculadora-rtc-simples-nacional) sobre a
base oficial de dados (data/rtc.db) e confere valores declarados em documentos
fiscais (NF-e, NFS-e ou JSON normalizado).

Uso:
  rtc.py consultar cclasstrib 200028 [--data 2027-01-01]
  rtc.py consultar cst 200 [--data ...]
  rtc.py consultar ncm 10063021 [--data ...]
  rtc.py consultar nbs 122011200 [--data ...]
  rtc.py consultar busca "construção" [--data ...]
  rtc.py validar entrada.json [--json]
  rtc.py validar --nfse nota.xml [--json]
  rtc.py validar --nfe nota.xml [--json]
  rtc.py extrair --nfse nota.xml      (só converte o XML para o JSON normalizado)
"""
import argparse
import ast
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rtc.db"
TRIBUTOS = {2: "CBS", 3: "IBSUF", 4: "IBSMun"}
TOL_MOEDA = Decimal("0.01")
Q8 = Decimal("0.00000001")
Q2 = Decimal("0.01")
# Tratamentos com monofasia/ajuste: a calculadora oficial não calcula
# (CAL-007) ou usa constantes provisórias; só fazemos checagens estruturais.
TRATAMENTOS_NAO_CALCULADOS = {23, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36, 37, 41, 42}


# ───────────────────────── utilidades numéricas ─────────────────────────
def D(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", ".")) if not isinstance(v, Decimal) else v
    except InvalidOperation:
        return None


def q8(v):
    return v.quantize(Q8, ROUND_HALF_EVEN)


def moeda(v):
    return None if v is None else v.quantize(Q2, ROUND_HALF_EVEN)


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, Decimal):
        s = format(v, "f")
        if "." in s:
            inteiro, dec = s.split(".")
            dec = dec.rstrip("0").ljust(2, "0")
            return f"{inteiro}.{dec}"
        return s + ".00"
    return str(v)


def casas(v):
    s = str(v)
    return len(s.split(".")[1]) if "." in s else 0


def tol_aliquota(declarado):
    return Decimal(5) * Decimal(10) ** (-(casas(declarado) + 1)) + Decimal("0.0001")


class Avaliador(ast.NodeVisitor):
    """Avaliador aritmético restrito (equivalente ao JexlSandbox da calculadora)."""

    def __init__(self, vars_):
        self.v = vars_

    def visit_Expression(self, n):
        return self.visit(n.body)

    def visit_BinOp(self, n):
        a, b = self.visit(n.left), self.visit(n.right)
        if isinstance(n.op, ast.Add):
            return a + b
        if isinstance(n.op, ast.Sub):
            return a - b
        if isinstance(n.op, ast.Mult):
            return q8(a * b)
        if isinstance(n.op, ast.Div):
            return q8(a / b) if b != 0 else Decimal(0)
        raise ValueError("operador não permitido")

    def visit_UnaryOp(self, n):
        x = self.visit(n.operand)
        return -x if isinstance(n.op, ast.USub) else x

    def visit_Constant(self, n):
        return Decimal(str(n.value))

    def visit_Name(self, n):
        x = self.v.get(n.id)
        return Decimal(0) if x is None else x

    def generic_visit(self, n):
        raise ValueError(f"elemento não permitido: {type(n).__name__}")


def avaliar(expr, vars_):
    if expr is None or str(expr).strip() == "":
        return None
    return q8(Avaliador(vars_).visit(ast.parse(str(expr), mode="eval")))


# ───────────────────────────── base oficial ─────────────────────────────
class Base:
    def __init__(self, path=DB_PATH):
        if not Path(path).exists():
            sys.exit(f"Base não encontrada em {path}. Rode scripts/atualizar_base.py.")
        self.c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.c.row_factory = sqlite3.Row

    def q(self, sql, *p):
        return self.c.execute(sql, p).fetchall()

    def q1(self, sql, *p):
        r = self.c.execute(sql, p).fetchone()
        return r

    @staticmethod
    def vig(prefix):
        return f"{prefix}_INICIO_VIGENCIA <= :d AND ({prefix}_FIM_VIGENCIA IS NULL OR {prefix}_FIM_VIGENCIA >= :d)"

    def versao(self):
        r = self.q1("SELECT * FROM VERSAO_BASE_DADO ORDER BY rowid DESC LIMIT 1")
        return dict(r) if r else {}

    def cst(self, cod, d):
        """CST vigente vinculado à CBS/IBS."""
        return self.c.execute(
            f"""SELECT s.* FROM SITUACAO_TRIBUTARIA s
                JOIN TRIBUTO_SITUACAO_TRIBUTARIA t ON t.TRST_SITR_ID = s.SITR_ID AND t.TRST_TBTO_ID = 2
                WHERE s.SITR_CD = :c AND {self.vig('s.SITR')} AND {self.vig('t.TRST')}""",
            {"c": cod, "d": d}).fetchone()

    def cclasstrib(self, cod, d):
        """cClassTrib vigente de CBS/IBS (exclui as classificações do Imposto Seletivo)."""
        return self.c.execute(
            f"""SELECT c.*, s.SITR_CD FROM CLASSIFICACAO_TRIBUTARIA c
                JOIN SITUACAO_TRIBUTARIA s ON s.SITR_ID = c.CLTR_SITR_ID
                JOIN TRIBUTO_SITUACAO_TRIBUTARIA t ON t.TRST_SITR_ID = s.SITR_ID AND t.TRST_TBTO_ID = 2
                WHERE c.CLTR_CD = :c AND {self.vig('c.CLTR')}""",
            {"c": cod, "d": d}).fetchone()

    def tratamento(self, cltr_id, d):
        return self.c.execute(
            f"""SELECT tt.* FROM TRATAMENTO_CLASSIFICACAO tc
                JOIN TRATAMENTO_TRIBUTARIO tt ON tt.TRTR_ID = tc.TRCL_TRTR_ID
                WHERE tc.TRCL_CLTR_ID = :i AND {self.vig('tc.TRCL')}""",
            {"i": cltr_id, "d": d}).fetchone()

    def reducao(self, cltr_id, tbto, d):
        r = self.c.execute(
            f"SELECT PERE_VALOR FROM PERCENTUAL_REDUCAO WHERE PERE_CLTR_ID=:i AND PERE_TBTO_ID=:t AND {self.vig('PERE')}",
            {"i": cltr_id, "t": tbto, "d": d}).fetchone()
        return D(r[0]) if r else None

    def aliq_referencia(self, tbto, d):
        r = self.c.execute(
            f"SELECT ALRE_VALOR FROM ALIQUOTA_REFERENCIA WHERE ALRE_TBTO_ID=:t AND {self.vig('ALRE')}",
            {"t": tbto, "d": d}).fetchone()
        return D(r[0]) if r else None

    def aliq_ad_valorem(self, cltr_id, tbto, d):
        r = self.c.execute(
            f"SELECT AADV_VALOR FROM ALIQUOTA_AD_VALOREM WHERE AADV_CLTR_ID=:i AND AADV_TBTO_ID=:t AND {self.vig('AADV')}",
            {"i": cltr_id, "t": tbto, "d": d}).fetchone()
        return D(r[0]) if r and r[0] is not None else None

    def tipos_dfe(self, cltr_id, d):
        return [r[0] for r in self.c.execute(
            f"""SELECT t.TPDF_TIPO FROM TIPO_DFE_CLASSIFICACAO x JOIN TIPO_DFE t ON t.TPDF_ID = x.TDCL_TPDF_ID
                WHERE x.TDCL_CLTR_ID = :i AND {self.vig('x.TDCL')}""", {"i": cltr_id, "d": d})]

    def ncm_vinculada(self, ncm, cltr_id, d):
        tem_anexo = self.c.execute(
            f"SELECT 1 FROM NCM_APLICAVEL WHERE NCMA_CLTR_ID=:i AND {self.vig('NCMA')} LIMIT 1",
            {"i": cltr_id, "d": d}).fetchone()
        if not tem_anexo:
            return None
        ok = self.c.execute(
            f"""SELECT 1 FROM NCM_APLICAVEL n
                WHERE n.NCMA_CLTR_ID=:i AND n.NCMA_NCM_CD = substr(:n,1,length(n.NCMA_NCM_CD)) AND {self.vig('n.NCMA')}
                AND NOT EXISTS (SELECT 1 FROM EXCECAO_NCM_APLICAVEL e WHERE e.ENCM_NCMA_ID = n.NCMA_ID
                    AND e.ENCM_NCM_CD = substr(:n,1,length(e.ENCM_NCM_CD)) AND {self.vig('e.ENCM')}) LIMIT 1""",
            {"i": cltr_id, "n": ncm, "d": d}).fetchone()
        return bool(ok)

    def nbs_vinculada(self, nbs, cltr_id, d):
        tem_anexo = self.c.execute(
            f"SELECT 1 FROM NBS_APLICAVEL WHERE NBSA_CLTR_ID=:i AND {self.vig('NBSA')} LIMIT 1",
            {"i": cltr_id, "d": d}).fetchone()
        if not tem_anexo:
            return None
        ok = self.c.execute(
            f"""SELECT 1 FROM NBS_APLICAVEL WHERE NBSA_CLTR_ID=:i
                AND NBSA_NBS_CD = substr(:n,1,length(NBSA_NBS_CD)) AND {self.vig('NBSA')} LIMIT 1""",
            {"i": cltr_id, "n": nbs, "d": d}).fetchone()
        return bool(ok)

    def combinacao_nfse(self, nbs, cclass, cindop, ctribnac, d):
        """Combinações NBS × cClassTrib × cIndOp × item LC 116 (validação oficial da NFS-e)."""
        rows = self.c.execute(
            f"""SELECT c.CNIL_LSLC_CD lc, io.IOIC_CD cindop, ct.CLTR_CD cclass FROM CLASSIF_NBS_INDOP_LC c
                JOIN CLASSIFICACAO_TRIBUTARIA ct ON ct.CLTR_ID = c.CNIL_CLTR_ID
                JOIN INDICADOR_OPERACAO_IBS_CBS io ON io.IOIC_ID = c.CNIL_IOIC_ID
                WHERE c.CNIL_NBS_CD = :n AND {self.vig('c.CNIL')}""", {"n": nbs, "d": d}).fetchall()
        lc = formatar_ctribnac(ctribnac)
        # cTribNac de 6 dígitos (item.subitem.desdobramento) casa com o subitem da LC 116 na base.
        casa_lc = lambda r: lc is None or r["lc"] == lc or lc.startswith(r["lc"] + ".")
        exato = [r for r in rows if r["cclass"] == cclass and r["cindop"] == cindop and casa_lc(r)]
        return exato, rows

    def redutor_compra_gov(self, d):
        r = self.c.execute(f"SELECT RCGO_VALOR FROM REDUTOR_COMPRA_GOVERNAMENTAL WHERE {self.vig('RCGO')}", {"d": d}).fetchone()
        return D(r[0]) if r else Decimal(0)


def formatar_ctribnac(c):
    """Converte cTribNac (ex.: 070201) no item da LC 116 usado na base (7.02.01)."""
    if not c:
        return None
    c = str(c).strip()
    if "." in c:
        return c
    if len(c) == 4:
        return f"{int(c[:2])}.{c[2:4]}"
    if len(c) == 6:
        return f"{int(c[:2])}.{c[2:4]}.{c[4:6]}"
    return None


# ───────────────────────────── relatório ─────────────────────────────
class Relatorio:
    def __init__(self):
        self.itens = []
        self.gerais = []

    def novo_item(self, numero):
        it = {"numero": numero, "checagens": []}
        self.itens.append(it)
        return it

    @staticmethod
    def add(alvo, status, regra, detalhe, esperado=None, declarado=None, codigo=None):
        alvo["checagens"].append({
            "status": status, "regra": regra, "detalhe": detalhe,
            "esperado": fmt(esperado) if esperado is not None else None,
            "declarado": fmt(declarado) if declarado is not None else None,
            "codigo": codigo})

    def resumo(self):
        cont = {}
        for alvo in self.itens + self.gerais:
            for c in alvo["checagens"]:
                cont[c["status"]] = cont.get(c["status"], 0) + 1
        return cont


def comparar_moeda(alvo, regra, esperado, declarado, codigo=None, detalhe=""):
    if declarado is None:
        Relatorio.add(alvo, "ALERTA", regra, f"valor não declarado no documento. {detalhe}".strip(), moeda(esperado))
        return
    if esperado is None:
        Relatorio.add(alvo, "NAO_VERIFICADO", regra, detalhe or "sem valor esperado", None, declarado)
        return
    dif = abs(moeda(esperado) - declarado)
    st = "OK" if dif <= TOL_MOEDA else "DIVERGENTE"
    Relatorio.add(alvo, st, regra, (detalhe + (f" diferença {fmt(dif)}" if st != "OK" else "")).strip(),
                  moeda(esperado), declarado, codigo if st != "OK" else None)


def comparar_aliq(alvo, regra, esperado, declarado, codigo=None, detalhe=""):
    if declarado is None:
        Relatorio.add(alvo, "ALERTA", regra, f"alíquota não declarada. {detalhe}".strip(), esperado)
        return
    if esperado is None:
        Relatorio.add(alvo, "NAO_VERIFICADO", regra, detalhe or "sem valor esperado", None, declarado)
        return
    st = "OK" if abs(esperado - declarado) <= tol_aliquota(declarado) else "DIVERGENTE"
    Relatorio.add(alvo, st, regra, detalhe, esperado.quantize(Decimal("0.0001"), ROUND_HALF_EVEN), declarado,
                  codigo if st != "OK" else None)


# ───────────────────────────── bases de cálculo ─────────────────────────────
ELEMENTOS_NFE = [  # tag, operação, natureza (None = ambas), ano início, ano fim, modelos
    ("vProd", +1, None, 2026, 2033, {55, 65}), ("vFrete", +1, None, 2026, 2033, {55, 65}),
    ("vSeg", +1, None, 2026, 2033, {55, 65}), ("vOutro", +1, None, 2026, 2033, {55, 65}),
    ("vII", +1, "bem", 2026, 2033, {55}), ("vIS", +1, None, 2027, 2033, {55, 65}),
    ("vDesc", -1, None, 2026, 2033, {55, 65}), ("vPIS", -1, None, 2026, 2026, {55, 65}),
    ("vCOFINS", -1, None, 2026, 2026, {55, 65}), ("vICMS", -1, "bem", 2026, 2032, {55, 65}),
    ("vICMSUFDest", -1, "bem", 2026, 2032, {55}), ("vFCP", -1, "bem", 2026, 2032, {55, 65}),
    ("vFCPUFDest", -1, "bem", 2026, 2032, {55}), ("vICMSMono", -1, "bem", 2026, 2032, {55, 65}),
    ("vISSQN", -1, "servico", 2026, 2032, {55, 65}),
]


def base_nfe(comp, ano, natureza, modelo, avisos):
    total = Decimal(0)
    for tag, op, nat, ini, fim, mods in ELEMENTOS_NFE:
        v = D(comp.get(tag))
        if not v:
            continue
        if not (ini <= ano <= fim) or (nat and nat != natureza) or modelo not in mods:
            avisos.append(f"{tag} não compõe a base em {ano}/{natureza}/modelo {modelo} e foi ignorado")
            continue
        total += op * v
    return q8(total)


def base_nfse(comp, ano, avisos):
    """vBC IBS/CBS da NFS-e: vServ - vDescIncond - vCalcReeRepRes - vCalcDedRedIBSCBS - ISS - PIS - COFINS."""
    v = lambda k: D(comp.get(k)) or Decimal(0)
    pis, cofins, iss = v("vPIS"), v("vCOFINS"), v("vISSQN")
    if ano >= 2027 and (pis or cofins):
        avisos.append("PIS/COFINS informados a partir de 2027 (extintos): não deduzidos")
        pis = cofins = Decimal(0)
    if ano >= 2033 and iss:
        avisos.append("ISSQN informado a partir de 2033 (extinto): não deduzido")
        iss = Decimal(0)
    return q8(v("vServ") - v("vDescIncond") - v("vCalcReeRepRes") - v("vCalcDedRedIBSCBS") - iss - pis - cofins)


# ───────────────────────────── regime regular ─────────────────────────────
def aliquota_nominal(base, cl, tbto, d, ano, declarado, informada):
    """Retorna (alíquota nominal esperada em %, origem)."""
    tipo = "Padrão" if cl["CLTR_CD"] == "510001" else cl["CLTR_TIPO_ALIQUOTA"]
    if tipo in ("Fixa", "Uniforme setorial"):
        v = base.aliq_ad_valorem(cl["CLTR_ID"], tbto, d)
        if v is not None:
            return v, f"alíquota {tipo.lower()} da base oficial"
    if tipo == "Sem alíquota" and informada is None:
        return Decimal(0), "cClassTrib sem alíquota"
    if informada is not None:
        return informada, "alíquota nominal informada"
    if ano <= 2026:
        return base.aliq_referencia(tbto, d), "alíquota de referência 2026 (ano-teste)"
    # A partir de 2027 a calculadora exige alíquotas informadas (REG-037):
    # a nominal declarada é aceita e só a consistência é verificada.
    return declarado, "nominal declarada (a partir de 2027 a alíquota não vem da base)"


def validar_item_regular(base, rel, op, item, d, ano):
    it = rel.novo_item(item.get("numero"))
    add = lambda *a, **k: Relatorio.add(it, *a, **k)
    decl = item.get("declarado", {})
    cst_cd, cc = str(item.get("CST", "")).zfill(3), str(item.get("cClassTrib", ""))
    tpdoc = int(op.get("tpDoc") or 0)

    cst = base.cst(cst_cd, d)
    if not cst:
        add("DIVERGENTE", "CST", f"CST {cst_cd} inexistente ou fora de vigência em {d}", codigo="REG-004")
        return
    add("OK", "CST", f"{cst_cd} - {cst['SITR_DESCRICAO']}")
    cl = base.cclasstrib(cc, d)
    if not cl:
        add("DIVERGENTE", "cClassTrib", f"{cc} inexistente ou fora de vigência em {d}", codigo="REG-005")
        return
    if cl["SITR_CD"] != cst_cd:
        add("DIVERGENTE", "cClassTrib × CST", f"{cc} pertence ao CST {cl['SITR_CD']}, não ao {cst_cd}",
            cl["SITR_CD"], cst_cd, "REG-006")
        return
    add("OK", "cClassTrib", f"{cc} - {cl['CLTR_DESCRICAO'][:120]}")

    if tpdoc:
        tipos = base.tipos_dfe(cl["CLTR_ID"], d)
        if tipos and tpdoc not in tipos:
            add("DIVERGENTE", "cClassTrib × tipo de documento",
                f"{cc} não é admitido no documento modelo {tpdoc} (admitidos: {sorted(tipos)})", codigo="REG-029")
        elif tipos:
            add("OK", "cClassTrib × tipo de documento", f"modelo {tpdoc} admitido")

    ncm, nbs = item.get("ncm"), item.get("nbs")
    if ncm and nbs:
        add("DIVERGENTE", "Nomenclatura", "NCM e NBS informadas no mesmo item", codigo="REG-001")
    if ncm:
        r = base.ncm_vinculada(str(ncm), cl["CLTR_ID"], d)
        if r is False:
            add("DIVERGENTE", "NCM × cClassTrib", f"NCM {ncm} não consta do anexo do cClassTrib {cc}", codigo="REG-011")
        elif r:
            add("OK", "NCM × cClassTrib", f"NCM {ncm} vinculada ao anexo")
    if nbs:
        r = base.nbs_vinculada(str(nbs), cl["CLTR_ID"], d)
        if r is False:
            add("DIVERGENTE", "NBS × cClassTrib", f"NBS {nbs} não consta do anexo do cClassTrib {cc}", codigo="REG-012")
        elif r:
            add("OK", "NBS × cClassTrib", f"NBS {nbs} vinculada ao anexo")
        if item.get("cIndOp"):
            exato, rows = base.combinacao_nfse(str(nbs), cc, str(item["cIndOp"]), item.get("cTribNac"), d)
            if exato:
                add("OK", "NBS × cClassTrib × cIndOp × LC116", "combinação válida na tabela oficial")
            elif rows:
                sug = sorted({f"{r['cclass']}/cIndOp {r['cindop']}/LC {r['lc']}" for r in rows})[:8]
                st = "ALERTA" if cc == "000001" else "DIVERGENTE"
                obs = (" A calculadora usa 000001 como padrão quando não há classificação específica; "
                       "confirme se a operação não se enquadra numa das classificações listadas.") if cc == "000001" else ""
                add(st, "NBS × cClassTrib × cIndOp × LC116",
                    f"combinação não cadastrada. Válidas para a NBS: {'; '.join(sug)}.{obs}")
            else:
                add("ALERTA", "NBS × cClassTrib × cIndOp × LC116", "NBS sem combinações cadastradas na data")

    tt = base.tratamento(cl["CLTR_ID"], d)
    if not tt:
        add("DIVERGENTE", "Tratamento tributário", "sem tratamento vigente para o cClassTrib", codigo="REG-008")
        return

    tem_grupo = bool(cst["SITR_IND_GIBSCBS"])
    valores_decl = [decl.get(k) for k in ("vCBS", "vIBSUF", "vIBSMun", "vBC")]
    if not tem_grupo:
        if any(D(v) for v in valores_decl):
            add("DIVERGENTE", "Grupo gIBSCBS", f"CST {cst_cd} não admite grupo gIBSCBS, mas há valores destacados")
        else:
            add("OK", "Grupo gIBSCBS", f"CST {cst_cd} sem grupo de cálculo, nada destacado")
        return
    if tt["TRTR_ID"] in TRATAMENTOS_NAO_CALCULADOS or cst["SITR_IND_GIBSCBSMONO"]:
        add("NAO_VERIFICADO", "Cálculo", f"tratamento '{tt['TRTR_DESCRICAO']}' (monofasia/ajuste/alíquota fixa com ajuste) "
            "não é calculado pela calculadora oficial; conferir manualmente", codigo="CAL-007")

    # Base de cálculo
    avisos = []
    comp = item.get("componentesBase")
    v_is = D(item.get("vIS")) or Decimal(0)
    if comp:
        if op.get("documento", "").upper().startswith("NFS"):
            bc_inf = base_nfse(comp, ano, avisos)
        else:
            bc_inf = base_nfe(comp, ano, item.get("natureza", "bem"), tpdoc or 55, avisos)
    else:
        bc_inf = D(decl.get("vBC"))
    for a in avisos:
        add("ALERTA", "Base de cálculo", a)
    vars_ = {"baseCalculoInformada": bc_inf, "impostoSeletivoInformado": v_is,
             "impostoSeletivoCalculado": v_is, "quantidade": D(item.get("quantidade"))}
    bc = avaliar(tt["TRTR_EXPRESSAO_BASE_CALCULO"], vars_) if bc_inf is not None else None
    if bc is not None and bc < 0:
        bc = Decimal(0)
    if comp:
        comparar_moeda(it, "vBC", bc, D(decl.get("vBC")), "REG-034", "base recalculada dos componentes.")
    elif bc is None:
        add("NAO_VERIFICADO", "vBC", "sem vBC nem componentes para recalcular")
        return
    else:
        if tt["TRTR_ID"] in (17, 40):
            add("ALERTA", "vBC", "tratamento com redução/exclusão de base: informe componentesBase para conferir")
        add("OK", "vBC", "vBC declarado usado como base (sem componentes para recalcular)", declarado=D(decl.get("vBC")))
        bc = D(decl.get("vBC"))

    p_red_gov = D(op.get("pRedutorCompraGov"))
    if op.get("tpEnteGov") and p_red_gov is None:
        p_red_gov = base.redutor_compra_gov(d)
    exige_desoneracao = bool(tt["TRTR_IN_EXIGE_GRUPO_DESONERACAO"])
    reg = item.get("tributacaoRegular") or {}
    if exige_desoneracao and not reg:
        add("DIVERGENTE", "gTribRegular", "tratamento exige grupo de tributação regular (gTribRegular) e ele não foi informado",
            codigo="REG-009")
    if reg and not exige_desoneracao:
        add("DIVERGENTE", "gTribRegular", "gTribRegular informado para CST/cClassTrib que não o exige", codigo="REG-022")

    informadas = item.get("aliquotasNominais") or {}
    total_ibs = Decimal(0)
    for tbto, nome in TRIBUTOS.items():
        p_decl, red_decl = D(decl.get(f"p{nome}")), D(decl.get(f"pRed{nome}"))
        efet_decl, v_decl = D(decl.get(f"pAliqEfet{nome}")), D(decl.get(f"v{nome}"))
        red = base.reducao(cl["CLTR_ID"], tbto, d) if tt["TRTR_IN_POSSUI_PERCENTUAL_REDUCAO"] else None
        nominal, origem = aliquota_nominal(base, cl, tbto, d, ano, p_decl, D(informadas.get(nome)))
        expr_aliq = tt["TRTR_EXPRESSAO_ALIQUOTA"]
        if D(informadas.get(nome)) is None and expr_aliq and expr_aliq.strip() == "0":
            nominal, origem = Decimal(0), f"alíquota zerada pelo tratamento '{tt['TRTR_DESCRICAO']}'"
        if exige_desoneracao:
            nominal, origem = Decimal(0), "grupo principal zerado (valores vão no gTribRegular)"
        if nominal is None:
            add("NAO_VERIFICADO", f"p{nome}", "alíquota nominal desconhecida")
            continue
        comparar_aliq(it, f"p{nome}", nominal, p_decl, detalhe=origem)
        if cst["SITR_IND_GRED"] and red is not None:
            comparar_aliq(it, f"pRedAliq {nome}", red, red_decl, codigo="CAL-010", detalhe="percentual de redução oficial")
        elif red_decl and red_decl > 0:
            add("DIVERGENTE", f"pRedAliq {nome}", f"CST {cst_cd} não admite grupo de redução (gRed)", 0, red_decl)
        vars_a = {"aliquota": nominal / 100, "percentualReducao": (red or Decimal(0)) / 100,
                  "pRedutorCompraGov": p_red_gov or Decimal(0)}
        efet = avaliar(tt["TRTR_EXPRESSAO_ALIQUOTA_EFETIVA"], vars_a)
        efet = vars_a["aliquota"] if efet is None else efet
        if cst["SITR_IND_GRED"] or p_red_gov:
            comparar_aliq(it, f"pAliqEfet {nome}", efet * 100, efet_decl,
                          detalhe="p × (1 − pRedAliq) × (1 − redutor compra gov.)")
        vtrib = avaliar(tt["TRTR_EXPRESSAO_TRIBUTO_CALCULADO"],
                        {"baseCalculo": bc, "aliquotaEfetiva": efet, "quantidade": vars_["quantidade"]})
        vdev = vtrib
        p_dif, v_dif_decl = D(decl.get(f"pDif{nome}")), D(decl.get(f"vDif{nome}"))
        if cst["SITR_IND_GDIF"]:
            if p_dif is None:
                add("ALERTA", f"Diferimento {nome}", "CST com diferimento sem pDif declarado; assumido 100% (padrão da base)")
                p_dif = Decimal(100)
            v_dif = q8(vtrib * p_dif / 100)
            comparar_moeda(it, f"vDif {nome}", v_dif, v_dif_decl, detalhe=f"vTributo × pDif ({fmt(p_dif)}%).")
            vdev = vtrib - v_dif
        comparar_moeda(it, f"v{nome}", vdev, v_decl, detalhe=f"vBC × alíquota efetiva{' − diferimento' if cst['SITR_IND_GDIF'] else ''}.")
        if tbto in (3, 4):
            total_ibs += moeda(vdev)
        if reg:
            p_reg_decl = D(reg.get(f"pAliqEfetReg{nome}"))
            v_reg_decl = D(reg.get(f"vTribReg{nome}"))
            if p_reg_decl is not None:
                comparar_moeda(it, f"vTribReg {nome}", q8(bc * p_reg_decl / 100), v_reg_decl,
                               detalhe="gTribRegular: vBC × pAliqEfetReg.")
    if reg and reg.get("cClassTribReg"):
        clr = base.cclasstrib(str(reg["cClassTribReg"]), d)
        if not clr:
            add("DIVERGENTE", "cClassTribReg", f"{reg['cClassTribReg']} inexistente/fora de vigência", codigo="REG-005")
        elif reg.get("CSTReg") and clr["SITR_CD"] != str(reg["CSTReg"]).zfill(3):
            add("DIVERGENTE", "cClassTribReg × CSTReg", f"{reg['cClassTribReg']} pertence ao CST {clr['SITR_CD']}", codigo="REG-006")
        else:
            add("OK", "cClassTribReg", f"{reg['cClassTribReg']} - {clr['CLTR_DESCRICAO'][:80]}")
    v_ibs_decl = D(decl.get("vIBS"))
    if v_ibs_decl is not None:
        comparar_moeda(it, "vIBS", total_ibs, v_ibs_decl, detalhe="vIBSUF + vIBSMun.")
    it["_calc"] = {"vBC": moeda(bc)}


# ───────────────────────────── Simples Nacional ─────────────────────────────
def validar_item_simples(base, rel, op, item, d):
    it = rel.novo_item(item.get("numero"))
    add = lambda *a, **k: Relatorio.add(it, *a, **k)
    decl = item.get("declarado", {})
    crt, tpreg = str(op.get("CRT", "")), str(op.get("tpRegimeIBSCBS") or "")
    if crt == "4" or (crt == "3" and tpreg != "2"):
        add("NAO_VERIFICADO", "Regime", "CRT fora do escopo do cálculo do Simples Nacional (MEI ou regime normal)")
        return
    regime = base.c.execute(
        f"""SELECT * FROM REGIME_APURACAO_SIMPLES_NACIONAL WHERE RASN_CRT = :c
            AND (RASN_TPREGIMEIBSCBS IS NULL OR RASN_TPREGIMEIBSCBS = '' OR RASN_TPREGIMEIBSCBS = :t) AND {Base.vig('RASN')}""",
        {"c": crt, "t": tpreg, "d": d}).fetchone()
    if not regime:
        add("DIVERGENTE", "Regime", f"CRT {crt}/tpRegimeIBSCBS {tpreg} sem parametrização em {d}", codigo="VSN")
        return
    cl = base.c.execute(f"SELECT * FROM CLASSIFICACAO_TRIBUTARIA WHERE CLTR_CD=:c AND {Base.vig('CLTR')} ORDER BY CLTR_TPRBSN DESC",
                        {"c": str(item.get("cClassTrib")), "d": d}).fetchone()
    if not cl:
        add("DIVERGENTE", "cClassTrib", f"{item.get('cClassTrib')} inexistente em {d}")
        return
    tr = base.c.execute(f"SELECT * FROM TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL WHERE TRBS_CD=:c AND {Base.vig('TRBS')}",
                        {"c": str(cl["CLTR_TPRBSN"]), "d": d}).fetchone()
    if not tr:
        add("DIVERGENTE", "tpRBSN", f"tipo de receita {cl['CLTR_TPRBSN']} sem parametrização em {d}")
        return
    add("OK", "tpRBSN", f"cClassTrib {cl['CLTR_CD']} → tpRBSN {tr['TRBS_CD']} ({tr['TRBS_DESCRICAO']})")
    if decl.get("tpRBSN") is not None and str(decl["tpRBSN"]) != str(tr["TRBS_CD"]):
        add("DIVERGENTE", "tpRBSN declarado", "tipo de receita bruta diferente do derivado do cClassTrib",
            tr["TRBS_CD"], decl["tpRBSN"])
    bc_inf = D(item.get("baseCalculo")) or Decimal(0)
    v_is = D(item.get("valorImpostoSeletivo")) or Decimal(0)
    vrb = (bc_inf + (v_is if tr["TRBS_IN_IS_COMPOE_RECEITA"] else 0)) if tr["TRBS_IN_COMPOE_RECEITA"] else Decimal(0)
    comparar_moeda(it, "vRBSNitem", vrb, D(decl.get("vRBSNitem")), detalhe="receita bruta do item.")
    cativ = item.get("cAtivSN")
    ativ = cativ and base.c.execute(f"SELECT * FROM ATIVIDADE_SIMPLES_NACIONAL WHERE ATSN_CATIVSN=:c AND {Base.vig('ATSN')}",
                                    {"c": str(cativ).zfill(2), "d": d}).fetchone()
    if not ativ:
        add("ALERTA", "cAtivSN", "atividade ausente/inválida: a calculadora oficial não calcula o item (NAO_CALCULADO)")
        return
    add("OK", "cAtivSN", f"{ativ['ATSN_CATIVSN']} - {ativ['ATSN_DESCRICAO'][:90]} (anexo {ativ['ATSN_ROTULO']})")
    fator = D(tr["TRBS_FATOR_RECEITA"])
    p_ibs, p_cbs = D(item.get("pIBSSN")), D(item.get("pCBSSN"))
    if tr["TRBS_IN_EXIGE_ALIQUOTA"] and (p_cbs is None or (regime["RASN_IN_GERA_IBS"] and p_ibs is None)):
        add("ALERTA", "Alíquotas SN", "tpRBSN exige pIBSSN/pCBSSN e elas não foram informadas")
    ente = op.get("tpEnteGov")
    if ente and (p_ibs is not None or p_cbs is not None):
        p_ibs, p_cbs = p_ibs or Decimal(0), p_cbs or Decimal(0)
        if str(ente) == "1":
            p_ibs, p_cbs = Decimal(0), p_cbs + p_ibs
        else:
            f = base.c.execute(f"SELECT TACG_FATOR FROM TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL WHERE {Base.vig('TACG')}",
                               {"d": d}).fetchone()
            f = D(f[0]) if f else Decimal(0)
            p_ibs, p_cbs = p_ibs + q8(f * p_cbs), q8((1 - f) * p_cbs)
        add("OK", "Compra governamental", f"alíquotas deslocadas: pIBSSN {fmt(p_ibs)} / pCBSSN {fmt(p_cbs)}")
    vbc = q8(vrb * fator)
    comparar_moeda(it, "vBC", vbc, D(decl.get("vBC")), detalhe=f"vRBSNitem × fator {fmt(fator)}.")
    pend = bool(tr["TRBS_IN_PENDENTE_SUSPENSO"])
    destino = regime["RASN_DESTINO_PENDENTE_SUSPENSO"] if pend else regime["RASN_DESTINO_DEVIDO"]
    for nome, p, gera in (("IBS", p_ibs, regime["RASN_IN_GERA_IBS"]), ("CBS", p_cbs, True)):
        if not gera:
            continue
        val = q8(vbc * p / 100) if p is not None and fator else Decimal(0)
        devido = val if destino == "DEVIDO" else Decimal(0)
        susp = val if destino == "PENDENTE_SUSPENSO" else Decimal(0)
        comparar_moeda(it, f"v{nome}SN", devido, D(decl.get(f"v{nome}SN")), detalhe=f"destino {destino}.")
        if susp or decl.get(f"v{nome}PendSusp") is not None:
            comparar_moeda(it, f"v{nome}PendSusp", susp, D(decl.get(f"v{nome}PendSusp")))


# ───────────────────────────── orquestração ─────────────────────────────
def validar(op, base):
    rel = Relatorio()
    d = str(op.get("dhFatoGerador") or op.get("data") or "")[:10]
    if not d:
        sys.exit("dhFatoGerador obrigatório (REG-021)")
    ano = int(d[:4])
    geral = {"numero": "Totais do documento", "checagens": []}
    rel.gerais.append(geral)
    if ano < 2026:
        Relatorio.add(geral, "NAO_VERIFICADO", "Vigência", "fato gerador anterior a 2026: CBS/IBS ainda não existem")
        return rel, d
    if op.get("regime") == "simples":
        for item in op.get("itens", []):
            validar_item_simples(base, rel, op, item, d)
        return rel, d
    for item in op.get("itens", []):
        validar_item_regular(base, rel, op, item, d, ano)
    tot = op.get("totais") or {}
    if tot:
        soma = lambda k: sum((D(i.get("declarado", {}).get(k)) or Decimal(0)) for i in op["itens"])
        for k in ("vBC", "vCBS", "vIBSUF", "vIBSMun", "vIBS"):
            if tot.get(k) is not None:
                comparar_moeda(geral, f"Total {k}", soma(k), D(tot[k]), detalhe="soma dos itens.")
    return rel, d


def imprimir(rel, op, d, base):
    v = base.versao()
    print(f"# Auditoria CBS/IBS — {op.get('documento', 'documento')} — fato gerador {d}")
    print(f"Base oficial: {v.get('VRBD_VERSAO_BASE_DADO', '?')} de {str(v.get('VRBD_DATA', ''))[:10]} | "
          f"regime: {op.get('regime', 'regular')}\n")
    simb = {"OK": "✅", "DIVERGENTE": "❌", "ALERTA": "⚠️", "NAO_VERIFICADO": "➖"}
    for alvo in rel.itens + rel.gerais:
        if not alvo["checagens"]:
            continue
        titulo = alvo["numero"] if isinstance(alvo["numero"], str) else f"Item {alvo['numero']}"
        print(f"## {titulo}")
        print("| | Regra | Esperado | Declarado | Detalhe |\n|---|---|---|---|---|")
        for c in alvo["checagens"]:
            det = c["detalhe"] + (f" [{c['codigo']}]" if c["codigo"] else "")
            print(f"| {simb[c['status']]} | {c['regra']} | {c['esperado'] or ''} | {c['declarado'] or ''} | {det} |")
        print()
    r = rel.resumo()
    print("**Resumo:** " + ", ".join(f"{k}: {n}" for k, n in sorted(r.items())))


# ───────────────────────────── leitura de XML ─────────────────────────────
def _ln(tag):
    return tag.rsplit("}", 1)[-1]


def achar(no, caminho):
    """Busca por nomes locais (ignora namespace). caminho = 'a/b/c'."""
    if no is None:
        return None
    partes = caminho.split("/")
    atual = [no]
    for p in partes:
        prox = []
        for n in atual:
            prox += [f for f in n.iter() if _ln(f.tag) == p and f is not n]
        if not prox:
            return None
        atual = prox[:1]
    return atual[0]


def txt(no, caminho):
    n = achar(no, caminho)
    return n.text.strip() if n is not None and n.text else None


def num(no, caminho):
    return txt(no, caminho)


def ou(no, padrao):
    return padrao if no is None else no


def extrair_nfse(path):
    raiz = ET.parse(path).getroot()
    inf = ou(achar(raiz, "infNFSe"), raiz)
    dps = achar(inf, "infDPS")
    ibs_dps = achar(dps, "IBSCBS")
    ibs_res = None
    for f in inf:
        if _ln(f.tag) == "IBSCBS":
            ibs_res = f
    val = achar(ibs_res, "valores")
    decl = {
        "vBC": num(val, "vBC"),
        "pIBSUF": num(val, "uf/pIBSUF"), "pRedIBSUF": num(val, "uf/pRedAliqUF"), "pAliqEfetIBSUF": num(val, "uf/pAliqEfetUF"),
        "pIBSMun": num(val, "mun/pIBSMun"), "pRedIBSMun": num(val, "mun/pRedAliqMun"), "pAliqEfetIBSMun": num(val, "mun/pAliqEfetMun"),
        "pCBS": num(val, "fed/pCBS"), "pRedCBS": num(val, "fed/pRedAliqCBS"), "pAliqEfetCBS": num(val, "fed/pAliqEfetCBS"),
        "vIBSUF": num(ibs_res, "totCIBS/gIBS/gIBSUFTot/vIBSUF"), "vIBSMun": num(ibs_res, "totCIBS/gIBS/gIBSMunTot/vIBSMun"),
        "vIBS": num(ibs_res, "totCIBS/gIBS/vIBSTot"), "vCBS": num(ibs_res, "totCIBS/gCBS/vCBS"),
    }
    pis = num(dps, "piscofins/vPis")
    comp = {
        "vServ": num(dps, "vServPrest/vServ"), "vDescIncond": num(dps, "vDescCondIncond/vDescIncond"),
        "vCalcReeRepRes": num(val, "vCalcReeRepRes"), "vCalcDedRedIBSCBS": num(val, "vCalcDedRedIBSCBS"),
        "vISSQN": num(inf, "valores/vISSQN") if achar(inf, "valores") is not None else None,
        "vPIS": pis, "vCOFINS": num(dps, "piscofins/vCofins"),
    }
    gtrib = achar(ibs_dps, "gIBSCBS")
    reg = achar(ibs_dps, "gTribRegular")
    item = {
        "numero": 1, "nbs": txt(dps, "cServ/cNBS"), "cTribNac": txt(dps, "cServ/cTribNac"),
        "cIndOp": txt(ibs_dps, "cIndOp"), "CST": txt(gtrib, "CST"), "cClassTrib": txt(gtrib, "cClassTrib"),
        "componentesBase": {k: v for k, v in comp.items() if v is not None},
        "declarado": {k: v for k, v in decl.items() if v is not None},
    }
    if reg is not None:
        item["tributacaoRegular"] = {_ln(f.tag): f.text for f in reg if f.text}
    op_sn = txt(dps, "regTrib/opSimpNac")
    op = {"documento": "NFS-e", "tpDoc": 91,
          "dhFatoGerador": txt(dps, "dCompet") or (txt(dps, "dhEmi") or "")[:10],
          "regime": "regular", "opSimpNac": op_sn, "numero": txt(inf, "nNFSe"),
          "emitente": txt(achar(inf, "emit"), "xNome"), "itens": [item],
          "totais": {}}
    if op_sn in ("2", "3", "4"):
        op["observacao"] = ("Prestador optante do Simples/MEI (opSimpNac " + op_sn +
                            "): conferir pelo regime do Simples Nacional se recolhe IBS/CBS pelo DAS.")
    return op


def extrair_nfe(path):
    raiz = ET.parse(path).getroot()
    inf = ou(achar(raiz, "infNFe"), raiz)
    ide = achar(inf, "ide")
    op = {"documento": "NF-e" if txt(ide, "mod") != "65" else "NFC-e", "tpDoc": int(txt(ide, "mod") or 55),
          "dhFatoGerador": (txt(ide, "dhEmi") or "")[:10], "regime": "regular",
          "CRT": txt(inf, "emit/CRT"), "tpEnteGov": txt(ide, "gCompraGov/tpEnteGov"),
          "pRedutorCompraGov": txt(ide, "gCompraGov/pRedutor"), "numero": txt(ide, "nNF"),
          "emitente": txt(inf, "emit/xNome"), "itens": []}
    for det in [f for f in inf if _ln(f.tag) == "det"]:
        prod, imp = achar(det, "prod"), achar(det, "imposto")
        g = achar(imp, "IBSCBS")
        gi = achar(g, "gIBSCBS")
        icms = achar(imp, "ICMS")
        comp = {k: num(prod, k) for k in ("vProd", "vFrete", "vSeg", "vOutro", "vDesc")}
        comp.update({"vII": num(imp, "II/vII"), "vIS": num(imp, "IS/vIS"), "vPIS": num(imp, "PIS/vPIS"),
                     "vCOFINS": num(imp, "COFINS/vCOFINS"), "vICMS": num(icms, "vICMS"), "vFCP": num(icms, "vFCP"),
                     "vICMSUFDest": num(imp, "ICMSUFDest/vICMSUFDest"), "vFCPUFDest": num(imp, "ICMSUFDest/vFCPUFDest"),
                     "vICMSMono": num(icms, "vICMSMono"), "vISSQN": num(imp, "ISSQN/vISSQN")})
        decl = {"vBC": num(gi, "vBC"), "vIBS": num(gi, "vIBS")}
        for nome, grp in (("IBSUF", "gIBSUF"), ("IBSMun", "gIBSMun"), ("CBS", "gCBS")):
            gg = achar(gi, grp)
            decl.update({f"p{nome}": num(gg, f"p{nome}"), f"v{nome}": num(gg, f"v{nome}"),
                         f"pRed{nome}": num(gg, "gRed/pRedAliq"), f"pAliqEfet{nome}": num(gg, "gRed/pAliqEfet"),
                         f"pDif{nome}": num(gg, "gDif/pDif"), f"vDif{nome}": num(gg, "gDif/vDif")})
        item = {"numero": int(det.get("nItem", len(op["itens"]) + 1)), "ncm": txt(prod, "NCM"),
                "quantidade": txt(prod, "qCom"), "vIS": comp.get("vIS"),
                "natureza": "servico" if achar(imp, "ISSQN") is not None else "bem",
                "CST": txt(g, "CST"), "cClassTrib": txt(g, "cClassTrib"),
                "componentesBase": {k: v for k, v in comp.items() if v is not None},
                "declarado": {k: v for k, v in decl.items() if v is not None}}
        reg = achar(gi, "gTribRegular")
        if reg is not None:
            item["tributacaoRegular"] = {_ln(f.tag): f.text for f in reg if f.text}
        op["itens"].append(item)
    tot = achar(inf, "IBSCBSTot")
    op["totais"] = {k: v for k, v in {
        "vBC": num(tot, "vBCIBSCBS"), "vIBS": num(tot, "gIBS/vIBS"), "vIBSUF": num(tot, "gIBS/gIBSUF/vIBSUF"),
        "vIBSMun": num(tot, "gIBS/gIBSMun/vIBSMun"), "vCBS": num(tot, "gCBS/vCBS")}.items() if v is not None}
    return op


# ───────────────────────────── consultas ─────────────────────────────
def consultar(base, tipo, codigo, d):
    out = {}
    if tipo == "cclasstrib":
        rows = base.c.execute(f"""SELECT c.*, s.SITR_CD, s.SITR_DESCRICAO FROM CLASSIFICACAO_TRIBUTARIA c
                     JOIN SITUACAO_TRIBUTARIA s ON s.SITR_ID=c.CLTR_SITR_ID WHERE c.CLTR_CD=:c AND {Base.vig('c.CLTR')}""",
                              {"c": codigo, "d": d}).fetchall()
        out = []
        for c in rows:
            tt = base.tratamento(c["CLTR_ID"], d)
            fund = base.q(f"""SELECT f.FDLG_REFERENCIA_NORMATIVA, f.FDLG_TEXTO_CURTO FROM FUNDAMENTACAO_CLASSIFICACAO x
                    JOIN FUNDAMENTACAO_LEGAL f ON f.FDLG_ID=x.FDCL_FDLG_ID WHERE x.FDCL_CLTR_ID=?""", c["CLTR_ID"])
            out.append({
                "cClassTrib": c["CLTR_CD"], "CST": c["SITR_CD"], "descricaoCST": c["SITR_DESCRICAO"],
                "descricao": c["CLTR_DESCRICAO"], "tipoAliquota": c["CLTR_TIPO_ALIQUOTA"],
                "nomenclatura": c["CLTR_NOMENCLATURA"], "anexo": c["CLTR_ANEXO"], "tpRBSN": c["CLTR_TPRBSN"],
                "creditoOperacaoAntecedente": c["CLTR_CREDITO_OPERACAO_ANTECEDENTE"],
                "vigencia": [c["CLTR_INICIO_VIGENCIA"], c["CLTR_FIM_VIGENCIA"]],
                "reducao_%": {n: fmt(base.reducao(c["CLTR_ID"], t, d)) for t, n in TRIBUTOS.items()},
                "aliquotaBase_%": {n: fmt(base.aliq_ad_valorem(c["CLTR_ID"], t, d)) for t, n in TRIBUTOS.items()},
                "tiposDocumento": sorted(base.tipos_dfe(c["CLTR_ID"], d)),
                "tratamento": dict(tt) if tt else None,
                "memoriaCalculo": c["CLTR_MEMORIA_CALCULO"],
                "fundamentacao": [dict(f) for f in fund]})
    elif tipo == "cst":
        out = [dict(r) for r in base.q(
            "SELECT * FROM SITUACAO_TRIBUTARIA WHERE SITR_CD=? AND SITR_INICIO_VIGENCIA<=? AND (SITR_FIM_VIGENCIA IS NULL OR SITR_FIM_VIGENCIA>=?)",
            codigo.zfill(3), d, d)]
        for o in out:
            o["cClassTribs"] = [f"{r[0]} - {r[1][:90]}" for r in base.q(
                "SELECT CLTR_CD, CLTR_DESCRICAO FROM CLASSIFICACAO_TRIBUTARIA WHERE CLTR_SITR_ID=? AND CLTR_INICIO_VIGENCIA<=? AND (CLTR_FIM_VIGENCIA IS NULL OR CLTR_FIM_VIGENCIA>=?) ORDER BY 1",
                o["SITR_ID"], d, d)]
    elif tipo == "ncm":
        n = base.q1("SELECT * FROM NCM WHERE NCM_CD=?", codigo)
        vinc = base.q(f"""SELECT DISTINCT c.CLTR_CD, n.NCMA_NCM_CD FROM NCM_APLICAVEL n JOIN CLASSIFICACAO_TRIBUTARIA c ON c.CLTR_ID=n.NCMA_CLTR_ID
                     WHERE n.NCMA_NCM_CD = substr(?,1,length(n.NCMA_NCM_CD)) AND n.NCMA_INICIO_VIGENCIA<=? AND (n.NCMA_FIM_VIGENCIA IS NULL OR n.NCMA_FIM_VIGENCIA>=?)""",
                      codigo, d, d)
        out = {"ncm": dict(n) if n else None, "cClassTribs_com_anexo": [f"{r[0]} (anexo {r[1]})" for r in vinc]}
    elif tipo == "nbs":
        n = base.q1("SELECT * FROM NBS WHERE NBS_CD=?", codigo)
        comb = base.q(f"""SELECT c.CNIL_LSLC_CD, io.IOIC_CD, io.IOIC_LOCAL_INCIDENCIA, ct.CLTR_CD FROM CLASSIF_NBS_INDOP_LC c
                     JOIN CLASSIFICACAO_TRIBUTARIA ct ON ct.CLTR_ID=c.CNIL_CLTR_ID JOIN INDICADOR_OPERACAO_IBS_CBS io ON io.IOIC_ID=c.CNIL_IOIC_ID
                     WHERE c.CNIL_NBS_CD=? AND c.CNIL_INICIO_VIGENCIA<=? AND (c.CNIL_FIM_VIGENCIA IS NULL OR c.CNIL_FIM_VIGENCIA>=?)""", codigo, d, d)
        vinc = base.q("""SELECT DISTINCT c.CLTR_CD FROM NBS_APLICAVEL n JOIN CLASSIFICACAO_TRIBUTARIA c ON c.CLTR_ID=n.NBSA_CLTR_ID
                     WHERE n.NBSA_NBS_CD = substr(?,1,length(n.NBSA_NBS_CD))""", codigo)
        out = {"nbs": dict(n) if n else None, "cClassTribs_com_anexo": [r[0] for r in vinc],
               "combinacoes_nfse": [{"itemLC116": r[0], "cIndOp": r[1], "localIncidencia": r[2], "cClassTrib": r[3]} for r in comb]}
    elif tipo == "busca":
        termo = f"%{codigo}%"
        out = [f"{r[0]} (CST {r[1]}) {r[2][:110]}" for r in base.q(
            f"""SELECT c.CLTR_CD, s.SITR_CD, c.CLTR_DESCRICAO FROM CLASSIFICACAO_TRIBUTARIA c JOIN SITUACAO_TRIBUTARIA s ON s.SITR_ID=c.CLTR_SITR_ID
                WHERE (c.CLTR_DESCRICAO LIKE ? OR c.CLTR_CD LIKE ?) AND c.CLTR_INICIO_VIGENCIA<=? AND (c.CLTR_FIM_VIGENCIA IS NULL OR c.CLTR_FIM_VIGENCIA>=?) ORDER BY 1""",
            termo, termo, d, d)]
        out += [f"NBS {r[0]} {r[1][:110]}" for r in base.q("SELECT NBS_CD, NBS_DESCRICAO FROM NBS WHERE NBS_DESCRICAO LIKE ? LIMIT 30", termo)]
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consultar")
    c.add_argument("tipo", choices=["cclasstrib", "cst", "ncm", "nbs", "busca"])
    c.add_argument("codigo")
    c.add_argument("--data", default=date.today().isoformat())
    for nome in ("validar", "extrair"):
        v = sub.add_parser(nome)
        v.add_argument("arquivo", nargs="?")
        v.add_argument("--nfse")
        v.add_argument("--nfe")
        v.add_argument("--json", action="store_true")
        v.add_argument("--data", help="sobrescreve a data do fato gerador")
    a = ap.parse_args()
    base = Base()
    if a.cmd == "consultar":
        return consultar(base, a.tipo, a.codigo, a.data)
    if a.nfse:
        op = extrair_nfse(a.nfse)
    elif a.nfe:
        op = extrair_nfe(a.nfe)
    elif a.arquivo:
        op = json.loads(Path(a.arquivo).read_text(encoding="utf-8"))
    else:
        sys.exit("informe um arquivo JSON, --nfse ou --nfe")
    if a.data:
        op["dhFatoGerador"] = a.data
    if a.cmd == "extrair":
        print(json.dumps(op, ensure_ascii=False, indent=2))
        return
    rel, d = validar(op, base)
    if a.json:
        print(json.dumps({"documento": op.get("documento"), "dataFatoGerador": d, "resumo": rel.resumo(),
                          "itens": [{k: v for k, v in i.items() if not k.startswith("_")} for i in rel.itens],
                          "documentoGeral": rel.gerais}, ensure_ascii=False, indent=2, default=str))
    else:
        if op.get("observacao"):
            print(f"> {op['observacao']}\n")
        imprimir(rel, op, d, base)


if __name__ == "__main__":
    main()
