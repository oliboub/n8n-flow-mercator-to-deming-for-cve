#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from copy import deepcopy

BASE_URL = "http://0.0.0.0:8030/api"
CREDENTIALS = {"email": "api@admin.localhost", "password": "12345678"}

# Flags de restauration (option B)
RESTORE_USERS = True
RESTORE_LOGS = False
RESTORE_DOCUMENTS = True

# Clés fonctionnelles par type
BUSINESS_KEYS = {
    "attributes": "name",
    "domains": "title",
    "measures": "clause",
    "controls": "name",
    "users": "login",
    "documents": "filename",
}

# Ordre logique de création (sans liens)
STEP1_ORDER = ["attributes", "domains", "measures", "controls",  "users", "documents"]

def run_curl(args_list, debug=False):
    """
    args_list: liste pour subprocess (sans shell)
    """
    if debug:
        # Affichage style shell pour debug
        debug_cmd = " ".join(
            a if "'" not in a else '"' + a.replace('"', '\\"') + '"'
            for a in args_list
        )
        print(f"\n🟦 CURL DEBUG:\n{debug_cmd}")
    result = subprocess.run(args_list, capture_output=True, text=True)
    return result


def get_token(debug=False):
    payload = json.dumps(CREDENTIALS)
    args = [
        "curl", "-s", "-X", "POST",
        f"{BASE_URL}/login",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-d", payload,
    ]
    res = run_curl(args, debug=debug)
    if res.returncode != 0:
        print(f"❌ Erreur curl login (rc={res.returncode}): {res.stderr}")
        sys.exit(1)
    try:
        data = json.loads(res.stdout)
    except Exception as e:
        print("❌ Réponse login non JSON:", res.stdout)
        sys.exit(1)
    token = data.get("token")
    if not token:
        print("❌ Token manquant dans la réponse login:", data)
        sys.exit(1)
    print("🔓 Token OK")
    return token


def curl_get_collection(endpoint, token, debug=False):
    args = [
        "curl", "-s", "-X", "GET",
        f"{BASE_URL}/{endpoint}",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
    ]
    res = run_curl(args, debug=debug)
    if res.returncode != 0:
        print(f"❌ Erreur GET {endpoint}: {res.stderr}")
        return None, res.returncode
    if res.stdout.strip() == "":
        return [], 0
    try:
        data = json.loads(res.stdout)
    except Exception:
        print(f"⚠️ Réponse non JSON pour {endpoint}: {res.stdout}")
        return None, 0
    if isinstance(data, dict) and "data" in data:
        return data["data"], 0
    return data, 0


def curl_post(endpoint, token, payload_dict, debug=False):
    payload = json.dumps(payload_dict, ensure_ascii=False)
    args = [
        "curl", "-s", "-X", "POST",
        f"{BASE_URL}/{endpoint}",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-d", payload,
    ]
    res = run_curl(args, debug=debug)
    if res.returncode != 0:
        print(f"❌ Erreur POST {endpoint}: {res.stderr}")
        return None, res.returncode
    try:
        data = json.loads(res.stdout) if res.stdout.strip() else {}
    except Exception:
        print(f"⚠️ Réponse non JSON POST {endpoint}: {res.stdout}")
        data = {}
    return data, 0


def curl_put(endpoint, token, payload_dict, debug=False):
    payload = json.dumps(payload_dict, ensure_ascii=False)
    args = [
        "curl", "-s", "-X", "PUT",
        f"{BASE_URL}/{endpoint}",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "-d", payload,
    ]
    res = run_curl(args, debug=debug)
    if res.returncode != 0:
        print(f"❌ Erreur PUT {endpoint}: {res.stderr}")
        return None, res.returncode
    try:
        data = json.loads(res.stdout) if res.stdout.strip() else {}
    except Exception:
        print(f"⚠️ Réponse non JSON PUT {endpoint}: {res.stdout}")
        data = {}
    return data, 0


def should_restore(endpoint):
    if endpoint == "users":
        return RESTORE_USERS
    if endpoint == "logs":
        return RESTORE_LOGS
    if endpoint == "documents":
        return RESTORE_DOCUMENTS
    return True


def build_business_map_from_api(endpoint, token, debug=False):
    """
    Retourne: { business_key_value: real_id }
    """
    key = BUSINESS_KEYS.get(endpoint)
    if not key:
        return {}
    items, _ = curl_get_collection(endpoint, token, debug=debug)
    if not isinstance(items, list):
        return {}
    mapping = {}
    for it in items:
        bid = it.get("id")
        bval = it.get(key)
        if bid is not None and bval:
            mapping[bval] = bid
    return mapping


def clean_payload_for_step1(obj):
    """
    Supprime id, created_at, updated_at, et les champs de liaison.
    """
    o = deepcopy(obj)
    for k in ["id", "created_at", "updated_at"]:
        o.pop(k, None)
    # On enlève les relations pour la 1ère passe
    for rel in ["attributes", "domains", "measures", "controls", "users", "documents"]:
        if rel in o:
            o.pop(rel, None)
    return o


