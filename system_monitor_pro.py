#!/usr/bin/env python3
import json, os, platform, re, socket, subprocess, time, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import psutil

APP_TITLE='System Monitor Pro'
POINTS=60

def hb(v):
    if v is None: return 'N/A'
    v=float(v)
    for u in ('B','KB','MB','GB','TB'):
        if v<1024 or u=='TB': return f'{v:.1f} {u}'
        v/=1024

def hs(v): return hb(v)+'/s' if v is not None else '0 B/s'

def temp_sensors():
    out=[]
    try:
        for chip, entries in psutil.sensors_temperatures().items():
            for e in entries:
                if e.current is not None: out.append((e.label or chip, float(e.current)))
    except Exception: pass
    if out: return out
    for z in Path('/sys/class/thermal').glob('thermal_zone*'):
        try:
            t=float((z/'temp').read_text().strip())/1000
            n=(z/'type').read_text().strip()
            out.append((n,t))
        except Exception: pass
    return out

def net_iface():
    try:
        o=subprocess.run(['ip','route','show','default'],capture_output=True,text=True,timeout=2).stdout
        m=re.search(r'default via \S+ dev (\S+)',o); return m.group(1) if m else ''
    except Exception: return ''

def local_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(1); s.connect(('8.8.8.8',80)); x=s.getsockname()[0]; s.close(); return x
    except Exception: return 'N/A'

class Graph:
    def __init__(self,parent,title,unit=''):
        self.title,self.unit=title,unit; self.values=[]
        self.c=tk.Canvas(parent,height=145,background='#11151a',highlightthickness=1,highlightbackground='#303740'); self.c.pack(fill='x',padx=6,pady=4)
    def add(self,v):
        self.values.append(float(v)); self.values=self.values[-POINTS:]; self.draw()
    def draw(self):
        c=self.c; c.delete('all'); w=max(c.winfo_width(),300); h=max(c.winfo_height(),120)
        c.create_text(10,10,anchor='nw',text=self.title,fill='#e5e7eb',font=('TkDefaultFont',9,'bold'))
        if self.values: c.create_text(w-10,10,anchor='ne',text=f'{self.values[-1]:.1f}{self.unit}',fill='white')
        for i in range(1,5):
            y=30+(h-45)*i/5; c.create_line(8,y,w-8,y,fill='#252b32')
        if len(self.values)<2:return
        mx=max(max(self.values),1); pts=[]
        for i,v in enumerate(self.values):
            x=10+(w-20)*i/max(1,len(self.values)-1); y=h-10-(h-42)*min(1,v/mx); pts += [x,y]
        c.create_line(*pts,fill='#4cc9f0',width=2,smooth=True)

