from database import (
    ja_foi_enviado, 
    registrar_envio, 
    normalizar_url, 
    obter_pagina_ponteiro, 
    salvar_pagina_ponteiro
)

# Tamanho do lote de páginas por ciclo
TAMANHO_LOTE = 5

async def executar_ciclo():
    """Varre páginas progressivamente salvando o ponteiro no banco para cobrir todo o site."""
    pagina_inicio = obter_pagina_ponteiro()
    pagina_fim = pagina_inicio + TAMANHO_LOTE - 1

    print(f"\n⏰ [{time.strftime('%H:%M:%S')}] Iniciando ciclo de varredura...")
    print(f"🔍 Raspando lote atual de páginas: {pagina_inicio} até {pagina_fim}...")

    # Raspa as páginas do lote atual
    jogos_lote = []
    for pag in range(pagina_inicio, pagina_fim + 1):
        url = SITE_ALVO if pag == 1 else f"{SITE_ALVO}page/{pag}/"
        jogos_pagina = obter_todos_os_jogos(url, limite_paginas=1)
        if jogos_pagina:
            jogos_lote.extend(jogos_pagina)

    if not jogos_lote:
        print(f"⚠️ Nenhum jogo encontrado entre as páginas {pagina_inicio} e {pagina_fim}. Reiniciando varredura da página 1...")
        salvar_pagina_ponteiro(1)
        return

    # Inverte para processar do mais antigo do lote para o mais recente
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

    # SE CHEGOU AQUI: Significa que TODOS os jogos do lote atual já foram postados!
    # Avança o ponteiro para que o próximo ciclo leia as PRÓXIMAS páginas do site.
    nova_pagina = pagina_fim + 1
    salvar_pagina_ponteiro(nova_pagina)
    print(f"➡️ Todos os jogos das páginas {pagina_inicio} a {pagina_fim} já foram publicados.")
    print(f"📍 Ponteiro atualizado no MongoDB! O próximo ciclo vai ler a partir da Página {nova_pagina}.")