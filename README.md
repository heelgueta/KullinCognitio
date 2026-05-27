# 🐾 KullinCognitio

**Fauna del saber digital** — *kullin* (animal, ser vivo — mapudungun) + *cognitio* (conocimiento — latín).

Suite de herramientas para investigación con corpus de prensa, organizada como un ecosistema de apps especializadas que interactúan entre sí.

## Apps

| | App | Puerto | Descripción |
|--|--|--|--|
| 🦊 | **CulpemCorpus**    | 5001 | Scraper de medios para construir corpus académicos |
| 🐋 | **YeneConservatio** | 5002 | Archivo local persistente de medios |
| 🕷️ | **LlallinRelatio**  | 5003 | Red de conceptos desde corpus (Gephi) |

Dashboard en [`localhost:5050`](http://localhost:5050).

---

## Setup

```powershell
# Clonar con submódulos
git clone --recursive https://github.com/heelgueta/KullinCognitio.git
cd KullinCognitio

# Si ya clonaste sin --recursive:
# git submodule update --init --recursive

# Dependencias del launcher
pip install -r requirements.txt

# Dependencias de cada app
pip install -r CulpemCorpus/requirements.txt
pip install -r YeneConservatio/requirements.txt
pip install -r LlallinRelatio/requirements.txt
python -m spacy download es_core_news_sm  # para LlallinRelatio
```

## Uso

```powershell
python launcher.py
```

Esto:
- Levanta las tres apps en sus puertos (5001, 5002, 5003)
- Sirve un dashboard en `localhost:5050` con estado en vivo
- Abre el navegador automáticamente

**Detener todo:** `Ctrl+C` en la terminal del launcher.

## Logs

Cada app escribe a `./logs/<app_id>.log`. Útil para debugging cuando un app no levanta.

## Estructura

```
KullinCognitio/
├── CulpemCorpus/        [submódulo]
├── YeneConservatio/     [submódulo]
├── LlallinRelatio/      [submódulo]
├── launcher.py          ← punto de entrada
├── templates/
│   └── index.html       ← dashboard
└── logs/                ← gitignored
```

El launcher también detecta los apps si están como **directorios hermanos** de KullinCognitio (workflow de desarrollo local).
