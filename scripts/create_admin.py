import sys
import os
import argparse
import getpass
import hmac

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.db import SessionLocal
from src.db.models import Admin
from src.core.security import get_password_hash

def create_admin(username, password):
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.username == username).first()
        if existing:
            print(f"L'amministratore '{username}' esiste già.")
            return

        hashed_password = get_password_hash(password)
        new_admin = Admin(username=username, hashed_password=hashed_password)
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        print(f"Amministratore '{username}' creato con successo! (ID: {new_admin.id})")
    except Exception as e:
        print(f"Errore durante la creazione: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crea un account amministratore per Hermes.")
    parser.add_argument("username", help="L'username per l'amministratore")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Conferma password: ")

    if len(password) < 8:
        parser.error("La password deve contenere almeno 8 caratteri.")
    if not hmac.compare_digest(password, confirmation):
        parser.error("Le password non coincidono.")

    create_admin(args.username, password)