def restore_step1(data, token, debug=False):
    """
    Création des objets sans liens, en se basant sur les clés fonctionnelles.
    On ne se fie jamais aux id du JSON.
    """
    print("\n=== PASS 1 : Création des objets sans liens ===")
    for ep in STEP1_ORDER:
        if ep not in data:
            continue
        if not should_restore(ep):
            print(f"⏭️  {ep} ignoré (flag RESTORE_*)")
            continue

        items = data[ep]
        if not items:
            print(f"📭 Aucun objet à restaurer pour {ep}.")
            continue

        print(f"\n📦 Endpoint {ep} : {len(items)} objets...")

        # Map existant en base pour éviter les doublons
        existing_map = build_business_map_from_api(ep, token, debug=debug)
        key = BUSINESS_KEYS.get(ep)

        for obj in items:
            if not isinstance(obj, dict):
                continue
            bval = obj.get(key) if key else None
            if bval and bval in existing_map:
                print(f"🔁 {ep} déjà présent ({key}={bval}), on saute la création.")
                continue

            payload = clean_payload_for_step1(obj)
            created, rc = curl_post(ep, token, payload, debug=debug)
            if rc != 0:
                print(f"❌ Erreur création {ep} ({bval})")
                continue
            print(f"➕ Création {ep} ({bval}) OK")


def restore_step2_links(data, token, debug=False):
    """
    Création des liens en se basant sur les clés fonctionnelles.
    - measures <-> controls
    - éventuellement measures.attributes (si utilisé)
    On reconstruit les id réels à partir des clés fonctionnelles.
    """
    print("\n=== PASS 2 : Création des liens ===")

    # Rebuild maps depuis la base (après step1)
    attr_map = build_business_map_from_api("attributes", token, debug=debug)
    dom_map = build_business_map_from_api("domains", token, debug=debug)
    meas_map = build_business_map_from_api("measures", token, debug=debug)
    ctrl_map = build_business_map_from_api("controls", token, debug=debug)

    # 1) Liaisons measures -> controls (pivot)
    if "measures" in data:
        print("\n🔗 Liaisons measures → controls")
        for m in data["measures"]:
            if not isinstance(m, dict):
                continue
            clause = m.get("clause")
            if not clause:
                continue
            real_measure_id = meas_map.get(clause)
            if not real_measure_id:
                print(f"⚠️ Measure introuvable en base pour clause={clause}, on saute.")
                continue

            # Dans le JSON, on a controls: [id1, id2, ...] (ids du dump)
            # On doit les traduire en noms, puis en ids réels.
            original_controls_ids = m.get("controls") or []
            if not original_controls_ids:
                continue

            # Construire map id_dump -> name pour controls à partir du JSON
            dump_ctrl_id_to_name = {}
            for c in data.get("controls", []):
                if isinstance(c, dict) and "id" in c and "name" in c:
                    dump_ctrl_id_to_name[c["id"]] = c["name"]

            real_control_ids = []
            for cid in original_controls_ids:
                cname = dump_ctrl_id_to_name.get(cid)
                if not cname:
                    print(f"⚠️ Control id={cid} introuvable dans le dump, pour measure {clause}")
                    continue
                real_cid = ctrl_map.get(cname)
                if not real_cid:
                    print(f"⚠️ Control name={cname} introuvable en base, pour measure {clause}")
                    continue
                real_control_ids.append(real_cid)

            if not real_control_ids:
                continue

            # On envoie un PUT sur /measures/{id} avec uniquement le champ controls
            payload = {"controls": real_control_ids}
            endpoint = f"measures/{real_measure_id}"
            updated, rc = curl_put(endpoint, token, payload, debug=debug)
            if rc != 0:
                print(f"❌ Erreur liaison controls pour measure {clause}")
            else:
                print(f"✅ Liaisons controls mises à jour pour measure {clause}")

    # 2) Liaisons controls → measures (optionnel si déjà géré par 1)
    # Si Deming gère le pivot dans les deux sens via le même champ, on peut s'arrêter là.
    # Sinon, on peut faire l'inverse de manière similaire en se basant sur controls[].measures.


def main():
    parser = argparse.ArgumentParser(description="Restore Deming backup (B)")
    parser.add_argument("--file", required=True, help="Fichier JSON de backup")
    parser.add_argument("--debug", action="store_true", help="Affiche les commandes curl complètes")
    parser.add_argument("--step1-only", action="store_true", help="Ne faire que la création des objets sans liens")
    parser.add_argument("--bypass-step1", action="store_true", help="Ne faire que les liens (pass 2)")
    args = parser.parse_args()

    if args.step1_only and args.bypass_step1:
        print("❌ --step1-only et --bypass-step1 sont incompatibles.")
        sys.exit(1)

    # Chargement du fichier
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Erreur lecture fichier {args.file}: {e}")
        sys.exit(1)

    print("🔑 Authentification...")
    token = get_token(debug=args.debug)

    if not args.bypass_step1:
        restore_step1(data, token, debug=args.debug)

    if args.step1_only:
        print("\n⏹️  Arrêt après PASS 1 (--step1-only).")
        return

    restore_step2_links(data, token, debug=args.debug)
    print("\n✨ Restore terminé.")

if __name__ == "__main__":
    main()
