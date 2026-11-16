# Simples Nacional: regras da calculadora oficial

Fonte: `ReceitaFederal/calculadora-rtc-simples-nacional` (`SimplesNacionalCalculoService`, NT 2026.005) e as tabelas `REGIME_APURACAO_SIMPLES_NACIONAL`, `TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL`, `ATIVIDADE_SIMPLES_NACIONAL` e `TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL`. Vigência a partir de 01/01/2027. Em 2026 o optante não destaca IBS/CBS pelo Simples.

## Escopo por CRT

| CRT | tpRegimeIBSCBS | Situação | Gera IBS | Destino do valor normal | Destino do pendente/suspenso |
|---|---|---|---|---|---|
| 1 | — | Simples Nacional | sim | DEVIDO | PENDENTE_SUSPENSO |
| 2 | — | Excesso de sublimite | **não**: o IBS vai no gIBSCBS da nota (regime regular) | DEVIDO | PENDENTE_SUSPENSO |
| 3 | 2 | Regime normal com opção pelo SN pendente | sim | PENDENTE_SUSPENSO | ZERO |
| 3 | 1 ou vazio | Regime normal | fora do escopo: use o regime regular | | |
| 4 | — | MEI | fora do escopo | | |

## Cálculo por item

1. `tpRBSN` vem do cClassTrib (coluna `CLTR_TPRBSN`).
2. Receita bruta do item: `vRBSNitem = baseCalculo` (sem IS) se o tipo compõe receita, senão 0. Hoje o IS não entra em nenhuma vigência; o valor é só repassado.
3. `cAtivSN` (código da atividade, 2 dígitos) precisa ser válido e admitido no tpDoc. Se não for, o item é `NAO_CALCULADO` (sem erro) e só informa vRBSNitem e tpRBSN.
4. Base: `vBC = vRBSNitem × fator`. Tributo: `v = vBC × p/100`, com pIBSSN e pCBSSN informados (alíquotas do Simples, em %).
5. Repartição pelo destino do regime: DEVIDO vai para vIBSSN/vCBSSN, PENDENTE_SUSPENSO vai para vIBSPendSusp/vCBSPendSusp, ZERO zera tudo.
6. `totalItem = IBS devido + CBS devido + IS`. O pendente/suspenso fica fora.

## Tipos de receita bruta (tpRBSN)

| tpRBSN | Descrição | Compõe receita | Fator | Pendente/suspenso | Exige alíquota |
|---|---|---|---|---|---|
| 0 | Não é receita bruta | não | 0 | não | não |
| 1 | Receita bruta interna | sim | 1,0 | não | sim |
| 2 | Interna sem cálculo de IBS/CBS | sim | 0 | não | não |
| 3 | Exportação direta | sim | 0 | não | não |
| 4 | Exportação indireta | sim | 1,0 | **sim** | sim |
| 5 | Mercado interno e exportação | sim | 0,5 | não | sim |
| 9 | Fornecimento incompatível com SN | sim | 0 | não | não |

## Compra governamental (tpEnteGov)

- União (1): `pCBS' = pCBS + pIBS`, `pIBS' = 0`.
- Estado, DF ou Município (2/3/4): `pIBS' = pIBS + f × pCBS` e `pCBS' = (1 − f) × pCBS`, onde f é o fator de transição: 0 em 2027–2028, 0,1 em 2029, 0,2 em 2030, 0,3 em 2031, 0,4 em 2032 e 1,0 a partir de 2033.

## Atividades (cAtivSN), com anexo da LC 123

| cAtivSN | Descrição resumida | Anexo |
|---|---|---|
| 01 | Revenda / venda de industrializados | I |
| 02 | Demais bens materiais sem ICMS | I menos ICMS |
| 03, 04 | Industrialização incentivada na ZFM | II |
| 05, 06 | Transporte intermunicipal/interestadual; comunicação | III menos ISS mais ICMS do I |
| 07 | Serviços com ISS do Anexo III | III |
| 08 | Contábeis com ISS fixo | III menos ISS |
| 09 | Serviços sujeitos ao Fator R | III ou V |
| 10 | Transporte municipal de passageiros (16.01) | III |
| 11 | Locação de bens móveis e afins sem ISS | III menos ISS |
| 12 | Construção civil 7.02/7.05 (Anexo III) | III |
| 13 | Construção civil 7.02/7.05 (Anexo IV) | IV |
| 14 | Prestação de serviços do Anexo IV | IV |
| 90 | Operações não tributáveis | — |

Fator R: se a atividade tem anexo com Fator R (09 → V), o modo é OBRIGATÓRIO, OPCIONAL, INDISPONÍVEL ou NÃO_APLICÁVEL, conforme os anexos configurados.

## NFS-e de prestador optante

- `opSimpNac` 3 ou 4 exige `regApIBSCBSSN`:
  - 1 = IBS e CBS pelo SN
  - 2 = CBS pelo SN e IBS regular
  - 3 = ambos regulares
- Não optante (1) não pode informar regApIBSCBSSN.
- Para regApIBSCBSSN 3, valide pelo regime regular.
- A baseSN da NFS-e é vServ − vDescIncond − ajustes de IBS/CBS, sem deduzir tributos.
