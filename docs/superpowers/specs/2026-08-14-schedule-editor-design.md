# Edytor grafiku — projekt

**Data:** 14 sierpnia 2026
**Dotyczy:** wersji 0.2.0
**Stan przed:** działa kartoteka pracowników i cała warstwa danych; ekrany „Grafik", „Raporty"
i „Ustawienia" to zaślepki.

---

## 1. Co budujemy

Grafik układa się w tabeli: wiersze to kolejne dni okresu, kolumny to wybrani pracownicy,
w komórce wpisuje się godziny pracy. Pod tabelą stoi wiersz z sumą godzin każdej osoby.

```
             Kowalska Anna   Nowak Marek   Zając Ola
pt 14.08     10:00–15:00                   8:00–16:00
sb 15.08                     9:00–14:00
nd 16.08     ── zamknięte ──────────────────────────
pn 17.08     8:00–20:00      12:00–20:00
─────────────────────────────────────────────────────
Suma         23,0 h          13,0 h        8,0 h
```

**Liczba wierszy wynika wprost z okresu.** Okres 12–31 sierpnia to dokładnie 20 wierszy,
każdy dzień raz, po kolei. Liczba kolumn wynika wprost z liczby zaznaczonych pracowników.
Żadnych pustych wierszy w zapasie.

---

## 2. Podział na etapy

Całość jest za duża na jeden plan wdrożenia, więc rozpada się na dwa. Etapu B nie da się
zbudować bez A, bo siatka potrzebuje okresu, składu i godzin otwarcia.

**Etap A — fundament.** Godziny otwarcia w Ustawieniach, lista grafików, kreator nowego
grafiku. Efekt: da się utworzyć pusty grafik i zobaczyć go na liście.

**Etap B — siatka.** Tabela dni × pracownicy, wpisywanie godzin, wiersz sum. Efekt: działający
edytor.

---

## 3. Decyzje podjęte przy projektowaniu

| Pytanie | Rozstrzygnięcie | Dlaczego |
|---|---|---|
| Gdzie godziny otwarcia | W Ustawieniach jako domyślne, w kreatorze do nadpisania | Zwykle są stałe, ale wyjazd na inwentaryzację czy święta zdarzają się nieregularnie |
| Ile zmian dziennie na osobę | Jedna | Decyzja biznesowa; pilnuje jej baza, nie tylko interfejs |
| Urlop, L4 | Poza zakresem | Pusta komórka znaczy „nie pracuje"; znaczniki wymagają nowej kolumny i zmiany w sumowaniu |
| Jak wpisywać godziny | Z klawiatury, jak w Excelu | Miesiąc to 31 × 8 komórek; popup z listami to setki kliknięć na grafik |
| Godziny poza otwarciem | Ostrzeżenie, ale zapis przechodzi | Dostawa przed otwarciem i inwentaryzacja po zamknięciu to normalne wyjątki |
| Skrócenie okresu z wpisanymi zmianami | Pytanie z liczbą zmian do usunięcia | Utrata pracy musi być świadoma, ale blokada zmuszałaby do ręcznego czyszczenia |

Dwa ostatnie wiersze to założenia przyjęte bez potwierdzenia — pytanie przepadło przy
przerwanej rozmowie. Obie decyzje da się odwrócić w jednym miejscu w kodzie.

---

## 4. Baza danych

### Nowa tabela `opening_hours`

Domyślne godziny otwarcia apteki, edytowane w Ustawieniach. Dokładnie siedem wierszy.

| Kolumna | Uwagi |
|---|---|
| `id` | klucz główny |
| `weekday` | 0–6, poniedziałek to 0, zgodnie z `date.weekday()`; unikalny |
| `opens`, `closes` | `NULL` w obu znaczy dzień zamknięty |

CHECK pilnuje, że albo obie są puste, albo obie wypełnione i `closes > opens`. Nie ma
osobnej flagi „zamknięte", bo dwa źródła tej samej prawdy prędzej czy później się rozjadą.

### Nowa tabela `schedule_opening_hours`

Ta sama budowa plus `schedule_id` (CASCADE) i unikalna para (grafik, dzień tygodnia).

**Kreator kopiuje tu ustawienia w chwili tworzenia grafiku.** To celowe: gdy za pół roku
zmienią się godziny apteki, archiwalne grafiki nie mogą się przeliczyć na inne. Grafik ma być
samowystarczalny. Cena: te same siedem wierszy leży w bazie raz na grafik — przy dwunastu
grafikach rocznie to 84 wiersze, czyli nic.

### Zmiana w `shifts`

Unikalny indeks `uq_shifts_one_per_day` na parze (`schedule_employee_id`, `shift_date`).
Poprzedni projekt dopuszczał duplikaty i odsyłał wykrywanie do przyszłego silnika reguł;
decyzja o jednej zmianie dziennie właśnie to unieważniła.

