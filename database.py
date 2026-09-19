import os
from pymongo import MongoClient

# URI de conexão do MongoDB Atlas
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://crowbrawl937_db_user:aLXwCJtSpUHhEbrZ@gamesejogos.yzj7pgg.mongodb.net/?appName=GameseJogos"
)

client = MongoClient(MONGO_URI)
db = client["bot_jogos"]
colecao = db["historico_enviados"]


def ja_foi_enviado(url_pagina: str) -> bool:
    """Verifica se a URL do jogo já foi salva no MongoDB."""
    try:
        resultado = colecao.find_one({"url_pagina": url_pagina})
        return resultado is not None
    except Exception as e:
        print(f"⚠️ [Database] Erro ao consultar banco: {e}")
        return False


def registrar_envio(url_pagina: str):
    """Grava a URL do jogo no MongoDB Atlas para evitar duplicatas."""
    try:
        colecao.insert_one({"url_pagina": url_pagina})
        print(f"💾 [Database] Salvo no histórico: {url_pagina}")
    except Exception as e:
        print(f"⚠️ [Database] Erro ao salvar no banco: {e}")