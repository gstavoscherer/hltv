def is_cloudflare_page(content: str) -> bool:
    """
    Detecta se a página é uma tela de bloqueio do Cloudflare de fato.
    Evita falsos positivos vindos de JS interno.
    """
    if not content:
        return False
    text = content.lower()

    # sinais fortes de challenge page
    challenge_signals = [
        "<title>just a moment...</title>",
        "checking your browser before accessing",
        "cf-browser-verification",
        "wait while we check your browser",
        "please enable javascript and cookies",
    ]

    # exige ao menos 2 sinais fortes pra considerar CF real
    matches = [sig for sig in challenge_signals if sig in text]
    return len(matches) >= 2
