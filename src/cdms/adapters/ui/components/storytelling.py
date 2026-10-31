"""Narrativa de ciclo: leitura e exportação, sem publicação externa."""
import streamlit as st

from cdms.application.use_cases.generate_cycle_story import (
    GenerateCycleStoryUseCase, StoryAudience, safe_markdown,
)


def render_cycle_story(core, growth, cycle_id):
    audience = st.selectbox(
        "Público da narrativa", [item.value for item in StoryAudience],
        key="growth_story_audience",
        help="O público adapta a apresentação. Não altera permissões nem publica o conteúdo.",
    )
    simulated = not st.session_state.get("_auth_token") and st.session_state.get("studio_workspace") == "CDMS Demo"
    story = GenerateCycleStoryUseCase(core, growth).execute(cycle_id, audience, simulated=simulated)
    with st.container(key="cycle_story"):
        st.caption(f"NARRATIVA DO CICLO / {cycle_id} · GERADOR v{story.version}")
        if simulated:
            st.caption("DADOS SIMULADOS · Demonstração")
        if story.audience == StoryAudience.COMMUNICATION:
            st.caption("Resumo para revisão antes de compartilhar. Sem valores financeiros, responsáveis ou notas internas.")
        for index, block in enumerate(story.blocks):
            with st.container(key=f"story_block_{index}"):
                st.subheader(block.title)
                st.markdown(safe_markdown(block.text))
                with st.expander("Fontes deste bloco"):
                    for source in block.sources:
                        st.caption(source)
        st.markdown("**Próximo passo**")
        st.write(story.next_step)
        st.caption("Oportunidade estimada não é receita realizada. Resultado registrado não comprova causalidade ou execução na plataforma.")
        st.download_button(
            "Baixar narrativa (.md)", data=story.markdown,
            file_name=f"narrativa_{cycle_id}_{story.audience.name.lower()}.md",
            mime="text/markdown", key="story_download", icon=":material/download:",
        )
