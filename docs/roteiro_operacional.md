# 🗺️ Roteiro Operacional e de Engenharia — CDMS & CGS Suite

**Versão da Suíte:** CDMS v2.4.0 + CGS v1.2.0  
**Status do Projeto:** 51/51 Testes Automatizados Aprovados (100% Sucesso)  
**Ambiente:** Python 3.11+, Streamlit, SQLite nativo via `src/` layout (PEP 517/621)  

---

## 🎯 Objetivo Deste Roteiro

Este guia atua como a referência canônica operacional para desenvolvedores, gestores de tráfego e criadores de conteúdo que utilizam a suíte integrada. Ele cobre:
1. **Configuração de Ambiente e Homologação Técnica**
2. **Roteiro Semanal de Operação (Ritual do CDMS + Diagnóstico CGS)**
3. **Fluxo de Experimentação em Circuito Fechado**
4. **Resolução de Problemas e Boas Práticas Multiplataforma**

---

## 💻 1. Guia de Instalação e Homologação Técnica

### 1.1. Inicialização do Ambiente Virtual

Abra o terminal na raiz do projeto `cdms`:

```bash
# Criar ambiente virtual caso não exista
python -m venv .venv

# Ativar no Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Ativar no Linux / macOS:
source .venv/bin/activate

# Atualizar pip e instalar o pacote com dependências completas
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 1.2. Execução da Suíte de Testes Automatizados

Antes de iniciar qualquer ciclo operacional, confirme a integridade dos contratos e esquemas SQLite executando a suíte consolidada de 51 testes:

```bash
pytest -v
```

**Resultado Esperado:**
* `tests/integration/test_lifecycle_and_sync.py`: 4 testes aprovados (máquina de estados, trava causal, funil de 2 passos e sincronização CDMS).
* `tests/integration/test_sqlite_growth_repo.py`: 7 testes aprovados (migrações 2 e 3, ranking ICE).
* `tests/integration/test_sqlite_repo.py`: 2 testes aprovados (atomicidade e calibração).
* `tests/unit/test_diagnose_scenario.py`: 3 testes aprovados (cobertura exaustiva de 81 combinações).
* `tests/unit/test_funnel_analyzer.py`: 11 testes aprovados (validações, empates e detecção de gargalo).
* `tests/unit/test_growth_hypothesis.py`: 15 testes aprovados (ICE score, limites numéricos).
* `tests/unit/test_metrics.py`: 6 testes aprovados (snapshots e desvios).
* `tests/unit/test_run_weekly_ritual.py`: 3 testes aprovados (idempotência e auditoria de decisões).
* **Total:** `51 passed in ~8s`

### 1.3. Inicialização da Interface Unificada

```bash
streamlit run app.py
```
Acesse o painel em `http://localhost:8501`.

---

## 🗓️ 2. Roteiro Operacional do Ritual Semanal (Segunda-Feira)

O ritual ocorre semanalmente às segundas-feiras (`cycle_id = YYYY-MM-DD`), seguindo uma sequência estrita em 4 passos:

```text
[Passo 1: Auditoria] ➔ [Passo 2: Ingestão] ➔ [Passo 3: Diagnóstico] ➔ [Passo 4: Decisão Única]
```

---

### Passo 1: Auditoria da Hipótese do Ciclo Anterior
* **Objetivo:** Confrontar a decisão anterior com as evidências reais da semana e fechar o aprendizado.
* **Ações no Painel:**
  1. Revise a meta estabelecida na semana anterior.
  2. Selecione o veredito operacional:
     - `ACHIEVED`: Meta alcançada sem ressalvas.
     - `PARTIAL`: Aprendizado conclusivo, meta parcialmente cumprida.
     - `NOT_ACHIEVED`: Invalidação de hipótese ou meta não alcançada.
  3. Insira notas e aprendizados qualitativos (sazonalidades, bloqueios de plataforma).
