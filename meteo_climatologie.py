#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path
from meteo import Meteo
import string
import time

def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Format de date invalide, attendu AAAA-MM-DD"
        )

def process_inputs(json_file, excel_file, args):
    print(f"--- Traitement: {json_file.name} -> {excel_file.name} ---")

    meteo = Meteo(
        api_base_url=args.api_url,
        api_key=args.api_key,
        current_dir=os.getcwd(),
        inputs_file=str(json_file),
        excel_file=str(excel_file),
        date_deb=args.date_deb,
        date_fin=args.date_fin,
        parameter=args.parameter,
        country=args.country,
        language=args.language,
        timeout=args.timeout,
        force=args.force
    )

    cities_file = json_file
    if cities_file.exists():
        with cities_file.open("r", encoding="utf-8") as f:
            cities = json.load(f)
            if not isinstance(cities, list):
                print(f"Erreur: Le fichier JSON {json_file} ne contient pas une liste. Ignoré.")
                return
    else:
        print(f"Erreur: Fichier {json_file} introuvable.")
        return
        
    excel_col_index = 1
    for city in cities:
        city_name = city.get('name')
        city_departement = city.get('departement')
        city_county = city.get('county')
        city_country = city.get('country', 'France')
        city_language = city.get('language', 'fr')
        city_parameter = city.get('parameter', 'temperature')
        city_force = city.get('force', False)
        
        # Override global force if specific force is set? 
        # Actually logic inside meteo.py uses API_FORCE or force param.
        # Here we pass city_force to write_stations_by_departement but logic for data download 
        # depends on global args in current code?
        # Let's check: get_and_download_file uses Meteo class state.
        # But wait, send_command_station uses self.API_DATE_DEB etc.
        # The original code didn't seem to use city_force for download/command, only for stations list?
        # Let's keep original logic.
        
        meteo.write_stations_by_departement(city_departement, city_parameter, city_force)

        result = meteo.geocode_city_with_county(city_name, city_county, city_country, city_language)
        if result is None:
            print(f"Aucune coordonnée trouvée pour: {city_name}, département {city_departement}, country {city_country}")
            # continue instead of exit to process other cities/files
            continue 
        
        city, lat, lon, label = result
    
        # DEBUG
        print()
        print(f"Ville:      {city}, département {city_departement}, {city_country}")
        print(f"Latitude:   {lat:.6f}")
        print(f"Longitude:  {lon:.6f}")
        print(f"Résultat:   {label}")
        print()
        
        nearest = meteo.find_nearest_station(lat, lon, city_departement)
        print(nearest)

        meteo.send_command_station()
        meteo.get_and_download_file(city_name)

        # Générer les lettres simples A-Z
        letters = list(string.ascii_uppercase)
        # Générer les combinaisons AA-ZZ
        col_letters = letters[:]  # commence avec A-Z
        for first in letters:
            for second in letters:
                col_letters.append(first + second)

        excel_row = 4
        excel_col = col_letters[excel_col_index]
        meteo.set_excel(excel_row, excel_col, city_name, city_departement, city_county)
        excel_col_index += 1

