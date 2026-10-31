# Future work — Growth Intelligence

Registro: 2026-10-30.

Status: propostas para evolução futura; este documento não declara funcionalidades implementadas, nem altera o escopo das especificações vigentes.

## Origem e direção

Propostas discutidas com o usuário após a análise do material **Growth Intelligence — Estratégia de Crescimento com Dados, IA e Experimentação**, do professor Fabrizzio Topper, USP/ESALQ. O usuário relatou ter participado de uma palestra do professor e destacou a sequência **dados → métricas → resultados → gestão = growth**.

A direção é transformar dados em decisões de gestão e aprendizado contínuo. A métrica principal oferece uma referência para a gestão estratégica; essa camada também precisa de objetivos, metas, responsáveis e decisões. O ritual CDMS e a experimentação CGS são a base operacional para essa evolução.

Referência local consultada: `C:\Projetos\USPESALQ\Growth Intelligence.pdf`. As páginas abaixo correspondem à numeração física do PDF. A referência é conceitual; os números e casos apresentados não foram validados como benchmarks do projeto. Exercícios e instruções contidos nos slides não constituem requisitos do produto.

## Sequência de evolução acordada

1. Consolidar, integrar e validar as funcionalidades já desenvolvidas que sustentam o fluxo diagnóstico → hipótese → decisão → execução → avaliação.
2. Introduzir uma métrica principal e uma árvore de métricas enxuta assim que esse fluxo central funcionar de ponta a ponta, sem aguardar todo o roadmap.
3. Aprimorar a medição de impacto incremental, planejando a avaliação antes da execução dos experimentos.
4. Evoluir a análise de retenção por coortes conforme a disponibilidade de histórico adequado. A preparação desses dados pode ocorrer em paralelo às etapas anteriores.
5. Considerar um modelo preditivo quando houver dados suficientes e uma decisão operacional concreta a apoiar.

As demais propostas abaixo permanecem no backlog conceitual. A sequência é uma orientação de dependências, sem compromisso de prazo ou implementação automática.

## FW-01 — Métrica principal e árvore de métricas

**Referência:** páginas 25–30. **Prioridade sugerida:** alta após a consolidação do fluxo central.

- Definir uma North Star por negócio/workspace, com descrição, fórmula, unidade, período e fonte dos dados.
- Validar se representa valor entregue ao cliente, pode ser influenciada pelo time e tem relação verificável com receita sustentável.
- Relacionar a métrica principal a poucas alavancas e aos indicadores operacionais existentes.
- Vincular cada hipótese CGS à alavanca que pretende mover, explicitando a relação esperada com o objetivo do negócio.
- Registrar metas, responsáveis e versões das definições para preservar a interpretação histórica.

**Primeiro recorte:** uma métrica principal, poucas alavancas e vínculo explícito das hipóteses. A escolha da métrica depende do modelo de negócio; nenhuma North Star foi definida nesta conversa.

**Critério para detalhar a implementação:** conseguir percorrer objetivo → métrica principal → alavanca → indicador → hipótese → decisão semanal, com dados disponíveis e definições claras.

## FW-02 — Medição de impacto incremental

**Referência:** páginas 31–32. **Prioridade sugerida:** alta após a definição da direção estratégica.

- Distinguir oportunidade financeira estimada, variação observada e efeito atribuível à intervenção.
- Planejar antes do teste: hipótese, público elegível, controle/tratamento, métrica, unidade de alocação, amostra, janela e critérios de decisão.
- Usar controle randomizado quando viável; registrar limitações quando o desenho não permitir uma conclusão causal.
- Apresentar efeito estimado e incerteza, incluindo resultado inconclusivo quando necessário.
- Vincular a avaliação à hipótese e ao relatório do ciclo, respeitando experimentos cuja janela ultrapasse uma semana.

**Revisões prévias identificadas na análise do código:**

- `ExportCycleReportUseCase` apresenta redução de oportunidade estimada entre ciclos como “ROI de Governança Positivo”. Revisar a nomenclatura; essa diferença, isoladamente, não comprova retorno causado pela gestão. ROI requer benefícios e custos medidos.
- `BayesianExperimentAnalyzer` utiliza uma aproximação normal com proporção combinada. Alinhar método, nomenclatura, validações e regras de parada antes de apresentar o resultado como evidência bayesiana ou causal.