Jako indeks, nie jako `UniqueConstraint`, bo SQLite nie potrafi dołożyć ograniczenia do
istniejącej tabeli bez przepisania jej w trybie wsadowym.

### Migracja

Jedna nowa rewizja: dwie tabele i jeden indeks. Siedmiu wierszy `opening_hours` migracja
**nie** zakłada — robi to serwis przy pierwszym odczycie. Powód: testy budują schemat przez
`create_all`, z pominięciem migracji, więc dane zaszyte w migracji byłyby w testach
niewidoczne i kod i tak musiałby radzić sobie z pustą tabelą.

---

## 5. Warstwa serwisów

Układ jak dotąd: UI → serwisy → repozytoria → SQLAlchemy. Jedna operacja użytkownika to jedna
transakcja.

**`OpeningHoursService`**
- `week()` — siedem wpisów po kolei; brakujące zakłada z domyślnych (pn–pt 8–20, sb 9–14,
  nd zamknięte)
- `save(entries)` — waliduje i zapisuje

**`ScheduleService`**
- `list_schedules(status=None)` — zwraca `ScheduleSummary`, nie obiekty ORM
- `create(name, start_date, end_date, employee_ids, week)` — grafik, skład i kopia godzin
  w jednej transakcji
- `open_schedule(schedule_id)` — `ScheduleData`: okres, pasy i tygodniowe godziny jako zwykłe
  wartości, z wszystkim doczytanym przed zamknięciem sesji
- `rename(schedule_id, name)`, `delete(schedule_id)`

Zmiana okresu po utworzeniu grafiku **nie powstała** — patrz punkt 8.

Walidacja: nazwa niepusta do 120 znaków, `end_date >= start_date`, co najmniej jeden
pracownik, okres nie dłuższy niż 366 dni (zabezpieczenie przed literówką w roku, która
zrobiłaby siatkę na 30 000 wierszy).

**`ShiftService`**
- `grid(schedule_id)` — wszystkie zmiany grafiku jako `{(schedule_employee_id, data): Shift}`
- `set_shift(schedule_employee_id, date, start, end)` — wstawia albo nadpisuje
- `clear_shift(schedule_employee_id, date)`
- `totals(schedule_id)` — minuty na pracownika

**`services/time_text.py`** — `parse_range(text)` zwraca parę `time` albo `None`.
Przyjmuje `10-15`, `10:00-15:00`, `10.00 - 15.00`, `8–16` z półpauzą, `od 8 do 16`.
Pusty tekst to nie błąd, tylko czyszczenie komórki — rozstrzyga o tym wywołujący.

Sumy liczone są w minutach i dopiero na wyjściu zamieniane na godziny, żeby zmiana
8:30–16:00 nie zgubiła połówki przy zaokrąglaniu.

---

## 6. Interfejs

### Ustawienia

Siedem wierszy, w każdym nazwa dnia, przełącznik „otwarte" i dwa pola czasu. Pola gasną,
gdy dzień jest zamknięty. Na dole „Zapisz".

Widget `OpeningHoursEditor` jest wspólny dla Ustawień i kreatora — jedno miejsce z układem
i walidacją.

### Lista grafików

Tabela: nazwa, okres, liczba osób, status. Filtr statusu jako lista rozwijana (wszystkie /
robocze / gotowe / archiwalne) — jedna zakładka z filtrem, nie osobna zakładka archiwum.
Podwójne kliknięcie otwiera siatkę. Stan pusty z przyciskiem do pierwszego kroku.

### Kreator nowego grafiku

Jedno okno, nie wieloetapowy kreator — pól jest za mało, żeby dzielić je na kroki:

