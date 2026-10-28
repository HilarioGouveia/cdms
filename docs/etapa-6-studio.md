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
- Shell contínuo inspirado no Studio de referência: sem margens externas, dock
  estreito, explorador e evidências com divisórias e barra superior compacta.
- Workspace e ciclo acessíveis pelo controle da barra superior; explorador com
  navegação por seção. Painel de evidências aberto inicialmente e recolhível.
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

Unificar rascunhos por ciclo e integrar seleção de workspaces autorizados via API.
O modo autenticado deve consumir
a API com token escopado; não deve reutilizar o container global local por tenant.

## Verificação

`python -m pytest tests/ui/test_suite_ui.py -q`

Os testes usam bancos temporários. Cobrem o ciclo completo CDMS/CGS pela navegação
do Studio, rascunhos, painéis e evidências filtradas por ciclo. AppTest valida
comportamento; inspeção visual no navegador deve ser feita com o servidor em execução.

Resultado desta etapa: oito casos de interface aprovados (seis fluxos existentes e
dois casos novos do Studio). Os 39 avisos dos fluxos existentes são de depreciação
Streamlit/pandas. O SHA-256 do banco local permaneceu inalterado. A inspeção visual
no navegador ficou pendente na entrega inicial.

Na revisão do shell contínuo, os dois testes específicos do Studio passaram
novamente e o layout foi inspecionado no navegador em 1280 × 720. A instância local
foi reiniciada em `http://127.0.0.1:8501` para carregar as alterações, com o deploy
oculto, fonte base de 14 px e regiões separadas por divisórias contínuas.

## Navegação contextual por módulo

A dock seleciona Governança ou Experimentos e reabre o explorador quando fechado.
O explorador apresenta apenas as quatro seções do módulo ativo. O centro renderiza
somente a seção selecionada, sem as antigas abas de navegação entre páginas.
As abas de status das hipóteses continuam dentro do backlog.

O cabeçalho central contém o caminho da seção e uma descrição breve da tarefa.
Os títulos institucionais repetidos de CDMS/CGS foram removidos: a marca fica na
barra superior e a versão das regras na barra de status.

Cada módulo lembra a última seção aberta. Os atalhos do Cockpit abrem diretamente
o ritual ou o diagnóstico, mesmo quando outra seção foi usada anteriormente.
Campos do ritual, métricas, calibrações, hipótese, diagnóstico e baseline possuem
estado de sessão preservado durante a navegação. Isso não substitui gravação:
somente os botões de concluir ou salvar persistem os dados no banco. Os grupos de
campos de hipótese e baseline usam containers e botões explícitos para permitir
preservação de rascunhos sem depender do envio de um formulário.

Validação desta revisão: dez testes de interface aprovados, cobrindo fluxo completo
CDMS/CGS, exportação sem dados, seções exclusivas, memória de navegação e rascunhos
de ritual, hipótese e baseline. O banco local manteve seu SHA-256. A revisão visual
desta navegação não foi concluída: o navegador de verificação não conseguiu anexar
uma aba nesta sessão; os testes de comportamento foram executados com AppTest.

## Ritual guiado e mobile

O ritual usa quatro etapas: Aprendizado, Métricas, Diagnóstico e Decisão.
O módulo `src/cdms/adapters/ui/ritual_wizard.py` renderiza apenas a etapa aberta.
No desktop, o seletor superior permite navegar diretamente; Anterior/Próxima
orientam o percurso. No mobile, o seletor é ocultado e permanece o indicador
"Etapa N de 4", com os botões abaixo do conteúdo e os campos em uma coluna.

Até 900 px, os painéis laterais do ritual ficam recolhidos. Seções e evidências
continuam acessíveis por popovers na barra superior; a dock permanece disponível.
O ajuste é de apresentação: não modifica permissões nem dados.

Rascunhos são separados por ciclo na sessão, incluindo etapa, métricas, aprendizado
e decisão. Voltar para um ciclo recupera seu rascunho. Fechar/reiniciar a sessão
não oferece persistência durável desses rascunhos. Diagnóstico e revisão final
são recalculados usando os valores e calibrações atuais, sem gravar dados.

Na etapa 4, a revisão reúne aprendizado, métricas e diagnóstico. Somente o botão
"Concluir ritual" executa o caso de uso transacional existente. A conclusão exige
que as métricas tenham sido preenchidas e que a decisão esteja completa. Quando
houver auditoria pendente, exige uma escolha explícita do resultado; sem pendência,
a etapa de aprendizado permite avançar. Um ritual concluído aparece como registro
fechado, sem oferecer sobrescrita pela interface.

A importação continua oferecendo dados extraídos para conferência; não aplica
valores automaticamente aos campos. A prévia extraída permanece no rascunho do ciclo.

Validação do ritual guiado: 12 testes de interface aprovados, incluindo isolamento
dos rascunhos por ciclo, diagnóstico recalculado e bloqueio de conclusão quando
métricas ou auditoria anterior estão incompletas. Revisão no navegador em 390×844
e 1280×800, com navegação Anterior/Próxima e acesso às evidências pelo menu mobile.
O SHA-256 do banco local permaneceu inalterado.
