Akatsuki_members = ["Hac Bach Zetsu", "Deidara", "Sasori", "Hidan", "Kakuzu", "Hoshigaki Kisame", "Konan", "Uchiha Itachi", "Pain", "Uchiha Obito"]
while True:
    print("Tu gio ban la thanh vien cua Akatsuki")
    print("0. Thoat chuong trinh")
    print("1. Tim va nhap ten")
    print("2. Them thanh vien")
    command = input("Ban chon gi? ")
    if command == "0":
        break
    elif command == "1":
        name = input("Ten ban muon tim la: ")
        found = [True, False]
        for Akatsuki_member in Akatsuki_members:
            if Akatsuki_member == name:
                found = True
                break
            if found:
                print("Da tim thay danh tinh cua: ", name)
                break
            else:
                found = False
                print("Khong tim thay danh tinh cua: ", name)
    elif command == "2":
        name = input("Nhap ten thanh vien Akatsuki moi: ")
        for Akatsuki_member in Akatsuki_members:
            if Akatsuki_member == True:
                print("Da co trong danh sach")
            else:
                Akatsuki_members.append(name)
print("Ket thuc chuong trinh")

import pygame as pg
print("Hello world")