* **Impacto no CGS:** Caso a decisão tenha sido promovida a partir de uma hipótese do CGS, o `SyncCDMSOutcomeUseCase` sincroniza automaticamente seu status:
  - `ACHIEVED` ou `PARTIAL` $\rightarrow$ `HypothesisStatus.COMPLETED`
  - `NOT_ACHIEVED` $\rightarrow$ `HypothesisStatus.DISCARDED`

---

### Passo 2: Inserção de Métricas Canônicas
* **Objetivo:** Alimentar os indicadores fundamentais sem vaidade.
* **Entrada Manual ou Ingestão por Arquivo (CSV/XLSX):**
  - **Alcance Semanal (`reach`):** Usuários únicos alcançados no canal principal.
  - **Retenção Média (`avg_retention_pct`):** Média percentual ponderada de consumo dos vídeos.
  - **CTR (`ctr_pct`):** Percentual médio de cliques por impressão.
  - **Conversões (`conversions`):** Vendas diretas ou novos cadastros qualificados.
* **Ingestão Assistida:** Utilize o importador `PlatformMetricsParser` para carregar relatórios brutos do YouTube Studio, Meta Ads ou TikTok.

---

### Passo 3: Avaliação Heurística de Cenário
* **Objetivo:** Receber o diagnóstico determinístico gerado pelo motor de 81 combinações:
  - 🟢 **STABILITY (Equilíbrio Nominal):** Nenhuma métrica abaixo e no máximo 1 acima da referência. Foco em consistência.
  - 🚀 **SCALE (Alavancagem de Escala):** 0 métricas abaixo e 2 ou mais acima. Momento propício para expansão de volume ou budget.
  - 🔴 **PRE_DROP (Risco de Queda):** 2 ou mais métricas abaixo da baseline. Prioridade máxima em contenção de danos e correção rápida.
  - 🟠 **ANOMALY (Assimetria Crítica):** Ao menos 1 métrica abaixo e 1 acima simultaneamente. Ajuste de transição entre etapas do funil.
  - ⚪ **INCONCLUSIVE:** Dispersão sem enquadramento (`MIXED_SIGNALS`) ou falta de métricas (`MISSING_DATA`).

---

### Passo 4: Travar a Decisão Única do Ciclo
* **Objetivo:** Garantir causalidade analítica impedindo múltiplos testes descontrolados na mesma semana.
* **Ação:**
  - Consuma a minuta gerada na aba de Propostas do CGS ou declare manualmente a hipótese.
  - Clique em **"Gravar Ritual Semanal"** para executar o commit atômico no SQLite.

---

## 🚀 3. Roteiro de Experimentação e Funil (Creator Growth System)

Acesse o módulo **CGS (Growth Engine)** pelo menu lateral do painel para diagnosticar gargalos monetários e manter o backlog de experimentação vivo.

---

### Etapa 3.1: Calibração da Linha de Base Comercial (Aba 3)
1. Escolha o modelo de conversão da operação:
   - **Venda Direta (`DIRECT_SALE`):** Para infoprodutos, e-commerces e checkouts diretos.
   - **Funil em Dois Passos (`LEAD`):** Para operações com opt-in, captura de leads e fechamento posterior.
2. Defina os parâmetros:
   - **Ticket Médio ($R\$$):** Valor médio por produto comercializado.
   - **CTR Meta (%):** Taxa de cliques de referência no criativo.
   - **Taxa de Captura (%):** Percentual esperado de cliques que viram leads (apenas modelo `LEAD`).
   - **Taxa de Fechamento (%):** Percentual esperado de leads que fecham compra (apenas modelo `LEAD`).
3. Clique em **"Salvar Baseline Ativa"**.

---

### Etapa 3.2: Diagnóstico de Funil e Histórico Acumulado (Aba 1)
1. Insira os dados brutos da semana: `Impressões`, `Cliques`, `Leads` (se aplicável) e `Conversões`.
2. Clique em **"Executar Diagnóstico Financeiro"**:
   - Visualize a oportunidade estimada em reais ($R\$$) decomposta em:
     - **Perda em Intenção (CTR)**
     - **Perda em Captura de Lead**
     - **Perda em Fechamento de Venda**
   - Identifique o gargalo crítico: `INTENTION`, `LEAD_CAPTURE`, `LEAD_CLOSING` ou `CONVERSION`.
