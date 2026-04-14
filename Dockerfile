# 1. Sử dụng hệ điều hành Linux siêu nhẹ có sẵn Python
FROM python:3.11-slim

# 2. Báo cho Python biết phải in log ngay lập tức để dễ gỡ lỗi
ENV PYTHONUNBUFFERED True

# 3. Tạo thư mục làm việc
WORKDIR /app

# 4. Tối ưu hóa việc cài đặt thư viện (Cài thư viện trước khi copy code)
# Cách này giúp build nhanh hơn ở những lần sau nếu bạn chỉ sửa code mà không thêm thư viện mới
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy toàn bộ mã nguồn vào (nhớ là file .gitignore sẽ chặn các file nhạy cảm)
COPY . .

# 6. (Tùy chọn) Đảm bảo thư mục /app có quyền ghi nếu app của bạn cần tạo file tạm
RUN chmod -R 777 /app

# 7. Lệnh khởi động Server chuẩn Enterprise
# Chú ý: app:app nghĩa là file app.py và biến app = Flask(__name__)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app