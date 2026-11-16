# Onde ler cada campo

## NFS-e Nacional (XML `NFSe/infNFSe`), conforme o modelo do gerador oficial de DANFSe

| Dado | Caminho no XML | Uso na auditoria |
|---|---|---|
| Nº da NFS-e | `infNFSe/nNFSe` | identificação |
| Competência (fato gerador) | `infNFSe/DPS/infDPS/dCompet` (ou `dhEmi`) | data das regras |
| Emitente | `infNFSe/emit/CNPJ`, `xNome` | |
| Regime do prestador | `infDPS/prest/regTrib/opSimpNac` (1 não optante, 2 MEI, 3 ME/EPP, 4 pendente), `regApTribSN`, `regEspTrib` | regime regular ou SN |
| Código de tributação nacional | `infDPS/serv/cServ/cTribNac` (6 dígitos = item.subitem.desdobro da LC 116) | combinação com NBS |
| NBS | `infDPS/serv/cServ/cNBS` | anexo e combinação |
| Valor do serviço | `infDPS/valores/vServPrest/vServ` | base |
| Descontos | `infDPS/valores/vDescCondIncond/vDescIncond` (só o incondicionado reduz a base) | base |
| Dedução/redução do ISS | `infDPS/valores/vDedRed/pDR`, `vDR`; calculado em `infNFSe/valores/vCalcDR` | mostrado no DANFSe |
| ISS | `infNFSe/valores/vBC`, `pAliqAplic`, `vISSQN`; retenção em `infDPS/valores/trib/tribMun/tpRetISSQN` | deduz da base até 2032 |
| PIS/COFINS | `infDPS/valores/trib/tribFed/piscofins/vPis`, `vCofins` | deduz só em 2026 |
| Retenções federais | `tribFed/vRetIRRF`, `vRetCSLL`, `vRetCP` | não afetam a base de IBS/CBS |
| Indicador da operação | `infDPS/IBSCBS/cIndOp` | local de incidência e combinação |
| Finalidade | `infDPS/IBSCBS/finNFSe` | |
| CST / cClassTrib | `infDPS/IBSCBS/valores/trib/gIBSCBS/CST`, `cClassTrib` | |
| Tributação regular | `infDPS/IBSCBS/valores/trib/gIBSCBS/gTribRegular/...` | suspensão |
| Base IBS/CBS | `infNFSe/IBSCBS/valores/vBC` | vBC |
| Reembolso/repasse | `infNFSe/IBSCBS/valores/vCalcReeRepRes` | deduz da base |
| IBS UF | `infNFSe/IBSCBS/valores/uf/pIBSUF`, `pRedAliqUF`, `pAliqEfetUF` | |
| IBS Mun | `infNFSe/IBSCBS/valores/mun/pIBSMun`, `pRedAliqMun`, `pAliqEfetMun` | |
| CBS | `infNFSe/IBSCBS/valores/fed/pCBS`, `pRedAliqCBS`, `pAliqEfetCBS` | |
| Totais | `infNFSe/IBSCBS/totCIBS/gIBS/vIBSTot`, `gIBSUFTot/vIBSUF`, `gIBSMunTot/vIBSMun`, `gCBS/vCBS`, `vTotNF` | |
| Localidade de incidência | `infNFSe/IBSCBS/cLocalidadeIncid`, `xLocalidadeIncid`, `uf` | confere com o cIndOp |
| Imóvel (obra) | `infDPS/IBSCBS/imovel/inscImobFisc`; `serv/obra/cObra` | construção civil |

O DANFSe mostra "Exclusões/Reduções da BC" = vDescIncond + vISSQN + vCalcDR + vCalcReeRepRes + vPis + vCofins, e a linha da Lei 12.741 com `totTrib`.

**Lendo um DANFSe em PDF**: use os mesmos rótulos (Valor do Serviço, Desconto Incondicionado, ISSQN, PIS, COFINS, Base de cálculo IBS/CBS, alíquotas e valores de CBS, IBS UF e IBS Mun, CST, cClassTrib, NBS, Código de Tributação Nacional, Indicador de Operação) e monte o JSON normalizado.

## NF-e / NFC-e (grupo `det/imposto/IBSCBS`, NT 2025.002)

| Dado | Caminho |
|---|---|
| Data, modelo | `ide/dhEmi`, `ide/mod` |
| Compra governamental | `ide/gCompraGov/tpEnteGov`, `pRedutor` |
| Regime | `emit/CRT` |
| Produto | `det/prod/NCM`, `vProd`, `vFrete`, `vSeg`, `vOutro`, `vDesc`, `qCom` |
| Tributos que deduzem | `imposto/ICMS*/vICMS`, `vFCP`, `vICMSMono`; `imposto/ICMSUFDest/vICMSUFDest`, `vFCPUFDest`; `PIS/vPIS`; `COFINS/vCOFINS`; `II/vII`; `ISSQN/vISSQN`; `IS/vIS` |
| CST, cClassTrib | `imposto/IBSCBS/CST`, `cClassTrib` |
| Grupo de cálculo | `IBSCBS/gIBSCBS/vBC`; `gIBSUF/pIBSUF`, `gIBSUF/gDif/pDif`, `vDif`, `gIBSUF/gRed/pRedAliq`, `pAliqEfet`, `vIBSUF`; o mesmo para `gIBSMun` e `gCBS`; `vIBS` |
| Tributação regular | `gIBSCBS/gTribRegular/CSTReg`, `cClassTribReg`, `pAliqEfetRegIBSUF`, `vTribRegIBSUF`, ... |
| Compra governamental (item) | `gIBSCBS/gTribCompraGov/pAliqIBSUF`, `vTribIBSUF`, ... |
| Monofasia | `IBSCBS/gIBSCBSMono/...`, `vTotIBSMonoItem`, `vTotCBSMonoItem` |
| Totais | `total/IBSCBSTot/vBCIBSCBS`, `gIBS/vIBS`, `gIBS/gIBSUF/vIBSUF`, `gIBS/gIBSMun/vIBSMun`, `gCBS/vCBS` |

`rtc.py extrair --nfe/--nfse` mostra o que foi lido. Se algum campo vier vazio por causa de uma variação de leiaute, complete o JSON à mão.
