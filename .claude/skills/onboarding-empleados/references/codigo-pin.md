# Generación de código de empleado y PIN — pseudocódigo y pruebas

## Normalización

```python
import unicodedata, re

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z]", "", s).lower()

def first_token(s: str) -> str:
    return s.strip().split()[0] if s.strip() else ""
```

## Código con escalado determinista + reintento transaccional

```python
def candidate_codes(nombre: str, apellido: str):
    n = normalize(first_token(nombre))      # "pepe"
    a = normalize(first_token(apellido))    # "garcia"
    max_level = max(len(n), len(a))
    # Niveles 2+2, 3+3, ... mientras haya letras
    for k in range(2, max_level + 1):
        code = (n[:k].capitalize() + a[:k].capitalize())
        yield code
    # Comodín final: sufijo numérico sobre el nivel base (2+2)
    base = (n[:2].capitalize() + a[:2].capitalize())
    i = 2
    while True:
        yield f"{base}{i}"
        i += 1

def create_employee(db, nombre, apellido, ...):
    for code in candidate_codes(nombre, apellido):
        code_norm = code.lower()
        try:
            # INSERT con UNIQUE(code_norm). Si choca, ProbaR siguiente candidato.
            return db.insert_worker(code=code, code_norm=code_norm, ...)  # commit
        except UniqueViolation:
            db.rollback()
            continue   # siguiente nivel / sufijo
```

> Clave: la UNIQUE de `code_norm` en Postgres es la única garantía real frente a altas
> concurrentes. El `try/except UniqueViolation` convierte la colisión en "subir de nivel".

## PIN inicial

```python
import secrets

TRIVIALES = {"000000","111111","123456","654321","112233"}

def generate_pin(code_norm: str) -> str:
    while True:
        pin = f"{secrets.randbelow(1_000_000):06d}"
        if pin in TRIVIALES: continue
        if len(set(pin)) == 1: continue          # 000000, 111111...
        if pin == code_norm[:6]: continue         # no derivable del código
        return pin

# Guardar SOLO el hash:
pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt())
# Devolver `pin` en claro UNA vez en la respuesta del alta; marcar pin_temporary=True.
```

## Casos de prueba

| Nombre | Apellido | Existentes | Esperado |
|--------|----------|-----------|----------|
| Pepe | Garcia | — | PeGa |
| Penelope | Garza | pega | PenGar |
| Pa | Li | pali ocupado, y agota letras | PaLi2 |
| José | Núñez | — | JoNu (acentos fuera) |
| Pepe | Garcia | pega, pepgar, pepegarc... todos | PeGa2 (sufijo) |

- Verificar: dos `create_employee` concurrentes con mismo nombre NO producen código
  duplicado (uno gana la UNIQUE, el otro reintenta).
- Verificar: PIN inicial nunca trivial; se entrega una vez; primer login fuerza cambio.