- nazwa (podpowiadana z miesiąca, np. „Wrzesień 2026")
- data od, data do
- lista aktywnych pracowników z polami wyboru; `display_order` idzie za kolejnością na liście
  (czyli po nazwisku), nie za kolejnością klikania — inaczej kolumny ustawiałyby się losowo
- podsumowanie godzin otwarcia jednym zdaniem plus przycisk „Dostosuj…", który otwiera
  `OpeningHoursEditor` z kopią ustawień

Pod spodem podpowiedź na żywo: „20 dni × 5 osób".

### Siatka

`QTableView` z własnym modelem i delegatem, czyli ten sam wzorzec, co w kartotece
pracowników. Nawigacja strzałkami, Tab i Enter przychodzą od Qt za darmo.

- Nagłówek pionowy: `pt 14.08`. Weekendy i dni zamknięte ciemniejsze.
- Komórka pokazuje `10:00–15:00`, pusta znaczy „nie pracuje".
- Edycja: `QLineEdit` w komórce z podpowiedziami — godziny otwarcia tego dnia i zmiany już
  użyte w tym grafiku.
- Tekst nie do rozpoznania: komórka nie zapisuje i pokazuje komunikat na pasku stanu.
- Godziny poza otwarciem: żółte tło i podpowiedź po najechaniu; zapis przechodzi.
- Dzień zamknięty: wiersz wyszarzony, komórki nieedytowalne.
- Wiersz sum: **osobna, jednowierszowa tabela pod główną**, z szerokościami kolumn i
  poziomym przewijaniem zsynchronizowanymi z główną. Przy 31 dniach suma jako ostatni wiersz
  zwykłej tabeli zjeżdżałaby poza ekran dokładnie wtedy, kiedy jest potrzebna.

Zapis jest natychmiastowy — każda zatwierdzona komórka to jedna transakcja. Bez przycisku
„Zapisz", bo lokalna aplikacja na jednego użytkownika nie ma powodu, żeby trzymać zmiany
w pamięci i ryzykować ich utratę.

### Nawigacja

Ekran „Grafik" zamiast zaślepki dostaje `QStackedWidget`: lista grafików albo siatka
otwartego grafiku, z powrotem przyciskiem „← Grafiki".

---

## 7. Testy

| Zakres | Co sprawdzamy |
|---|---|
| Baza | dwie nowe tabele, CHECK godzin, unikalność jednej zmiany dziennie, kasowanie kaskadowe |
| `time_text` | każdy przyjmowany zapis, odrzucanie bzdur, godziny spoza doby |
| `OpeningHoursService` | zakładanie brakujących wpisów, walidacja, zapis |
| `ScheduleService` | tworzenie ze składem i kopią godzin, walidacja, skrócenie okresu |
| `ShiftService` | wstawianie, nadpisywanie, czyszczenie, sumy z minutami |
| Siatka | liczba wierszy równa długości okresu, liczba kolumn równa liczbie osób, sumy, dni zamknięte nieedytowalne |

Testy Qt jak dotąd działają bezgłowo.

---

## 7a. Święta i reguła obsady (dołożone później)

**Święta** liczone są z czystej funkcji, nie trzymane w bazie: dziewięć dat stałych, cztery
ruchome wyliczane z daty Wielkanocy algorytmem Meeusa. Nie wymaga to pliku z danymi ani sieci
i działa dla dowolnego roku. Wigilia liczy się jako święto **od 2025 roku**, zgodnie ze zmianą
ustawy.

Święto domyślnie zamyka dzień. Odstępstwa trzyma tabela `schedule_day_overrides`
(grafik, data, godziny; puste godziny znaczą zamknięte). Kolejność rozstrzygania:
**wyjątek dla daty → święto zamyka → tygodniowy wzorzec**. Ta sama tabela obsługuje ruch
w drugą stronę — zamknięcie zwykłego dnia na inwentaryzację.

W siatce święto ma niebieski wiersz i nazwę przy dacie, także wtedy gdy zostało otwarte —
informacja „to jest święto" nie znika przez to, że tego dnia się pracuje. Kalendarz przy
wyborze okresu podświetla święta, a kreator liczy, ile ich wypada w okresie.

**Reguła obsady magistra:** ostrzeżenie, gdy w jakimkolwiek momencie godzin otwarcia nie ma
żadnego magistra. Liczenie to scalenie przedziałów zmian magistrów, przycięcie do godzin
otwarcia i zebranie dziur. Dni zamknięte nie stawiają wymagań. Wynik to pasek pod sumami:
albo „bez zastrzeżeń", albo lista dni z niepokrytymi godzinami.

Ostrzeżenie, nie blokada — pusty grafik z założenia pokazuje wszystkie dni jako niepokryte
i to jest prawda o nim, a nie usterka.

## 8. Czego świadomie nie robimy

Wykrywanie nakładania zmian, reguła obecności magistra, wydruk i PDF, cofanie zmian,
przeciąganie zmian myszą, kopiowanie tygodnia, urlopy i L4, zmiana składu po utworzeniu
grafiku, raporty. Ekran „Raporty" zostaje zaślepką.

**Zmiana okresu istniejącego grafiku** też nie powstała, choć pierwsza wersja tego dokumentu
ją przewidywała. Powód: rozstrzygnięcie, co zrobić ze zmianami wypadającymi poza skrócony
okres, nie zostało potwierdzone — pytanie przepadło przy przerwanej rozmowie. Zgadywanie
tutaj kasowałoby cudzą pracę, więc okres na razie ustala się raz, przy tworzeniu. Pomyłka
oznacza nowy grafik. Do dołożenia, gdy odpowiedź będzie znana.
