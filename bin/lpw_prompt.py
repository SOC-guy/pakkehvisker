import streamlit as st
from lpw_ollamaClient import OllamaClient
from lpw_init import returnValue
from lpw_rag import format_context, search_capture


def returnSystemText(retrieved_context: str = "") -> str:
    system_message = returnValue('system_message')
    if not retrieved_context:
        return system_message
    return f"{system_message}\n\nRetrieved packet evidence:\n{retrieved_context}"

def _getClient():
    if 'ollama_client' not in st.session_state:
        st.session_state['ollama_client'] = OllamaClient()
    return st.session_state['ollama_client']

def setLLMServer(server, port):
    _getClient().setServer(server, port)

def getOllamaClient():
    return _getClient()

def initLLM() -> None:
    client = _getClient()
    client.clear_history()
    returnValue('messages').clear()
    st.session_state['insights_done'] = False
    st.session_state['insights_file_done'] = False
    st.session_state['insights_raw'] = ""
    client.set_system_message(system_message=returnSystemText())

def exitLLM() -> None:
    _getClient().set_system_message(system_message=returnValue('system_message'))

def getModelList() -> tuple[list[str], bool]:
    return _getClient().getModelList()

def chatWithModel(
    prompt: str,
    model: str,
    capture_id: str | None,
    embedding_model: str,
):
    retrieved_context = ""
    if capture_id:
        matches = search_capture(
            capture_id=capture_id,
            query=prompt,
            embedding_model=embedding_model,
            ollama_client=getOllamaClient(),
        )
        retrieved_context = format_context(matches)

    client = _getClient()
    client.set_system_message(system_message=returnSystemText(retrieved_context))
    return client.chat(prompt=prompt, model=model, temp=0.4)

def clearHistory():
    _getClient().clear_history()

def modifySM(new_sm: str) -> None:
    _getClient().edit_system_message(new_sm)