def main():
    parser = argparse.ArgumentParser(description="Appel API Météo-France DPClim (SSL désactivé).")
    parser.add_argument("--api-url", "-u", default=os.environ.get("METEOFRANCE_API_URL"), help="API URL Meteo France.")
    parser.add_argument("--api-key", "-a", default=os.environ.get("METEOFRANCE_API_KEY"), help="Clé API Meteo France.")
    parser.add_argument("--inputs-file", default="inputs.json", help="Fichier JSON contenant la liste de dictionnaire avec les informations des villes à traiter.")
    parser.add_argument("--excel-file", default="Calculette_T_pucerons.xlsx", help="Fichier Excel pour l'exportation des données météo.")
    parser.add_argument("--date-deb", required=True, help="Début de période au format AAAA-MM-DD.")
    parser.add_argument("--date-fin", type=parse_date, help="Fin de période au format AAAA-MM-DD (par défaut : aujourd'hui)")
    parser.add_argument("--country", "-c", default="France", help="Pays (défaut: France).")
    parser.add_argument("--language", "-l", default="fr", help="Langue des résultats (défaut: fr).")
    parser.add_argument("--parameter", "-p", default="temperature", help="Paramètre de climatologie.")
    parser.add_argument("--timeout", "-t", type=float, default=10.0, help="Timeout en secondes.")
    parser.add_argument("--force", "-f", action="store_true", help="Force la mise à jour de toutes les données.")
    args = parser.parse_args()
        
    # # DEBUG
    # print(f"args.api_url = {args.api_url}")
    # print(f"args.api_key = {args.api_key}")
    # os._exit(0)

    # Validation API URL et Key
    if not args.api_url:
        print("Erreur: fournissez METEOFRANCE_API_URL ou --api-url ou -u", file=sys.stderr)
        print("API URL Météo France introuvable dans les variables d'environnement utilisateur.")
        sys.exit(2)
    if not args.api_key:
        print("Erreur: fournissez METEOFRANCE_API_KEY ou --api-key ou -a", file=sys.stderr)
        print("Clé API Météo France introuvable dans les variables d'environnement utilisateur.")
        sys.exit(3)

    today = date.today()
    # Valeur par défaut
    if args.date_fin is None:
        args.date_fin = str(today)
    # Si date-fin > aujourd'hui → on force aujourd'hui
    elif args.date_fin > today:
        args.date_fin = str(today)

    # Validation simple des dates (et conversion se fait dans call_api)
    for label, d in (("--date-deb", args.date_deb), ("--date-fin", args.date_fin)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"Erreur: {label} invalide '{d}'. Format attendu: AAAA-MM-DD.", file=sys.stderr)
            sys.exit(4)

    # Vérifier que date_deb <= date_fin
    if args.date_deb > args.date_fin:
        print("Erreur: date-deb doit être antérieure ou égale à date-fin.", file=sys.stderr)
        sys.exit(5)

    # Nouvelle structure : Scan du répertoire inputs/
    current_dir = Path(os.getcwd())
    inputs_dir = current_dir / "inputs"
    
    if inputs_dir.exists() and inputs_dir.is_dir():
        # Mode répertoire inputs
        json_files = list(inputs_dir.glob("*.json"))
        if not json_files:
             print(f"Attention: Le répertoire {inputs_dir} est vide ou ne contient pas de fichiers JSON.")
        
        import shutil
        
        for json_file in json_files:
            # ex: pucerons.json -> Calculette_T_pucerons.xlsx
            base_name = json_file.stem # pucerons
            excel_name = f"Calculette_T_{base_name}.xlsx"
            excel_file_path = current_dir / excel_name
            
            # Gestion création fichier Excel si manquant
            if not excel_file_path.exists():
                template_path = current_dir / "Calculette_T_empty.xlsx"
                if template_path.exists():
                    print(f"Création de {excel_name} à partir du modèle.")
                    shutil.copy(template_path, excel_file_path)
                else:
                    print(f"Erreur: Le modèle {template_path} est introuvable. Impossible de créer {excel_name}.", file=sys.stderr)
                    continue
            
            process_inputs(json_file, excel_file_path, args)
            
    else:
        # Fallback ancient mode (if inputs dir doesn't exist)
        print("Répertoire inputs/ non trouvé, utilisation des arguments par défaut.")

        # Wait until the VPN is fully open
        print("Wait 120 seconds until the VPN is fully open.")
        time.sleep(120)  # 120 secondes = 2 minutes

        meteo = Meteo(
            api_base_url=args.api_url,
            api_key=args.api_key,
            current_dir=os.getcwd(),
            inputs_file=args.inputs_file,
            excel_file=args.excel_file,
            date_deb=args.date_deb,
            date_fin=args.date_fin,
            parameter=args.parameter,
            country=args.country,
            language=args.language,
            timeout=args.timeout,
            force=args.force
        )

        cities_file = Path(args.inputs_file)
        if cities_file.exists():
            with cities_file.open("r", encoding="utf-8") as f:
                cities = json.load(f)
                if not isinstance(cities, list):
                    raise ValueError("Le fichier JSON ne contient pas une liste")
        else:
            print("Erreur: fournissez --inputs-file", file=sys.stderr)
            raise RuntimeError("Fichier JSON contenant la liste de dictionnaire avec les informations des villes à traiter introuvable.")

        excel_col_index = 1
        for city in cities:
            city_name = city.get('name')
            city_departement = city.get('departement')
            city_county = city.get('county')
            city_country = city.get('country', 'France')
            city_language = city.get('language', 'fr')
            city_parameter = city.get('parameter', 'temperature')
            city_force = city.get('force', False)

            meteo.write_stations_by_departement(city_departement, city_parameter, city_force)

            result = meteo.geocode_city_with_county(city_name, city_county, city_country, city_language)
            if result is None:
                print(f"Aucune coordonnée trouvée pour: {city_name}, département {city_departement}, country {city_country}")
                sys.exit(1)
            city, lat, lon, label = result
        
            # DEBUG
            print()
            print(f"Ville:      {city}, département {city_departement}, {city_country}")
            print(f"Latitude:   {lat:.6f}")
            print(f"Longitude:  {lon:.6f}")
            print(f"Résultat:   {label}")
            print()
            
            nearest = meteo.find_nearest_station(lat, lon, city_departement)
            print(nearest)

            meteo.send_command_station()
            meteo.get_and_download_file(city_name)

            # Générer les lettres simples A-Z
            letters = list(string.ascii_uppercase)
            # Générer les combinaisons AA-ZZ
            col_letters = letters[:]  # commence avec A-Z
            for first in letters:
                for second in letters:
                    col_letters.append(first + second)

            excel_row = 4
            excel_col = col_letters[excel_col_index]
            meteo.set_excel(excel_row, excel_col, city_name, city_departement, city_county)
            excel_col_index += 1


if __name__ == "__main__":
    # Désactive l'avertissement InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
