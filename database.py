import os
import time
import certifi
from pymongo import MongoClient

# URI oficial do Cluster GameseJogos
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://crowbrawl937_db_user:crowbrawl937_db_user@gamesejogos.yzj7pgg.mongodb.net/?retryWrites=true&w=majority&appName=GameseJogos"
)

# Conexão com suporte SSL seguro via certifi (compatível com Linux no Render e Windows)
try:
    client = MongoClient(
        MONGO_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000
    )
    db = client["bot_telegram_jogos"]
    colecao_historico = db["historico_postagens"]
    colecao_config = db["configuracoes_bot"]
except Exception as e:
    print(f"❌ Erro ao inicializar cliente MongoDB: {e}")

def normalizar_url(url: str) -> str:
    """Padroniza a URL removendo espaços e garantindo a barra no final."""
    if not url:
        return ""
    url = url.strip()
    if not url.endswith('/'):
        url += '/'
    return url

def ja_foi_enviado(url: str) -> bool:
    """Verifica se a URL normalizada já existe no MongoDB Atlas."""
    url_limpa = normalizar_url(url)
    if not url_limpa:
        return False
    try:
        return colecao_historico.find_one({"url": url_limpa}) is not None
    except Exception as e:
        print(f"⚠️ Erro ao consultar MongoDB (ja_foi_enviado): {e}")
        return False

def registrar_envio(url: str):
    """Registra a URL normalizada no banco de dados."""
    url_limpa = normalizar_url(url)
    if not url_limpa:
        return
    try:
        colecao_historico.update_one(
            {"url": url_limpa},
            {"$set": {"url": url_limpa, "timestamp": time.time()}},
            upsert=True
        )
    except Exception as e:
        print(f"⚠️ Erro ao registrar envio no MongoDB: {e}")

def obter_pagina_ponteiro() -> int:
    """Obtém a página atual onde a varredura do site parou."""
    try:
        doc = colecao_config.find_one({"chave": "pagina_varredura"})
        return doc["valor"] if doc else 1
    except Exception as e:
        print(f"⚠️ Erro ao ler ponteiro no MongoDB: {e}")
        return 1

def salvar_pagina_ponteiro(pagina: int):
    """Atualiza a página atual de varredura no banco."""
    try:
        colecao_config.update_one(
            {"chave": "pagina_varredura"},
            {"$set": {"valor": pagina}},
            upsert=True
        )
    except Exception as e:
        print(f"⚠️ Erro ao salvar ponteiro no MongoDB: {e}")