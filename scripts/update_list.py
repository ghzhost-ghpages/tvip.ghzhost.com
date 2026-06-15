import urllib.request
import re
import json
import os
import concurrent.futures

M3U_SOURCES = [
    {"url": "https://iptv-org.github.io/iptv/countries/br.m3u", "country": "Brasil"},
    {"url": "https://iptv-org.github.io/iptv/countries/pt.m3u", "country": "Portugal"}
]

# Regex para parsear linhas M3U
# Ex: #EXTINF:-1 tvg-id="Globo" tvg-name="Globo" tvg-logo="https://..." group-title="General",Globo TV
INF_PATTERN = re.compile(r'#EXTINF:[^,\n]*(?:tvg-logo="([^"]*)")?(?:group-title="([^"]*)")?[^,\n]*,([^\n]+)')

def test_stream(channel):
    """Testa se a URL do stream está ativa usando HEAD request"""
    url = channel['url']
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            method='HEAD'
        )
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status in [200, 206, 301, 302]:
                return channel
    except Exception:
        # Se falhar HEAD, tentamos GET curto
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status in [200, 206, 301, 302]:
                    return channel
        except Exception:
            pass
    return None

def parse_m3u(content, country):
    channels = []
    lines = content.split('\n')
    current_info = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('#EXTINF:'):
            match = INF_PATTERN.match(line)
            if match:
                logo = match.group(1) or ""
                group = match.group(2) or "Geral"
                name = match.group(3).strip()
                current_info = {"name": name, "logo": logo, "group": group, "country": country}
        elif line.startswith('http') and current_info:
            current_info["url"] = line
            channels.append(current_info)
            current_info = None
            
    return channels

def main():
    print("Iniciando a busca de listas IPTV...")
    all_channels = []
    
    for source in M3U_SOURCES:
        try:
            req = urllib.request.Request(
                source["url"], 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8', errors='ignore')
                channels = parse_m3u(content, source["country"])
                print(f"Encontrados {len(channels)} canais para {source['country']}")
                all_channels.extend(channels)
        except Exception as e:
            print(f"Erro ao carregar fonte {source['url']}: {e}")
            
    # Remover duplicados pelo nome
    seen_names = set()
    unique_channels = []
    for c in all_channels:
        if c['name'].lower() not in seen_names:
            seen_names.add(c['name'].lower())
            unique_channels.append(c)
            
    print(f"Total de canais únicos para testar: {len(unique_channels)}")
    
    # Testar conectividade em paralelo (threads)
    active_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(test_stream, unique_channels)
        for res in results:
            if res:
                active_channels.append(res)
                
    print(f"Total de canais ativos confirmados: {len(active_channels)}")
    
    # Criar pasta data se não existir
    os.makedirs('data', exist_ok=True)
    
    # Gravar JSON
    with open('data/channels.json', 'w', encoding='utf-8') as f:
        json.dump(active_channels, f, ensure_ascii=False, indent=2)
        
    # Gravar M3U
    with open('tvip.m3u', 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for c in active_channels:
            logo_attr = f' tvg-logo="{c["logo"]}"' if c["logo"] else ''
            group_attr = f' group-title="{c["group"]}"' if c["group"] else ''
            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{c["name"]}"{logo_attr}{group_attr},{c["name"]} ({c["country"]})\n')
            f.write(f'{c["url"]}\n')
            
    print("Atualização concluída com sucesso! Arquivos tvip.m3u and data/channels.json gerados.")

if __name__ == '__main__':
    main()
