import os
import time
import certifi
from pymongo import MongoClient

# Atualize com a nova senha definida no Atlas
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://crowbrawl937_db_user:Bladesan@gamesejogos.yzj7pgg.mongodb.net/?retryWrites=true&w=majority&authSource=admin"
)

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where()
)

db = client["bot_telegram_jogos"]
colecao_historico = db["historico_postagens"]
colecao_config = db["configuracoes_bot"]

def normalizar_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.endswith('/'):
        url += '/'
    return url

def ja_foi_enviado(url: str) -> bool:
    url_limpa = normalizar_url(url)
    if not url_limpa:
        return False
    return colecao_historico.find_one({"url": url_limpa}) is not None

def registrar_envio(url: str):
    url_limpa = normalizar_url(url)
    if not url_limpa:
        return
    colecao_historico.update_one(
        {"url": url_limpa},
        {"$set": {"url": url_limpa, "timestamp": time.time()}},
        upsert=True
    )

def obter_pagina_ponteiro() -> int:
    doc = colecao_config.find_one({"chave": "pagina_varredura"})
    return doc["valor"] if doc else 1

def salvar_pagina_ponteiro(pagina: int):
    colecao_config.update_one(
        {"chave": "pagina_varredura"},
        {"$set": {"valor": pagina}},
        upsert=True
    )