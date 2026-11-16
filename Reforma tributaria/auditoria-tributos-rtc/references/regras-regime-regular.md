# Regime regular: regras da calculadora oficial

Fonte: `ReceitaFederal/calculadora-rtc-regime-regular`, principalmente `CalculoCbsIbsService`, `CalculoTributoService`, `BaseCalculoUnificadaService`, `BaseCalculoUnificadaNfseService`, `ArredondamentoUtils` e as tabelas Flyway. As tabelas no fim deste arquivo são um retrato da base `data/rtc.db` (V0059, 30/09/2026). Na dúvida, consulte a base com `rtc.py consultar`.

## 1. Sequência do cálculo por item e tributo (CBS, IBS UF, IBS Mun)

1. Valida estrutura: NCM e NBS juntos (REG-001), NCM com 8 dígitos e NBS com 9 (REG-015/016), município da UF (REG-018).
2. Localiza CST (REG-004) e cClassTrib (REG-005) vigentes na data do fato gerador, e confere o vínculo entre eles (REG-006).
3. Confere o cClassTrib contra o tipo de DF-e (REG-029) e a nomenclatura:
   - Se o cClassTrib tem anexo, a NCM/NBS deve estar nele, por prefixo, sem estar em exceção (REG-011/012).
   - Na NF-e e na NFC-e só se aceita NCM; na NFS-e, só NBS (REG-030).
4. Obtém o **tratamento tributário** do cClassTrib. São expressões aritméticas guardadas na base (tabela abaixo) e avaliadas com as variáveis:
   - `aliquota`: nominal / 100
   - `percentualReducao`: % de redução / 100, da tabela `PERCENTUAL_REDUCAO` por tributo
   - `pRedutorCompraGov`: em %
   - `baseCalculoInformada`, `impostoSeletivoInformado`, `impostoSeletivoCalculado`, `quantidade`
5. Determina a alíquota nominal pelo **tipo de alíquota** do cClassTrib:
   - `Padrão` / `Uniforme nacional (referência)`: alíquota informada ou, em 2026, a de referência: CBS 0,9, IBS UF 0,1, IBS Mun 0,0. O 510001 é tratado como Padrão.
   - `Uniforme setorial` / `Fixa`: alíquota da tabela `ALIQUOTA_AD_VALOREM` ligada ao cClassTrib. Exemplo: operações de FGTS e setor financeiro.
   - `Sem alíquota`: 0, salvo alíquota informada.
   - Se a expressão de alíquota é `0` (suspensão, documento específico, exclusão de BC, ZFM/ALC), a alíquota é zerada, salvo alíquota nominal informada, que prevalece.
6. Calcula, nesta ordem:
   - alíquota efetiva: `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)`
   - base (se negativa, vira 0)
   - tributo calculado: `baseCalculo*aliquotaEfetiva`
   - tributo devido
   - diferimento, se houver
7. Se o CST não tem gIBSCBS (`SITR_IND_GIBSCBS = 0`), não há grupo de cálculo. Exemplos: isenção (400) e imunidade (410).
8. Saída: `pRedAliq` e `pAliqEfet` em %, só nos CSTs com gRed; valores com 2 casas, HALF_EVEN. `vIBS = vIBSUF + vIBSMun`.

**Precisão**: tudo em BigDecimal com 8 casas internas, HALF_EVEN. Moeda com 2 casas. Alíquota com 2 a 4 casas.

## 2. Datas que mudam a regra

| Data | Efeito |
|---|---|
| 2026 | Ano-teste. Alíquotas de referência CBS 0,9 / IBS UF 0,1 / IBS Mun 0. A calculadora **proíbe** alíquotas informadas (REG-036). PIS/COFINS deduzem da base. |
| 01/01/2027 | Alíquotas nominais **obrigatórias** (REG-037), e os cálculos saem como `CALCULO_SIMULADO`. PIS/COFINS deixam de deduzir. IS passa a existir e o vIS entra na base. Começa a vigência de CSTs como 100, 300, 500 e 600. |
| 2029–2032 | Transferência da CBS a entes em compras governamentais: 10%, 20%, 30%, 40%. |
| 2033 | Transferência de 100%. ICMS e ISS extintos, sem dedução da base. |

