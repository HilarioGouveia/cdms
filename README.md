# 🎯 Creator Data Marketing System (CDMS)

Sistema de governança analítica semanal e diagnóstico heurístico de momento operacional para criadores de conteúdo e gestores de tráfego/mídia.

O projeto segue rigorosamente o padrão **Spec-Driven Development (SDD)**, arquitetura limpa (**Clean Architecture**), **Ports & Adapters (Arquitetura Hexagonal)** e empacotamento canónico Python com `src/` layout.

---

## 📌 Visão Geral do MVP (Fase 1)

O principal diferencial do CDMS é o **Ritual Semanal de Decisão Única**:

1. **Auditoria do Ciclo Anterior:** Avaliação formal da hipótese prévia (`ACHIEVED`, `PARTIAL`, `NOT_ACHIEVED`, `INCONCLUSIVE`), amarrada ao identificador unívoco da decisão.
2. **Ingestão das 4 Métricas Canónicas:** Coleta padronizada de Alcance, Retenção Média ponderada, CTR e Conversões, com suporte a indisponibilidade formal (`NO_EXPOSURE`, `ZERO_IMPRESSIONS`).
3. **Diagnóstico Heurístico em Cascata:** Classificação determinística e exaustiva das **81 combinações ($3^4$)** entre `PRE_DROP`, `ANOMALY`, `SCALE`, `STABILITY` e `INCONCLUSIVE` (com diferenciação entre `MISSING_DATA` e `MIXED_SIGNALS`).
4. **Trava da Decisão Única do Ciclo:** Definição obrigatória de ação, hipótese causal, critério de sucesso verificável e prazo de avaliação.
5. **Persistência Atómica e Idempotente:** Armazenamento relacional em SQLite puro com transações atómicas e chave canónica `cycle_id = YYYY-MM-DD` (segunda-feira).

---

## 🏗️ Arquitetura do Sistema

```
cdms-project/
├── pyproject.toml                     # Configuração de empacotamento (PEP 517/621)
├── pytest.ini                         # Configurações do Pytest
├── README.md                          # Documentação executiva
├── .gitignore                         # Regras de isolamento (ignora data/*.db)
├── app.py                             # Bootstrap da interface Streamlit
├── data/
│   └── .gitkeep                       # Diretório da base SQLite local
├── docs/
│   └── SDD-CDMS-001-v2.3.1.md         # Especificação formal da arquitetura e regras
├── tests/
│   ├── unit/
│   │   ├── test_metrics.py            # Validação de entidades e cálculos numéricos
│   │   ├── test_diagnose_scenario.py  # Teste das 81 combinações do classificador
│   │   └── test_run_weekly_ritual.py  # Teste de fluxo de ritual e idempotência
│   └── integration/
│       └── test_sqlite_repo.py        # Teste de persistência e integridade transacional
└── src/
    └── cdms/
        ├── config/
        │   ├── settings.py            # Variáveis de ambiente, paths e fuso horário
        │   └── container.py           # Injeção de dependências (Composition Root)
        ├── domain/
        │   ├── entities/              # Entidades puras (Metric, Scenario, Decision, etc.)
        │   └── services/              # ScenarioClassifier (motor heurístico de domínio puro)
        ├── application/
        │   ├── ports/                 # RepositoryPort (Driven Port)
        │   └── use_cases/             # Casos de uso desacoplados (Ritual, Calibração, etc.)
        └── adapters/
            ├── persistence/           # SQLiteRepository e migrações SQL nativas
            └── ui/                    # Dashboard Streamlit e componentes modulares
```

---

## 🚀 Instalação e Execução

### 1. Requisitos

* Python 3.11+
* Git

### 2. Configurar o Ambiente Virtual

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar no Linux / macOS:
source .venv/bin/activate

# Ativar no Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 3. Instalar o Pacote em Modo Editável

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Executar os Testes Automatizados

A suíte cobre 100% dos testes unitários e de integração descritos na SDD v2.3.1 (incluindo as 81 combinações do motor e rollback transacional):

```bash
pytest
```
*Ou utilizando o executor nativo do Python:*
```bash
python -m unittest discover -s tests -v
```

### 5. Iniciar a Interface Streamlit

```bash
streamlit run app.py
```

O dashboard estará acessível em `http://localhost:8501`.

---

## 📊 Tabela de Cenários e Regras de Precedência

O motor avalia o vetor das 4 métricas canónicas com precedência estrita:

| Precedência | Cenário | Condição Lógica Estrita | Cobertura Teórica |
| :---: | :--- | :--- | :---: |
| **1** | `PRE_DROP` (Risco de Queda) | $\ge 2$ métricas em `BELOW` | 33 combinações (40.7%) |
| **2** | `ANOMALY` (Assimetria Crítica) | $\ge 1$ métrica em `BELOW` e $\ge 1$ métrica em `ABOVE` | 28 combinações (34.6%) |
| **3** | `SCALE` (Alavancagem de Escala) | $0$ métricas em `BELOW` e $\ge 2$ métricas em `ABOVE` | 11 combinações (13.6%) |
| **4** | `STABILITY` (Equilíbrio Nominal) | $0$ métricas em `BELOW` e $\le 1$ métrica em `ABOVE` | 5 combinações (6.2%) |
| **Fallback** | `INCONCLUSIVE` (Sinais Mistos) | $1$ métrica em `BELOW` e $3$ em `HEALTHY` | 4 combinações (4.9%) |

> **Nota:** Se qualquer métrica canônica faltar ou estiver marcada como indisponível (`is_available = False`), a Guarda Prévia retorna imediatamente `INCONCLUSIVE` com motivo `MISSING_DATA`.

---

## 💾 Governança do Banco SQLite e Backups

Conforme a seção 6.2 da SDD v2.3.1:

* O banco de dados de desenvolvimento é mantido em `data/cdms_dev.db`.
* O esquema relacional habilita chaves estrangeiras (`PRAGMA foreign_keys = ON;`) e migrações rastreadas em `schema_migrations`.
* Para gerar backup consistente a frio (com a aplicação fechada):
  ```bash
  sqlite3 data/cdms_dev.db ".backup 'data/backup_cdms_$(date +%Y%m%d).db'"
  ```

---

## 🗺️ Roadmap de Evolução

* **Fase 1 (MVP Local - Concluída):** Monólito Streamlit + SQLite nativo, foco no ritual e governança analítica semanal.
* **Fase 2 (Nuvem & Multi-Tenant):** FastAPI REST API, PostgreSQL, Alembic, autenticação OAuth2/JWT e suporte a múltiplos criadores/canais.
* **Fase 3 (Automação & IA):** Conectores de dados (YouTube, Meta, TikTok), Creator Health Index e geração assistida de hipóteses com LLMs.
