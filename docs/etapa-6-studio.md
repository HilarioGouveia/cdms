# Etapa 6 — Estrutura inicial do Studio

O ponto de entrada `app.py` abre o CDMS Studio. O shell fica em
`src/cdms/adapters/ui/studio.py`, com estilos escopados em `styles/studio.css`.

## Entregue nesta etapa

- Barra superior, identificação do workspace local e ciclo de referência.
- Dock com Cockpit, Governança e Experimentos.
- Navegação contextual e painel de evidências recolhíveis.
- Cockpit com oportunidade estimada, ritual e backlog consultados nos repositórios
  existentes. Ausência de dados aparece como estado vazio, sem números demonstrativos.
- Cobalto para ações e menta para a oportunidade financeira, com valores em formato brasileiro.
- Preservação dos campos identificados do rascunho de ritual ao navegar entre módulos.
- Fluxos existentes de calibração, ritual, diagnóstico, hipóteses e relatórios mantidos.

## Limites intencionais

O workspace local usa o banco configurado pelo servidor. O seletor é informativo e
não oferece caminhos de arquivo ou organizações arbitrárias. Não representa um
tenant autenticado nem permite escolher um workspace da API.

O ciclo superior filtra o Cockpit e o painel de evidências. Os formulários mantêm
suas datas explícitas de origem e destino: um diagnóstico pode se referir à semana
anterior e uma proposta pode apontar para a semana seguinte. Não há alteração
silenciosa das datas desses formulários ao consultar outro ciclo no Cockpit.

O backlog é do workspace, ordenado por ICE; propostas reservadas mostram seu ciclo.
Oportunidade estimada não é receita realizada. Não há delta inventado, assistente
conectado ou indicação de rollback executado.

## Próximas entregas

Separar os fluxos legados em páginas contextuais, unificar rascunhos por ciclo e
integrar seleção de workspaces autorizados via API. O modo autenticado deve consumir
a API com token escopado; não deve reutilizar o container global local por tenant.

## Verificação

`python -m pytest tests/ui/test_suite_ui.py -q`

Os testes usam bancos temporários. Cobrem o ciclo completo CDMS/CGS pela navegação
do Studio, rascunhos, painéis e evidências filtradas por ciclo. AppTest valida
comportamento; inspeção visual no navegador deve ser feita com o servidor em execução.

Resultado desta etapa: oito casos de interface aprovados (seis fluxos existentes e
dois casos novos do Studio). Os 39 avisos dos fluxos existentes são de depreciação
Streamlit/pandas. O SHA-256 do banco local permaneceu inalterado. A inspeção visual
no navegador está pendente; nenhum servidor foi iniciado nesta etapa.
