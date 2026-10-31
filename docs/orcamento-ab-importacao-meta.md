# Orçamento, avaliação A/B e importação Meta no Studio

## Onde usar

- **Experimentos → Orçamento dos testes**: selecione o ciclo na lateral, cadastre
  hipóteses no Backlog, configure o teto e aloque valores por hipótese. OWNER/ADMIN
  alteram o teto; MEMBER também pode alocar e registrar gasto acumulado. VIEWER
  apenas consulta. No modo local explícito, o operador pode gerenciar orçamento.
- **Experimentos → Avaliação A/B**: escolha uma hipótese, descreva evento e unidade
  de exposição, informe as contagens de controle/tratamento e a amostra mínima.
  Confirme a revisão dos grupos antes de salvar. Cada avaliação mantém entradas,
  método, autor e data, sem sobrescrever a anterior.
- **Configurações → Integrações**: OWNER/ADMIN validam e cadastram contas Meta Ads,
  atualizam credenciais recadastrando a mesma conta e desativam conexões.
- **Cockpit → Importações Meta Ads**: acompanhe os jobs da semana selecionada,
  solicite coleta, repita falhas ou crie uma nova geração de resultados. Atualize
  a lista manualmente para acompanhar o worker.
- Depois de SUCCESS, revise o resultado e confirme **Usar no rascunho do ritual**.
  O ritual abre na etapa Métricas. Nenhuma decisão é concluída automaticamente.

## Painel contextual de evidências

O botão **Evidências** abre um card flutuante à direita sem reduzir a área
principal. O painel começa fechado e pode ser fechado pelo X. No celular, o
botão fica junto aos controles de navegação.

Em Orçamento e Avaliação A/B, acompanha a hipótese selecionada. No Backlog,
use **Ver evidências** em cada hipótese. Mostra orçamento e avaliação salvos,
diagnóstico, decisão e origem Meta do ciclo correspondente. Alterações ainda
não salvas ficam no formulário principal e não aparecem como evidência.

Os rascunhos de orçamento/A-B são mantidos durante a abertura e fechamento do
card. A troca de workspace autenticado limpa a sessão e a seleção de contexto.

## Regras do orçamento

Valores em BRL, com centavos. O teto inicial é R$ 5.000 por ciclo e pode ser
alterado antes de comprometer valores maiores. A verificação e a alocação ocorrem
na mesma transação. Editar uma alocação preserva gasto e data inicial.
O gasto é acumulado, não pode diminuir e pode exceder o alocado: esse excesso
fica visível como alerta. O sistema registra valores; não movimenta dinheiro,
pausa campanhas ou atualiza automaticamente gasto de hipóteses a partir da Meta.

O modelo novo usa experiment_budgets, experiment_cycle_limits,
experiment_budget_events e experiment_evaluations. Por orientação do usuário,
não há importação ou compatibilidade com tabelas antigas de orçamento/avaliação.
Os arquivos de banco existentes não são apagados.

## Interpretação da avaliação

Posteriores independentes Beta(conversões+1, amostra-conversões+1), com prior
Beta(1,1), calculadas com 30.000 simulações reproduzíveis. São apresentados
probabilidade de tratamento superar controle e intervalo de credibilidade de
95% da diferença das taxas, em pontos percentuais. É uma aproximação Monte Carlo,
não o antigo Z-score. Conversões precisam representar unidades binárias únicas;
contagens de eventos repetidos por pessoa não são entradas válidas desse modelo.

A amostra mínima vale para os dois grupos. O limiar de ganho é 95%. Com menos de
metade da amostra mínima, a análise permanece inconclusiva. Uma perda observada
superior a 30%, com probabilidade de ganho de até 5% e pelo menos metade da amostra
em ambos os grupos, gera indicação de considerar interrupção, sem ação externa.
Essas regras são uma política operacional, não uma garantia de resultado.
Controle com zero conversões tem lift relativo indefinido, exibido como tal.

O resultado não comprova causalidade por si só: depende da alocação adequada dos
grupos, mesma métrica e janela e independência das unidades. A janela do registro
é o ciclo semanal escolhido. Avaliações não mudam o estado da hipótese nem fecham
seu resultado no ritual; essa decisão continua explícita.

## Infraestrutura Meta

O Studio reutiliza os mesmos serviços e bancos da API; não exige API HTTP local.
São necessários no ambiente do Studio e dos workers:

