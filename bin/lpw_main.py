import streamlit as st
from lpw_rag import register_rag_cleanup

register_rag_cleanup()

main_page = st.Page("lpw_home.py", title="LPW Home", icon="🏠")
settings_page = st.Page("lpw_settings.py", title="LPW Settings", icon="⚙️")

pg = st.navigation([main_page, settings_page])
#st.set_page_config(page_title="Data manager", page_icon=":material/edit:")
pg.run()
