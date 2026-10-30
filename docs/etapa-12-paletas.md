# Etapa 12 — Dark Premium e Soft Light

O Studio usa Dark Premium por padrão: fundo grafite `#20242C`, painéis slate
`#292E38`, cartões `#323844`, texto `#E7E9EC`, menta para oportunidade e crescimento,
âmbar para atenção e coral para risco. Cobalto aparece como acento discreto.
O preenchimento dos botões primários é mais fechado para manter texto branco legível.

Soft Light usa fundo `#F2F3F1`, painéis `#FAFAF8`, cartões `#E8EBE8`, texto `#252B33`
e versões profundas dos mesmos acentos. Não há fundo branco puro na paleta.

Perfis nativos do Streamlit, também consumidos pelos tokens do shell:

- `.streamlit/themes/dark-premium.toml`
- `.streamlit/themes/soft-light.toml`

Para usar Soft Light, a partir da raiz do projeto, altere `theme.base` em
`.streamlit/config.toml` para `.streamlit/themes/soft-light.toml` e reinicie o servidor.
Alternativamente, inicie com:

```powershell
.venv/Scripts/python.exe -m streamlit run app.py --theme.base=.streamlit/themes/soft-light.toml
```

A escolha é um perfil de configuração do servidor, comum a seus usuários; não é
um seletor por workspace ou uma preferência individual salva na sessão.

Campos, botões, abas, alertas, tabelas e gráficos nativos recebem as cores do perfil.
O shell, os indicadores e o funil Plotly usam os mesmos tokens via `ui/theme.py`.
O gráfico de tendências não usa mais ciano/vermelho/verde neon. Os componentes da
página demonstrativa antiga também usam os tokens, sem importar fontes externas.
`design_tokens.json` registra os dois perfis como catálogo; os TOMLs são a fonte.

Validação em 30/10/2026: oito testes selecionados passaram (quatro de tema e quatro
de fluxos da interface). Após o refinamento das legendas, os quatro testes de tema
passaram novamente. Os testes verificam contraste mínimo de 4,5:1 para texto,
legendas e acentos nas superfícies previstas, alertas semânticos, texto dos botões
primários e rótulos do funil; verificam também que os dados do gráfico são preservados.
Ambos os temas foram conferidos no navegador; a prévia temporária Soft Light foi
encerrada. O Dark Premium permanece em `127.0.0.1:8501`.

Antes da atualização do GitHub, a verificação conjunta de Storytelling, temas e
interface passou com **43 testes** e quatro avisos existentes:
`python -m pytest tests/unit/test_cycle_story.py tests/unit/test_studio_theme.py tests/ui/test_suite_ui.py -q`.
