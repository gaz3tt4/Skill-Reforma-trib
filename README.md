# Skill-Reforma-trib
# auditoria-tributos-rtc

Skill para Claude que confere se os tributos da Reforma Tributária do Consumo (CBS, IBS e Imposto Seletivo – LC 214/2025) estão corretos em documentos fiscais.

## O que faz
- Lê XML de NF-e/NFC-e e de NFS-e Nacional (ou dados de PDF, planilha ou ERP convertidos para JSON).
- Confere:
  - CST, cClassTrib e tipo de documento;
  - vínculo de NCM/NBS com o cClassTrib;
  - combinação NBS × cIndOp × item da LC 116;
  - base de cálculo, reduções, alíquota efetiva e valores de CBS, IBS UF e IBS Mun;
  - diferimento, suspensão, compra governamental e totais.
- Calcula o IBS/CBS do Simples Nacional (CRT, tipo de receita bruta, atividade, valor devido ou pendente).
- Consulta cClassTrib, CST, NCM e NBS na base oficial.

## Base
Regras e dados extraídos dos repositórios públicos da Receita Federal:
- [calculadora-rtc-regime-regular](https://github.com/ReceitaFederal/calculadora-rtc-regime-regular)
- [calculadora-rtc-simples-nacional](https://github.com/ReceitaFederal/calculadora-rtc-simples-nacional)
- [calculadora-rtc-gerador-danfse](https://github.com/ReceitaFederal/calculadora-rtc-gerador-danfse)

`data/rtc.db` é um SQLite gerado dos scripts Flyway oficiais. Para atualizá-lo, rode `python -I scripts/atualizar_base.py`.

## Uso
    python -I scripts/rtc.py validar --nfse nota.xml
    python -I scripts/rtc.py validar --nfe nota.xml
    python -I scripts/rtc.py consultar cclasstrib 200028 --data 2027-01-01

Para usar como skill, copie a pasta para `~/.claude/skills/` ou envie o `.zip` ao claude.ai.

## Limites
- Para 2027 em diante, a skill aceita a alíquota declarada na nota e confere a consistência do cálculo, mas não indica a alíquota oficial de cada ente.
- Monofasia e ajustes não são calculados (a calculadora oficial também não os calcula).
- Não substitui a análise de um contador sobre o enquadramento da operação.

Projeto independente, sem vínculo com a Receita Federal. Os dados de origem estão sob licença MIT.
