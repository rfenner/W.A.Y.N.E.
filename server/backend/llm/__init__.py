from llm.local_llm_client import LocalLLMClient

#shared llm for systems that need to call the llm
# so we don't have to have a client per system
system_llm = None
def get_system_llm():
    global system_llm
    if system_llm is None:
        system_llm = LocalLLMClient()
    return system_llm