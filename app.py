import os
import sqlite3
import json
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_FILE = 'repertorio.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS canciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            genero TEXT NOT NULL,
            titulo TEXT NOT NULL,
            tonalidad TEXT,
            carpeta TEXT,
            letra TEXT,
            secciones TEXT,
            en_setlist INTEGER DEFAULT 0,
            orden_setlist INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/canciones', methods=['GET'])
def get_canciones():
    conn = get_db_connection()
    canciones = conn.execute('SELECT * FROM canciones').fetchall()
    conn.close()
    
    result = []
    for c in canciones:
        result.append({
            'id': c['id'],
            'genero': c['genero'],
            'titulo': c['titulo'],
            'tonalidad': c['tonalidad'],
            'carpeta': c['carpeta'],
            'letra': c['letra'],
            'secciones': json.loads(c['secciones']) if c['secciones'] else {"vientos":[], "percusion":[], "armonia":[]},
            'enSetlist': bool(c['en_setlist'])
        })
    return jsonify(result)

@app.route('/api/canciones', methods=['POST'])
def add_cancion():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    secciones = json.dumps(data.get('secciones', {"vientos":[], "percusion":[], "armonia":[]}))
    
    cursor.execute('''
        INSERT INTO canciones (genero, titulo, tonalidad, carpeta, letra, secciones, en_setlist, orden_setlist)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('genero', ''),
        data.get('titulo', ''),
        data.get('tonalidad', ''),
        data.get('carpeta', ''),
        data.get('letra', ''),
        secciones,
        1 if data.get('enSetlist') else 0,
        0
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    
    data['id'] = new_id
    return jsonify(data), 201

@app.route('/api/canciones/<int:id>', methods=['PUT'])
def update_cancion(id):
    data = request.json
    conn = get_db_connection()
    
    secciones = json.dumps(data.get('secciones', {"vientos":[], "percusion":[], "armonia":[]}))
    
    conn.execute('''
        UPDATE canciones 
        SET genero = ?, titulo = ?, tonalidad = ?, carpeta = ?, letra = ?, secciones = ?, en_setlist = ?
        WHERE id = ?
    ''', (
        data.get('genero', ''),
        data.get('titulo', ''),
        data.get('tonalidad', ''),
        data.get('carpeta', ''),
        data.get('letra', ''),
        secciones,
        1 if data.get('enSetlist') else 0,
        id
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/canciones/<int:id>', methods=['DELETE'])
def delete_cancion(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM canciones WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/setlist', methods=['GET'])
def get_setlist():
    conn = get_db_connection()
    canciones = conn.execute('SELECT * FROM canciones WHERE en_setlist = 1 ORDER BY orden_setlist ASC').fetchall()
    conn.close()
    
    result = []
    for c in canciones:
        result.append({
            'id': c['id'],
            'genero': c['genero'],
            'titulo': c['titulo'],
            'tonalidad': c['tonalidad'],
            'carpeta': c['carpeta'],
            'letra': c['letra'],
            'secciones': json.loads(c['secciones']) if c['secciones'] else {"vientos":[], "percusion":[], "armonia":[]},
            'enSetlist': True
        })
    return jsonify(result)

@app.route('/api/setlist', methods=['PUT'])
def update_setlist():
    setlist = request.json # Expecting an array of objects in new order
    conn = get_db_connection()
    
    # First, mark all as not in setlist
    conn.execute('UPDATE canciones SET en_setlist = 0, orden_setlist = 0')
    
    # Then update the ones in the new setlist
    for index, cancion in enumerate(setlist):
        conn.execute('UPDATE canciones SET en_setlist = 1, orden_setlist = ? WHERE id = ?', (index, cancion['id']))
        
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/publicar', methods=['POST'])
def publicar_github():
    try:
        # 1. Obtener el setlist activo
        conn = get_db_connection()
        canciones = conn.execute('SELECT * FROM canciones WHERE en_setlist = 1 ORDER BY orden_setlist ASC').fetchall()
        conn.close()
        
        setlist = []
        for c in canciones:
            setlist.append({
                'id': c['id'],
                'genero': c['genero'],
                'titulo': c['titulo'],
                'tonalidad': c['tonalidad'],
                'carpeta': c['carpeta'],
                'letra': c['letra'],
                'secciones': json.loads(c['secciones']) if c['secciones'] else {"vientos":[], "percusion":[], "armonia":[]}
            })
            
        # 2. Guardar en setlist_publico.json
        with open('setlist_publico.json', 'w', encoding='utf-8') as f:
            json.dump(setlist, f, ensure_ascii=False, indent=2)
            
        # 3. Comandos de Git
        # Añadir setlist y carpeta ARCHIVOS (incluyendo subcarpetas y pdfs)
        subprocess.run(['git', 'add', 'setlist_publico.json'], check=True)
        # Usamos try/except para el add ARCHIVOS/ por si no existe aún
        if os.path.exists('ARCHIVOS'):
            subprocess.run(['git', 'add', 'ARCHIVOS/'], check=True)
            
        # Verificar si hay cambios antes de hacer commit
        status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not status.stdout.strip():
            return jsonify({'success': True, 'message': 'Ya está todo actualizado. No hay cambios nuevos.'})
            
        subprocess.run(['git', 'commit', '-m', 'Publicación automática de setlist y partituras'], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True) # Asume que la rama es main
        
        return jsonify({'success': True, 'message': '¡Publicado con éxito en GitHub Pages!'})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'message': f'Error de Git: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
