# Trening tagów Aircall

Aplikacja treningowa dla telefundraiserek i telefundraiserów Otwartych Klatek.
Ćwiczy tagowanie rozmów: 16 sytuacji z prawdziwej pracy, panel tagów odwzorowujący
ekran „Select tags" w Aircallu, informacja zwrotna z wyjaśnieniem i wskazaniem,
jaki status zapisze się w Salesforce.

## Uruchomienie lokalnie

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Skąd pochodzi merytoryka

- Nazwy i kolory tagów: panel „Select tags" w Aircallu (stan: sierpień 2026).
- Logika statusów: `TaskAircallParseHelper.deriveStatusFromTags` w produkcyjnym
  Salesforce. Funkcja `derive_status()` jest jej wiernym portem, zgodność
  potwierdzona na wszystkich kombinacjach tagów.

Przy zmianie tej klasy w Salesforce trzeba zaktualizować `derive_status()`.

Kod źródłowy i notatki utrzymaniowe: `~/pro/dash/local_dashboard/`.
