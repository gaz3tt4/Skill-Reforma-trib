---
name: auditoria-tributos-rtc
description: Audita se CBS, IBS e Imposto Seletivo (Reforma Tributária do Consumo, LC 214/2025) estão corretos em documentos fiscais (NF-e, NFC-e, NFS-e, DANFSe, planilhas ou dados do ERP). Usa a base oficial e as fórmulas das calculadoras RTC da Receita Federal (regime regular e Simples Nacional). Acione sempre que o usuário pedir para conferir, validar, auditar, revisar ou recalcular tributos de uma nota ou medição, verificar CST/cClassTrib, alíquota, redução, base de cálculo, vBC, vCBS, vIBS, gIBSCBS, gTribRegular, diferimento, compra governamental, NBS/NCM ou cIndOp, ou perguntar "o imposto desta nota está certo?". Também serve para consultar qual cClassTrib/CST usar para um serviço ou produto.
---

# Auditoria de tributos da Reforma Tributária (CBS/IBS/IS)

A skill reproduz as regras de três repositórios oficiais da Receita Federal:

- `calculadora-rtc-regime-regular`: cálculo de CBS/IBS/IS no regime regular, base unificada da NF-e e da NFS-e, tabelas de CST, cClassTrib, reduções, NCM/NBS e cIndOp.
- `calculadora-rtc-simples-nacional`: cálculo de IBS/CBS no Simples Nacional (NT 2026.005).
- `calculadora-rtc-gerador-danfse`: leiaute do XML da NFS-e Nacional e campos do DANFSe.

Tudo fica em `data/rtc.db`, um SQLite gerado dos scripts Flyway oficiais (versão no rodapé de cada relatório). O script `scripts/rtc.py` faz as consultas e validações. **Use o script em vez de fazer contas de cabeça**: as reduções, os vínculos e as vigências mudam por cClassTrib e por data.

## Fluxo de trabalho

1. **Obtenha os dados do documento.**
   - XML de NFS-e Nacional: `python -I scripts/rtc.py validar --nfse nota.xml`
   - XML de NF-e/NFC-e: `python -I scripts/rtc.py validar --nfe nota.xml`
   - PDF (DANFSe/DANFE), imagem, planilha ou tela do ERP: leia o documento e monte o JSON normalizado (formato abaixo; exemplos em `exemplos/`). Depois rode `python -I scripts/rtc.py validar entrada.json`.
   - Para ver o que foi lido de um XML antes de validar, use `rtc.py extrair --nfse nota.xml`.
2. **Identifique o regime do emitente.** NF-e: `CRT` 1 ou 2 = Simples Nacional, 3 = regime normal, 4 = MEI. NFS-e: `opSimpNac` 1 = não optante, 2 = MEI, 3 = ME/EPP, 4 = pendente. Optante do Simples que recolhe pelo DAS usa `"regime": "simples"` (veja [references/regras-simples-nacional.md](references/regras-simples-nacional.md)). Nos demais casos use `"regime": "regular"`.
3. **Rode o validador** e leia cada checagem. Os status são:
   - ✅ OK
   - ❌ DIVERGENTE: erro, com o código oficial quando existe (REG-xxx/CAL-xxx; veja [references/codigos-erro.md](references/codigos-erro.md))
   - ⚠️ ALERTA: dado ausente ou situação que pede confirmação humana
   - ➖ NAO_VERIFICADO: regra que nem a calculadora oficial automatiza
4. **Investigue cada divergência** com `rtc.py consultar ...` (abaixo), para dizer qual seria o valor ou o código correto.
5. **Entregue o parecer** no formato da seção "Relatório para o usuário".

## Consultas rápidas

```
python -I scripts/rtc.py consultar cclasstrib 200028 --data 2027-01-01   # CST, tipo de alíquota, % redução por tributo, docs admitidos, fórmulas, base legal
python -I scripts/rtc.py consultar cst 200 --data 2026-11-16             # descrição, grupos exigidos, cClassTribs do CST
python -I scripts/rtc.py consultar ncm 10063021                          # cClassTribs cujo anexo inclui a NCM
python -I scripts/rtc.py consultar nbs 101011200                         # cClassTribs e combinações NBS × cIndOp × item LC 116 (NFS-e)
python -I scripts/rtc.py consultar busca "construção"                    # busca textual em cClassTrib e NBS
```

