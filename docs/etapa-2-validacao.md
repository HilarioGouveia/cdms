# Etapa 2 — Ambiente e testes

## Alterações

- Dependências centralizadas em `pyproject.toml`, com extras `api`, `automation` e `dev`; `requirements.txt` instala o conjunto completo.
- Bibliotecas utilizadas diretamente pela interface e pelo importador declaradas no manifesto, incluindo `openpyxl`.
- Compatibilidade entre Passlib 1.7.4 e bcrypt delimitada no extra de API.
- Configuração de pytest mantida apenas em `pytest.ini`.
- Importação e fixtures da auditoria de funil alinhadas à entidade do CGS.
- Conexões dos três repositórios CGS fechadas deterministicamente, com commit ou rollback antes do fechamento.
- Fixture de banco temporário sem coleta de lixo forçada ou tentativas de exclusão.
- Expectativa Markdown de ROI corrigida para considerar o negrito existente; verificação adicional de quebras de linha reais no relatório.
- Regressões de commit, rollback e fechamento de conexão para os três repositórios.

## Validação em 2026-10-28

Ambiente: Windows, Python 3.11.9, pytest 9.1.1.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api,automation]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Resultado da suíte completa: **75 testes aprovados**, sem exclusões e sem erros de teardown. `pip check` não encontrou dependências quebradas. A revisão de espaços com `git diff --check` passou.

As limitações funcionais da API multi-tenant, da autenticação demonstrativa e dos conectores simulados registradas no checkpoint continuam fora do escopo desta etapa. O próximo passo é validar a interface e o fluxo integrado com bancos temporários.
