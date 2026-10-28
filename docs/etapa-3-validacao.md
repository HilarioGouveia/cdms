# Etapa 3 — Interface e fluxo CDMS/CGS

## Resultado

A interface real de `app.py` foi validada com `streamlit.testing.v1.AppTest`, datas fixas e banco SQLite temporário. A suíte completa passou com **88 testes**, incluindo seis cenários da interface. Foram corrigidos problemas de integração encontrados durante a análise.

## Fluxo consolidado

1. O CGS cadastra baseline, diagnostica o funil e organiza hipóteses.
2. Preparar uma hipótese reserva sua segunda-feira alvo, mantendo-a pendente.
3. No CDMS, o usuário seleciona a proposta para preencher a decisão.
4. Ao concluir o ritual, uma única transação grava o ritual, a decisão e o vínculo real, ativando a hipótese.
5. A auditoria no ritual seguinte sincroniza o resultado com a hipótese: `ACHIEVED` e `PARTIAL` resultam em `COMPLETED`; `NOT_ACHIEVED` resulta em `DISCARDED`; `INCONCLUSIVE` mantém `ACTIVE`.

A preparação não cria uma tabela alternativa de decisões nem inventa IDs. As ações manuais de conclusão e descarte do CGS foram preservadas.

## Correções

- CDMS e CGS usam o mesmo caminho de banco configurado.
- Propostas usam segunda-feira explícita; o formulário CDMS permite selecionar a proposta e conferir os campos preenchidos.
- O vínculo `Decision.source_hypothesis_id` é persistido em `decisions.cgs_hypothesis_id`; bancos canônicos existentes recebem a coluna sem perder rituais anteriores.
- Ativação e sincronização da hipótese ocorrem dentro da transação do ritual, com rollback em caso de falha.
- A verificação de variável concorrente é repetida no commit, sob transação de escrita.
- Gráficos e alerta de deriva usam `healthy_min`, `healthy_max` e a chave canônica `avg_retention_pct`.
- O relatório distingue ritual pendente de ritual concluído.
- Uso de `width="stretch"` nos componentes editados e requisito mínimo Streamlit 1.57 para a interface atual.

## Verificações

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/ui
git diff --check
```

Foram cobertos:

- Navegação CDMS/CGS, calibração e gravação de ritual.
- Baselines e diagnósticos de venda direta e funil de leads.
- Cadastro de hipótese, preparação, preenchimento da decisão e ativação com ID real.
- Auditoria positiva e negativa pela interface; quatro resultados de auditoria na integração.
- Campos obrigatórios e métrica indisponível com motivo persistido.
- Quatro ciclos acima do limite, alerta de recalibração e gráficos das quatro métricas.
- Rollback após falha de persistência e após conflito de variável.
- Atualização idempotente do esquema de um banco anterior com preservação do ritual.

Ambiente: Windows, Python 3.11.9, Streamlit 1.66.1, pytest 9.1.1. A suíte completa emitiu 39 avisos `Pandas4Warning` originados no código interno de gráficos do Streamlit. Não houve falhas. O hash SHA-256 do banco de desenvolvimento foi conferido antes e depois da suíte e permaneceu igual.

## Limites desta validação

AppTest verifica elementos e comportamento Python, sem validar aparência CSS, responsividade ou execução de JavaScript no navegador. Upload real de arquivos e contas de plataformas externas não foram testados. Autenticação real e isolamento por workspace continuam como próxima etapa; este trabalho não homologa a API multi-tenant para produção.
