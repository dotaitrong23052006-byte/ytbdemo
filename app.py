from flask import Flask, request, send_file, after_this_request, render_template, jsonify
from flask_cors import CORS
import yt_dlp
import os
import uuid
import re

app = Flask(__name__, template_folder='templates')
CORS(app)

app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Giới hạn 50MB

def sanitize_filename(filename):
    """Làm sạch tên file để loại bỏ ký tự không hợp lệ"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def download_media(url, format_type):
    try:
        if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
            os.makedirs(app.config['DOWNLOAD_FOLDER'])

        file_id = str(uuid.uuid4())
        output_template = os.path.join(app.config['DOWNLOAD_FOLDER'], f'{file_id}.%(ext)s')

        ydl_opts = {
            'outtmpl': output_template,
            'quiet': False,  # Hiển thị thông tin để debug
            'no_warnings': False,
        }

        if format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Kiểm tra URL trước khi tải
            info = ydl.extract_info(url, download=False)  # First get info without downloading
            print(f"Thông tin video: {info.get('title', 'Không có tiêu đề')}")
            
            # Now download
            ydl.download([url])
            
            # Get the actual filename
            filename = ydl.prepare_filename(info)
            
            # For MP3, find the actual file created
            if format_type == 'mp3':
                base_path = os.path.splitext(filename)[0]
                final_filename = base_path + '.mp3'
                
                # Check if the MP3 file actually exists
                if not os.path.exists(final_filename):
                    # Try to find any audio file that was created
                    for ext in ['.mp3', '.m4a', '.webm']:
                        possible_file = base_path + ext
                        if os.path.exists(possible_file):
                            final_filename = possible_file
                            break
                
                if not os.path.exists(final_filename):
                    return None, "Không thể tạo file MP3. Có thể FFmpeg chưa được cài đặt."
            else:
                final_filename = filename

            return final_filename, info.get('title', 'download')

    except Exception as e:
        print(f"Lỗi chi tiết: {str(e)}")
        return None, str(e)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download', methods=['GET'])
def download():
    url = request.args.get('url')
    format_type = request.args.get('format', 'mp4')
    
    # Debug: in ra các tham số nhận được
    print(f"URL nhận được: {url}")
    print(f"Format nhận được: {format_type}")

    if not url:
        return jsonify({'error': 'URL là bắt buộc'}), 400

    # Kiểm tra định dạng
    if format_type not in ['mp4', 'mp3']:
        return jsonify({'error': 'Định dạng không hợp lệ. Chỉ chấp nhận mp4 hoặc mp3'}), 400

    filepath, result = download_media(url, format_type)

    if not filepath:
        return jsonify({'error': f'Lỗi khi tải: {result}'}), 500

    # Kiểm tra file tồn tại
    if not os.path.exists(filepath):
        return jsonify({'error': 'File tải về không tồn tại'}), 500

    filename = os.path.basename(filepath)
    clean_filename = sanitize_filename(result) + os.path.splitext(filename)[1]

    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Lỗi khi xóa file: {e}")
        return response

    return send_file(filepath, as_attachment=True, download_name=clean_filename)


if __name__ == '__main__':
    # Kiểm tra xem FFmpeg có sẵn không
    try:
        os.system('ffmpeg -version')
        print("FFmpeg đã được cài đặt")
    except:
        print("Cảnh báo: FFmpeg có thể chưa được cài đặt. Cần FFmpeg để chuyển đổi sang MP3.")
    
    import os

port = int(os.environ.get("PORT", 10000))  # Render cung cấp PORT qua biến môi trường

app.run(debug=False, host='0.0.0.0', port=port)
