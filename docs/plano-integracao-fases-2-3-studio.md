# Integração das fases 2 e 3 no Studio

Atualização: orçamento, avaliação A/B e importação revisada Meta foram integrados
ao Studio. Consulte [o guia de uso e configuração](orcamento-ab-importacao-meta.md).
O escopo restante (otimização, sugestões e índice de saúde) continua pendente.
O levantamento abaixo registra as lacunas identificadas antes dessa entrega;
o guia descreve o comportamento final do recorte implementado.

Inspeção de código em 2026-10-31. Este documento descreve trabalho necessário;
não afirma que as funcionalidades abaixo foram implementadas ou homologadas.
Escopo: CGS (orçamento, avaliação de experimentos, otimização) e CDMS
(conexões, ingestão, sugestões e índice de saúde). Login, workspaces e gestão
de usuários já estão no Studio.

## 1. Correções necessárias antes das telas

### Orçamento — CGS fase 2

Arquivos: `allocate_experiment_budget.py` e `sqlite_cgs_fase2_repo.py`.

- Persistir teto por workspace/ciclo. Hoje o caso de uso assume R$ 5.000 e a API
  não oferece configuração desse teto.
- Tornar a leitura do comprometido e a gravação uma única transação para impedir
  duas alocações concorrentes de ultrapassarem o limite.
- Definir orçamento por hipótese/ciclo. A tabela tem UNIQUE apenas na hipótese;
  seu UPSERT não atualiza cycle_id e recria gasto executado como zero ao editar.
- Criar registro de gasto, preservando histórico e permitindo registrar excesso
  real como ocorrência. A entidade atual rejeita gasto acima do alocado.
- Validar valores finitos, positivos, centavos, CPA e segunda-feira do ciclo;
  conferir hipótese, estado e vínculo com o ciclo no serviço compartilhado.

### Avaliação de experimentos — CGS fase 2

Arquivos: `bayesian_analyzer.py` e `sqlite_cgs_fase2_repo.py`.

- Resolver a divergência de método: o código usa aproximação normal com proporção
  combinada, apesar de apresentar o resultado como probabilidade bayesiana.
  Implementar posterior Beta-Binomial ou corrigir nomenclatura e interpretação.
- Validar contagens inteiras não negativas, conversões <= amostra, amostra mínima
  positiva, limites do limiar e suficiência dos dois grupos. Hoje apenas amostras
  maiores que zero são verificadas, e o piso considera somente tratamento.
- Definir como tratar controle com zero conversões: lift relativo não deve ser
  fabricado como 100%.
- Registrar desenho, grupos, período e unidade da métrica; apresentar incerteza e
  política de parada coerente com o método escolhido.
- Corrigir persistência: ao reavaliar, o UPSERT muda resultado, mas mantém as
  contagens e a data anteriores. A tabela só retém uma avaliação por hipótese.
  Preservar avaliações por execução/período e recuperar suas datas originais.

### Otimização e disjuntores — CGS fase 3

Arquivos: `optimize_variant_allocation.py`, `bandit_allocator.py`,
`auto_circuit_breaker.py` e `sqlite_cgs_fase3_repo.py`.

- Validar pelo menos dois braços, IDs únicos, contagens e parâmetros antes de
  acessar arms[0]. Hoje lista vazia pode gerar IndexError.
- Corrigir o piso de exploração: aplicar max(piso, peso) e depois normalizar
  pode reduzir o peso final abaixo do piso prometido. Garantir soma de 100%.
- Usar limites salvos no orçamento, com tratamento de ausência/atraso de dados;
  não depender apenas de limites reenviados em cada solicitação.
- Acrescentar proteção por orçamento esgotado e avaliar todos os tratamentos;
  hoje o disjuntor compara apenas os dois primeiros braços.
- Consultar o disjuntor persistido antes de nova otimização e implementar
  reativação explícita. Hoje um novo cálculo pode voltar a recomendar pesos
  mesmo com evento anterior ainda marcado como ativo.
- Exibir decisão efetiva após disparo, não pesos anteriores. O endpoint de leitura
  atual retorna a última alocação, sem incorporar o evento de bloqueio posterior.
- Preservar datas e histórico por ciclo, definir idempotência e registrar autor,
  entradas, versão da política e decisão.
- Corrigir mensagens: atualmente o código registra uma recomendação e um evento;
  não há adaptador que aplique os pesos ou faça rollback em campanhas reais.

## 2. Telas e serviços compartilhados

O Studio pode continuar chamando serviços de aplicação diretamente. Não é
necessário converter toda a interface em cliente HTTP. Extrair das rotas a
orquestração que ainda estiver acoplada a Request/HTTPException e reutilizá-la
na API e no Studio, com autorização e seleção do banco do workspace no servidor.

