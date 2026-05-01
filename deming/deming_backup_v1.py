import requests
import json
import time

BASE_URL = "http://localhost:8030/api"
CREDENTIALS = {"email": "api@admin.localhost", "password": "12345678"}

# Liste exhaustive des points d'entrée
ENDPOINTS = [
    "attributes", "domains", "measures", "controls",
    "documents"
]

# logs et users retiré
def get_headers():
    try:
        r = requests.post(f"{BASE_URL}/login", data=CREDENTIALS)
        r.raise_for_status()
        return {
            "Authorization": f"Bearer {r.json().get('token')}",
            "Content-Type": "application/json"
        }
    except Exception as e:
        print(f"❌ Erreur lors de l'authentification : {e}")
        return None

def full_dump():
    h = get_headers()
    if not h: return
    
    dump = {}
    
    for ep in ENDPOINTS:
        print(f"📡 Analyse de l'endpoint : {ep}...")
        try:
            # 1. Premier appel pour lister les IDs
            res = requests.get(f"{BASE_URL}/{ep}", headers=h)
            
            # Gestion des erreurs (ex: 404 si l'endpoint n'existe pas encore)
            if res.status_code != 200:
                print(f"⚠️ Endpoint {ep} non disponible (Code {res.status_code})")
                continue

            data_list = res.json()
            # Mercator enveloppe souvent dans une clé 'data'
            items = data_list.get('data', []) if isinstance(data_list, dict) else data_list
            
            if not items:
                print(f"📭 Aucun objet trouvé pour {ep}.")
                dump[ep] = []
                continue

            # 2. Pour chaque item, on récupère la version détaillée par ID
            detailed_items = []
            print(f"🔍 Récupération des détails pour {len(items)} objets dans {ep}...")
            
            for item in items:
                i_id = item.get('id')
                if i_id is not None:
                    # Appel spécifique /endpoint/{id}
                    #detail_res = requests.get(f"{BASE_URL}/{ep}/{i_id}", headers=h)
                    INCLUDE_FIELDS = [ "attributes", "domains", "measures", "controls","users", "documents" ]
                    params = "include=" + ",".join(INCLUDE_FIELDS)
                    
                    time.sleep(1)
                    detail_res = requests.get(f"{BASE_URL}/{ep}/{i_id}?{params}", headers=h)
                    if detail_res.status_code == 200:
                        detail_data = detail_res.json()
                        # On garde la donnée extraite de 'data' ou l'objet racine
                        final_obj = detail_data.get('data', detail_data) if isinstance(detail_data, dict) else detail_data
                        detailed_items.append(final_obj)
                # Enrichissement spécifique pour les opérations
                if ep == "operations":
                    final_obj["actor_names"] = [a.get("name") for a in final_obj.get("actors", []) if isinstance(a, dict)]
                    final_obj["activity_names"] = [a.get("name") for a in final_obj.get("activities", []) if isinstance(a, dict)]

                    # Récupérer le nom de l'activité liée
                    activity = final_obj.get("activity")
                    if isinstance(activity, dict) and "name" in activity:
                        final_obj["activity_name"] = activity["name"]

                if ep == "processes":
                    entities = final_obj.get("entities", [])
                    final_obj["entities_names"] = [e.get("name") for e in entities if isinstance(e, dict) and "name" in e]

                    applications = final_obj.get("applications", [])
                    final_obj["application_names"] = [a.get("name") for a in applications if isinstance(a, dict) and "name" in a]

                    activities = final_obj.get("activities", [])
                    final_obj["activity_names"] = [a.get("name") for a in activities if isinstance(a, dict) and "name" in a]

                if ep == "applications":
                    activities = final_obj.get("activities", [])
                    final_obj["activity_names"] = [a.get("name") for a in activities if isinstance(a, dict) and "name" in a]

                    processes = final_obj.get("processes", [])
                    final_obj["process_names"] = [p.get("name") for p in processes if isinstance(p, dict) and "name" in p]

                    logical_servers = final_obj.get("logical_servers", [])
                    final_obj["logical_server_names"] = [ls.get("name") for ls in logical_servers if isinstance(ls, dict) and "name" in ls]

                    databases = final_obj.get("databases", [])
                    final_obj["database_names"] = [db.get("name") for db in databases if isinstance(db, dict) and "name" in db]


            # 3. On sauvegarde le résultat complet
            dump[ep] = detailed_items
            print(f"✅ {len(detailed_items)} objets sauvegardés pour {ep}.")

        except Exception as e:
            print(f"❌ Erreur critique sur {ep}: {e}")

    # Sauvegarde finale
    filename = "deming_backup_dump_v1.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=4, ensure_ascii=False)
    
    print(f"\n✨ Backup terminé ! Fichier généré : {filename}")

if __name__ == "__main__":
    full_dump()
