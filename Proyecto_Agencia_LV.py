import hashlib, os, re, binascii
from abc import ABC, abstractmethod
from datetime import datetime

# ============================================================
#                    SEGURIDAD
# ============================================================
def hash_pwd(p):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, 100_000)
    return f"{binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verificar_pwd(p, h):
    try:
        salt_hex, hash_hex = h.split('$')
        dk = hashlib.pbkdf2_hmac('sha256', p.encode(), binascii.unhexlify(salt_hex), 100_000)
        return binascii.hexlify(dk).decode() == hash_hex
    except Exception:
        return False

# ============================================================
#                    EXCEPCIONES
# ============================================================
class ErrorApp(Exception): pass
class ErrorAuth(ErrorApp): pass
class ErrorDup(ErrorApp): pass

# ============================================================
#                    MODELOS
# ============================================================
class Usuario(ABC):
    def __init__(self, id_u, nombre, correo, pwd):
        self.id, self.nombre, self.correo = id_u, nombre, correo.lower()
        self.pwd_hash = hash_pwd(pwd)

    def autenticar(self, pwd): return verificar_pwd(pwd, self.pwd_hash)

    @abstractmethod
    def rol(self): ...

    def __str__(self): return f"[{self.rol()}] {self.id} - {self.nombre} ({self.correo})"


class Cliente(Usuario):
    def __init__(self, id_u, nombre, correo, pwd):
        super().__init__(id_u, nombre, correo, pwd)
        self.reservas = []

    def rol(self): return "Cliente"


class Agente(Usuario):
    def __init__(self, id_u, nombre, correo, pwd, codigo):
        super().__init__(id_u, nombre, correo, pwd)
        self.codigo = codigo

    def rol(self): return "Agente"


class Paquete:
    def __init__(self, id_p, destino, precio_clp, dias, cupos, fecha):
        self.id, self.destino = id_p, destino
        self.precio, self.dias = int(precio_clp), dias
        self.cupos, self.fecha = cupos, fecha
        self.activo = True

    def precio_fmt(self): return f"${self.precio:,.0f} CLP".replace(",", ".")

    def __str__(self):
        return (f"[{self.id}] {self.destino} | {self.dias} días | "
                f"{self.precio_fmt()} | Cupos: {self.cupos} | Salida: {self.fecha}")


class Reserva:
    def __init__(self, id_r, cliente, paquete, personas):
        if not paquete.activo or paquete.cupos < personas:
            raise ErrorApp("Sin cupos suficientes.")
        self.id, self.cliente, self.paquete, self.personas = id_r, cliente, paquete, personas
        self.estado, self.fecha = "PENDIENTE", datetime.now()
        paquete.cupos -= personas
        cliente.reservas.append(self.id)

    def total(self): return self.paquete.precio * self.personas
    def total_fmt(self): return f"${self.total():,.0f} CLP".replace(",", ".")

    def cancelar(self):
        if self.estado == "CANCELADA": raise ErrorApp("Ya cancelada.")
        self.paquete.cupos += self.personas
        self.estado = "CANCELADA"

    def __str__(self):
        return (f"[{self.id}] {self.cliente.nombre} → {self.paquete.destino} | "
                f"{self.personas} persona(s) | Total: {self.total_fmt()} | {self.estado}")

# ============================================================
#                    GESTOR
# ============================================================
class Gestor:
    def __init__(self):
        self.usuarios, self.paquetes, self.reservas = {}, {}, {}
        self.actual = None
        self.cu = self.cp = self.cr = 0

    def _id(self, pre, attr):
        setattr(self, attr, getattr(self, attr) + 1)
        return f"{pre}{getattr(self, attr):03d}"

    def _buscar_correo(self, c):
        return next((u for u in self.usuarios.values() if u.correo == c.lower()), None)

    def registrar(self, tipo, nombre, correo, pwd, **kw):
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", correo): raise ErrorApp("Correo inválido.")
        if len(pwd) < 6: raise ErrorApp("Contraseña muy corta (mín. 6).")
        if self._buscar_correo(correo): raise ErrorDup("Correo ya registrado.")
        if tipo == "cliente":
            u = Cliente(self._id("CLI", "cu"), nombre, correo, pwd)
        else:
            u = Agente(self._id("AGE", "cu"), nombre, correo, pwd, kw.get("codigo", "EMP"))
        self.usuarios[u.id] = u
        return u

    def login(self, correo, pwd):
        u = self._buscar_correo(correo)
        if not u or not u.autenticar(pwd): raise ErrorAuth("Credenciales inválidas.")
        self.actual = u
        return u

    def logout(self): self.actual = None

    def crear_paquete(self, destino, precio, dias, cupos, fecha):
        if not isinstance(self.actual, Agente): raise ErrorAuth("Solo agentes.")
        p = Paquete(self._id("PKG", "cp"), destino, precio, dias, cupos, fecha)
        self.paquetes[p.id] = p
        return p

    def reservar(self, id_p, personas=1):
        if not isinstance(self.actual, Cliente): raise ErrorAuth("Solo clientes.")
        p = self.paquetes.get(id_p)
        if not p: raise ErrorApp("El paquete no existe.")
        r = Reserva(self._id("RES", "cr"), self.actual, p, personas)
        self.reservas[r.id] = r
        return r

    def seed(self):
        ag = self.registrar("agente", "Admin", "admin@viajes.com", "admin123", codigo="EMP-001")
        self.registrar("cliente", "Juan Perez", "juan@correo.com", "juan123")
        self.actual = ag
        self.crear_paquete("Cancún, México",      1_850_000, 7, 20, "15/03/2026")
        self.crear_paquete("Machu Picchu, Perú",  1_250_000, 5, 15, "10/04/2026")
        self.crear_paquete("París, Francia",      2_890_000, 6, 10, "20/05/2026")
        self.crear_paquete("Bariloche, Argentina",  890_000, 4, 25, "05/07/2026")
        self.actual = None

