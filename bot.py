import os
import asyncio
import io
import html
import urllib.parse
import time
import re
import secrets
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Bot
import cloudscraper
from database import (
    ja_foi_enviado, 
    registrar_envio, 
    normalizar_url, 
    obter_pagina_ponteiro, 
    salvar_pagina_ponteiro
)
from scraper import obter_todos_os_jogos, raspar_detalhes_do_jogo, gerar_link_gameplay_youtube

# Cache em memória da sessão
ENVIADOS_EM_MEMORIA = set()

# === SERVIDOR HTTP DUMMY (Impede crash por Health Check no Render / Ping UptimeRobot) ===
class SimplePingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        response_text = "Bot de Jogos esta ativo e operacional no Render!"
        self.wfile.write(response_text.encode("utf-8"))

    def log_message(self, format, *args):
        print(f"📡 [Ping HTTP] Requisição de saude/keep-alive recebida de: {self.client_address[0]}")

def iniciar_servidor_ping():
    porta = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", porta), SimplePingHandler)
        print(f"🌐 [Render Web Service] Servidor HTTP escutando na porta {porta}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Erro ao iniciar servidor HTTP na porta {porta}: {e}")

# Inicia o servidor HTTP em background antes do bot rodar
thread_http = threading.Thread(target=iniciar_servidor_ping, daemon=True)
thread_http.start()

# === CONFIGURAÇÕES ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8830071006:AAHXk4JjRmYTrylvkOuSm1jpcy_8FLB63iw")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@gamesejogoss")
SITE_ALVO = "https://fitgirl-repacks.site/"

INTERVALO_HORAS = 2.0 
TAMANHO_LOTE = 5 

DOMINIO_ENCURTADOR = "linkmonetizado.com"
ENCURTADOR_API_KEY = os.environ.get("ENCURTADOR_API_KEY", "b56fc7474ea7a7cfc3606ce7fd38802dd10dc9e8")

bot = Bot(token=TELEGRAM_TOKEN)

img_downloader = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

def baixar_imagem_bytes(imagem_url: str) -> bytes | None:
    if not imagem_url:
        return None

    headers = {
        "Referer": "https://fitgirl-repacks.site/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = img_downloader.get(imagem_url, headers=headers, timeout=15)
        if res.status_code == 200 and len(res.content) > 1000:
            if res.content.startswith(b'\xff\xd8') or res.content.startswith(b'\x89PNG') or res.content.startswith(b'RIFF'):
                return res.content
    except Exception as e:
        print(f"⚠️ [Imagem] Erro no download direto ({imagem_url}): {e}")

    try:
        proxy_url = f"https://images.weserv.nl/?url={urllib.parse.quote(imagem_url)}"
        res = img_downloader.get(proxy_url, timeout=15)
        if res.status_code == 200 and len(res.content) > 1000:
            return res.content
    except Exception as e:
        print(f"⚠️ [Imagem] Erro no proxy de imagem: {e}")

    return None

def criar_pagina_intermediaria_rentry(titulo: str, magnet: str, sinopse: str, url_yt: str, requisitos_rec: str) -> str | None:
    try:
        edit_code = secrets.token_hex(12)
        conteudo = (
            f"# 🎮 {titulo}\n\n"
            f"📝 **Sinopse:**\n{sinopse}\n\n"
            f"🚀 **Requisitos Recomendados:**\n{requisitos_rec}\n\n"
            f"🎬 **[👉 Assistir Gameplay no YouTube]({url_yt})**\n\n"
            f"---\n\n"
            f"### ⬇️ Opções de Download:\n\n"
            f"⚡ **[👉 Clique aqui para Abrir Direto no Cliente Torrent]({magnet})**\n\n"
            f"📋 **Magnet Link para Cópia Manual:**\n\n"
            f"```\n{magnet}\n```\n"
        )

        payload = {"text": conteudo, "edit_code": edit_code}
        scraper = cloudscraper.create_scraper()
        res = scraper.post("https://rentry.co/api/new", data=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "200":
                return data.get("url")
    except Exception as e:
        print(f"⚠️ Erro ao criar página no Rentry: {e}")
    return None

def encurtar_fallback_tinyurl(url_destino: str) -> str:
    try:
        scraper = cloudscraper.create_scraper()
        api_url = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(url_destino)}"
        res = scraper.get(api_url, timeout=10)
        if res.status_code == 200:
            link = res.text.strip()
            if link.startswith("http"):
                return link
    except Exception:
        pass
    return url_destino

def gerar_alias_unico(titulo: str) -> str:
    limpo = re.sub(r'[^a-zA-Z0-9]', '', titulo)[:12].lower()
    timestamp = str(int(time.time()))[-5:]
    return f"g_{limpo}_{timestamp}"

def encurtar_link_monetizado(url_destino: str, titulo: str) -> str:
    if not ENCURTADOR_API_KEY:
        return encurtar_fallback_tinyurl(url_destino)

    alias_unico = gerar_alias_unico(titulo)
    url_encoded = urllib.parse.quote(url_destino)
    url_api = f"https://{DOMINIO_ENCURTADOR}/api?api={ENCURTADOR_API_KEY}&url={url_encoded}&alias={alias_unico}"

    try:
        scraper_api = cloudscraper.create_scraper()
        res = scraper_api.get(url_api, timeout=15)
        if res.status_code == 200:
            try:
                data = res.json()
                if data.get("status") != "error" and ("shortenedUrl" in data or "shorturl" in data):
                    link_json = (data.get("shortenedUrl") or data.get("shorturl") or "").strip().replace("\\", "")
                    if link_json.startswith("http"):
                        return link_json
            except Exception:
                res_text = res.text.strip().replace("\\", "")
                if res_text.startswith("http"):
                    return res_text
    except Exception as e:
        print(f"⚠️ [LinkMonetizado] Erro de conexão com API: {e}")

    return encurtar_fallback_tinyurl(url_destino)

async def enviar_telegram(titulo: str, magnet: str, imagem_url: str | None, sinopse: str, requisitos_rec: str) -> bool:
    titulo_safe = html.escape(titulo)
    sinopse_safe = html.escape(sinopse)
    req_rec = html.escape(requisitos_rec)

    url_gameplay = gerar_link_gameplay_youtube(titulo)
    url_pagina_download = criar_pagina_intermediaria_rentry(titulo, magnet, sinopse, url_gameplay, requisitos_rec) or magnet
    link_monetizado = encurtar_link_monetizado(url_pagina_download, titulo)

    mensagem = (
        f"🎮 <b>{titulo_safe}</b>\n\n"
        f"📖 <b>Sinopse:</b>\n<i>{sinopse_safe}</i>\n\n"
        f"⚙️ <b>Requisitos Recomendados:</b>\n<i>{req_rec}</i>\n\n"
        f"🎬 <a href=\"{url_gameplay}\"><b>[ 🎥 Assistir Gameplay no YouTube ]</b></a>\n"
        f"🚀 <a href=\"{link_monetizado}\"><b>[ ⬇️ Clique aqui para Baixar o Torrent ]</b></a>"
    )

    foto_bytes = baixar_imagem_bytes(imagem_url) if imagem_url else None

    if foto_bytes:
        try:
            foto_file = io.BytesIO(foto_bytes)
            foto_file.name = "cover.jpg"
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=foto_file,
                caption=mensagem,
                parse_mode="HTML"
            )
            print(f"✅ [Telegram] Postado com foto: {titulo}")
            return True
        except Exception as e:
            print(f"⚠️ [Telegram] Falha ao enviar foto em bytes ({e}). Enviando texto...")

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=mensagem,
            parse_mode="HTML"
        )
        print(f"✅ [Telegram] Postado (texto): {titulo}")
        return True
    except Exception as e:
        print(f"❌ [Telegram] Erro ao enviar mensagem: {e}")
        return False

