import urllib.parse
import cloudscraper
from bs4 import BeautifulSoup

def criar_scraper():
    """Cria uma instância do cloudscraper simulando navegador real."""
    return cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

def obter_todos_os_jogos(url_alvo: str, limite_paginas: int = 1) -> list:
    """Raspa os títulos e links das páginas especificadas."""
    scraper = criar_scraper()
    jogos = []

    try:
        res = scraper.get(url_alvo, timeout=20)
        if res.status_code != 200:
            print(f"⚠️ Erro ao acessar {url_alvo}: Status {res.status_code}")
            return jogos

        soup = BeautifulSoup(res.text, "html.parser")
        artigos = soup.find_all("article")

        for art in artigos:
            header = art.find("h1", class_="entry-title")
            if not header:
                continue
            a_tag = header.find("a")
            if not a_tag:
                continue

            titulo = a_tag.get_text(strip=True)
            link = a_tag.get("href", "").strip()

            if titulo and link:
                jogos.append({
                    "titulo": titulo,
                    "url_pagina": link
                })
    except Exception as e:
        print(f"❌ Erro ao raspar lista de jogos ({url_alvo}): {e}")

    return jogos

def raspar_detalhes_do_jogo(url_pagina: str, titulo: str) -> dict | None:
    """Extrai magnet link, imagem de capa, sinopse e requisitos de uma página de jogo."""
    scraper = criar_scraper()
    try:
        res = scraper.get(url_pagina, timeout=20)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        entry_content = soup.find("div", class_="entry-content")
        if not entry_content:
            return None

        # Busca do Magnet Link
        magnet = None
        for a in entry_content.find_all("a", href=True):
            href = a["href"]
            if href.startswith("magnet:?"):
                magnet = href
                break

        if not magnet:
            return None

        # Busca de Imagem
        imagem_url = None
        img_tag = entry_content.find("img")
        if img_tag and img_tag.get("src"):
            imagem_url = img_tag["src"]

        # Busca de Sinopse e Requisitos
        texto_completo = entry_content.get_text("\n")
        sinopse = "Confira a descrição completa e opções de download no link."
        requisitos = "Não informados"

        paragrafos = [p.get_text(strip=True) for p in entry_content.find_all("p") if p.get_text(strip=True)]
        if paragrafos:
            for p in paragrafos:
                if len(p) > 50 and not p.startswith("http") and "Repack Features" not in p:
                    sinopse = p[:400] + "..." if len(p) > 400 else p
                    break

        return {
            "magnet": magnet,
            "imagem_url": imagem_url,
            "sinopse": sinopse,
            "requisitos_recomendados": requisitos
        }
    except Exception as e:
        print(f"❌ Erro ao raspar detalhes de {titulo}: {e}")
        return None

def gerar_link_gameplay_youtube(titulo: str) -> str:
    """Gera link de busca no YouTube para a gameplay do jogo."""
    query = urllib.parse.quote(f"{titulo} gameplay trailer")
    return f"https://www.youtube.com/results?search_query={query}"