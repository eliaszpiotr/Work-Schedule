# Audyt bezpieczeństwa — Work Scheduler 0.2.0

Data: 2026-08-26 · zakres: cały projekt (`src/`, `tests/`, migracje, konfiguracja, historia gita, zależności, uprawnienia plików na dysku)

Wszystkie ustalenia zostały naprawione tego samego dnia. Stan każdego z nich jest odnotowany przy opisie.

## Model zagrożeń

Aplikacja desktopowa dla jednego stanowiska: PySide6 + SQLite, **zero kodu sieciowego**, brak logowania i kont.
Nie ma tu powierzchni ataku typowej dla aplikacji webowej. Realne ryzyko to:

1. dane osobowe pracowników (imię, nazwisko, zawód, pełny rozkład godzin pracy) leżące w pliku na dysku → RODO,
2. utrata danych (jeden plik SQLite, usuwanie nieodwracalne, brak kopii),
3. inny użytkownik tego samego komputera,
4. łańcuch dostaw (zależności instalowane bez blokady wersji).

## Ustalenia

### Średnie

**M1. Baza danych czytelna dla każdego konta na komputerze** — *naprawione*

`work_scheduler.db` miał uprawnienia `0644`, katalog `0755`. Plik zawiera dane osobowe całego zespołu,
więc każde inne konto lokalne mogło go odczytać i skopiować.

Poprawka: nowy moduł [privacy.py](src/work_scheduler/privacy.py) z jednym kompletem reguł dla wszystkiego,
co aplikacja zapisuje. Baza dostaje `0600` przy pierwszym połączeniu (nasłuch `first_connect`
w [session.py](src/work_scheduler/database/session.py)), czyli także istniejące instalacje naprawiają się przy
najbliższym starcie. Katalogi zakładane przez aplikację dostają `0700` — ale tylko te, które sama zakłada:
ścieżka bazy może wskazywać na katalog domowy, a zawężanie uprawnień czegoś, czego nie stworzyliśmy,
byłoby niespodzianką.

**M2. Brak kopii zapasowych, kasowanie nieodwracalne** — *naprawione*

Cała historia to jeden plik, a migracje w trybie `render_as_batch` przebudowują tabele.

Poprawka: `back_up()` w [bootstrap.py](src/work_scheduler/database/bootstrap.py) robi kopię przed
`command.upgrade`, do `backups/` obok bazy, z rotacją pięciu ostatnich. Kopia nie powstaje, jeśli od
poprzedniej nic się nie zmieniło (ten sam rozmiar i czas modyfikacji), więc restart bez pracy nie zaśmieca
katalogu. Znacznik czasu w nazwie ma mikrosekundy — dwie kopie w tej samej sekundzie inaczej trafiłyby
na jedną nazwę, a to nazwy ustawiają kopie w kolejności.

**M3. Zależności bez zablokowanych wersji** — *naprawione*

`pyproject.toml` podawał same przedziały, więc instalacja na nowej maszynie brała to, co akurat jest na PyPI.

Poprawka: [requirements.txt](requirements.txt) i [requirements-dev.txt](requirements-dev.txt) z dokładnymi
wersjami całego domknięcia zależności, generowane przez [tools/lock.py](tools/lock.py).
Hashe to następny krok (`pip-compile --generate-hashes` albo `uv lock`) — przypinają koło dla każdej
platformy, a nie tylko dla tej, na której akurat stoi środowisko.

**M4. Eksport PDF zapisywany z domyślną maską** — *naprawione*

Plik z nazwiskami i pełnym grafikiem trafiał do `~/` z prawami `0644`, a przerwany zapis zostawiał
uszkodzony PDF pod właściwą nazwą.

Poprawka: [document.py](src/work_scheduler/export/document.py) rysuje do pliku tymczasowego obok celu,
utworzonego od razu z prawami `0600`, i dopiero gotowy dokument przenosi na miejsce przez `os.replace`.
Nieudany zapis nie zostawia niczego.

### Niskie

**N1. Cache ikon we wspólnym katalogu tymczasowym** — *naprawione*

Na Linuksie `/tmp` jest zapisywalny dla wszystkich, a nazwy plików były przewidywalne, więc obcy użytkownik
mógł podłożyć własne pliki dokładnie tam, skąd arkusz stylów je czyta.
Poprawka: cache przeniesiony do katalogu danych aplikacji, z prawami `0700`
([resources.py](src/work_scheduler/ui/resources.py), [icons.py](src/work_scheduler/ui/icons.py)).

**N2. QLabel renderował dane użytkownika jako HTML** — *naprawione*

Qt zgaduje, czy napis jest HTML-em, i renderuje go jako znaczniki, kiedy tak wygląda. Nazwiska i nazwy
grafików są wpisywane ręcznie, więc nazwisko z nawiasem ostrym przestawiało układ okna zamiast się w nim pojawić.
Poprawka: klasa `PlainLabel` w [components.py](src/work_scheduler/ui/components.py) ustawia
`Qt.TextFormat.PlainText`; wszystkie etykiety w aplikacji przez nią przechodzą, łącznie z `Avatar`, `Badge`,
`Glyph` i `BrandMark`. Selektory arkusza stylów typu `QLabel#brand` obejmują podklasy, więc wygląd się nie zmienia.