- CDMS_IDENTITY_DB_PATH e CDMS_WORKSPACE_DATA_DIR apontando para os mesmos dados.
- CDMS_CREDENTIAL_KEY: chave Fernet própria, estável, diferente da chave JWT.
- CDMS_REDIS_URL, por exemplo redis://127.0.0.1:6381/0 para o compose existente.
- Token Meta de leitura da conta e Insights, ID act_..., evento e versão de API.
  CDMS_META_API_VERSION pode definir a versão padrão. Valide a versão e as
  permissões disponíveis na sua conta ao configurar a integração.

Redis (não iniciado automaticamente pela interface):

```powershell
docker compose -f compose.automation.yml up -d
```

Worker local Windows e agendador, em terminais separados com o mesmo ambiente:

```powershell
.\.venv\Scripts\python.exe -m celery -A cdms.adapters.tasks.celery_app worker --pool=solo --loglevel=info
.\.venv\Scripts\python.exe -m celery -A cdms.adapters.tasks.celery_app beat --loglevel=info
```

Mantenha apenas um beat por instalação. O compose atual fornece somente Redis.
Sem broker, a solicitação continua na outbox como pendente; worker e dispatcher
precisam voltar para processá-la. Marcar sincronização automática ativa a coleta
semanal via beat, não inicia processos. Uma conexão salva não prova que a fila
está operacional. O painel não exibe uma indicação inventada de saúde do worker.

As credenciais são cifradas no banco e não são retornadas nas listas. Os campos
secretos do formulário são limpos após o envio. Não há OAuth nem renovação
automática do token. Desativar localmente não revoga o token externo.

## Importação e rastreabilidade

Somente semanas completas encerradas no fuso da conta são aceitas. O batch
preserva período, moeda, fuso, evento, versão e definições das métricas. Retenção
média continua indisponível no adaptador Meta; não vira zero. Gasto em moeda
estrangeira não é convertido para reais. A coleta é agregada por conta, não por
variante A/B, e não alimenta automaticamente a avaliação de experimentos.

O aceite da importação grava origem, usuário e data em ritual_metric_sources.
Os valores podem ser revisados no rascunho. Um ritual encerrado não é sobrescrito.
Nova coleta mantém as versões anteriores. A revisão não encerra o ritual nem
constitui registro de gasto de um experimento.

## Demonstração offline (pacote 2.0)

Em **CDMS Demo → Demonstração**, carregue ou restaure o pacote. A versão 2.0
inclui 13 orçamentos, 13 avaliações A/B e 15 coletas fictícias, distribuídas entre
os ciclos históricos e um ciclo de prática aberto. Há ganho, perda, amostra
insuficiente, gasto acima da alocação e coletas concluídas, pendentes e com falha.

O botão **Praticar orçamento, A/B e importação** abre o Cockpit no ciclo aberto.
As três contas em **Configurações → Integrações** são fictícias e não pedem token.
No Cockpit, conclua a coleta pendente, repita a falha ou gere uma nova versão;
as operações acontecem localmente, sem Meta, Redis, worker ou credenciais.
Revise o resultado antes de preencher o rascunho do ritual. Os rituais históricos
continuam protegidos contra sobrescrita. As amostras A/B são exemplos didáticos
de grupos e não são extraídas dos agregados Meta simulados.

Pacotes 1.0 já carregados precisam ser carregados novamente ou restaurados para
receber os novos exemplos. A restauração cria uma nova geração isolada, preserva
o banco anterior e limpa os rascunhos. O modo Local e workspaces autenticados
continuam usando seus próprios bancos e serviços; a simulação só aceita arquivos
dentro da raiz de demonstração.

## API de experimentos

/growth-v2 mantém orçamento e avaliação, agora com cycle_id obrigatório na
avaliação e lift_pct opcional. Foram adicionados:

- GET /api/v1/growth-v2/cycles/{cycle_id}/budget
- PUT /api/v1/growth-v2/cycles/{cycle_id}/limit, com amount_reais
- PUT /api/v1/growth-v2/budgets/{hypothesis_id}/cycles/{cycle_id}/spend, com amount_reais
- GET /api/v1/growth-v2/evaluations/{hypothesis_id}/history?cycle_id=YYYY-MM-DD

Os endpoints Meta continuam em /api/v1/automation e compartilham os serviços de
conexão e fila do Studio. Login, papel vigente e armazenamento isolado por
workspace continuam obrigatórios.

## Validação

Os testes usam SQLite temporário, HTTP Meta controlado e credenciais de teste.
A homologação com conta Meta real exige credenciais e permissões do proprietário;
nenhuma conta externa real foi conectada automaticamente.

Suíte completa: `python -m pytest -q -x` — **242 testes aprovados e 1 ignorado**
(transporte Redis de teste não configurado), com cinco avisos de depreciação de
dependências. O teste de orçamento/A-B no Studio também foi repetido após o
ajuste final de isolamento dos formulários e passou.
