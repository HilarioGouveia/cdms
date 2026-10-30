# Etapa 8 — Rodapé e rolagem do Studio

O Studio ocupa a altura disponível da janela. Cabeçalho e rodapé permanecem
visíveis; navegação, área central e evidências possuem rolagens independentes.
O dimensionamento acompanha a altura real do cabeçalho, inclusive quando quebra
em duas linhas. A mudança de layout não altera os dados dos workspaces.

O rodapé tem 28 px no desktop. Mostra modo local (a UI acessa o banco diretamente),
telemetria não configurada, painel carregado, workspace, ciclo e versão das regras.
"Painel carregado" confirma a renderização, não o sucesso de um diagnóstico ou
de uma integração. Não há percentuais, estados de conectividade ou quantidades
de nós simulados. O Demo preserva a indicação de dados simulados.

Até 900 px, as laterais dão lugar aos menus Seções e Evidências em todos os módulos.
O rodapé omite telemetria e ciclo; até 480 px, usa duas linhas (48 px) para manter
contexto e versão legíveis. As cores do shell usam as cores e a base configuradas
no tema do Streamlit, sem depender da identificação tardia do tema pelo navegador.

Validação em 30/10/2026: 18 testes de fluxos principais passaram na execução inicial;
após atualizar a verificação da identificação Demo para seu cabeçalho persistente,
os quatro testes de Demo e troca de contexto passaram separadamente (22 distintos).
No navegador, a rolagem do formulário de métricas moveu apenas o painel central;
navegação e evidências permaneceram em posição. Layout mobile conferido em 390×844.