async def executar_ciclo():
    pagina_inicio = obter_pagina_ponteiro()
    pagina_fim = pagina_inicio + TAMANHO_LOTE - 1

    print(f"\n⏰ [{time.strftime('%H:%M:%S')}] Iniciando ciclo de varredura...")
    print(f"🔍 Raspando lote de páginas: {pagina_inicio} até {pagina_fim}...")

    jogos_lote = []
    for pag in range(pagina_inicio, pagina_fim + 1):
        url = SITE_ALVO if pag == 1 else f"{SITE_ALVO}page/{pag}/"
        jogos_pagina = obter_todos_os_jogos(url, limite_paginas=1)
        if jogos_pagina:
            jogos_lote.extend(jogos_pagina)

    if not jogos_lote:
        print(f"⚠️ Nenhum jogo encontrado no lote {pagina_inicio}-{pagina_fim}. Reiniciando da Página 1...")
        salvar_pagina_ponteiro(1)
        return

    jogos_ordenados = list(reversed(jogos_lote))

    for jogo in jogos_ordenados:
        url_pagina = normalizar_url(jogo["url_pagina"])

        if url_pagina in ENVIADOS_EM_MEMORIA or ja_foi_enviado(url_pagina):
            continue

        titulo = jogo["titulo"]
        print(f"🆕 [Jogo Selecionado] Processando: {titulo}")

        detalhes = raspar_detalhes_do_jogo(url_pagina, titulo)
        if not detalhes or not detalhes.get("magnet"):
            print(f"❌ Falha ao extrair Magnet Link para: {titulo}. Buscando próximo...")
            continue

        sucesso = await enviar_telegram(
            titulo=titulo,
            magnet=detalhes["magnet"],
            imagem_url=detalhes.get("imagem_url"),
            sinopse=detalhes.get("sinopse", "Confira os detalhes no link de download."),
            requisitos_rec=detalhes.get("requisitos_recomendados", "Não informados")
        )

        if sucesso:
            registrar_envio(url_pagina)
            ENVIADOS_EM_MEMORIA.add(url_pagina)
            print("🎯 Postagem efetuada com sucesso!")
            return

    nova_pagina = pagina_fim + 1
    salvar_pagina_ponteiro(nova_pagina)
    print(f"➡️ Todos os jogos das páginas {pagina_inicio} a {pagina_fim} já foram publicados.")
    print(f"📍 Ponteiro atualizado no MongoDB! O próximo ciclo vai ler a partir da Página {nova_pagina}.")

async def main():
    print("🤖 Bot ativado em modo de execução periódica por ponteiro dinâmico.")
    print(f"⏱️ Intervalo configurado: exatamente {INTERVALO_HORAS} horas entre postagens.\n")

    while True:
        try:
            await executar_ciclo()
        except Exception as e:
            print(f"❌ Erro não tratado durante o ciclo: {e}")

        tempo_espera_segundos = int(INTERVALO_HORAS * 3600)
        proxima_execucao = time.strftime('%H:%M:%S', time.localtime(time.time() + tempo_espera_segundos))
        print(f"💤 Entrando em repouso. Próximo envio agendado para às: {proxima_execucao}")
        await asyncio.sleep(tempo_espera_segundos)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Execução interrompida pelo usuário.")