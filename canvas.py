from tkinter import *
WIDTH=600
HEIGHT=400

root = Tk()
root.title("CS101")

canvas = Canvas(root, width=WIDTH, height=HEIGHT)
canvas.pack()

a = canvas.create_rectangle(30, 40, 550, 160, fill='red', outline='red')
print(canvas.coords(a))

root.mainloop()