from flask import Flask, render_template, url_for, flash, request, send_from_directory
from mysql_db import MySQL
import mysql.connector
import nh3
import os
import hashlib

app = Flask(__name__)

application = app

app.config.from_pyfile('config.py')

db = MySQL(app)


@app.route('/')
def index():
    query = '''SELECT Albums.name as name, Albums.description as description, Skin.mime as mime, Skin.md5 as md5 FROM Albums
                LEFT JOIN Skin ON Albums.skin = Skin.id
            '''

    values = []
    try:

        if db.connection() is None:
            print("Ошибка: соединение с базой данных не установлено.")
            flash('Ошибка соединения с базой данных', 'danger')

        cursor = db.connection().cursor()
        print("Соединение с базой данных установлено.")
        cursor.execute(query)
        values = cursor.fetchall()
        print(values)
        cursor.close()
    except Exception as e:
        flash(f'При создании страницы произошла ошибка: {str(e)}', 'danger')

    return render_template('index.html', values=values)



@app.route('/get_image', methods=['GET'])
def get_image():
    md5 = request.args.get('md5')
    mime = request.args.get('mime')

    # Проверка на наличие параметров
    if not md5 or not mime:
        print("Отсутствует md5 или mime", 400)   # Возврат ошибки 400 Bad Request

    print(f"md5: {md5}, mime: {mime}")  # Логирование значений

    # Проверка на корректность MIME типа
    if mime and '/' in mime:
        filename = f"{md5}.{mime.split('/')[1]}"
    else:
        # Логирование ошибки или установка значения по умолчанию
        print(f"Ошибка: некорректный MIME тип: '{mime}' для md5: '{md5}'")
        return "Некорректный MIME тип", 400  # Возврат ошибки 400 Bad Request

    return send_from_directory('images', filename)



# Пример кода для создания элемента
@app.route('/create_item', methods=['POST', 'GET'])
def create_item():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        description = nh3.clean(description)
        userfile = request.files['userfile']

        errors = validate(name, description, userfile)
        if len(errors.keys()) > 0:
            return render_template('create_item.html', **errors)

        md5_hash = hashlib.md5(userfile.read()).hexdigest()
        mime_type = userfile.mimetype
        name_f = f"{md5_hash}.{mime_type.split('/')[1]}"

        try:
            query = '''
                SELECT id FROM Skin WHERE md5 = %s
            '''

            cursor = db.connection().cursor()  # Обычный курсор
            cursor.execute(query, (md5_hash,))
            skin = cursor.fetchone()
            cursor.close()

            skin_id = skin[0] if skin else None  # Извлечение id из кортежа

            if not skin_id:
                query = '''
                INSERT INTO Skin (md5, mime, name) VALUES (%s, %s, %s)
                '''
                cursor = db.connection().cursor()
                cursor.execute(query, (md5_hash, mime_type, name_f))
                db.connection().commit()
                cursor.close()

                cursor = db.connection().cursor()
                cursor.execute(query, (md5_hash,))
                skin = cursor.fetchone()
                cursor.close()

                skin_id = skin[0] if skin else None  # Извлечение id из кортежа

                userfile.seek(0)

                if not os.path.exists('images'):
                    os.makedirs('images')

                userfile.save(os.path.join('images', name_f))
                flash(f'Обложка {skin_id} успешно создана.', 'success')
        except mysql.connector.errors.DatabaseError:
            db.connection().rollback()
            flash(f'При создании обложки произошла ошибка.', 'danger')
            return render_template('create_item.html')

        try:
            query = '''
                INSERT INTO Albums (name, description, skin)
                VALUES (%s, %s, %s)
            '''
            cursor = db.connection().cursor()
            cursor.execute(query, (name, description, skin_id))
            db.connection().commit()
            cursor.close()

            query = '''
                SELECT id FROM Albums ORDER BY id DESC LIMIT 1
            '''
            cursor = db.connection().cursor()
            cursor.execute(query)
            item = cursor.fetchone()
            cursor.close()
            flash(f'Товар {item[0]} успешно создан.', 'success')  # Извлечение id из кортежа
        except mysql.connector.errors.DatabaseError:
            db.connection().rollback()
            flash(f'При создании товара произошла ошибка.', 'danger')
            return render_template('create_item.html')

    return render_template('create_item.html')


def validate(name, description, userfile):
    errors = {}
    if not name:
        errors['name_message'] = "Название не может быть пустым"
    if not description:
        errors['description_message'] = "Описание не может быть пустым"
    if not userfile:
        errors['userfile_message'] = "Обложка не может быть пустой"

    return errors

if __name__ == '__main__':
    app.run(debug=True)