3. Inspecione o **Histórico Acumulado de Oportunidades**:
   - Avalie o delta de redução de desperdício em $R\$$ frente ao ciclo anterior (ROI da governança).
   - Analise o gráfico temporal de barras empilhadas e a tabela de auditorias gravadas.

---

### Etapa 3.3: Gestão de Backlog e Governança de Hipóteses (Aba 2)
1. **Cadastrar Nova Hipótese:**
   - Especifique a ação prática e selecione a **Variável Única** (`CREATIVE`, `HOOK`, `CTA`, `OFFER` ou `LANDING_PAGE`).
   - Defina a métrica-alvo, direção (`HIGHER_IS_BETTER` ou `LOWER_IS_BETTER`), referência atual, meta de sucesso e piso de invalidação rápida.
   - Calibre as notas de **Impacto (1-10)**, **Confiança (1-10)** e **Facilidade (1-10)** para gerar o ICE Score.
   - Salve no backlog (status `PENDING`).
2. **Promover para Ritual CDMS:**
   - Na sub-aba **⏳ Pendentes**, selecione a hipótese de maior ICE Score e clique em **"Preparar para Ritual CDMS"**.
   - O sistema valida a **trava causal de variável única** (`ConflictingActiveVariableError`). Se já houver um teste rodando com a mesma variável no mesmo ciclo, a ativação é bloqueada.
   - Caso aprovada, uma `Decision` vinculada é gerada atomicamente no CDMS e a hipótese é transicionada para **`ACTIVE`**.
3. **Acompanhar e Concluir Testes:**
   - Na sub-aba **🔬 Em Teste (ACTIVE)**, audite o experimento ao final da janela de 7 dias, marcando-o como `COMPLETED` ou `DISCARDED` (ou aguarde a sincronização direta via ritual do CDMS).

---

## 🛠️ 4. Guia Rápido de Manutenção e Resolução de Problemas

### 4.1. Travamento de Arquivo no Windows (`PermissionError [WinError 32]`)
* **Causa:** Conexões SQLite abertas mantidas na memória durante execução concorrente de testes ou múltiplas instâncias do Streamlit.
* **Solução:** O repositório e as fixtures foram atualizados com coleta explícita de lixo (`gc.collect()`). Se persistir, encerre processos órfãos:
  ```powershell
  Get-Process python | Stop-Process -Force
  ```

### 4.2. Inconsistência de Status em Bases Legadas
* **Causa:** Registros antigos salvos com `BACKLOG` ou `PROPOSED`.
* **Solução:** O repositório `SQLiteGrowthRepository` normaliza automaticamente a leitura de status com equivalência semântica:
  ```sql
  SELECT * FROM growth_hypotheses WHERE status IN ('BACKLOG', 'PENDING');
  ```

### 4.3. Backup Preventivo do Banco de Dados
Antes de rodar rituais importantes ou aplicar migrações manuais, execute o backup consistente a frio (com a UI fechada):

```bash
# Backup no Windows PowerShell
sqlite3 data/cdms_dev.db ".backup 'data/backup_cdms_$(Get-Date -Format 'yyyyMMdd_HHmm').db'"

# Backup no Linux / macOS
sqlite3 data/cdms_dev.db ".backup 'data/backup_cdms_$(date +%Y%m%d_%H%M).db'"
```

---

## 📈 5. Checklist de Sucesso Operacional

- [x] 51 testes automatizados passando em `pytest -v`.
- [x] Esquema SQLite com índices de integridade aplicados (versões 2 e 3).
- [x] Baseline comercial calibrada (ticket, CTR, taxa de leads e fechamento).
- [x] Ritual semanal fechado com idempotência toda segunda-feira.
- [x] Trava de variável única ativa impedindo experimentos concorrentes no mesmo ciclo.
- [x] Histórico de perdas financeiras auditado com cálculo de ROI de governança.
- [x] Vereditos do CDMS sincronizados de volta para o CGS sem estados órfãos.