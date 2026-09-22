#!/usr/bin/env python3
import hashlib, json, os, subprocess, threading, time, tkinter as tk
from collections import defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

CHUNK_SIZE = 1024 * 1024

def human_size(n):
    v=float(n)
    for u in ('B','KB','MB','GB','TB'):
        if v < 1024 or u == 'TB': return f'{v:.2f} {u}'
        v /= 1024

def sha256_file(path):
    h=hashlib.sha256()
    try:
        with open(path,'rb') as f:
            while True:
                b=f.read(CHUNK_SIZE)
                if not b: break
                h.update(b)
        return h.hexdigest()
    except (OSError,PermissionError): return None

def collect_files(root):
    out=[]
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
        for name in files:
            p=Path(base)/name
            try:
                if not p.is_symlink() and p.is_file(): out.append((p,p.stat().st_size))
            except (OSError,PermissionError): pass
    return out

def find_duplicates(folder, progress=None, stop=None):
    files=collect_files(folder)
    if progress: progress('files',len(files),0)
    by_size=defaultdict(list)
    for p,s in files: by_size[s].append(p)
    candidates=[(p,s) for s,ps in by_size.items() if len(ps)>1 for p in ps]
    if progress: progress('candidates',len(candidates),len(files))
    by_hash=defaultdict(list)
    total=len(candidates)
    for i,(p,s) in enumerate(candidates,1):
        if stop and stop.is_set(): return {}
        h=sha256_file(p)
        if h: by_hash[(s,h)].append(p)
        if progress: progress('hash',i,total)
    return {k:v for k,v in by_hash.items() if len(v)>1}