## 3. Base de cálculo unificada

**NF-e/NFC-e** (`ElementoBaseCalculo`):

| Campo | Op. | Natureza | Anos | Modelos |
|---|---|---|---|---|
| vProd, vFrete, vSeg, vOutro | + | todas | 2026–2033 | 55, 65 |
| vII | + | bem | 2026–2033 | 55 |
| vIS | + | todas | 2027–2033 | 55, 65 |
| vDesc | − | todas | 2026–2033 | 55, 65 |
| vPIS, vCOFINS | − | todas | só 2026 | 55, 65 |
| vICMS, vFCP, vICMSMono | − | bem | 2026–2032 | 55, 65 |
| vICMSUFDest, vFCPUFDest | − | bem | 2026–2032 | 55 |
| vISSQN | − | serviço | 2026–2032 | 55, 65 |

As bases resultantes são duas:
- baseIS: mesma soma sem vIS, e sem PIS/COFINS a partir de 2027.
- baseSN (Simples): vProd + vFrete + vSeg + vOutro + vIS − vDesc, sem deduzir tributos.

**NFS-e** (`BaseCalculoUnificadaNfseService` / `NfseService`):

`vBC = vServ − vDescIncond − vCalcReeRepRes − vCalcDedRedIBSCBS − vISSQN(ano<2033) − vPIS − vCOFINS(ano<2027)`

Documentos de ajuste (`tpAjusteBC`):
- 101 subcontratação, 102 consórcio, 103 intermediação, 104 cessão de mão de obra e 105 ressarcimento reduzem a base de IBS/CBS. O 199 (outros) também reduz e exige descrição (`xTpAjusteBC`).
- 9 (profissional parceiro) só reduz a baseSN, no salão parceiro.
- Se a soma dos ajustes for ≥ vServ: erro E1534.

Locação de imóveis (99.03):
- `vServEfetivo = pCopropriedade% × vTotOper`, menos o desconto e os ajustes proporcionais, menos PIS/COFINS. **Não deduz ISS.**
- Vedada a MEI e a ME/EPP optantes.

MEI: as bases não se aplicam (E1302).

O DANFSe (gerador oficial) mostra "Exclusões/Reduções da BC" = vDescIncond + vISSQN + vCalcDR + vCalcReeRepRes + vPis + vCofins.

## 4. Imposto Seletivo

- Base de CBS/IBS = base do IS + IS informado. Se a base declarada for diferente, é erro REG-026; se for menor que a base do IS, REG-027.
- IS com cálculo: `baseCalculo*aliquotaAdValorem + quantidade*aliquotaAdRem`.
- O IS só vale a partir de 2027 e só para NCM/NBS do anexo do IS (REG-013/014/032/035).
- A suspensão de CBS/IBS **não** suspende o IS.

## 5. Grupos especiais

- **Diferimento** (CST 510, 515): `vDif = vTributo × pDif`, e o devido é o tributo menos o diferido. A base oficial usa pDif 100% como padrão quando o documento não informa outro.
- **Suspensão / desoneração** (CST 550, e cClassTribs ZFM/ALC 200022/200024):
  - O grupo principal sai zerado.
  - É obrigatório o `gTribRegular` (CSTReg, cClassTribReg, pAliqEfetReg e vTribReg de cada tributo) (REG-009). Informado sem exigência, é erro REG-022.
- **Compra governamental** (`gCompraGov/tpEnteGov`, `pRedutor`):
  - A alíquota efetiva incorpora o redutor, que hoje é 0% na base.
  - Gera o `gTribCompraGov` com pAliq e vTrib de cada ente. A partir de 2029 a CBS é transferida em parte ao ente comprador.
  - Com suspensão: gRed com pRedAliq 0 e pAliqEfet 0; gTribRegular com o cálculo sem suspensão; gTribCompraGov zerado.
