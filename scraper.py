import re
import html
import urllib.parse
import cloudscraper
from bs4 import BeautifulSoup

# Instância do scraper para acessar a FitGirl e APIs
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)


def extrair_magnet(html_text: str) -> str | None:
    """Extrai e decodifica o Magnet Link da página."""
    pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+[^\s"\'<>]*'
    matches = re.findall(pattern, html_text, re.IGNORECASE)
    if matches:
        return html.unescape(matches[0])
    return None


def limpar_titulo_para_busca(titulo: str) -> str:
    """Limpa o título removendo números de versão, DLCs e tags do repack."""
    titulo_limpo = re.sub(r'\(.*?\)', '', titulo)
    titulo_limpo = re.sub(r'\[.*?\]', '', titulo_limpo)
    titulo_limpo = re.sub(r'v\d+(\.\d+)*.*', '', titulo_limpo, flags=re.IGNORECASE)
    titulo_limpo = re.split(r'–|-|:', titulo_limpo)[0]
    return titulo_limpo.strip()


def traduzir_para_portugues(texto: str) -> str:
    """Traduz qualquer texto para português usando a API pública do Google Translate."""
    if not texto or len(texto) < 5:
        return texto

    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={urllib.parse.quote(texto)}"
        res = scraper.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # O Google Translate retorna o texto traduzido dividido em segmentos
            traducao = "".join([part[0] for part in data[0] if part[0]])
            return traducao
    except Exception as e:
        print(f"⚠️ Erro ao traduzir texto: {e}")

    return texto


def buscar_sinopse_wikipedia(titulo_jogo: str) -> str | None:
    """Busca um resumo descritivo do jogo via API pública da Wikipedia (PT primeiro, depois EN)."""
    nome_limpo = limpar_titulo_para_busca(titulo_jogo)
    if not nome_limpo:
        return None

    # 1. Tentativa na Wikipedia em Português
    url_pt = f"https://pt.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(nome_limpo)}"
    try:
        res = scraper.get(url_pt, timeout=8)
        if res.status_code == 200:
            data = res.json()
            extract = data.get("extract")
            if extract and len(extract) > 40 and "pode referir-se" not in extract.lower():
                return extract
    except Exception:
        pass

    # 2. Tentativa na Wikipedia em Inglês (será traduzida depois)
    url_en = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(nome_limpo)}"
    try:
        res = scraper.get(url_en, timeout=8)
        if res.status_code == 200:
            data = res.json()
            extract = data.get("extract")
            if extract and len(extract) > 40 and "may refer to" not in extract.lower():
                # Traduz o trecho em inglês para português
                return traduzir_para_portugues(extract)
    except Exception:
        pass

    return None


def extrair_metadados_fitgirl(soup: BeautifulSoup) -> str:
    """Fallback: Extrai gêneros e desenvolvedora e traduz para português."""
    entry_content = soup.find('div', class_='entry-content')
    if not entry_content:
        return "Gênero e detalhes disponíveis no link de download."

    info_genero = ""
    info_dev = ""

    for p in entry_content.find_all('p'):
        txt = p.get_text()
        if "Genres/Tags:" in txt or "Genres:" in txt:
            info_genero = txt.replace("Genres/Tags:", "Gêneros:").replace("Genres:", "Gêneros:").strip()
        if "Company:" in txt or "Companies:" in txt or "Developer:" in txt:
            info_dev = txt.replace("Company:", "Desenvolvedora:").replace("Companies:", "Desenvolvedoras:").strip()

    partes = [p for p in [info_genero, info_dev] if p]
    if partes:
        texto_metadados = " | ".join(partes)
        return traduzir_para_portugues(texto_metadados)

    return "Gênero e detalhes disponíveis no link de download."


