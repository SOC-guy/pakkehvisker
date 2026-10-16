import streamlit as st
from lpw_ollamaClient import OllamaClient
from lpw_init import returnValue

def returnSystemText(pcap_data : str) -> str:
    PACKET_WHISPERER = f"""
        {returnValue('system_message')}
        packet_capture_info : {pcap_data}
    """
    return PACKET_WHISPERER

def _getClient():
    if 'ollama_client' not in st.session_state:
        st.session_state['ollama_client'] = OllamaClient()
    return st.session_state['ollama_client']

def setLLMServer(server, port):
    _getClient().setServer(server, port)

def initLLM(pcap_data) -> None:
    _getClient().set_system_message(system_message=returnSystemText(pcap_data))

def exitLLM() -> None:
    _getClient().set_system_message(system_message=returnValue('system_message'))

def getModelList() -> tuple[list[str], bool]:
    return _getClient().getModelList()

def chatWithModel(prompt:str, model: str):
    return _getClient().chat(prompt=prompt, model=model, temp=0.4)

def clearHistory():
    _getClient().clear_history()

def modifySM(new_sm: str) -> None:
    _getClient().edit_system_message(new_sm)
