# Etapa 10 — Identidade compartilhada

O padrão aprovado no Cockpit foi propagado para Governança, Experimentos e
as páginas auxiliares do Studio. Cabeçalhos, navegação, evidências, abas,
expansores, cartões e tipografia numérica usam a mesma hierarquia e tokens.

`components/identity.py` concentra os indicadores escapados e a formatação
financeira brasileira. Ritual e catálogo usam os mesmos tons de cenário do
Cockpit; backlog usa as mesmas tags de variável e ICE. O diagnóstico financeiro
mostra oportunidade estimada em menta e identifica seu resumo como persistido,
sem usar uma mensagem verde de sucesso para representar um gargalo.

Fluxos, critérios, vínculos, controles, chaves de formulários e persistência não
mudaram. Erros e avisos nativos mantêm sua semântica. As rolagens e a navegação
compacta seguem o shell já aprovado.

Validação em 30/10/2026: 22 testes da suíte de interface passaram, com quatro
avisos existentes do runtime. Conferência visual de Governança e Experimentos
no desktop e do backlog em 390×844. O banco local permaneceu com SHA-256
`4DECF4BEA1B9DB3645A5CBCFE89B1C029ECFF0AC84DB9A9C29C64A8411ED10E8`.