def extrair_sinopse_com_busca(soup: BeautifulSoup, titulo_jogo: str) -> str:
    """Gerencia as camadas de busca e garante a tradução para Português."""
    sinopse = buscar_sinopse_wikipedia(titulo_jogo)
    if not sinopse:
        sinopse = extrair_metadados_fitgirl(soup)

    if len(sinopse) > 350:
        sinopse = sinopse[:347] + "..."

    return sinopse


def gerar_link_gameplay_youtube(titulo: str) -> str:
    """Gera um link de busca de gameplay no YouTube."""
    titulo_limpo = limpar_titulo_para_busca(titulo)
    query = f"{titulo_limpo} gameplay"
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"


def raspar_detalhes_do_jogo(url_jogo: str, titulo_jogo: str) -> dict | None:
    """Acessa a página do jogo e extrai magnet link, capa e sinopse em português."""
    print(f"🔍 Acessando: {url_jogo}")
    try:
        response = scraper.get(url_jogo, timeout=30)
        if response.status_code != 200:
            return None

        html_content = response.text
        magnet = extrair_magnet(html_content)

        if not magnet:
            return None

        soup = BeautifulSoup(html_content, 'html.parser')

        # Busca a URL da imagem da capa
        img_tag = soup.find('img', src=re.compile(r'\.(jpg|png|webp)', re.IGNORECASE))
        imagem_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None

        # Obtém e traduz a sinopse
        sinopse = extrair_sinopse_com_busca(soup, titulo_jogo)

        return {
            "magnet": magnet,
            "imagem_url": imagem_url,
            "sinopse": sinopse
        }
    except Exception as e:
        print(f"❌ Erro ao raspar página: {e}")
        return None


def obter_todos_os_jogos(url_home: str, limite_paginas: int | None = None) -> list[dict]:
    """Mapeia todas as páginas do site e coleta os links dos jogos."""
    jogos = []
    urls_vistas = set()
    pagina_atual = 1

    try:
        res = scraper.get(url_home, timeout=30)
        if res.status_code == 200:
            soup_home = BeautifulSoup(res.text, 'html.parser')
            links_paginas = soup_home.find_all('a', class_='page-numbers')
            paginas_num = [int(l.get_text()) for l in links_paginas if l.get_text().isdigit()]
            total_paginas = max(paginas_num) if paginas_num else 100
        else:
            total_paginas = 100
    except Exception:
        total_paginas = 100

    if limite_paginas:
        total_paginas = min(total_paginas, limite_paginas)

    print(f"🌐 [Scraper] Mapeando um total de {total_paginas} páginas no site...")

    padrao_ignorar = re.compile(
        r'/(category|tag|search|uncategorized|comments|feed)/',
        re.IGNORECASE
    )

    while pagina_atual <= total_paginas:
        target_url = url_home if pagina_atual == 1 else f"{url_home.rstrip('/')}/page/{pagina_atual}/"
        print(f"\n🌐 Raspando página {pagina_atual}/{total_paginas}: {target_url}")

        try:
            response = scraper.get(target_url, timeout=30)
            if response.status_code != 200:
                pagina_atual += 1
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            artigos = soup.find_all('article')

            for artigo in artigos:
                titulo_header = artigo.find(['h1', 'h2'], class_=re.compile(r'entry-title', re.IGNORECASE)) or artigo.find(['h1', 'h2'])
                if not titulo_header:
                    continue

                link_tag = titulo_header.find('a', href=True) or artigo.find('a', href=True)

                if link_tag:
                    titulo = titulo_header.get_text(strip=True)
                    url_pagina = link_tag['href']

                    if (
                        url_pagina.startswith('http')
                        and url_pagina not in urls_vistas
                        and len(titulo) > 3
                        and not padrao_ignorar.search(url_pagina)
                    ):
                        urls_vistas.add(url_pagina)
                        jogos.append({"titulo": titulo, "url_pagina": url_pagina})

        except Exception as e:
            print(f"❌ Erro ao listar página {pagina_atual}: {e}")

        pagina_atual += 1

    return jogos