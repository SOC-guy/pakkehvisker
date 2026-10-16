import pyshark as ps
import streamlit as st
import re
import asyncio
import tempfile
from pathlib import Path

def remove_ansi_escape_sequences(input_string):
    # Define a regular expression pattern to match ANSI escape sequences
    ansi_escape_pattern = r'\x1B(?:[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]'
    
    # Use re.sub() to replace ANSI escape sequences with an empty string
    cleaned_string = re.sub(ansi_escape_pattern, '', input_string)
    
    return cleaned_string

@st.cache_data
def getPcapData(
    input_file: bytes = b"",
    filter: str = "",
    decode_info: dict[str, str] | None = None,
) -> str:
    eventloop = asyncio.new_event_loop()
    try:
        with tempfile.TemporaryDirectory() as capture_dir:
            capture_path = Path(capture_dir) / "upload.pcap"
            capture_path.write_bytes(input_file)
            cap = None
            try:
                cap = ps.FileCapture(
                    input_file=str(capture_path),
                    display_filter=filter,
                    eventloop=eventloop,
                )
                out_string = "\n".join(str(packet) for packet in cap)
            except ps.tshark.tshark.TSharkNotFoundException:
                st.error(body='TShark/Wireshark is not installed. \n Please install [wireshark](https://tshark.dev/setup/install/#install-wireshark-with-a-package-manager) first', icon='🚨')
                st.warning(body='LPW is now stopped', icon='🛑')
                st.stop()
            finally:
                if cap is not None:
                    cap.close()
    finally:
        eventloop.close()
    return remove_ansi_escape_sequences(out_string)