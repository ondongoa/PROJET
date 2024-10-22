from flask import Flask, render_template, redirect, url_for, request, flash
import mysql.connector
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import json
from flask import jsonify, send_file
import os

# Initialize the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  

# Initialize the Login Manager and Bcrypt
login_manager = LoginManager(app)
bcrypt = Bcrypt(app)
login_manager.login_view = 'login'

# Connexion à la base de données
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="", 
        database="cave"  
    )

# User model
class Utilisateur(UserMixin):
    def __init__(self, pseudo_utilisateur, nom_utilisateur, prenom_utilisateur, email_utilisateur):
        self.pseudo_utilisateur = pseudo_utilisateur
        self.nom_utilisateur = nom_utilisateur
        self.prenom_utilisateur = prenom_utilisateur
        self.email_utilisateur = email_utilisateur
    
    def get_id(self):
        return self.pseudo_utilisateur 

@login_manager.user_loader
def load_user(pseudo_utilisateur):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT pseudo_utilisateur, nom_utilisateur, prenom_utilisateur, email_utilisateur FROM UTILISATEUR WHERE pseudo_utilisateur = %s", (pseudo_utilisateur,))
    user_data = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if user_data:
        return Utilisateur(*user_data)
    return None

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pseudo = request.form['pseudo_utilisateur']
        mdp = request.form['mdp_utilisateur']
        
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT mdp_utilisateur FROM UTILISATEUR WHERE pseudo_utilisateur = %s", (pseudo,))
        user_data = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if user_data and bcrypt.check_password_hash(user_data[0], mdp):
            login_user(Utilisateur(pseudo, '', '', ''))
            return redirect(url_for('dashboard'))
        else:
            flash('ID invalid')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        pseudo = request.form['pseudo_utilisateur']
        mdp = request.form['mdp_utilisateur']
        nom = request.form['nom_utilisateur']
        prenom = request.form['prenom_utilisateur']
        email = request.form['email_utilisateur']

        hashed_password = bcrypt.generate_password_hash(mdp).decode('utf-8')

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO UTILISATEUR (pseudo_utilisateur, mdp_utilisateur, nom_utilisateur, prenom_utilisateur, email_utilisateur) VALUES (%s, %s, %s, %s, %s)",
                           (pseudo, hashed_password, nom, prenom, email))
            connection.commit()
            flash('Inscription successful!')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Inscription failed: ' + str(e))
        finally:
            cursor.close()
            connection.close()

    return render_template('register.html')

@app.route('/compte', methods=['GET', 'POST'])
@login_required
def compte():
    if request.method == 'POST':
        if 'nouveau_mdp' in request.form:  # Changement de mot de passe
            mot_de_passe_actuel = request.form['mot_de_passe_actuel']
            nouveau_mdp = request.form['nouveau_mdp']
            
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT mdp_utilisateur FROM UTILISATEUR WHERE pseudo_utilisateur = %s", (current_user.pseudo,))
            user_data = cursor.fetchone()
            
            if user_data and bcrypt.check_password_hash(user_data[0], mot_de_passe_actuel):
                hashed_password = bcrypt.generate_password_hash(nouveau_mdp).decode('utf-8')
                cursor.execute("UPDATE UTILISATEUR SET mdp_utilisateur = %s WHERE pseudo_utilisateur = %s", (hashed_password, current_user.pseudo))
                connection.commit()
                flash('Mot de passe modifié avec succès.')
            else:
                flash('Le mot de passe actuel est incorrect.')
            cursor.close()
            connection.close()
        
        elif 'supprimer_compte' in request.form:  # Suppression de compte
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM UTILISATEUR WHERE pseudo_utilisateur = %s", (current_user.pseudo,))
            connection.commit()
            cursor.close()
            connection.close()
            
            logout_user()
            flash('Compte supprimé avec succès.')
            return redirect(url_for('register'))

    return render_template('compte.html')

@app.route('/dashboard')
@login_required
def dashboard():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM CAVE WHERE pseudo_utilisateur = %s", (current_user.pseudo_utilisateur,))
    caves = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('dashboard.html', caves=caves)

