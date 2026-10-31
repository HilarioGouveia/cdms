"""Prévia, carregamento e catálogo de cenários simulados."""
from collections import Counter
from datetime import date, timedelta
import csv
import io

import streamlit as st

from cdms.application.demo_data import PACKAGES, VERSION, scenario_catalog, tour_preview
from cdms.adapters.ui.components.scenario_card import render_scenario_card
from cdms.adapters.ui.studio_workspaces import load_demo, present_cycle,open_demo_practice


def render_demo_data():
    st.subheader("Dados para apresentação")
    st.write("O pacote será carregado somente neste CDMS Demo. Seus dados locais permanecem separados.")
    manifest = st.session_state.get("_demo_manifest")
    st.session_state.setdefault("demo_package", manifest["package"] if manifest else PACKAGES[0])
    package = st.selectbox("Pacote de demonstração", PACKAGES, key="demo_package")
    today = date.today()
    anchor = date.fromisoformat(manifest["anchor"]) if manifest else today - timedelta(days=today.weekday())
    preview = tour_preview(anchor)
    with st.container(border=True):
        st.markdown("**Prévia do pacote**")
        st.write("12 ciclos · 12 diagnósticos · 18 hipóteses · 11 aprendizados auditados")
        st.write('13 orçamentos · 13 avaliações A/B · 15 coletas Meta fictícias')
        st.caption('Inclui gastos acima do alocado, ganho/perda/amostra insuficiente e um ciclo aberto para praticar a importação. Simulação offline, sem token ou Redis.')
        st.caption("Venda direta e leads; estabilidade, queda, assimetria, escala, dados indisponíveis e recalibração.")
        if package == "Cobertura completa":
            st.write("Inclui o catálogo de 81 combinações e 4 exemplos de indisponibilidade.")
            st.caption("Após o carregamento, abre o catálogo completo. Os 81 exemplos não são adicionados à linha do tempo do tour.")
        else:
            st.caption("O catálogo completo também pode ser consultado pela navegação de Demonstração.")
        st.dataframe([{"Ciclo": row["cycle"], "Exemplo": row["title"], "Cenário": row["scenario"],
                       "Funil": row["funnel"]} for row in preview], hide_index=True, width="stretch")
    st.caption("Carregar cria um novo conjunto simulado. Restaurar volta ao pacote inicial e reinicia os rascunhos do Demo nesta sessão.")
    with st.container(horizontal=True):
        st.button("Carregar pacote", key="demo_load", type="primary", on_click=load_demo,
                  disabled=bool(manifest and manifest["package"] == package and manifest.get('version')==VERSION))
        st.button("Restaurar pacote inicial", key="demo_restore", disabled=not bool(manifest),
                  on_click=load_demo, args=(True,))
    if st.session_state.get("_demo_notice"):
        st.success(st.session_state["_demo_notice"])
    if st.session_state.get("_demo_error"):
        st.error(st.session_state["_demo_error"])
    if manifest:
        st.caption(f"Pacote carregado · {manifest['package']} · v{manifest.get('version','1.0')}")
        if manifest.get('version')!=VERSION:
            st.info('Há uma nova versão do Demo. Carregue o pacote novamente para incluir orçamento, A/B e importações simuladas.')
        if manifest.get('sandbox_cycle'):
            st.button('Praticar orçamento, A/B e importação',key='demo_practice',on_click=open_demo_practice)
            st.caption(f"Ciclo de prática: {manifest['sandbox_cycle']} · Não possui ritual encerrado no pacote inicial.")
        selected = st.selectbox("Ciclo do tour", [row["cycle"] for row in manifest["cycles"]], index=11, key="demo_tour_cycle")
        row = next(item for item in manifest["cycles"] if item["cycle"] == selected)
        st.write(f"**{row['title']}** · {row['scenario']} · {row['funnel']}")
        st.caption("Apresentar aplica a baseline e os valores simulados deste exemplo ao Demo e abre o Cockpit.")
        st.button("Apresentar ciclo", key="demo_present_cycle", on_click=present_cycle, args=(row,))


def render_demo_catalog():
    examples = scenario_catalog()
    if st.session_state.get("_demo_notice"):
        st.success(st.session_state["_demo_notice"])
    st.subheader("Catálogo de cenários")
    st.write("81 combinações das quatro métricas, mais 4 exemplos com métrica indisponível. O catálogo não cria rituais nem altera dados.")
    st.caption("B = abaixo · H = faixa saudável · A = acima · U = indisponível. Ordem: alcance, retenção, CTR, conversões.")
    st.caption("Referências fixas: calibrações padrão do pacote, independentemente dos ajustes feitos no Demo.")
    counts = Counter(item["scenario"].type.value for item in examples)
    selected_type = st.selectbox("Filtrar cenário", ["Todos", *sorted(counts)], key="demo_catalog_filter")
    filtered = [item for item in examples if selected_type == "Todos" or item["scenario"].type.value == selected_type]
    rows = [{"Código": item["code"], "Cenário": item["scenario"].type.value,
             **{snapshot.definition.name: f"{snapshot.observed_value:g}" if snapshot.is_available else "Indisponível"
                for snapshot in item["snapshots"]}} for item in filtered]
    st.dataframe(rows, hide_index=True, width="stretch")
    options = [item["code"] for item in filtered]
    if st.session_state.get("demo_catalog_example") not in options:
        st.session_state["demo_catalog_example"] = options[0]
    selected = st.selectbox("Explorar exemplo", options, key="demo_catalog_example")
    render_scenario_card(next(item for item in filtered if item["code"] == selected)["scenario"])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    st.download_button("Baixar catálogo filtrado (CSV)", output.getvalue(), "cdms-demo-cenarios.csv", "text/csv")
