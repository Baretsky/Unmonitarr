#!/usr/bin/env python3
"""
Script de diagnostic pour identifier le problème de base de données
"""
import os
import sqlite3
import stat
import pwd
import grp
from pathlib import Path

def debug_database_issue():
    """Diagnostic complet du problème de base de données"""
    
    print("=" * 60)
    print("🔍 DIAGNOSTIC COMPLET DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    # 1. Informations sur l'utilisateur actuel
    try:
        uid = os.getuid()
        gid = os.getgid()
        user_info = pwd.getpwuid(uid)
        group_info = grp.getgrgid(gid)
        print(f"👤 Utilisateur: {user_info.pw_name} (uid:{uid}, gid:{gid})")
        print(f"👥 Groupe: {group_info.gr_name}")
    except Exception as e:
        print(f"❌ Erreur lecture utilisateur: {e}")
    
    # 2. Répertoire de travail actuel
    print(f"📂 Répertoire de travail: {os.getcwd()}")
    
    # 3. Variables d'environnement pertinentes
    print(f"🌐 DATABASE_URL: {os.getenv('DATABASE_URL', 'NON DÉFINIE')}")
    
    # 4. Vérification des répertoires
    directories_to_check = ['/app', '/app/data', '/app/config']
    
    for dir_path in directories_to_check:
        print(f"\n📁 Analyse de {dir_path}:")
        if os.path.exists(dir_path):
            try:
                dir_stat = os.stat(dir_path)
                print(f"  ✅ Existe")
                print(f"  📊 Permissions: {stat.filemode(dir_stat.st_mode)}")
                print(f"  👤 Propriétaire: {dir_stat.st_uid}:{dir_stat.st_gid}")
                print(f"  ✅ Lecture: {os.access(dir_path, os.R_OK)}")
                print(f"  ✅ Écriture: {os.access(dir_path, os.W_OK)}")
                print(f"  ✅ Exécution: {os.access(dir_path, os.X_OK)}")
                
                # Contenu du répertoire
                try:
                    contents = os.listdir(dir_path)
                    print(f"  📋 Contenu: {contents}")
                except Exception as e:
                    print(f"  ❌ Impossible de lister: {e}")
                    
            except Exception as e:
                print(f"  ❌ Erreur stat: {e}")
        else:
            print(f"  ❌ N'existe pas")
            
            # Tentative de création
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"  ✅ Création réussie")
            except Exception as e:
                print(f"  ❌ Création échouée: {e}")
    
    # 5. Test de création de fichier SQLite
    test_db_paths = [
        "/app/data/test.db",
        "/app/test.db", 
        "/tmp/test.db"
    ]
    
    for db_path in test_db_paths:
        print(f"\n🧪 Test création SQLite: {db_path}")
        try:
            # Assurer que le répertoire parent existe
            parent_dir = os.path.dirname(db_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                
            # Test de création de fichier simple
            with open(db_path, 'w') as f:
                f.write("")
            print(f"  ✅ Création fichier réussie")
            
            # Test de connexion SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER)")
            cursor.execute("INSERT INTO test VALUES (1)")
            conn.commit()
            conn.close()
            print(f"  ✅ Connexion SQLite réussie")
            
            # Nettoyage
            os.remove(db_path)
            print(f"  ✅ Nettoyage réussi")
            
        except Exception as e:
            print(f"  ❌ Échec: {e}")
    
    # 6. Test avec les chemins exacts de l'application
    database_urls = [
        "sqlite:///app/data/unmonitarr.db",
        "sqlite:////app/data/unmonitarr.db"
    ]
    
    for db_url in database_urls:
        print(f"\n🎯 Test URL spécifique: {db_url}")
        
        if db_url.startswith("sqlite:////"):
            db_path = db_url.replace("sqlite:////", "/")
        elif db_url.startswith("sqlite:///"):
            relative_path = db_url.replace("sqlite:///", "")
            if relative_path.startswith("/"):
                db_path = relative_path
            else:
                db_path = f"/{relative_path}"
        
        print(f"  📁 Chemin calculé: {db_path}")
        db_dir = os.path.dirname(db_path)
        print(f"  📁 Répertoire: {db_dir}")
        
        try:
            # Création du répertoire
            os.makedirs(db_dir, exist_ok=True)
            
            # Test SQLite
            conn = sqlite3.connect(db_path)
            conn.close()
            print(f"  ✅ Test réussi")
            
            # Nettoyage
            if os.path.exists(db_path):
                os.remove(db_path)
                
        except Exception as e:
            print(f"  ❌ Test échoué: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 FIN DU DIAGNOSTIC")
    print("=" * 60)

if __name__ == "__main__":
    debug_database_issue()