from chat_guardian.services import LangChainLLMClient, build_llm_client
from chat_guardian.settings import settings


def test_build_llm_client_openai_compatible_backend() -> None:
    old_backend = settings.llm_langchain_backend
    old_model = settings.llm_langchain_model
    old_api_base = settings.llm_langchain_api_base
    old_api_key = settings.llm_langchain_api_key

    settings.llm_langchain_backend = "openai_compatible"
    settings.llm_langchain_model = "gpt-4o-mini"
    settings.llm_langchain_api_base = "https://api.deepseek.com/v1"
    settings.llm_langchain_api_key = "dummy"

    client = build_llm_client()

    assert isinstance(client, LangChainLLMClient)
    assert client.model.__class__.__name__ == "ChatOpenAI"

    settings.llm_langchain_backend = old_backend
    settings.llm_langchain_model = old_model
    settings.llm_langchain_api_base = old_api_base
    settings.llm_langchain_api_key = old_api_key


def test_build_llm_client_ollama_backend() -> None:
    old_backend = settings.llm_langchain_backend
    old_model = settings.llm_langchain_model
    old_api_base = settings.llm_langchain_api_base

    settings.llm_langchain_backend = "ollama"
    settings.llm_langchain_model = "qwen2.5:7b"
    settings.llm_langchain_api_base = "http://localhost:11434"

    client = build_llm_client()

    assert isinstance(client, LangChainLLMClient)
    assert client.model.__class__.__name__ == "ChatOllama"

    settings.llm_langchain_backend = old_backend
    settings.llm_langchain_model = old_model
    settings.llm_langchain_api_base = old_api_base
