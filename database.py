import os
import time
from pymongo import MongoClient

# Carrega a string de conexão das variáveis de ambiente (com fallback de segurança)
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://bladesan246:42131238805Paulo@cluster0.p0hbf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

client = MongoClient(MONGO_URI)
db = client["bot_telegram_jogos"]
colecao = db["historico_postagens"]

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
    return colecao.find_one({"url": url_limpa}) is not None

def registrar_envio(url: str):
    """Registra ou atualiza a URL normalizada no banco de dados."""
    url_limpa = normalizar_url(url)
    if not url_limpa:
        return
    colecao.update_one(
        {"url": url_limpa},
        {"$set": {"url": url_limpa, "timestamp": time.time()}},
        upsert=True
    )