`--data` é a data do fato gerador. O padrão é hoje. A vigência muda o resultado.

## Formato JSON normalizado

```json
{
  "documento": "NFS-e", "tpDoc": 91, "dhFatoGerador": "2026-11-10", "regime": "regular",
  "tpEnteGov": null, "pRedutorCompraGov": null,
  "itens": [{
    "numero": 1, "nbs": "101011200", "cTribNac": "070201", "cIndOp": "020201",
    "ncm": null, "CST": "200", "cClassTrib": "200045", "quantidade": null, "vIS": null,
    "natureza": "servico",
    "componentesBase": {"vServ": "10000.00", "vDescIncond": "0", "vISSQN": "500.00", "vPIS": "65.00", "vCOFINS": "300.00"},
    "aliquotasNominais": {"CBS": "8.8", "IBSUF": "0.1", "IBSMun": "0.0"},
    "declarado": {"vBC": "9135.00",
      "pCBS": "0.90", "pRedCBS": "60.00", "pAliqEfetCBS": "0.36", "vCBS": "32.89",
      "pIBSUF": "0.10", "pRedIBSUF": "60.00", "pAliqEfetIBSUF": "0.04", "vIBSUF": "3.65",
      "pIBSMun": "0.00", "pRedIBSMun": "60.00", "pAliqEfetIBSMun": "0.00", "vIBSMun": "0.00",
      "vIBS": "3.65", "pDifCBS": null, "vDifCBS": null},
    "tributacaoRegular": {"CSTReg": "000", "cClassTribReg": "000001", "pAliqEfetRegCBS": "0.90", "vTribRegCBS": "..."}
  }],
  "totais": {"vBC": "9135.00", "vCBS": "32.89", "vIBS": "3.65"}
}
```

- Valores vão como string decimal com ponto. Campos ausentes podem ser omitidos.
- `tpDoc`: 55 = NF-e, 65 = NFC-e, 91 = NFS-e, 57 = CT-e, 77 = NF-e ABI.
- `componentesBase` é opcional. Quando presente, o vBC é recalculado. NF-e: vProd, vFrete, vSeg, vOutro, vII, vIS, vDesc, vPIS, vCOFINS, vICMS, vICMSUFDest, vFCP, vFCPUFDest, vICMSMono, vISSQN. NFS-e: vServ, vDescIncond, vCalcReeRepRes, vCalcDedRedIBSCBS, vISSQN, vPIS, vCOFINS.
- `aliquotasNominais` é opcional. Use quando o usuário souber as alíquotas oficiais do ano e quiser conferir a alíquota declarada contra elas. De 2027 em diante, sem esse campo, a alíquota nominal declarada é aceita como premissa.
- Formato do Simples Nacional: veja `exemplos/entrada-simples-nacional.json`.

## Regras essenciais (resumo; detalhes em references/)

**Linha do tempo**
- 2026 (ano-teste): CBS 0,9%, IBS UF 0,1%, IBS Mun 0%. PIS, COFINS, ICMS e ISS continuam e são deduzidos da base.
- A partir de 2027: CBS plena, PIS/COFINS extintos (não deduzem mais), Imposto Seletivo começa. A calculadora deixa de ter alíquotas de referência e exige as nominais informadas.
- ICMS e ISS deduzem da base até 2032. Em 2033 são extintos.

**Fórmulas** (iguais ao `TRATAMENTO_TRIBUTARIO` oficial)
- `pAliqEfet = p × (1 − pRedAliq/100) × (1 − pRedutorCompraGov/100)`
- `vTributo = vBC × pAliqEfet/100`
- `vIBS = vIBSUF + vIBSMun`
- Diferimento: `vDif = vTributo × pDif/100`, e o valor devido é `vTributo − vDif`.