# ============================================================
#                    INTERFAZ
# ============================================================
LINEA = "=" * 62

def titulo(t):
    print("\n" + LINEA); print(f"  {t}"); print(LINEA)

def pausar(): input("\nPresione ENTER para continuar...")

def pedir_int(msg):
    while True:
        try: return int(input(msg).strip())
        except ValueError: print("  [!] Ingrese un número entero.")

def pedir_monto(msg):
    while True:
        try: return int(input(msg).strip().replace(".", "").replace(",", ""))
        except ValueError: print("  [!] Ingrese un monto válido (ej: 1850000).")


# ---------- MENÚ PRINCIPAL ----------
def menu_principal(g):
    while True:
        titulo("VIAJES AVENTURA - SISTEMA DE GESTIÓN")
        print("  1. Iniciar sesión")
        print("  2. Registrarse como cliente")
        print("  3. Salir")
        op = input("\n  Opción: ").strip()

        if op == "1":
            if login_ui(g): menu_usuario(g)
        elif op == "2": registrar_ui(g)
        elif op == "3": print("\n  ¡Hasta pronto!"); return
        else: print("  [!] Opción inválida."); pausar()


def login_ui(g):
    titulo("INICIAR SESIÓN")
    correo = input("  Correo     : ").strip()
    pwd    = input("  Contraseña : ").strip()
    try:
        u = g.login(correo, pwd)
        print(f"\n  [✓] Bienvenido/a, {u.nombre} ({u.rol()})")
        pausar(); return True
    except ErrorApp as e:
        print(f"\n  [✗] {e}"); pausar(); return False


def registrar_ui(g):
    titulo("REGISTRO DE CLIENTE")
    nombre = input("  Nombre completo : ").strip()
    correo = input("  Correo          : ").strip()
    pwd    = input("  Contraseña      : ").strip()
    try:
        u = g.registrar("cliente", nombre, correo, pwd)
        print(f"\n  [✓] Registrado con ID {u.id}")
    except ErrorApp as e:
        print(f"\n  [✗] {e}")
    pausar()


# ---------- MENÚ USUARIO ----------
def menu_usuario(g):
    u = g.actual
    while True:
        salir = menu_agente(g) if isinstance(u, Agente) else menu_cliente(g)
        if salir: return


# ---------- CLIENTE ----------
def menu_cliente(g):
    u = g.actual
    titulo(f"CLIENTE - {u.nombre}")
    print("  1. Ver paquetes disponibles")
    print("  2. Agendar un viaje (reservar)")
    print("  3. Ver mis reservas")
    print("  4. Cancelar una reserva")
    print("  5. Cerrar sesión")
    print("  0. Salir del sistema")
    op = input("\n  Opción: ").strip()

    if op == "1": ver_paquetes(g)
    elif op == "2": agendar_viaje(g)
    elif op == "3": ver_mis_reservas(g)
    elif op == "4": cancelar_ui(g, es_agente=False)
    elif op == "5": g.logout(); return True
    elif op == "0": print("\n  ¡Hasta pronto!"); exit()
    else: print("  [!] Opción inválida."); pausar()
    return False


def ver_paquetes(g):
    titulo("PAQUETES DISPONIBLES")
    activos = [p for p in g.paquetes.values() if p.activo and p.cupos > 0]
    if not activos: print("  No hay paquetes disponibles.")
    for p in activos: print(f"  {p}")
    pausar()