- **Monofasia** (CST 620, combustíveis): `quantidade × alíquota ad rem`. A calculadora usa constantes provisórias. Totais: `vTotIBSMonoItem = vIBSMono + vIBSMonoReten − vIBSMonoDif` (e o mesmo para a CBS).
- **Não implementados na calculadora (CAL-007)**: transferência de crédito (800), ajustes ZFM (810), ajustes (811), exclusão de BC (830), alíquota fixa com ajuste, monofasia sem alíquota.

## 6. Situações tributárias (CST) e grupos exigidos

| CST | Descrição | Vigência | gIBSCBS | gRed | gDif | Mono | TransfCred | ZFM | AjusteCompet |
|---|---|---|---|---|---|---|---|---|---|
| 000 | Tributação integral | 2026-01-01 → | sim |  |  |  |  |  |  |
| 010 | Tributação com alíquotas uniformes | 2026-01-01 → | sim |  |  |  |  |  |  |
| 011 | Tributação com alíquotas uniformes reduzidas | 2026-01-01 → | sim | sim |  |  |  |  |  |
| 200 | Alíquota reduzida | 2026-01-01 → | sim | sim |  |  |  |  |  |
| 220 | Alíquota fixa | 2026-01-01 → | sim |  |  |  |  |  |  |
| 221 | Alíquota fixa proporcional | 2026-01-01 → | sim |  |  |  |  |  |  |
| 222 | Redução de Base de Cálculo | 2026-01-01 → | sim |  |  |  |  |  |  |
| 400 | Isenção | 2026-01-01 → |  |  |  |  |  |  |  |
| 410 | Imunidade e não incidência | 2026-01-01 → |  |  |  |  |  |  |  |
| 510 | Diferimento | 2026-01-01 → | sim |  | sim |  |  |  |  |
| 515 | Diferimento com redução de alíquota | 2026-01-01 → | sim | sim | sim |  |  |  |  |
| 550 | Suspensão | 2026-01-01 → | sim |  |  |  |  |  |  |
| 620 | Tributação monofásica | 2026-01-01 → |  |  |  | sim |  |  |  |
| 800 | Transferência de crédito | 2026-01-01 → |  |  |  |  | sim |  |  |
| 810 | Ajustes de IBS na ZFM | 2026-01-01 → |  |  |  |  |  | sim |  |
| 811 | Ajustes | 2026-01-01 → |  |  |  |  |  |  | sim |
| 820 | Tributação em documento específico | 2026-01-01 → |  |  |  |  |  |  |  |
| 830 | Exclusão de base de cálculo | 2026-01-01 → | sim |  |  |  |  |  |  |

## 7. Tratamentos tributários (expressões oficiais)

