# Core Database Design (Faza 1)

**Data:** 2026-08-09
**Status:** zatwierdzony do implementacji

## Cel

Absolutne minimum pozwalające zapisać pracowników, grafik i zmiany tak, żeby przetrwały
restart aplikacji. Wszystko, co nie jest do tego konieczne, jest świadomie odłożone.

## Model

Cztery tabele.

| Tabela | Zawiera |
|---|---|
| `employees` | kartoteka pracowników |
| `schedules` | okresy grafików |
| `schedule_employees` | skład konkretnego grafiku |
| `shifts` | konkretne godziny pracy |

```
employees ──┐
            ├── schedule_employees ──── shifts
schedules ──┘
```

### employees

`id`, `first_name`, `last_name`, `profession`, `active`, `created_at`, `updated_at`

### schedules

`id`, `name`, `start_date`, `end_date`, `status`, `created_at`, `updated_at`, `finalized_at`

### schedule_employees

`id`, `schedule_id`, `employee_id`, `display_order`

`display_order` ustala kolejność pasów w kalendarzu.

### shifts

`id`, `schedule_employee_id`, `shift_date`, `start_time`, `end_time`, `created_at`, `updated_at`

Zmiana wskazuje na wpis składu, a nie osobno na grafik i pracownika. Dzięki temu z budowy
bazy wynika, że nie da się wpisać zmiany komuś spoza składu grafiku — to niemożliwe do
zapisania, zamiast być regułą do pilnowania.

Cena: raport za dowolny okres wymaga jednego złączenia więcej.

## Ograniczenia w bazie

To ochrona przed danymi technicznie niepoprawnymi, nie reguły biznesowe.

```
profession IN ('PHARMACIST', 'TECHNICIAN')
status IN ('DRAFT', 'FINAL', 'ARCHIVED')
schedules.end_date >= schedules.start_date
shifts.end_time > shifts.start_time
UNIQUE (schedule_id, employee_id)
```

## Kasowanie

| Operacja | Zachowanie |
|---|---|
| skasowanie grafiku | usuwa skład i zmiany (CASCADE) |
| usunięcie pracownika ze składu | usuwa jego zmiany w tym grafiku (CASCADE) |
| skasowanie pracownika | zablokowane, jeśli jest w jakimkolwiek grafiku (RESTRICT) |

Pracowników wycofuje się przez `active = False`, nigdy przez usunięcie. Historia zmian
opiera się na tych rekordach.

**Klucze obce w SQLite są domyślnie wyłączone.** Bez `PRAGMA foreign_keys=ON` wykonywanego
przy każdym połączeniu żadna z powyższych zasad nie działa.

## Świadome decyzje

**Zmiany przez północ są niemożliwe.** `end_time > start_time` blokuje je na poziomie bazy.
Dopóki apteka zamyka przed północą, jest to nieszkodliwe. Gdyby pojawił się dyżur nocny,
nie wystarczy poprawić reguły — trzeba zmienić sposób zapisu czasu i przemigrować dane.

**Duplikaty zmian są dopuszczalne.** Ta sama osoba, ten sam dzień, te same godziny dwa razy.
Wykrywanie nakładania się zmian należy do Rules Engine.

**Zawód jako pole, nie tabela.** Dwie wartości, które się nie zmieniają. Dołożenie trzeciej
wymaga migracji — przy dwóch stałych to uczciwy układ.

**Znaczniki czasu w UTC.** Daty i godziny grafiku są lokalne, `created_at` i `updated_at` nie.

## Świadomie pominięte

```
użytkownicy i logowanie        godziny otwarcia i ich profile
role użytkowników              święta i dni nietypowe
kontrakty, weekly_hours        reguły nakładania zmian
target_hours                   reguła obecności magistra
notatki przy pracowniku        historia zmian
kolor pracownika               ShiftAssignment (wielu na zmianie)
```

Logowanie zostało odrzucone świadomie: plik bazy leży niezaszyfrowany na dysku, więc hasło
w aplikacji byłoby ceremonią, a nie zabezpieczeniem. Dołożenie go później to jedna nowa
tabela i zero zmian w istniejących.

## Punkty otwarte

Nie blokują tej fazy.

1. Dokładne brzmienie reguły obecności magistra — pytanie do biznesu.
2. Czy zmiana poza godzinami otwarcia ma być zablokowana, czy tylko oznaczona ostrzeżeniem.

## Kolejność dalszych prac

```
Core database → Zarządzanie pracownikami → Tworzenie i otwieranie grafiku
→ Godziny otwarcia → Rules Engine → Raporty
```
