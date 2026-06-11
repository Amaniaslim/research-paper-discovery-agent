# Sprint 1 - Literature Discovery MVP

Dieser Ordner ist ein bewusst kleiner, live vorzeigbarer Ausschnitt aus dem
Gesamtprojekt `Research Paper Discovery Agent`. Der MVP nutzt bereits
gespeicherte Paper-Metadaten aus dem Projekt, damit die Praesentation auch ohne
Internet oder API-Key stabil funktioniert.

## Was im Sprint gezeigt wird

1. Eine Forschungsfrage wird eingegeben.
2. Fuenf vorhandene Paper werden anhand von Keyword-Ueberschneidung,
   Zitierungssignal und Aktualitaet neu gerankt.
3. Die Abstracte werden regelbasiert in Beitrag, Keywords und Limitationen
   zusammengefasst.
4. Das Ergebnis wird als `demo_output/review.md` exportiert.
5. Der ausgefuehrte Review wird als persistente Memory in ChromaDB gespeichert
   und kann ueber eine neue Anfrage wiedergefunden werden.

Das ist der Kern-Workflow des Produkts: Aus einer Forschungsfrage entsteht eine
erste strukturierte Literaturuebersicht. Live-API-Recherche, LLM-Summaries und
PDF-RAG sind bewusst als naechste Entwicklungsschritte abgegrenzt. ChromaDB
wird in Sprint 1 nur fuer die Memory bereits ausgefuehrter Recherchen verwendet,
nicht fuer eine Volltextanalyse von PDFs.

## Live-Demo starten

Vom Projektordner `Agentic Ai` aus:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ".\1 sprint\app_sprint1.py"
```

In der App:

1. Die vorbelegte Forschungsfrage stehen lassen oder leicht veraendern.
2. Auf `MVP ausfuehren` klicken.
3. Das Ranking und die erste extrahierte Zusammenfassung erklaeren.
4. Den Markdown-Export aufklappen oder herunterladen.
5. Unter `Persistent Memory mit ChromaDB` auf
   `Fruehere Recherchen abrufen` klicken.

Falls die Streamlit-Oberflaeche nicht gezeigt werden soll, funktioniert die
gleiche Pipeline auch im Terminal:

```powershell
.\.venv\Scripts\python.exe ".\1 sprint\sprint1_pipeline.py"
```

## Code fuer die Praesentation

| Datei | Was du daran erklaeren kannst |
| --- | --- |
| `sprint1_pipeline.py` | Der MVP-Ablauf: Daten laden, ranken, zusammenfassen, exportieren |
| `sprint1_memory.py` | ChromaDB-Langzeitgedaechtnis fuer ausgefuehrte Reviews |
| `app_sprint1.py` | Die kleine Benutzeroberflaeche fuer die Live-Demo |
| `demo_output/review.md` | Sichtbares Ergebnis des Codes |

Die Pipeline verwendet echte Module aus `src/lit_research_agent/`:
`models.py`, `ranking.py`, `summarize.py`, `synthesis.py` und `exporters.py`.

## Technische Entscheidung

Fuer Sprint 1 wird ein gespeicherter Beispieldatensatz statt einer Live-API
verwendet. Dadurch ist das Ranking und die Zusammenfassung reproduzierbar und
die Demo scheitert nicht an Rate Limits oder Netzwerkproblemen. Zusaetzlich
persistiert ChromaDB vergangene Review-Sessions als semantische Memory. Der
Trade-off: Neue Paper werden in diesem MVP noch nicht live geladen, und die
Memory basiert noch nicht auf PDF-Volltext. Die lokale Memory-Datenbank wird
automatisch unter `outputs/sprint1-memory/` angelegt.

## Learning und naechster Sprint

**Learning:** Eine automatisch erzeugte Literaturuebersicht muss transparent
zeigen, dass sie auf Abstracten basiert; sonst wirkt eine erste Zusammenfassung
staerker belegt, als sie ist.

**Naechster Sprint:** Anbindung von Semantic Scholar/arXiv fuer Live-Ergebnisse,
anschliessend optional LLM-Summaries und PDF-RAG fuer Volltextstellen.

## Sprint Summary fuer Moodle

In Sprint 1 wurde ein lauffaehiger MVP fuer den Research Paper Discovery Agent
umgesetzt. Nutzer geben eine Forschungsfrage ein, woraufhin vorhandene
Paper-Metadaten gerankt und deren Abstracte zu einer ersten strukturierten
Literaturuebersicht zusammengefasst werden. Die Ergebnisse koennen als Markdown
exportiert werden; ausserdem speichert ChromaDB ausgefuehrte Reviews als
persistent abrufbare Memory. Als technische Entscheidung nutzt der Sprint einen
reproduzierbaren Offline-Datensatz; Live-APIs und Volltext-RAG folgen in einem
weiteren Sprint. Repository-Link: `<hier euren Repository-Link einsetzen>`.