| Área | Tela e comportamento necessários |
|---|---|
| Experimentos / Orçamento | Hipótese, ciclo, teto, alocado, gasto, saldo, risco, CPA e histórico de alterações. |
| Experimentos / Avaliação A/B | Selecionar hipótese/execução, informar ou importar grupos, calcular, explicar resultado e consultar histórico. |
| Experimentos / Otimização | Cadastrar variantes, calcular pesos sugeridos, exibir bloqueios e registrar aprovação/reativação. |
| Configurações / Integrações | Cadastrar, validar, atualizar e desativar conta Meta; indicar permissões e agendamento. Nunca devolver tokens salvos ao navegador. |
| Integrações / Sincronizações | Solicitar semana encerrada, consultar fila, erros, resultado, retentativa e nova geração. Atualização periódica limitada, sem bloquear a página. |
| Ritual / Importar métricas | Revisar batch concluído, mostrar origem/semana/fuso/moeda/indisponibilidades e preencher rascunho; não fechar ritual automaticamente. |
| Experimentos / Sugestões | Gerar propostas a partir da auditoria, revisar/editar e adicionar ao backlog com vínculo à origem. |
| Cockpit / Saúde | Exibir índice, cobertura de dados, explicação e evolução a partir de rituais concluídos. |

VIEWER consulta; MEMBER opera experimentos e solicita sincronizações;
OWNER/ADMIN gerenciam conexões e limites conforme política documentada.
Manter os rascunhos isolados e limpar dados ao trocar identidade/workspace.

## 3. Integrações e infraestrutura

### Meta Ads

Já existem adaptador HTTP de leitura, credenciais Fernet, outbox, jobs com lease,
retentativas e agendamento. Falta interface, importação revisada no ritual e
homologação com conta real. As rotas estão em `routers/platforms.py`.

Para operar: chave Fernet CDMS_CREDENTIAL_KEY, credenciais válidas obtidas na Meta,
conta/evento de conversão, CDMS_REDIS_URL, processo Celery worker e processo beat.
Todos precisam compartilhar caminhos de identidade/workspaces e a chave de
credenciais. O compose atual sobe apenas Redis; worker e beat são processos
separados. Confirmar disponibilidade desses processos com evidência, sem exibir
"conectado" apenas porque há configuração. Não foram inspecionados os processos
em execução nesta análise.

OAuth e renovação automática não existem. YouTube e TikTok retornam 501 e exigem
adaptadores, contratos de métricas, autenticação e testes próprios. A ingestão
Meta atual é agregada por conta/semana: ela não fornece dados separados por
variante para o motor A/B/bandit. Criar mapeamento de campanhas/anúncios/grupos
para hipótese e variante, com janelas e deduplicação, antes de alimentar esse
motor automaticamente. Preservar moeda; não interpretar qualquer gasto como BRL.

### Sugestões

AIHypothesisGenerator é heurístico e não chama um LLM. A rota gera respostas,
mas não mantém histórico de revisão/aceite. Corrigir metas baseadas em defaults
de CTR/conversão e a inconsistência de sugerir taxa para uma métrica em unidades.
Persistir origem, regras/versão, entradas, estado e vínculo com a hipótese criada.
Um LLM é uma expansão opcional, com configuração e política de dados próprias.

### Índice de saúde

Há entidade e calculadora, mas não fluxo de aplicação/repositório/tela ligados
ao ritual. A migração antiga referencia workspaces e não deve ser copiada para
o banco operacional isolado sem adaptação. Criar persistência por ciclo com
versão do cálculo/calibrações. Decidir a política de dados ausentes: a calculadora
atual atribui zero a métrica indisponível, confundindo falta de dado com desempenho.

### Aplicação real de tráfego

É uma entrega distinta do cálculo de pesos. Exige um destino de execução
(plataforma de mídia ou serviço de roteamento), IDs das variantes, permissão de
escrita, aprovação, executor idempotente, leitura de confirmação, estado anterior,
rollback e auditoria. O adaptador Meta atual só lê métricas. Antes dessa entrega,
a interface deve apresentar pesos como sugestões e bloqueios como locais.

## 4. Ordem de implementação e aceite

1. Corrigir domínio e persistência; migrar sem perder registros existentes.
   Aceite: edição não zera gasto, avaliações são reconstituíveis, concorrência
   respeita teto, dados inválidos são recusados, bloqueio persiste até reativação.
2. Entregar Orçamento e Avaliação A/B no Studio. Aceite: fluxo real por hipótese,
   isolamento entre workspaces, VIEWER sem escrita e API/Studio com mesmas regras.
3. Entregar Otimização como recomendação. Aceite: pesos válidos, histórico,
   bloqueios e ausência de afirmações sobre execução externa não confirmada.
4. Entregar Integrações Meta e importação revisada. Aceite: fila indisponível não
   perde jobs, retentativa não duplica, tokens não vazam e ritual encerrado não
   é sobrescrito; homologação externa depende de conta/credenciais disponíveis.
5. Entregar sugestões e índice de saúde com origem e histórico verificáveis.
6. Só então adicionar execução externa de tráfego e novos conectores.

Testes necessários: domínio (limites e casos degenerados), migrações/UPSERT,
concorrência e idempotência, contratos API, AppTest dos fluxos, revogação de acesso,
isolamento por workspace, falha de broker e contratos HTTP simulados. Testes com
serviços reais são uma etapa separada dos testes determinísticos locais.
