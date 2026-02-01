
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import requests

API_BASE_URL = "https://public-api.meteofrance.fr/public/DPClim/v1"
ENDPOINT = "liste-stations/quotidienne"

def call_api(api_key: str, departement: str, parametre: str, timeout: float) -> dict:
    url = f"{API_BASE_URL}/{ENDPOINT}"
    headers = {
        "accept": "*/*",
        "apikey": api_key,
    }
    params = {
        "id-departement": departement,
        "parametre": parametre,
    }

    # Désactivation de la vérification SSL
    resp = requests.get(url, headers=headers, params=params, timeout=timeout, verify=False)
    resp.raise_for_status()
    return resp.json()

def main():
    parser = argparse.ArgumentParser(description="Appel API Météo-France DPClim (SSL désactivé).")
    parser.add_argument("--api-key", default=os.environ.get("METEOFRANCE_API_KEY"), help="Clé API.")
    parser.add_argument("--departement", default="49", help="ID du département.")
    parser.add_argument("--parametre", default="temperature", help="Paramètre.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout en secondes.")
    parser.add_argument("--output", default=None, help="Fichier de sortie JSON.")
    args = parser.parse_args()

    if not args.api_key:
        print("Erreur: fournissez --api-key ou METEOFRANCE_API_KEY.", file=sys.stderr)
        sys.exit(2)

    try:
        data = call_api(args.api_key, args.departement, args.parametre, args.timeout)
    except requests.HTTPError as e:
        print(f"Erreur HTTP: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(4)

    print(json.dumps(data, ensure_ascii=False, indent=2))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"JSON enregistré dans: {args.output}")

if __name__ == "__main__":
    # Désactive l'avertissement InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
