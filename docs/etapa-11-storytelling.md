# Etapa 11 — Storytelling de ciclo

Em **Experimentos → Relatório executivo → Storytelling**, selecione o ciclo e o
público: Gestor, Operador ou Comunicação. O Cockpit possui o atalho **Ver narrativa
do ciclo**, que abre o relatório com o mesmo ciclo selecionado.

A prévia contém Contexto e tensão, Decisão e ação, Resultado e aprendizado,
próximo passo e fontes por bloco. A exportação é um Markdown separado do relatório
consolidado anterior, preservado na segunda aba. O seletor também inclui ciclos
com ritual e sem auditoria financeira, além do ciclo atual e da referência do Cockpit.

O gerador v1.0 é determinístico, somente de leitura, sem LLM ou chamadas externas.
Consulta o diagnóstico do ciclo, o ritual e o aprendizado vinculado ao ID da
decisão daquele ritual. `ritual.learning` pode pertencer a uma decisão anterior e
não é usado como resultado da decisão atual. Evidências incompatíveis geram erro;
ausências são explicitadas. Falhas de consulta não são convertidas em sucesso.

Gestor recebe diagnóstico, oportunidade estimada, decisão, critério e aprendizado.
Operador também recebe o responsável registrado. Comunicação usa frases
predefinidas e omite valores financeiros, nomes de responsáveis, campos livres da
decisão e notas internas. Ciclo, identificadores das fontes e versões permanecem
como referências. A escolha do público não modifica autorização nem compartilha
conteúdo. O resumo deve ser revisado antes de divulgação.

Não se infere execução na plataforma, vencedor de variante, ganho de ROI,
receita realizada ou causalidade. Sem aprendizado da decisão atual, informa-se
que a avaliação está pendente. Campos registrados são escapados na prévia e no
Markdown, sem interpolação em HTML. Exportações do Demo levam DADOS SIMULADOS.

Não há migração, persistência de narrativas, edição manual ou novos conectores.
Cada geração reflete as evidências disponíveis no momento da consulta.

Código: `src/cdms/application/use_cases/generate_cycle_story.py` e
`src/cdms/adapters/ui/components/storytelling.py`.

Testes: `python -m pytest tests/unit/test_cycle_story.py tests/ui/test_suite_ui.py -q -k "cycle_story or storytelling or navigation_and_calibrated_ritual"`.

Validação em 30/10/2026: 19 testes selecionados passaram (16 do gerador e três da
interface; 20 testes não selecionados). Cobrem os quatro desfechos, ausência de
dados, isolamento das informações de comunicação, conteúdo escapado, vínculos
reais do Demo, somente leitura e regressão do relatório consolidado. Conferência
visual no desktop e em 390×844, incluindo troca de público. Banco local com SHA-256
inalterado: `4DECF4BEA1B9DB3645A5CBCFE89B1C029ECFF0AC84DB9A9C29C64A8411ED10E8`.
