# Códigos de erro das calculadoras oficiais

Catálogo do `ProblemType` da calculadora de regime regular. REG = inconsistência de entrada, CAL = falha de cálculo/parametrização. Erros da NFS-e: E1534 (ajustes ≥ vServ), E1302 (MEI sem base), E0436 (MEI com documentos de ajuste), LEIAUTE-XTP (tpAjusteBC 199 sem descrição), BASE-NEGATIVA. O Simples Nacional usa códigos VSN-xxx.

| Código | Título | Descrição |
|---|---|---|
| REG-024 | Campo inválido | O valor informado para o campo não é válido conforme as regras de negócio. |
| REG-001 | NCM e NBS informadas simultaneamente | Apenas uma nomenclatura (NCM ou NBS) deve ser informada por item. A presença simultânea impede a classificação. |
| REG-002 | NCM não encontrada | O código NCM informado não foi localizado na base de nomenclaturas vigente para a data do fato gerador. |
| REG-003 | NBS não encontrada | O código NBS informado não foi localizado na base de nomenclaturas vigente para a data do fato gerador. |
| REG-004 | Situação tributária não encontrada | A situação tributária (CST) informada não existe na base de dados para o tributo e data do fato gerador. |
| REG-005 | Classificação tributária não encontrada | A classificação tributária informada não foi localizada na base vigente para a data do fato gerador. |
| REG-006 | Classificação tributária não vinculada à situação tributária | A classificação tributária informada não está vinculada à situação tributária selecionada. |
| REG-007 | Erro de nomenclatura | A nomenclatura informada apresenta inconsistência com as regras de classificação tributária vigentes. |
| REG-008 | Tratamento de classificação não encontrado | Não foi encontrado tratamento de classificação tributária para os parâmetros informados. |
| REG-009 | Grupo de tributação regular não informado | O grupo de tributação regular é obrigatório para a situação tributária selecionada e não foi informado. |
| REG-010 | Incompatibilidade com suspensão | A classificação tributária informada é incompatível com a situação de suspensão aplicada ao item. |
| REG-011 | NCM não vinculada | O código NCM informado não está vinculado a nenhuma classificação tributária vigente. |
| REG-012 | NBS não vinculada | O código NBS informado não está vinculado a nenhuma classificação tributária vigente. |
| REG-013 | Dados do Imposto Seletivo não informados | Os dados do Imposto Seletivo são obrigatórios para a classificação tributária selecionada e não foram informados. |
| REG-014 | Dados do Imposto Seletivo informados indevidamente | Os dados do Imposto Seletivo foram informados, mas a classificação tributária selecionada não prevê incidência. |
| REG-015 | NCM completo não informado | O código NCM deve ser informado com todos os dígitos (completo) para a operação solicitada. |
| REG-016 | NBS completo não informado | O código NBS deve ser informado com todos os dígitos (completo) para a operação solicitada. |
| REG-018 | Município não pertencente à UF | O município informado não pertence à UF indicada na operação. |
| REG-019 | Município não encontrado | O código do município informado não foi localizado na base de dados. |
| REG-020 | UF não encontrada | A UF informada para a operação não foi encontrada na base de dados. |
| REG-021 | Data do fato gerador não informada | A data do fato gerador é obrigatória e não foi informada na requisição. |
| REG-022 | Grupo de tributação regular informado indevidamente | O grupo de tributação regular foi informado, mas a situação tributária selecionada não o exige. |
| REG-023 | Erro genérico de validação | Erro de validação que não se enquadra em nenhuma categoria específica. |
| REG-025 | Base de cálculo não informada | A base de cálculo de CBS e IBS é obrigatória quando o grupo do Imposto Seletivo não é informado. |
| REG-026 | Base de cálculo inconsistente | A base de cálculo de CBS e IBS informada difere da soma da base de cálculo do Imposto Seletivo com o Imposto Seletivo informado. |
| REG-027 | Base de cálculo menor que a base de cálculo do Imposto Seletivo | A base de cálculo de CBS e IBS informada é menor que a base de cálculo do Imposto Seletivo. |
| REG-028 | Tipo de documento fiscal não encontrado | O tipo de documento fiscal (tpDoc) informado na operação não existe ou está fora de vigência na data do fato gerador. |
| REG-029 | Classificação tributária não vinculada ao tipo de documento | A classificação tributária informada não possui vínculo vigente com o tipo de documento fiscal (tpDoc) da operação. |
| REG-030 | Nomenclatura incompatível com o tipo de documento | A nomenclatura informada (NCM ou NBS) não é aceita para a classificação tributária no tipo de documento fiscal (tpDoc) da operação. |
| REG-031 | Nomenclatura não permitida para o tipo de documento | O tipo de documento fiscal (tpDoc) da operação não admite o preenchimento de NCM ou NBS. |
| REG-032 | Imposto Seletivo não admitido pelo tipo de documento | O NCM/NBS informado é tributado pelo Imposto Seletivo, mas o tipo de documento fiscal (tpDoc) da operação não admite Imposto Seletivo. |
| REG-033 | Nomenclatura obrigatória não informada | A classificação tributária possui anexo com NCM e NBS aplicáveis e exige o preenchimento de um deles, completo, para o tipo de documento fiscal (tpDoc) da operação. |
| REG-034 | Base de cálculo inconsistente | A base de cálculo declarada no item diverge da base calculada a partir dos componentes informados |
| REG-035 | Alíquota do Imposto Seletivo não informada | A NCM/NBS possui incidência do Imposto Seletivo, mas a alíquota ainda não foi definida em lei e não foi informada pelo usuário. |
| REG-036 | Alíquotas nominais informadas indevidamente | As alíquotas nominais não podem ser informadas para fato gerador anterior a 01/01/2027, pois a calculadora resolve as alíquotas vigentes. |
| REG-037 | Alíquotas nominais não informadas | As alíquotas nominais (cbs, ibsEstadual e ibsMunicipal) devem ser informadas para fato gerador a partir de 01/01/2027. |
| CAL-001 | Alíquota não encontrada | Não foi possível localizar a alíquota aplicável para os parâmetros tributários informados. |
| CAL-002 | Alíquota padrão não encontrada | A alíquota padrão (de referência) não foi encontrada na base para o tributo e período informados. |
| CAL-003 | Alíquota de referência não encontrada | A alíquota de referência necessária para o cálculo não está disponível na base de dados. |
| CAL-004 | Alíquota ad rem não encontrada | A alíquota ad rem (valor fixo por unidade) não foi localizada para o produto e período informados. |
| CAL-005 | Alíquota negativa | O cálculo resultou em uma alíquota negativa, o que indica inconsistência nos parâmetros tributários. |
| CAL-006 | Tipo de alíquota desconhecido | O tipo de alíquota retornado pela base de dados não é reconhecido pelo sistema. |
| CAL-007 | Classificação tributária em desenvolvimento | A classificação tributária informada ainda não possui implementação completa no sistema. |
| CAL-008 | Erro no avaliador de expressão aritmética | Ocorreu um erro ao avaliar a expressão aritmética utilizada no cálculo do tributo. |
| CAL-009 | Tratamento tributário não encontrado | O tratamento tributário aplicável não foi localizado para a combinação de parâmetros informada. |
| CAL-010 | Percentual de redução não encontrado | O percentual de redução de alíquota previsto para a classificação não foi encontrado na base. |
| CAL-011 | Fundamentação não encontrada | A fundamentação legal para a classificação tributária não foi localizada na base de dados. |
| CAL-012 | Tributo/situação tributária não encontrado | A combinação de tributo e situação tributária informada não foi localizada na base. |
| CAL-999 | Erro interno do sistema | Erro interno inesperado durante o processamento do cálculo. Contate o suporte se o problema persistir. |
