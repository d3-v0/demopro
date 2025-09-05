# Danh sách mẫu chứa thông tin họ tên
danh_sach = [
    {"ho_ten": "Nguyễn Văn An", "tuoi": 25, "nghe_nghiep": "Kỹ sư"},
    {"ho_ten": "Trần Thị Bình", "tuoi": 30, "nghe_nghiep": "Giáo viên"},
    {"ho_ten": "Lê Văn Cường", "tuoi": 22, "nghe_nghiep": "Sinh viên"},
    {"ho_ten": "Phạm Thị Dung", "tuoi": 28, "nghe_nghiep": "Nhân viên văn phòng"},
]

# Hàm lọc họ tên theo điều kiện
def loc_ho_ten(danh_sach, tu_khoa=None):
    ket_qua = []
    
    if tu_khoa:
        # Lọc họ tên có chứa từ khóa (không phân biệt hoa thường)
        ket_qua = [nguoi["ho_ten"] for nguoi in danh_sach 
                  if tu_khoa.lower() in nguoi["ho_ten"].lower()]
    else:
        # Lấy tất cả họ tên
        ket_qua = [nguoi["ho_ten"] for nguoi in danh_sach]
    
    return ket_qua

# Ví dụ sử dụng
print("T
