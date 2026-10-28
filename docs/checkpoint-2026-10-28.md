# Checkpoint de consolidação — 2026-10-28

Este checkpoint preserva o estado de desenvolvimento existente antes das correções de ambiente, testes e integração. Não representa uma versão homologada para produção.

## Escopo consolidado

- Evolução do CDMS e CGS: ritual, funil de dois passos, hipóteses, governança causal, sincronização de resultados e exportação de relatórios.
- Interface Streamlit, componentes de gráficos, importador de métricas e configuração visual.
- Estrutura inicial de API, autenticação, contexto de workspace, conectores simulados e tarefas assíncronas.
- Migrações de persistência, alocação de orçamento, análise estatística, bandits e circuit breakers.
- Especificações e testes acrescentados durante o desenvolvimento.

## Validação observada

Ambiente local: Windows, Python 3.11.9, pytest 9.1.1 e Streamlit 1.66.1.

- A importação de `app.py` concluiu sem erro; isso não comprova o funcionamento de todas as telas.
- A execução completa de `python -m pytest -q` foi interrompida por dois erros de coleta: FastAPI ausente e importação de `cdms.domain.entities.funnel`, cujo módulo correspondente está em `cgs.domain.entities.funnel`.
- Excluindo os dois arquivos bloqueados, o resultado foi 64 testes aprovados, 1 falha e 3 erros de teardown.
- A falha está na expectativa de formatação Markdown do relatório de ROI.
- Os três erros de teardown são `PermissionError` ao remover bancos SQLite temporários no Windows.
- `git diff --check` identificou espaços finais em arquivos existentes; a limpeza fica para uma alteração posterior.

Comandos usados no ambiente virtual local:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/unit/test_fase2_api_auth.py --ignore=tests/unit/test_fase3_ai_and_connectors.py
.\.venv\Scripts\python.exe -c "import app; import streamlit; print(streamlit.__version__)"
```

## Limitações conhecidas

- Dependências das fases posteriores ainda não estão consolidadas no manifesto do projeto.
- O login da API é demonstrativo e a configuração JWT possui uma chave padrão de desenvolvimento.
- A rota de auditoria de funil recebe o contexto de tenant, mas não o utiliza para isolar a operação por workspace.
- Os conectores examinados retornam dados simulados; a tarefa assíncrona ainda não implementa a ingestão persistida completa.
- O README descreve recursos e garantias que ainda precisam ser conciliados com a implementação e os resultados de teste.

## Arquivos locais preservados fora do Git

O arquivo `CDMS.zip` contém fontes duplicados, banco local e caches. Ele foi excluído do versionamento por uma regra de ignore. Estava presente na inspeção inicial, mas não foi encontrado na conferência final; as ações desta consolidação não incluíram sua remoção. Bancos em `data/`, ambiente virtual, caches e credenciais locais também permanecem fora do versionamento conforme `.gitignore`.

## Próxima etapa

Consolidar dependências, corrigir a importação do teste, garantir fechamento das conexões SQLite e alinhar a exportação Markdown ao contrato esperado. Em seguida, executar novamente a suíte completa antes de avançar para a validação da interface e do isolamento por workspace.
