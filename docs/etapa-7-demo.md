# Etapa 7 — Dados de demonstração

## Como usar

1. Abra **Workspace e ciclo** e selecione **CDMS Demo**.
2. Em **Demonstração → Dados de demonstração**, escolha o pacote e confira a prévia.
3. Clique **Carregar pacote**.
4. No tour, escolha **Ciclo do tour → Apresentar ciclo** para abrir o Cockpit com
   a baseline e os dados financeiros daquele exemplo. As demais telas usam o mesmo
   banco simulado, inclusive rituais, backlog, histórico e relatórios.
5. **Restaurar pacote inicial** cria uma nova geração e reinicia apenas o contexto
   Demo. Voltar para **Local · CDMS** recupera a navegação e os rascunhos locais.

**Tour guiado** carrega 12 ciclos anteriores à segunda-feira de referência,
12 auditorias financeiras, 18 hipóteses e 11 aprendizados. Há os cinco cenários
heurísticos, os quatro resultados de aprendizado, hipóteses pendentes/reservadas,
ativas, concluídas e descartadas, venda direta e leads, seis tipos de diagnóstico
financeiro e quatro ciclos consecutivos acima das referências para recalibração.

**Cobertura completa** carrega o mesmo tour e abre o catálogo de **81 combinações**
das quatro métricas abaixo/dentro/acima das faixas, mais **quatro casos de métrica
indisponível**. O catálogo é calculado pelo classificador real com as calibrações
padrão do pacote, sem criar 81 rituais extras na linha do tempo. É possível filtrar,
explorar cada exemplo e exportar o catálogo filtrado em CSV.

## Isolamento

- O Demo é um contexto local de apresentação, sem autenticação e sem representar
  um tenant da API. O seletor aceita apenas Local e Demo; não recebe caminhos.
- Os bancos ficam em `data/demo/<uuid-da-sessão>/<uuid-da-geração>.db`, ignorados
  pelo Git. Cada sessão tem seu próprio Demo. O container global permanece local;
  o container de demonstração é privado da sessão e passado explicitamente à UI.
- Rascunhos, ciclos, calibrações e resultados de formulários são separados entre
  Local e Demo. Uploads também possuem identificação de contexto/geração própria.
- O pacote usa os casos de uso existentes para criar propostas, rituais e vínculos
  reais entre hipóteses, decisões e aprendizados. Nenhum ID fictício é promovido.
- A geração é construída em um arquivo novo e só é selecionada após sucesso.
  Uma falha mantém a geração anterior. Restaurar não apaga nem sobrescreve bancos
  locais ou gerações antigas; estas permanecem em disco, fora da apresentação atual.
- Não há credenciais, conexões de plataforma, requisições externas ou tarefas de
  ingestão real. Cabeçalho, explorador e rodapé identificam **dados simulados**.
- Rascunhos e seleção de workspace duram a sessão. Após reinício, pode-se carregar
  outro pacote. A referência do tour é preservada ao restaurar o pacote carregado.

## Código

- `src/cdms/application/demo_data.py`: catálogo e geração determinística do pacote.
- `src/cdms/adapters/ui/studio_workspaces.py`: troca de contexto e estado por sessão.
- `src/cdms/adapters/ui/demo_page.py`: prévia, carregamento, restauração e catálogo.

## Verificação

`python -m pytest tests/unit/test_demo_data.py tests/ui/test_suite_ui.py -q`

Os testes verificam cobertura, vínculos, resultados, repetibilidade do pacote,
isolamento dos dados locais, restauração em novo arquivo e recuperação dos rascunhos.

Validação em 28/10/2026: 24 testes passaram na execução conjunta; o teste adicional
de retorno de um contexto Demo pré-selecionado para Local passou separadamente
(25 testes distintos). O tour, a apresentação de ciclo no Cockpit e o catálogo
foram conferidos no navegador. O SHA-256 de `data/cdms_dev.db` permaneceu inalterado:
`4DECF4BEA1B9DB3645A5CBCFE89B1C029ECFF0AC84DB9A9C29C64A8411ED10E8`.