| ID | Tratamento | Alíquota | Alíquota efetiva | Base | Tributo calculado | Devido | Dif. | Exige gTribRegular | Ajuste |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Tributação pelo Imposto Seletivo - Com Cálculo |  |  | `baseCalculoInformada` | `baseCalculo*aliquotaAdValorem+quantidade*aliquotaAdRem` | `tributoCalculado` |  |  |  |
| 2 | Tributação pelo Imposto Seletivo - Sem Cálculo |  |  | `baseCalculoInformada` | `0` | `tributoCalculado` |  |  |  |
| 3 | Tributação integral | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 4 | Tributação com alíquotas uniformes - operações do FGTS | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 5 | Tributação com alíquotas uniformes - operações do setor financeiro | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 6 | Tributação com alíquotas uniformes reduzidas em 60% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 7 | Tributação com alíquotas uniformes | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 8 | Tributação com alíquotas uniformes reduzidas em 30% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 9 | Alíquota zero | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 10 | Alíquota zero apenas CBS e reduzida em 60% para IBS | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 11 | Alíquota Reduzida em 80% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 12 | Alíquota reduzida em 70% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 13 | Alíquota reduzida em 60% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 14 | Alíquota reduzida em 50% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 15 | Alíquota reduzida em 40% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 16 | Alíquota reduzida em 30% | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 17 | Redução de base de cálculo | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada*0.5` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 18 | Isenção | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 19 | Imunidade e não incidência | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 20 | Diferimento | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` | `1.00` |  |  |
| 21 | Diferimento com redução de alíquota | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` | `1.00` |  |  |
| 22 | Suspensão | `0` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  | sim |  |
| 23 | Tributação monofásica sobre combustíveis | `aliquotaAdRemPrincipal` |  | `quantidade` | `quantidade*aliquotaAdRemPrincipal` |  |  |  | sim |
| 24 | Tributação monofásica com responsabilidade pela retenção sobre combustíveis | `aliquotaAdRemPrincipal` | `aliquotaAdRemSecundaria` | `quantidade` | `quantidade*aliquotaAdRemPrincipal` | `(pBio/(1-pBio))*quantidade*aliquotaAdRemSecundaria` |  |  | sim |
| 25 | Tributação monofásica com tributos retidos por responsabilidade sobre combustíveis | `aliquotaAdRemPrincipal` |  | `quantidade` | `quantidade*aliquotaAdRemPrincipal` | `quantidade*aliquotaAdRemPrincipal*(1-percentualDiferimento)` |  |  | sim |
| 26 | Tributação monofásica sobre mistura de EAC com gasolina A em percentual superior ao obrigatório | `(1-pBio)*aliquotaAdRemPrincipal+pBio*aliquotaAdRemSecundaria` | `aliquotaAdRemSecundaria` | `quantidade` | `(variacaoPontoPercentual/100)*quantidade*(pBio/(1-pBio))*aliquotaAdRemSecundaria` | `quantidade*aliquota` |  |  | sim |
| 27 | Tributação monofásica sobre mistura de EAC com gasolina A em percentual inferior ao obrigatório | `(1-pBio)*aliquotaAdRemPrincipal+pBio*aliquotaAdRemSecundaria` | `aliquotaAdRemSecundaria` | `quantidade` | `(variacaoPontoPercentual/100)*quantidade*(pBio/(1-pBio))*aliquotaAdRemSecundaria` | `quantidade*aliquota` |  |  | sim |
| 28 | Tributação monofásica sobre combustíveis cobrada anteriormente | `(1-pBio)*aliquotaAdRemPrincipal+pBio*aliquotaAdRemSecundaria` | `aliquotaAdRemSecundaria` | `quantidade` | `(variacaoPontoPercentual/100)*quantidade*(pBio/(1-pBio))*aliquotaAdRemSecundaria` | `quantidade*aliquota` |  |  | sim |
| 29 | Transferência de crédito | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 30 | Ajuste de IBS na ZFM | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 31 | Ajustes | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 32 | Tributação em documento específico | `0` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 33 | Exclusão de base de cálculo | `0` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 34 | Alíquota fixa | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 35 | Alíquota fixa | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 36 | Alíquota fixa | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 37 | Alíquota fixa proporcional | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  | sim |
| 38 | Operação originada fora da ZFM - 200022 | `0` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  | sim |  |
| 39 | Operação originada fora das Áreas de Livre Comércio - 200024 | `0` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  | sim |  |
| 40 | Tributação com exclusão de base de cálculo em caso de não incidência | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `(baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado)*(1-100/100)` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |
| 41 | Suspensão em operações com hidrocarbonetos líquidos | `0` | `aliquota` | `quantidade` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  | sim | sim |
| 42 | Tributação monofásica sem alíquota | `0` | `0` | `0` | `0` | `0` |  |  | sim |
| 43 | Alíquota fixa fictícia | `aliquota` | `aliquota*(1-percentualReducao)*(1-pRedutorCompraGov/100)` | `baseCalculoInformada-impostoSeletivoInformado+impostoSeletivoCalculado` | `baseCalculo*aliquotaEfetiva` | `tributoCalculado` |  |  |  |

A tabela completa de cClassTrib vigentes (redução por tributo, documentos admitidos, tpRBSN) está em [tabela-cclasstrib.md](tabela-cclasstrib.md).