class App:
    def __init__(self,root):
        self.root=root; root.title('Duplicate File Finder'); root.geometry('950x650'); root.minsize(780,550)
        self.folder=''; self.results={}; self.running=False; self.stop_event=threading.Event(); self.vars={}
        self.build()
    def build(self):
        ttk.Label(self.root,text='DUPLICATE FILE FINDER',font=('TkDefaultFont',20,'bold')).pack(pady=(15,3))
        ttk.Label(self.root,text='Find duplicate files using file size + SHA-256').pack(pady=(0,12))
        top=ttk.Frame(self.root); top.pack(fill='x',padx=18)
        self.folder_var=tk.StringVar(value='No folder selected')
        ttk.Entry(top,textvariable=self.folder_var,state='readonly').pack(side='left',fill='x',expand=True)
        self.browse=ttk.Button(top,text='Browse',command=self.select_folder); self.browse.pack(side='left',padx=8)
        self.scan=ttk.Button(top,text='SCAN',command=self.start_scan); self.scan.pack(side='left',padx=(0,8))
        self.stop=ttk.Button(top,text='STOP',command=self.stop_scan,state='disabled'); self.stop.pack(side='left')
        self.progress=ttk.Progressbar(self.root,mode='determinate'); self.progress.pack(fill='x',padx=18,pady=(12,5))
        self.status=tk.StringVar(value='Ready'); ttk.Label(self.root,textvariable=self.status).pack(anchor='w',padx=18)
        summary=ttk.Frame(self.root); summary.pack(fill='x',padx=18,pady=8)
        self.groups=tk.StringVar(value='Duplicate groups: 0'); self.files=tk.StringVar(value='Duplicate files: 0'); self.reclaim=tk.StringVar(value='Potentially reclaimable: 0 B')
        for v in (self.groups,self.files,self.reclaim): ttk.Label(summary,textvariable=v).pack(side='left',padx=(0,20))
        frame=ttk.Frame(self.root); frame.pack(fill='both',expand=True,padx=18,pady=5)
        self.tree=ttk.Treeview(frame,columns=('group','size','file'),show='headings',selectmode='extended')
        for c,t,w in (('group','Group',70),('size','Size',110),('file','File',680)):
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor='center' if c=='group' else 'w')
        self.tree.column('size',anchor='e'); sb=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set); self.tree.pack(side='left',fill='both',expand=True); sb.pack(side='right',fill='y')
        bottom=ttk.Frame(self.root); bottom.pack(fill='x',padx=18,pady=12)
        self.delete=ttk.Button(bottom,text='DELETE SELECTED',command=self.delete_selected,state='disabled'); self.delete.pack(side='left')
        self.open=ttk.Button(bottom,text='OPEN FOLDER',command=self.open_folder,state='disabled'); self.open.pack(side='left',padx=8)
        self.export=ttk.Button(bottom,text='EXPORT JSON',command=self.export_json,state='disabled'); self.export.pack(side='right')
    def select_folder(self):
        f=filedialog.askdirectory(title='Select folder to scan')
        if f: self.folder=f; self.folder_var.set(f); self.status.set('Folder selected. Ready to scan.')
    def start_scan(self):
        if self.running: return
        if not self.folder:
            messagebox.showwarning('Duplicate File Finder','Please select a folder first.'); return
        self.running=True; self.stop_event.clear(); self.results={}
        for x in self.tree.get_children(): self.tree.delete(x)
        for b in (self.browse,self.scan,self.delete,self.open,self.export): b.config(state='disabled')
        self.stop.config(state='normal'); self.progress['value']=0; self.status.set('Scanning files...')
        threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        try:
            r=find_duplicates(self.folder,self.progress_update,self.stop_event); self.root.after(0,lambda:self.finished(r))
        except Exception as e: self.root.after(0,lambda:self.error(str(e)))
    def progress_update(self,stage,current,total): self.root.after(0,lambda:self.update(stage,current,total))
    def update(self,stage,current,total):
        if stage=='files': self.status.set(f'Found {current:,} files. Looking for candidates...'); self.progress['mode']='indeterminate'; self.progress.start(8)
        elif stage=='candidates': self.progress.stop(); self.progress['mode']='determinate'; self.progress['maximum']=max(total,1); self.progress['value']=0; self.status.set(f'{current:,} possible duplicate candidates...')
        else: self.progress['maximum']=max(total,1); self.progress['value']=current; self.status.set(f'Hashing files: {current:,} / {total:,}')
    def finished(self,r):
        self.running=False; self.results=r; self.progress.stop(); self.progress['mode']='determinate'; self.progress['value']=self.progress['maximum']; self.browse.config(state='normal'); self.scan.config(state='normal'); self.stop.config(state='disabled')
        self.populate(); groups=len(r); n=sum(len(x) for x in r.values()); reclaim=sum(s*(len(ps)-1) for (s,h),ps in r.items()); self.groups.set(f'Duplicate groups: {groups}'); self.files.set(f'Duplicate files: {n}'); self.reclaim.set(f'Potentially reclaimable: {human_size(reclaim)}')
        if r:
            self.delete.config(state='normal'); self.open.config(state='normal'); self.export.config(state='normal')
        self.status.set('Scan stopped.' if self.stop_event.is_set() else f'Scan completed. Found {groups} duplicate groups.')
    def error(self,e):
        self.running=False; self.progress.stop(); self.browse.config(state='normal'); self.scan.config(state='normal'); self.stop.config(state='disabled'); self.status.set('Scan failed.'); messagebox.showerror('Duplicate File Finder',e)
    def stop_scan(self): self.stop_event.set(); self.status.set('Stopping scan...')
    def populate(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        for g,((size,h),paths) in enumerate(self.results.items(),1):
            for p in paths: self.tree.insert('','end',values=(g,human_size(size),str(p)))
    def selected(self): return [Path(self.tree.item(x,'values')[2]) for x in self.tree.selection()]
    def delete_selected(self):
        paths=self.selected()
        if not paths: messagebox.showwarning('Duplicate File Finder','Select one or more files first.'); return
        if not messagebox.askyesno('Confirm deletion',f'Delete {len(paths)} selected file(s)?\n\nFiles will be moved to Trash when possible.'): return
        deleted=0; failed=[]
        for p in paths:
            try:
                if not p.exists(): continue
                gio=next((str(Path(d)/'gio') for d in os.environ.get('PATH','').split(os.pathsep) if (Path(d)/'gio').is_file() and os.access(Path(d)/'gio',os.X_OK)),None)
                if not gio: raise OSError('gio is not available; file was not deleted.')
                q=subprocess.run([gio,'trash',str(p)],capture_output=True,text=True,timeout=10)
                if q.returncode: raise OSError(q.stderr.strip() or 'gio trash failed')
                deleted+=1
            except Exception as e: failed.append(f'{p}: {e}')
        msg=f'Moved {deleted} file(s) to Trash.'
        if failed: msg+=f'\nCould not remove {len(failed)} file(s).'
        messagebox.showinfo('Duplicate File Finder',msg); self.start_scan()
    def open_folder(self):
        paths=self.selected()
        if not paths: return
        p=paths[0]
        if p.exists(): subprocess.Popen(['xdg-open',str(p.parent)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def export_json(self):
        if not self.results: return
        f=filedialog.asksaveasfilename(title='Export duplicate report',defaultextension='.json',initialfile='duplicate_report.json',filetypes=[('JSON files','*.json'),('All files','*.*')])
        if not f: return
        groups=[]
        for n,((size,h),paths) in enumerate(self.results.items(),1): groups.append({'group':n,'size_bytes':size,'size_human':human_size(size),'sha256':h,'files':[str(p) for p in paths]})
        report={'folder':self.folder,'created_at':time.strftime('%Y-%m-%d %H:%M:%S'),'duplicate_groups':len(groups),'groups':groups}
        try:
            with open(f,'w',encoding='utf-8') as out: json.dump(report,out,ensure_ascii=False,indent=2)
            messagebox.showinfo('Duplicate File Finder',f'Report saved:\n{f}')
        except OSError as e: messagebox.showerror('Duplicate File Finder',str(e))

def main():
    root=tk.Tk()
    try:
        style=ttk.Style(root)
        if 'clam' in style.theme_names(): style.theme_use('clam')
    except tk.TclError: pass
    App(root); root.mainloop()

if __name__=='__main__': main()