@app.route('/add_cave', methods=['POST'])
@login_required
def add_cave():
    cave_name = request.form['cave_name']
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Insérer la nouvelle cave
        cursor.execute("INSERT INTO CAVE (nom, pseudo_utilisateur) VALUES (%s, %s)", (cave_name, current_user.pseudo_utilisateur))
        connection.commit()

        # Récupérer l'id de la cave nouvellement créée
        cave_id = cursor.lastrowid

        # Créer automatiquement 5 étagères avec 3 emplacements chacune pour la nouvelle cave
        for numero_etagere in range(1, 6):  # 5 étagères
            cursor.execute(
                "INSERT INTO ETAGERE (numero_etagere, nbre_emplacement, nbre_bouteilles, id_cave) VALUES (%s, %s, %s, %s)",
                (numero_etagere, 3, 0, cave_id)  # 3 emplacements et 0 bouteilles initialement
            )

        # Commit pour enregistrer les étagères
        connection.commit()

        flash('etagere OK!')

    except Exception as e:
        connection.rollback()
        flash(f'erreur lors de la creation de l etagere: {e}')

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('dashboard'))


@app.route('/cellar/<int:cave_id>', methods=['GET', 'POST'])
@login_required
def cellar(cave_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        # Adding a new bottle with wine
        if 'add_bottle' in request.form:
            id_vin = request.form['id_vin']
            nom_emplacement_bouteille = request.form['nom_emplacement_bouteille']
            quantite_bouteille = request.form['quantite_bouteille']
            cursor.execute("INSERT INTO BOUTEILLE (nom_emplacement_bouteille, quantite_bouteille, id_cave, id_vin) VALUES (%s, %s, %s, %s)",
                           (nom_emplacement_bouteille, quantite_bouteille, cave_id, id_vin))
            connection.commit()

        # Deleting a bottle
        elif 'delete_bottle' in request.form:
            bottle_id = request.form['bottle_id']
            cursor.execute("DELETE FROM BOUTEILLE WHERE id_bouteille = %s", (bottle_id,))
            connection.commit()

        # Adding a comment and rating for a wine
        elif 'add_comment' in request.form:
            id_vin = request.form['id_vin']
            # flash(f'le id est : {id_vin}')
            # print("id_vin:", id_vin)
            commentaire = request.form['commentaire']
            note_commentaire = request.form['note_commentaire']
            pseudo_utilisateur = current_user.pseudo_utilisateur
            print("id_vin:", id_vin)# Assuming the current user's pseudo is accessible
            cursor.execute("""
                INSERT INTO COMMENTAIRE (commentaire, note_commentaire, pseudo_utilisateur, id_vin)
                VALUES (%s, %s, %s, %s)
            """, (commentaire, note_commentaire, pseudo_utilisateur, id_vin))
            connection.commit()
            # # Debugging step
            
            # Update the global rating for the wine
            cursor.execute("""
                UPDATE VIN
                SET note_globale_vin = (
                    SELECT AVG(note_commentaire)
                    FROM COMMENTAIRE
                    WHERE id_vin = %s
                )
                WHERE id_vin = %s
            """, (id_vin, id_vin))
            connection.commit()

    # Retrieve shelves and bottles
    cursor.execute("SELECT * FROM ETAGERE WHERE id_cave = %s", (cave_id,))
    etageres = cursor.fetchall()

    # Fetch all wines
    cursor.execute("SELECT * FROM VIN")
    vins = cursor.fetchall()

    # Fetch bottles per shelf
    bouteilles_par_etagere = {}
    for etagere in etageres:
        cursor.execute("""
            SELECT b.id_bouteille, b.nom_emplacement_bouteille, b.quantite_bouteille, v.id_vin, v.nom_vin, v.note_globale_vin
            FROM BOUTEILLE b
            JOIN VIN v ON b.id_vin = v.id_vin
            WHERE b.id_cave = %s AND b.nom_emplacement_bouteille = %s
        """, (cave_id, etagere[1]))
        bouteilles_par_etagere[etagere[0]] = cursor.fetchall()

    # Get all comments for wines in this cave
    cursor.execute("""
        SELECT c.commentaire, c.note_commentaire, c.pseudo_utilisateur, c.date_commentaire, v.nom_vin
        FROM COMMENTAIRE c
        JOIN VIN v ON c.id_vin = v.id_vin
        WHERE v.id_cave = %s
    """, (cave_id,))
    commentaires = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('cellar.html', etageres=etageres, bouteilles_par_etagere=bouteilles_par_etagere, cave_id=cave_id, vins=vins, commentaires=commentaires)



@app.route('/add_wine', methods=['GET', 'POST'])
@login_required
def add_wine():
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        nom_vin = request.form['nom_vin']
        type_vin = request.form['type_vin']
        annee_vin = request.form['annee_vin']
        prix_vin = request.form['prix_vin']
        commentaire_vin = request.form['commentaire_vin']
        id_cave = request.form['id_cave']  # ID de la cave associée

        # Ajouter le vin à la base de données
        cursor.execute("INSERT INTO VIN (nom_vin, type_vin, annee_vin, prix_vin, commentaire_vin, id_cave) VALUES (%s, %s, %s, %s, %s, %s)",
                       (nom_vin, type_vin, annee_vin, prix_vin, commentaire_vin, id_cave))
        connection.commit()

        return redirect(url_for('dashboard'))  # Redirigez où vous voulez après l'ajout

    # Récupérer toutes les caves pour le menu déroulant
    cursor.execute("SELECT id_cave, nom FROM CAVE")
    caves = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('add_wine.html', caves=caves)



@app.route('/add_bottle/<int:cave_id>/<int:id_etagere>', methods=['GET', 'POST'])
@login_required
def add_bottle(cave_id, id_etagere):
    if request.method == 'POST':
        bottle_name = request.form['nom_vin']
        quantity = request.form['quantite_bouteille']
        location = request.form['nom_emplacement_bouteille']
        id_vin = request.form['id_vin']  # ID du vin sélectionné
        id_vin = request.form['nom_vin']  # nom du vin sélectionné
        
        connection = get_db_connection()
        cursor = connection.cursor()

        # Ajouter la bouteille à l'emplacement sur l'étagère
        cursor.execute("""
            INSERT INTO BOUTEILLE (id_cave, id_etagere, nom_emplacement_bouteille, quantite_bouteille, id_vin, nom_vin) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (cave_id, id_etagere, location, quantity, id_vin, nom_vin))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return redirect(url_for('cellar', cave_id=cave_id))

    return render_template('add_bottle.html', cave_id=cave_id, id_etagere=id_etagere, vins=vins)

@app.route('/delete_bottle/<int:bottle_id>', methods=['POST'])
@login_required
def delete_bottle(bottle_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM BOUTEILLE WHERE id_bouteille = %s", (bottle_id,))
        connection.commit()
        flash('Bouteille supprimée avec succès !')
    except Exception as e:
        flash('Erreur lors de la suppression de la bouteille: ' + str(e))
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('cellar', cave_id=current_user.cave_id))

@app.route('/evaluate_wine/<int:wine_id>', methods=['POST'])
@login_required
def evaluate_wine(wine_id):
    note = request.form['note']
    commentaire = request.form['commentaire']

    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE VIN
            SET note_perso_vin = %s, commentaire_vin = %s
            WHERE id_vin = %s
        """, (note, commentaire, wine_id))
        connection.commit()
        flash('Evaluation mise à jour avec succès !')
    except Exception as e:
        flash('Erreur lors de la mise à jour de l\'évaluation: ' + str(e))
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('bottle_list', cave_id=current_user.cave_id))  # Redirige vers la liste des bouteilles