**Base de cálculo**
- NF-e: vProd + vFrete + vSeg + vOutro + vII + vIS(2027+) − vDesc − PIS/COFINS(só 2026) − ICMS/ICMS-UFDest/FCP/ICMS-Mono (até 2032) − ISSQN (serviço, até 2032).
- NFS-e: vServ − vDescIncond − vCalcReeRepRes − vCalcDedRedIBSCBS − ISS(<2033) − PIS − COFINS(<2027).
- Locação (99.03): fator de copropriedade, sem dedução de ISS.
- Com Imposto Seletivo, a base de CBS/IBS = base do IS + IS (REG-026/027).

**CST**
- Define quais grupos do XML podem ou devem existir: gIBSCBS, gRed (redução), gDif (diferimento), gTribRegular (suspensão 550 e cClassTribs que exigem desoneração), monofasia (620).
- CST sem gIBSCBS (400, 410 etc.) não pode ter valores destacados.

**Coerência dos códigos**
- O cClassTrib precisa pertencer ao CST (REG-006).
- O cClassTrib precisa ser admitido no modelo do documento (REG-029). Exemplo: 200028 (educação) só existe na NFS-e.
- Se o cClassTrib tem anexo, a NCM/NBS precisa constar dele (REG-011/012).
- Na NFS-e, a combinação NBS × cClassTrib × cIndOp × item da LC 116 precisa existir na tabela oficial.

**Arredondamento**
- A calculadora oficial usa 8 casas internas, HALF_EVEN (bancário), e 2 casas no valor final.
- Diferenças de até R$ 0,01 são toleradas. Mencione quando o emissor arredondou "para cima" (HALF_UP).

## Limites (diga isso ao usuário quando forem relevantes)

- **Alíquotas a partir de 2027.** A base oficial só tem as alíquotas de 2026. Para 2027 em diante a skill confere a consistência (redução, efetiva, valores e totais), mas não "a alíquota certa do ente". Peça as alíquotas vigentes publicadas ao usuário ou procure-as, e informe-as em `aliquotasNominais`.
- **Tratamentos sem cálculo oficial.** Monofasia de combustíveis, ajustes, transferência de crédito, ZFM e alíquota fixa com ajuste ficam como NAO_VERIFICADO (CAL-007). A calculadora oficial também não os calcula.
- **Compra governamental.** A skill aplica o redutor e o deslocamento do Simples. O rateio entre entes a partir de 2029 precisa de conferência manual.
- **Enquadramento.** O enquadramento (se a operação de fato se encaixa no cClassTrib) é julgamento tributário. A skill garante a coerência com a base oficial, não substitui o parecer do contador.
- **Base desatualizada.** Para atualizar a base com os scripts mais recentes do repositório oficial: `python -I scripts/atualizar_base.py`. Faça isso se o relatório mostrar uma versão de base antiga, ou se um cClassTrib não for encontrado.

## Relatório para o usuário

Responda em português, nesta ordem:

1. **Veredito** em uma linha: "Tributos corretos", "Corretos com ressalvas" ou "Há divergências", com o impacto em R$ (diferença total de CBS e de IBS).
2. **Divergências**: tabela com item, campo, declarado, correto, diferença e motivo, citando o código oficial (ex.: REG-029) e a regra.
3. **Alertas**: o que precisa de confirmação (dados ausentes, enquadramento, alíquotas de 2027+).
4. **Como corrigir**: CST/cClassTrib sugerido (via `consultar`), valores corretos e se cabe nota substituta ou carta de correção.
5. Rodapé com a versão da base oficial usada e a data do fato gerador.

Não cole o relatório bruto do script inteiro. Destaque o que importa e ofereça o detalhamento se o usuário quiser.

## Referências

- [references/regras-regime-regular.md](references/regras-regime-regular.md): tratamentos tributários e expressões, CSTs e grupos, base NF-e/NFS-e, IS, diferimento, compra governamental.
- [references/regras-simples-nacional.md](references/regras-simples-nacional.md): CRT/tpRegimeIBSCBS, tpRBSN, fatores, destino devido/pendente, cAtivSN, fator de transição.
- [references/layout-xml.md](references/layout-xml.md): de onde ler cada campo no XML da NFS-e Nacional, no DANFSe e na NF-e.
- [references/codigos-erro.md](references/codigos-erro.md): catálogo REG/CAL das calculadoras.