def agendar_viaje(g):
    titulo("AGENDAR VIAJE")
    activos = [p for p in g.paquetes.values() if p.activo and p.cupos > 0]
    if not activos:
        print("  No hay paquetes disponibles."); pausar(); return

    for p in activos: print(f"  {p}")

    print()
    id_p = input("  ID del paquete a reservar: ").strip().upper()
    p = g.paquetes.get(id_p)
    if not p:
        print("  [!] No existe un paquete con ese ID."); pausar(); return

    personas = pedir_int("  Cantidad de personas: ")
    print(f"\n  Destino      : {p.destino}")
    print(f"  Precio/pers. : {p.precio_fmt()}")
    print(f"  Personas     : {personas}")
    print(f"  TOTAL        : ${p.precio * personas:,.0f} CLP".replace(",", "."))

    if input("\n  ¿Confirmar reserva? (s/n): ").strip().lower() != "s":
        print("  Reserva cancelada."); pausar(); return

    try:
        r = g.reservar(id_p, personas)
        print(f"\n  [✓] Reserva {r.id} creada. Total a pagar: {r.total_fmt()}")
    except ErrorApp as e:
        print(f"\n  [✗] {e}")
    pausar()


def ver_mis_reservas(g):
    titulo("MIS RESERVAS")
    mias = [r for r in g.reservas.values() if r.cliente.id == g.actual.id]
    if not mias: print("  Aún no tienes reservas.")
    for r in mias: print(f"  {r}")
    pausar()


def cancelar_ui(g, es_agente):
    titulo("CANCELAR RESERVA")
    disponibles = list(g.reservas.values())
    if not es_agente:
        disponibles = [r for r in disponibles if r.cliente.id == g.actual.id]
    if not disponibles:
        print("  No hay reservas para mostrar."); pausar(); return
    for r in disponibles: print(f"  {r}")
    id_r = input("\n  ID de la reserva a cancelar: ").strip().upper()
    r = g.reservas.get(id_r)
    if not r or (not es_agente and r.cliente.id != g.actual.id):
        print("  [!] Reserva no encontrada."); pausar(); return
    try:
        r.cancelar()
        print(f"\n  [✓] Reserva {r.id} cancelada.")
    except ErrorApp as e:
        print(f"\n  [✗] {e}")
    pausar()


# ---------- AGENTE ----------
def menu_agente(g):
    u = g.actual
    titulo(f"AGENTE - {u.nombre}")
    print("  1. Ver todos los paquetes")
    print("  2. Crear nuevo paquete")
    print("  3. Ver todas las reservas")
    print("  4. Confirmar una reserva")
    print("  5. Cerrar sesión")
    print("  0. Salir del sistema")
    op = input("\n  Opción: ").strip()

    if op == "1":
        titulo("TODOS LOS PAQUETES")
        for p in g.paquetes.values(): print(f"  {p}")
        pausar()
    elif op == "2": crear_paquete_ui(g)
    elif op == "3":
        titulo("TODAS LAS RESERVAS")
        if not g.reservas: print("  Sin reservas.")
        for r in g.reservas.values(): print(f"  {r}")
        pausar()
    elif op == "4": confirmar_ui(g)
    elif op == "5": g.logout(); return True
    elif op == "0": print("\n  ¡Hasta pronto!"); exit()
    else: print("  [!] Opción inválida."); pausar()
    return False


def crear_paquete_ui(g):
    titulo("CREAR PAQUETE")
    destino = input("  Destino        : ").strip()
    precio  = pedir_monto("  Precio CLP     : $")
    dias    = pedir_int("  Duración (días): ")
    cupos   = pedir_int("  Cupos          : ")
    fecha   = input("  Fecha salida   : ").strip()
    try:
        p = g.crear_paquete(destino, precio, dias, cupos, fecha)
        print(f"\n  [✓] Paquete {p.id} creado.")
    except ErrorApp as e:
        print(f"\n  [✗] {e}")
    pausar()


def confirmar_ui(g):
    titulo("CONFIRMAR RESERVA")
    pendientes = [r for r in g.reservas.values() if r.estado == "PENDIENTE"]
    if not pendientes:
        print("  No hay reservas pendientes."); pausar(); return
    for r in pendientes: print(f"  {r}")
    id_r = input("\n  ID de la reserva a confirmar: ").strip().upper()
    r = g.reservas.get(id_r)
    if not r or r.estado != "PENDIENTE":
        print("  [!] Reserva no válida."); pausar(); return
    r.estado = "CONFIRMADA"
    print(f"\n  [✓] Reserva {r.id} confirmada.")
    pausar()


# ============================================================
#                    ARRANQUE
# ============================================================
if __name__ == "__main__":
    g = Gestor()
    g.seed()
    print(LINEA)
    print("  VIAJES AVENTURA - Precios en CLP (peso chileno)")
    print(LINEA)
    print("  Usuarios demo:")
    print("    Agente  -> admin@viajes.com  / admin123")
    print("    Cliente -> juan@correo.com   / juan123")
    menu_principal(g)