@app.route('/wine/<int:id_vin>', methods=['GET'])
@login_required
def wine_detail(id_vin):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    
    
    # Récupérer les détails du vin
    pseudo_utilisateur = current_user.pseudo_utilisateur  # Récupérer le pseudo de l'utilisateur connecté
    cursor.execute("SELECT id_cave FROM cave WHERE pseudo_utilisateur = %s", (pseudo_utilisateur,))
    id_cave = cursor.fetchone()[0] # Supposons que l'ID de la cave est à l'index 6, à adapter si besoin
    
    cursor.execute("SELECT * FROM VIN WHERE id_vin = %s", (id_vin,))
    wine = cursor.fetchone()
    # Récupérer les commentaires et les notes pour ce vin
    cursor.execute("""
        SELECT pseudo_utilisateur, commentaire, note_commentaire 
        FROM COMMENTAIRE 
        WHERE id_vin = %s
    """, (id_vin,))
    comments = cursor.fetchall()
    
    # Calculer la note moyenne
    cursor.execute("""
        SELECT AVG(note_commentaire) 
        FROM COMMENTAIRE 
        WHERE id_vin = %s
    """, (id_vin,))
    average_rating = cursor.fetchone()[0]  # Récupérer la moyenne
    
    cursor.close()
    connection.close()

    return render_template('wine_detail.html', wine=wine, comments=comments, cave_id=id_cave, average_rating=average_rating)