Esses apontamentos são de inspeção do código, não resultados de uma nova execução de testes.

## FW-03 — Retenção por coortes

**Referência:** páginas 8–11. **Prioridade sugerida:** alta quando houver dados adequados de clientes, compras, assinaturas ou uso.

O funil de aquisição/conversão não mostra sozinho se os clientes continuam recebendo valor após a compra. Agrupar clientes por entrada permite observar retenção, recompra e deterioração que os totais agregados podem esconder.

- Definir o evento de entrada na coorte: primeira compra, assinatura ou ativação, conforme o negócio.
- Definir o que significa permanecer ativo, recomprar ou cancelar, além da granularidade temporal apropriada.
- Exibir retenção por idade da coorte, com tamanhos dos grupos e denominadores explícitos.
- Diferenciar períodos ainda não observados de retenção zero; comparar coortes com maturidade equivalente.
- Evoluir para receita por coorte e valor do cliente quando os dados permitirem, com premissas explícitas para estimativas de LTV/CLV.
- Relacionar intervenções e segmentos às coortes sem atribuir causalidade apenas à diferença entre grupos.

**Dependências:** identificador estável de cliente no workspace, histórico de eventos com datas, tratamento de duplicidades e definições consistentes. Métricas semanais agregadas de mídia não bastam para reconstruir retenção de clientes.

**Primeiro recorte:** uma definição de coorte e uma matriz de retenção/recompra com contagens e taxas auditáveis. Coortes também podem fornecer histórico para futuros modelos preditivos.

## FW-04 — Modelo preditivo orientado à decisão

**Prioridade sugerida:** posterior à estruturação das métricas e à disponibilidade de histórico suficiente.

- Escolher um problema delimitado, como risco de cancelamento, ligado a uma ação operacional viável.
- Definir alvo, horizonte de previsão e dados disponíveis no momento da decisão.
- Comparar o modelo com uma regra simples, usando validação temporal e evitando vazamento de informação futura.
- Avaliar calibração, custo dos erros e capacidade operacional de atender aos alertas.
- Monitorar desempenho e mudanças nos dados após implantação.
- Avaliar o valor da intervenção separadamente da qualidade da previsão: prever quem cancelará não identifica automaticamente quem se beneficiará de uma ação.

Não foi escolhido algoritmo nem assumida suficiência dos dados atuais. O modelo deve apoiar uma decisão concreta e ter seu benefício operacional avaliado.

## FW-05 — Loop dominante de crescimento

**Referência:** páginas 22–23. **Prioridade sugerida:** média.

Registrar como o valor entregue gera retorno e realimenta o negócio, por exemplo conteúdo → engajamento → retorno → distribuição. Relacionar o loop às alavancas da árvore e ao backlog, sem presumir um único mecanismo para todos os modelos de negócio.

## FW-06 — Sugestões de IA com contexto e evidências

**Referência:** páginas 33–42. **Prioridade sugerida:** média.

Evoluir as sugestões heurísticas existentes com objetivo, segmento, restrições, dados disponíveis, evidências e critérios de sucesso. Preservar revisão humana e rastreabilidade das sugestões. Separar regras fixas de eventual integração com modelo generativo; a existência do gerador atual não comprova integração com LLM.

## FW-07 — Tempo entre sinal, decisão e ação

**Referência:** página 36. **Prioridade sugerida:** média/baixa, conforme a necessidade operacional.

Registrar quando o evento ocorreu, quando o dado ficou disponível, quando houve decisão e quando a ação foi executada. Começar com acompanhamento de prazos e alertas. Automação de intervenções exige desenho próprio e não decorre automaticamente desta proposta.

## Próximo passo quando este trabalho for retomado

Reavaliar o estado real da implementação e dos dados, transformar o primeiro recorte escolhido em especificação e definir critérios de aceite antes de desenvolver. Manter este documento como histórico da motivação e atualizar os vínculos para as especificações e entregas que vierem a concretizar cada proposta.
