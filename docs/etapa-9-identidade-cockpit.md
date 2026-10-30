# Etapa 9 — Identidade Decision Cockpit

A tela Cockpit é a referência inicial da identidade própria do CDMS. Mantém a
estrutura de painéis e rolagens do Studio, com hierarquia centrada na decisão:

- Diagnóstico financeiro em superfície discreta com acento menta, valor tabular
  em destaque e gargalo com rótulo legível. Ausência de diagnóstico não vira zero.
- Governança com cenário semântico, decisão, hipótese, critério, responsável e
  prazo provenientes do ritual persistido do ciclo selecionado.
- Até três hipóteses pendentes do workspace, ordenadas por ICE, com variável e
  reserva de ciclo. A lista não implica promoção nem teste ativo.
- Evidências apresentadas como registro técnico, com fonte e versão das regras.
- Navegação do Cockpit com preenchimento cobalto discreto e borda de seleção.

As cores se ajustam à base configurada do tema. Há tons para risco de queda,
assimetria, escala, estabilidade e inconclusivo; rótulos acompanham as cores.
Os componentes de interação continuam nativos do Streamlit. Os indicadores
decorativos usam HTML escapado; não há fontes externas, imagens ou dependências.

Não são inferidos crescimento temporal, receita realizada, trava causal ativa ou
status de integração. O Demo continua identificado e separado dos dados locais.
Governança e Experimentos mantêm seu desenho atual até a validação desta referência.

Validação automatizada: os dois testes existentes de filtro do Cockpit por ciclo
e carga/troca de workspace Demo passaram (20 outros testes não selecionados).
Conferência visual no navegador com estado vazio Local e estado preenchido Demo,
incluindo oportunidade, cenário, critério e backlog; mobile conferido em 390×844.