class App:
    def __init__(self,root):
        self.root=root; root.title(APP_TITLE); root.geometry('1050x760'); root.minsize(850,620)
        self.prev=None; self.data={}; self.running=True
        try:
            s=ttk.Style(root)
            if 'clam' in s.theme_names(): s.theme_use('clam')
        except tk.TclError: pass
        self.build(); psutil.cpu_percent(None); root.after(300,self.update); root.protocol('WM_DELETE_WINDOW',self.close)
    def build(self):
        top=ttk.Frame(self.root); top.pack(fill='x',padx=15,pady=10)
        ttk.Label(top,text=APP_TITLE,font=('TkDefaultFont',20,'bold')).pack(side='left')
        self.status=tk.StringVar(value='Monitoring'); ttk.Label(top,textvariable=self.status).pack(side='right')
        ttk.Button(top,text='Export JSON',command=self.export).pack(side='right',padx=10)
        nb=ttk.Notebook(self.root); nb.pack(fill='both',expand=True,padx=10); d=ttk.Frame(nb); p=ttk.Frame(nb); h=ttk.Frame(nb); nb.add(d,text='Dashboard'); nb.add(p,text='Processes'); nb.add(h,text='Hardware')
        self.build_dashboard(d); self.build_processes(p); self.build_hardware(h)
    def build_dashboard(self,p):
        cards=ttk.Frame(p); cards.pack(fill='x',padx=8,pady=8); self.cv={}
        for key in ('CPU','RAM','Disk','Network'):
            f=ttk.LabelFrame(cards,text=key,padding=10); f.pack(side='left',fill='both',expand=True,padx=4); v=tk.StringVar(value='--'); self.cv[key]=v; ttk.Label(f,textvariable=v,font=('TkDefaultFont',11,'bold')).pack()
        gf=ttk.LabelFrame(p,text='Realtime Usage',padding=4); gf.pack(fill='both',expand=True,padx=8,pady=5)
        self.gcpu=Graph(gf,'CPU Usage','%'); self.gram=Graph(gf,'RAM Usage','%'); self.gnet=Graph(gf,'Network Download',' B/s')
        inf=ttk.LabelFrame(p,text='Current Details',padding=10); inf.pack(fill='x',padx=8,pady=5); self.detail=tk.StringVar(); ttk.Label(inf,textvariable=self.detail,justify='left').pack(anchor='w')
    def build_processes(self,p):
        bar=ttk.Frame(p); bar.pack(fill='x',padx=8,pady=8); ttk.Label(bar,text='Sort:').pack(side='left'); self.sort=tk.StringVar(value='CPU'); cb=ttk.Combobox(bar,textvariable=self.sort,values=('CPU','RAM','PID','Name'),state='readonly',width=10); cb.pack(side='left',padx=5); cb.bind('<<ComboboxSelected>>',lambda e:self.refresh_processes()); ttk.Button(bar,text='Refresh',command=self.refresh_processes).pack(side='left'); ttk.Button(bar,text='Terminate Selected',command=self.kill).pack(side='right')
        f=ttk.Frame(p); f.pack(fill='both',expand=True,padx=8); cols=('pid','name','cpu','ram','status'); self.tree=ttk.Treeview(f,columns=cols,show='headings');
        for c,t,w in zip(cols,('PID','Process','CPU %','RAM %','Status'),(80,400,100,100,150)): self.tree.heading(c,text=t); self.tree.column(c,width=w)
        sb=ttk.Scrollbar(f,orient='vertical',command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set); self.tree.pack(side='left',fill='both',expand=True); sb.pack(side='right',fill='y'); self.refresh_processes()
    def build_hardware(self,p):
        f=ttk.LabelFrame(p,text='System Information',padding=15); f.pack(fill='x',padx=12,pady=12); self.hw=tk.StringVar(); ttk.Label(f,textvariable=self.hw,justify='left').pack(anchor='w'); sf=ttk.LabelFrame(p,text='Temperature Sensors',padding=12); sf.pack(fill='both',expand=True,padx=12); self.sensor=tk.Text(sf,state='disabled'); self.sensor.pack(fill='both',expand=True)
    def refresh_processes(self):
        rows=[]
        for x in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status']):
            try:
                i=x.info; rows.append((i['pid'],i['name'] or '',float(i['cpu_percent'] or 0),float(i['memory_percent'] or 0),i['status'] or ''))
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        k={'CPU':2,'RAM':3,'PID':0,'Name':1}[self.sort.get()]; rows.sort(key=lambda r:r[k],reverse=self.sort.get() in ('CPU','RAM'))
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in rows[:150]: self.tree.insert('','end',values=(r[0],r[1],f'{r[2]:.1f}',f'{r[3]:.1f}',r[4]))
    def kill(self):
        sel=self.tree.selection()
        if not sel:return
        v=self.tree.item(sel[0],'values'); pid=int(v[0])
        if pid==os.getpid():return
        if not messagebox.askyesno(APP_TITLE,f'Terminate process?\n\nPID: {pid}\nName: {v[1]}'):return
        try: psutil.Process(pid).terminate()
        except psutil.AccessDenied: messagebox.showerror(APP_TITLE,'Permission denied.')
        except psutil.NoSuchProcess: pass
        self.refresh_processes()
    def collect(self):
        m=psutil.virtual_memory(); sw=psutil.swap_memory(); du=psutil.disk_usage('/'); io=psutil.disk_io_counters(); now=time.monotonic(); nc=psutil.net_io_counters(); down=up=0
        if self.prev:
            old,t=self.prev; dt=now-t
            if dt>0: down=max(0,nc.bytes_recv-old.bytes_recv)/dt; up=max(0,nc.bytes_sent-old.bytes_sent)/dt
        self.prev=(nc,now); sensors=temp_sensors(); cpu_t=gpu_t=nv_t=None
        for n,t in sensors:
            q=n.lower()
            if cpu_t is None and any(x in q for x in ('cpu','package','tdie','tctl','coretemp','k10temp')): cpu_t=t
            if gpu_t is None and any(x in q for x in ('gpu','amdgpu','nvidia','nouveau')): gpu_t=t
            if nv_t is None and 'nvme' in q: nv_t=t
        freq=psutil.cpu_freq(); freqtxt=f'{(freq.current or 0)/1000:.2f} GHz' if freq else 'N/A'
        try: load=' / '.join(f'{x:.2f}' for x in os.getloadavg())
        except OSError: load='N/A'
        return {'timestamp':time.strftime('%Y-%m-%d %H:%M:%S'),'hostname':socket.gethostname(),'os':platform.platform(),'kernel':platform.release(),'architecture':platform.machine(),'cpu_percent':psutil.cpu_percent(None),'cpu_physical':psutil.cpu_count(False),'cpu_logical':psutil.cpu_count(True),'cpu_frequency':freqtxt,'load_average':load,'ram_total':m.total,'ram_used':m.used,'ram_available':m.available,'ram_percent':m.percent,'swap_total':sw.total,'swap_used':sw.used,'swap_percent':sw.percent,'disk_total':du.total,'disk_used':du.used,'disk_free':du.free,'disk_percent':du.percent,'disk_read':io.read_bytes if io else 0,'disk_write':io.write_bytes if io else 0,'download':down,'upload':up,'network_interface':net_iface(),'local_ip':local_ip(),'cpu_temp':cpu_t,'gpu_temp':gpu_t,'nvme_temp':nv_t,'temperature_sensors':[{'name':n,'temperature':t} for n,t in sensors]}
    def update(self):
        if not self.running:return
        try:
            d=self.collect(); self.data=d; self.cv['CPU'].set(f"{d['cpu_percent']:.1f}%"); self.cv['RAM'].set(f"{d['ram_percent']:.1f}%"); self.cv['Disk'].set(f"{d['disk_percent']:.1f}%"); self.cv['Network'].set(f"↓ {hs(d['download'])}  ↑ {hs(d['upload'])}"); self.gcpu.add(d['cpu_percent']); self.gram.add(d['ram_percent']); self.gnet.add(d['download']); self.detail.set(f"CPU: {d['cpu_physical']} physical / {d['cpu_logical']} logical    Frequency: {d['cpu_frequency']}    Load: {d['load_average']}\nRAM: {hb(d['ram_used'])} / {hb(d['ram_total'])}    Available: {hb(d['ram_available'])}\nDisk /: {hb(d['disk_used'])} / {hb(d['disk_total'])}    Free: {hb(d['disk_free'])}\nNetwork: {d['network_interface'] or 'N/A'}    Local IP: {d['local_ip']}"); self.update_hw(d)
            if int(time.monotonic())%2==0:self.refresh_processes()
        except Exception as e:self.status.set(f'Error: {e}')
        self.root.after(1000,self.update)
    def update_hw(self,d):
        def tf(x): return f'{x:.1f} °C' if x is not None else 'N/A'
        self.hw.set(f"Hostname: {d['hostname']}\nOS: {d['os']}\nKernel: {d['kernel']}\nArchitecture: {d['architecture']}\n\nCPU temperature: {tf(d['cpu_temp'])}\nGPU temperature: {tf(d['gpu_temp'])}\nNVMe temperature: {tf(d['nvme_temp'])}\nSwap: {hb(d['swap_used'])} / {hb(d['swap_total'])} ({d['swap_percent']:.1f}%)")
        self.sensor.config(state='normal'); self.sensor.delete('1.0','end')
        if d['temperature_sensors']:
            for s in d['temperature_sensors']: self.sensor.insert('end',f"{s['name']}: {s['temperature']:.1f} °C\n")
        else:self.sensor.insert('end','No temperature sensors detected.\nInstall lm-sensors for additional sensor support.'); self.sensor.config(state='disabled')
    def export(self):
        if not self.data:return
        fn=filedialog.asksaveasfilename(defaultextension='.json',initialfile='system_monitor_report.json',filetypes=[('JSON','*.json')])
        if not fn:return
        try:
            with open(fn,'w',encoding='utf-8') as f: json.dump(self.data,f,ensure_ascii=False,indent=2)
            messagebox.showinfo(APP_TITLE,f'Report saved:\n{fn}')
        except OSError as e:messagebox.showerror(APP_TITLE,str(e))
    def close(self):self.running=False;self.root.destroy()

def main():
    root=tk.Tk(); App(root); root.mainloop()
if __name__=='__main__': main()
