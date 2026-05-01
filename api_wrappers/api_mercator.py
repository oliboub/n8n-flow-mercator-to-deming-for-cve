import os
import subprocess
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# ============================================================================
# CONFIGURATION DES CHEMINS 
# ============================================================================

API_DIR = os.path.dirname(__file__)
# Racine du projet (on remonte d'un niveau par rapport au dossier de l'API)
SCRIPTS_ROOT_DIR = os.path.abspath(os.path.join(API_DIR, "..")) 

# Chemin vers l'exécutable python du venv
VENV_PYTHON = os.path.join(SCRIPTS_ROOT_DIR, ".venv", "bin", "python3")

# Chemin vers le script spécialisé dans la sauvegarde
SAVE_SCRIPT_PATH = os.path.join(
    SCRIPTS_ROOT_DIR, 
    "python_scripts", 
    "sauve_json_v300.py" 
) 

# ============================================================================
# INITIALISATION DE L'API
# ============================================================================

app = FastAPI(
    title="Mercator Save API",
    description="API restreinte à la sauvegarde de fichiers JSON.",
    version="1.0.0"
)

# ============================================================================
# ENDPOINT DE SAUVEGARDE
# ============================================================================

@app.post("/v3/sauve-json", tags=["Sauvegarde"])
async def save_json(request: Request):
    """
    Lance le script save_json_v300.py en passant le corps de la requête
    et les métadonnées (directory, filename) via les Headers.
    """
    # 1. Extraction des métadonnées depuis les En-têtes HTTP
    headers = request.headers
    directory = headers.get("directory")
    filename = headers.get("filename")
    mode = headers.get("mode", "save") 

    if not directory or not filename:
        raise HTTPException(
            status_code=400, 
            detail="Headers manquants : 'directory' et 'filename' sont obligatoires."
        )
        
    # 2. Lecture du corps (Contenu JSON brut)
    try:
        raw_body_bytes = await request.body()
        raw_json_content = raw_body_bytes.decode('utf-8')
        
        if not raw_json_content.strip():
             raise ValueError("Le corps de la requête est vide.")
             
        # Vérification rapide de la validité JSON
        json.loads(raw_json_content) 

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Le corps n'est pas un JSON valide.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de lecture : {str(e)}")

    if not os.path.exists(SAVE_SCRIPT_PATH):
        raise HTTPException(status_code=500, detail="Script de sauvegarde introuvable sur le serveur.")

    # 3. Préparation de la commande Subprocess
    command = [
        VENV_PYTHON, 
        SAVE_SCRIPT_PATH, 
        "--json", raw_json_content,
        "--directory", directory,
        "--filename", filename,
        "--mode", mode
    ]
    
    # 4. Exécution
    try:
        result = subprocess.run(
            command,
            cwd=SCRIPTS_ROOT_DIR, 
            check=True, 
            capture_output=True,
            text=True
        )
        
        try:
            script_output = json.loads(result.stdout)
        except json.JSONDecodeError:
             script_output = {"success": False, "stdout": result.stdout}

        return {
            "status": "success" if script_output.get("success") else "failure",
            "details": script_output,
            "stderr": result.stderr
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Erreur script externe : {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne API : {str(e)}")