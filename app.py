import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage
import mysql.connector

app = Flask(__name__)

# SỬA CORS: Mở cửa cho tất cả, giao toàn quyền cho thư viện tự xử lý
CORS(app, resources={r"/*": {"origins": "*"}})

# ===== CONFIG =====
DB_HOST = '34.158.45.10'
DB_USER = 'db_user'
DB_PASS = '123456Ab!'
DB_NAME = 'uth_documents'

BUCKET_NAME = 'doc-share'

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/secrets/key.json'
storage_client = storage.Client()

# ===== DB CONNECTION =====
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )

# ĐÃ XÓA HÀM @app.after_request VÌ KHÔNG CÒN CẦN THIẾT NỮA

# ===== DOCUMENTS =====
@app.route('/documents', methods=['GET'])
def get_documents():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM documents ORDER BY upload_date DESC")
        result = cursor.fetchall()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== UPLOAD =====
# ĐÃ BỎ 'OPTIONS' RA KHỎI methods
@app.route('/upload', methods=['POST'])
def upload_file():
    conn = None
    try:
        file = request.files.get('file')
        subject_name = request.form.get('subject_name')
        uploader_name = request.form.get('uploader_name')

        if not file:
            return jsonify({'error': 'No file uploaded'}), 400

        # Upload GCS
        blob = storage_client.bucket(BUCKET_NAME).blob(file.filename)
        blob.upload_from_string(file.read(), content_type=file.content_type)
        file_url = blob.public_url

        # Save DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (file_name, file_url, subject_name, uploader_name)
            VALUES (%s, %s, %s, %s)
        """, (file.filename, file_url, subject_name, uploader_name))
        conn.commit()

        return jsonify({'message': 'Tải lên thành công', 'file_url': file_url})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== DELETE =====
@app.route('/delete/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT file_url FROM documents WHERE id = %s", (doc_id,))
        res = cursor.fetchone()

        if not res:
            return jsonify({'error': 'Không tìm thấy tài liệu'}), 404

        file_url = res[0]
        file_name = file_url.split('/')[-1]

        # Delete GCS
        blob = storage_client.bucket(BUCKET_NAME).blob(file_name)
        if blob.exists():
            blob.delete()

        # Delete DB
        cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        conn.commit()
        return jsonify({'message': 'Đã xóa thành công'})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== SUBJECTS =====
@app.route('/subjects', methods=['GET'])
def get_subjects():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subject_code, subject_name FROM subjects ORDER BY subject_name")
        res = cursor.fetchall()

        subjects = [{'code': r[0], 'name': r[1]} for r in res]
        return jsonify(subjects)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== COMMENTS =====
@app.route('/comments/<int:doc_id>', methods=['GET'])
def get_comments(doc_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_name, content, created_at
            FROM comments
            WHERE doc_id = %s
            ORDER BY created_at DESC
        """, (doc_id,))
        res = cursor.fetchall()

        comments = [{
            'user': r[0],
            'content': r[1],
            'date': r[2].strftime('%d/%m/%Y %H:%M')
        } for r in res]
        return jsonify(comments)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== ADD COMMENT =====
@app.route('/comments/add', methods=['POST'])
def add_comment():
    conn = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO comments (doc_id, user_name, user_email, content)
            VALUES (%s, %s, %s, %s)
        """, (
            data.get('doc_id'),
            data.get('user_name'),
            data.get('user_email'),
            data.get('content')
        ))
        conn.commit()
        return jsonify({'message': 'Đã gửi bình luận!'})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== DOWNLOAD HIT =====
@app.route('/download-hit/<int:doc_id>', methods=['POST'])
def download_hit(doc_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE documents 
            SET download_count = COALESCE(download_count, 0) + 1 
            WHERE id = %s
        """, (doc_id,))
        conn.commit()
        return jsonify({'message': 'Đã cập nhật lượt tải'})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ===== RUN =====
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)