@app.route('/bottles/<int:cave_id>')
@login_required
def bottle_list(cave_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Fetch bottles for the specified cave
    cursor.execute("""
        SELECT B.id_bouteille, B.nom_emplacement_bouteille, B.quantite_bouteille, V.nom_vin, V.type_vin, V.annee_vin, V.commentaire_vin, V.prix_vin
        FROM BOUTEILLE B
        JOIN VIN V ON B.id_vin = V.id_vin
        WHERE B.id_cave = %s
    """, (cave_id,))
    
    bottles = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return render_template('bottle_list.html', bottles=bottles, cave_id=cave_id)


# Route pour exporter les données de la cave en JSON
@app.route('/export_cave/<int:cave_id>', methods=['GET'])
@login_required
def export_cave(cave_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Récupérer les informations sur la cave
    cursor.execute("SELECT * FROM CAVE WHERE id_cave = %s", (cave_id,))
    cave = cursor.fetchone()

    # Récupérer les informations sur les étagères
    cursor.execute("SELECT * FROM ETAGERE WHERE id_cave = %s", (cave_id,))
    etageres = cursor.fetchall()

    # Récupérer les informations sur les bouteilles
    cursor.execute("SELECT * FROM BOUTEILLE WHERE id_cave = %s", (cave_id,))
    bouteilles = cursor.fetchall()

    cursor.close()
    connection.close()

    # Organiser les données dans un format JSON
    cave_data = {
        'cave': {
            'id_cave': cave[0],
            'nom': cave[1],
            'pseudo_utilisateur': cave[2],
            'etageres': []
        }
    }

    # Ajouter les étagères et bouteilles associées
    for etagere in etageres:
        etagere_data = {
            'id_etagere': etagere[0],
            'numero_etagere': etagere[1],
            'nbre_emplacement': etagere[2],
            'nbre_bouteilles': etagere[3],
            'bouteilles': []
        }

        # Ajouter les bouteilles associées à cette étagère
        for bouteille in bouteilles:
            if bouteille[3] == etagere[0]:  # Vérifier si la bouteille appartient à cette étagère
                bouteille_data = {
                    'id_bouteille': bouteille[0],
                    'nom_emplacement_bouteille': bouteille[1],
                    'quantite_bouteille': bouteille[2],
                    'id_vin': bouteille[4]
                }
                etagere_data['bouteilles'].append(bouteille_data)

        cave_data['cave']['etageres'].append(etagere_data)

    # Convertir les données en JSON
    json_data = json.dumps(cave_data, ensure_ascii=False, indent=4)

    # Créer un fichier temporaire pour l'exportation
    json_filename = f'cave_{cave_id}.json'
    json_filepath = os.path.join(os.getcwd(), json_filename)
    
    with open(json_filepath, 'w', encoding='utf-8') as json_file:
        json_file.write(json_data)

    # Télécharger le fichier JSON
    return send_file(json_filepath, as_attachment=True, download_name=json_filename)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host="localhost", port=5000, use_reloader=False)