Okna `QMessageBox` zostawiono bez zmian celowo: ich treść to stałe polskie zdania i komunikaty `ServiceError`,
w których nie ma danych wpisywanych przez użytkownika.

**N3. Surowe komunikaty błędów pokazywane użytkownikowi** — *naprawione*

`prepare_database` zawijał każdy wyjątek w komunikat wyświetlany w oknie, razem z pełnymi ścieżkami i SQL-em.
Poprawka: użytkownik dostaje zdanie mówiące, gdzie szukać i co sprawdzić; szczegóły techniczne idą do logu
przez `logger.exception`, które i tak już tam było.

**N4. `WORK_SCHEDULER_DB` przyjmuje dowolną ścieżkę** — *bez zmian, świadoma decyzja*

Zmienna środowiskowa wskazuje plik, który aplikacja otworzy i zmigruje. Jest potrzebna w testach i przy
migracjach, a ustawić ją może tylko ktoś, kto i tak ma dostęp do konta. Odnotowane jako świadoma decyzja.

**N5. `finalized_at` w czasie lokalnym, reszta znaczników w UTC** — *naprawione*

Jedyne pole mówiące „kiedy ktoś to zatwierdził" było w innej strefie niż `created_at` obok niego.
Poprawka: [schedule_service.py](src/work_scheduler/services/schedule_service.py) używa `utcnow()`.
Test uruchamia się w strefie oddalonej o czternaście godzin od UTC, więc wychwyci powrót do czasu lokalnego
także na maszynie stojącej na UTC.

**N6. Brak śladu, kto wprowadził zmianę** — *bez zmian, świadoma decyzja*

Nie ma kont ani dziennika zmian. Dla jednego stanowiska ryzyko akceptowalne; odnotowane ze względu na
RODO art. 5 ust. 2 (rozliczalność). Wprowadzenie kont zmieniłoby aplikację w coś innego, niż jest.

**N7. Stary `pip` w środowisku deweloperskim (23.2.1)** — *naprawione*

Podniesiony do 26.2.1.

**N8. `pytest` 8.4.2 z podatnością PYSEC-2026-1845** — *naprawione*

Znalezione przez `pip-audit` już po napisaniu pierwszej wersji raportu. Katalogi tymczasowe pytesta miały
przewidywalną nazwę pod `/tmp` — dokładnie ta sama klasa problemu co N1, tylko w narzędziu.
Dotyczy wyłącznie środowiska deweloperskiego. Poprawka: `pytest>=9.0.3` w `pyproject.toml`, zainstalowany 9.1.1,
439 testów przechodzi.

## Zweryfikowane i czyste

- **Brak SQL injection.** Każde zapytanie idzie przez SQLAlchemy ORM/Core z parametrami wiązanymi; jedyne `session.execute` ([schedule_repository.py:29](src/work_scheduler/database/repositories/schedule_repository.py:29)) dostaje zbudowany `select()`. Brak `text()`, brak sklejania SQL.
- **Brak niebezpiecznych wywołań.** Zero `eval`, `exec`, `pickle`, `subprocess`, `os.system`, `__import__`. Żadnej deserializacji danych z zewnątrz.
- **Zero kodu sieciowego.** Brak HTTP, gniazd, telemetrii, automatycznych aktualizacji. Nic nie opuszcza komputera.
- **Brak sekretów w repozytorium i w historii gita.** Żadnego `.env`, `.db`, klucza ani `.idea`. `alembic.ini` ma pusty `sqlalchemy.url`.
- **Nazwa pliku PDF jest sanityzowana** ([report.py:80](src/work_scheduler/services/report.py:80) — tylko znaki alfanumeryczne, spacja, `-`, `_`). Nazwa grafiku nie pozwala wyjść z katalogu.
- **Walidacja wejścia jest kompletna**: długości nazw (80/120 znaków), kolejność dat, limit 366 dni, duplikaty osób, istnienie rekordów, godziny otwarcia. Wsparte przez `CHECK` i `UNIQUE` w bazie.
- **`parse_range`** ([time_text.py:5](src/work_scheduler/services/time_text.py:5)) ma regex liniowy — bez zagnieżdżonych kwantyfikatorów, brak ReDoS.
- **Integralność transakcji**: `session_scope` cofa zmiany przy każdym wyjątku, `PRAGMA foreign_keys=ON` na każde połączenie, `ondelete="RESTRICT"` na pracownikach chroni historię grafików.
- **`pip-audit` nie zgłasza żadnej podatności** ani dla zależności aplikacji, ani dla narzędzi (po podniesieniu pytesta).

## Weryfikacja poprawek

- 439 testów przechodzi (421 wcześniejszych plus 18 nowych w [tests/test_privacy.py](tests/test_privacy.py) i jeden dla `finalized_at`).
- `ruff check` i `ruff format --check` czyste na 90 plikach.
- Uruchomienie aplikacji na kopii prawdziwej bazy: plik przeszedł z `0644` na `0600`, kopia zapasowa powstała przed migracją w katalogu `0700`.
- `pip-audit` na obu plikach z zależnościami: bez podatności.

## Co zostało do zrobienia ręcznie

Katalog `~/Library/Application Support/WorkScheduler` powstał, zanim aplikacja umiała zakładać go prywatnie,
i nadal ma `0755`. Sama baza dostanie `0600` przy najbliższym starcie. Żeby zawęzić też katalog:

    chmod 700 ~/Library/Application\ Support/WorkScheduler
