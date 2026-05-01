import os
import json
import sys
import argparse
from typing import Dict, Any

def cleanup_null_values(data: Any) -> Any:
    """
    Parcourt récursivement les données et remplace les valeurs Python 'None' 
    et la chaîne de caractères "null" par "NC" (Non Communiqué).
    """
    placeholder = "NC"
    
    if isinstance(data, dict):
        return {k: cleanup_null_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [cleanup_null_values(item) for item in data]
    # Si la valeur est Python 'None' (null en JSON) ou la chaîne "null" ou chaîne vide
    elif data is None or str(data).lower() == "null" or data == "":
        return placeholder
    else:
        return data

def process_and_save_raw_json(raw_json_content: str, directory: str, filename: str, mode: str) -> Dict[str, Any]:
    """
    Traite, nettoie, et sauvegarde le contenu JSON brut.
    """
    try:
        # 1. Charger la chaîne JSON brute
        final_raw = json.loads(raw_json_content)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSONDecodeError: {e}", "details": raw_json_content}
    
    # --- Logique de re-parsing (si besoin, basée sur le code original) ---
    keys_to_reparse = list(final_raw.keys())
    for key in keys_to_reparse:
        value = final_raw.get(key)
        if isinstance(value, str) and value.strip().startswith(('{', '[')):
            try:
                final_raw[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    # --- Fin Logique de re-parsing ---
    
    # 4. Nettoyage des valeurs null
    final_cleaned = cleanup_null_values(final_raw)
    
    # 5. Formatage et Sauvegarde
    formatted = json.dumps(final_cleaned, indent=2, ensure_ascii=False)
    
    os.makedirs(directory, exist_ok=True)
    full_path = os.path.join(directory, filename)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(formatted)
    
    return {"success": True, "path": full_path, "mode": mode}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sauvegarde et nettoie un JSON brut dans un fichier.")
    
    # Note: On passe le JSON brut sous forme de string via la ligne de commande
    parser.add_argument("--json", type=str, required=True, help="Contenu JSON brut à sauvegarder (passé en string).")
    parser.add_argument("--directory", type=str, required=True, help="Répertoire de sauvegarde.")
    parser.add_argument("--filename", type=str, required=True, help="Nom du fichier de sauvegarde.")
    parser.add_argument("--mode", type=str, default="save", help="Mode d'opération (ex: 'save').")

    args = parser.parse_args()
    
    # Le JSON est passé comme argument, on appelle la fonction principale
    result = process_and_save_raw_json(args.json, args.directory, args.filename, args.mode)

    # Affiche le résultat en JSON pour que l'API wrapper puisse le lire (stdout)
    print(json.dumps(result))

    if not result.get("success"):
        # Quitter avec un code d'erreur si l'opération a échoué
        sys.exit(1)